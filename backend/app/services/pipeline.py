"""
pipeline.py
───────────
Multi-Stage Onboarding Pipeline Coordinator.

Orchestration Precedence Rule:
  1. Hard Reject (checked first):
       If Stage 1 == "fail" OR Stage 2 == "fail" -> status="rejected", escalated=False
       ((fail, borderline) is immediately rejected, never escalated).
  2. Borderline Escalation:
       If Stage 1 == "borderline" OR Stage 2 == "borderline" -> invoke Stage 3 LangGraph Agent.
       - Resolved -> APPROVE: status="approved", final_decision="pass"
       - Resolved -> REJECT:  status="rejected", final_decision="fail"
       - Unresolved:          status="escalated_for_review", final_decision="borderline", enqueued in review queue.
  3. Fast Pass:
       If Stage 1 == "pass" AND Stage 2 == "pass" -> status="approved", escalated=False, final_decision="pass"
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.agent.investigation import run_investigation_agent
from app.agent.sandbox import SanitizedOnboardingRecord, sanitize_onboarding_record
from app.utils.logging import get_logger

log = get_logger(__name__)


def derive_stage1_decision(record: SanitizedOnboardingRecord) -> str:
    """Derive Stage 1 (Liveness) classification from record signals."""
    if (
        record.deepfake_score >= 0.75
        or not record.challenge_match
        or abs(record.av_sync_ms) > 150.0
    ):
        return "fail"
    if (
        record.deepfake_score >= 0.40
        or abs(record.av_sync_ms) > 80.0
        or record.blink_rate_bpm < 8.0
    ):
        return "borderline"
    return "pass"


def derive_stage2_decision(record: SanitizedOnboardingRecord) -> str:
    """Derive Stage 2 (Identity) classification from record signals."""
    if (
        record.cosine_similarity_score < 0.35
        or record.registry_velocity_6hr >= 6
    ):
        return "fail"
    if (
        record.cosine_similarity_score < 0.60
        or record.registry_velocity_6hr >= 3
    ):
        return "borderline"
    return "pass"


def evaluate_onboarding_pipeline(
    raw_record: Dict[str, Any],
    ip: str = "unknown",
) -> Dict[str, Any]:
    """
    Execute full multi-stage onboarding pipeline evaluation.
    """
    # Step 0: Sandbox sanitization
    sanitized = sanitize_onboarding_record(raw_record)

    # Step 1 & 2: Derive or read stage decisions
    stage1 = sanitized.stage1_decision or derive_stage1_decision(sanitized)
    stage2 = sanitized.stage2_decision or derive_stage2_decision(sanitized)

    log.info(
        "pipeline.stages_evaluated",
        session_id=sanitized.session_id,
        stage1=stage1,
        stage2=stage2,
    )

    # Step 1 Precedence: Hard Fail checked FIRST
    if stage1 == "fail" or stage2 == "fail":
        return {
            "session_id": sanitized.session_id,
            "kin_token": sanitized.kin_token,
            "legal_name": sanitized.legal_name,
            "stage1_decision": stage1,
            "stage2_decision": stage2,
            "escalated_to_stage3": False,
            "stage3_result": None,
            "status": "rejected",
            "final_decision": "fail",
            "reason": f"Hard fail triggered by Stage 1 ({stage1}) or Stage 2 ({stage2}).",
        }

    # Step 2 Precedence: Borderline Escalation to Stage 3 LangGraph Agent
    if stage1 == "borderline" or stage2 == "borderline":
        investigation = run_investigation_agent(sanitized, ip=ip)

        if investigation.decision == "resolved":
            final_decision = "pass" if investigation.agent_recommendation == "APPROVE" else "fail"
            status = "approved" if final_decision == "pass" else "rejected"
        else:
            final_decision = "borderline"
            status = "escalated_for_review"

        return {
            "session_id": sanitized.session_id,
            "kin_token": sanitized.kin_token,
            "legal_name": sanitized.legal_name,
            "stage1_decision": stage1,
            "stage2_decision": stage2,
            "escalated_to_stage3": True,
            "stage3_result": investigation.model_dump(),
            "status": status,
            "final_decision": final_decision,
            "reason": f"Escalated to Stage 3 Agent due to borderline signal: {investigation.agent_recommendation}",
        }

    # Step 3 Precedence: Fast Pass Residual (both pass)
    return {
        "session_id": sanitized.session_id,
        "kin_token": sanitized.kin_token,
        "legal_name": sanitized.legal_name,
        "stage1_decision": "pass",
        "stage2_decision": "pass",
        "escalated_to_stage3": False,
        "stage3_result": None,
        "status": "approved",
        "final_decision": "pass",
        "reason": "All physiological, liveness, and identity checks nominal.",
    }

"""
review_queue.py
───────────────
Persistent Review Queue Service for Unresolved / Escalated Cases.

Aggregates:
  1. Escalated cases in review_queue.jsonl
  2. All verification sessions from VerificationService (verification_sessions.json)

Provides seamless reviewer portal synchronization for Pending, Approved, Rejected, and All tabs.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.utils.logging import get_logger

log = get_logger(__name__)

_QUEUE_LOCK = threading.Lock()


def _resolve_storage_file(filename: str) -> Path:
    env_root = os.getenv("STORAGE_LOCAL_ROOT")
    if env_root:
        p = Path(env_root) / filename
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    backend_dir = Path(__file__).resolve().parent.parent.parent
    root_file = backend_dir.parent / "data" / "storage" / filename
    if root_file.parent.exists():
        return root_file

    local_file = backend_dir / "data" / "storage" / filename
    local_file.parent.mkdir(parents=True, exist_ok=True)
    return local_file


def get_queue_path() -> Path:
    env_path = os.getenv("REVIEW_QUEUE_PATH")
    if env_path:
        p = Path(env_path)
    else:
        p = _resolve_storage_file("review_queue.jsonl")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def reset_queue(custom_path: Optional[Path | str] = None) -> None:
    """Clear review queue for testing."""
    with _QUEUE_LOCK:
        p = Path(custom_path) if custom_path else get_queue_path()
        if p.exists():
            p.unlink()


def enqueue_case_for_review(
    case_data: Dict[str, Any],
    queue_path: Optional[Path | str] = None,
) -> str:
    """
    Persist an escalated or unresolved onboarding case to the review queue.
    """
    with _QUEUE_LOCK:
        p = Path(queue_path) if queue_path else get_queue_path()
        case_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        entry = {
            "case_id": case_id,
            "session_id": case_data.get("session_id", str(uuid.uuid4())),
            "kin_token": case_data.get("kin_token", "unknown"),
            "legal_name": case_data.get("legal_name", "Anonymous"),
            "device_id": case_data.get("device_id", "unknown"),
            "created_at": now,
            "resolved_at": None,
            "reviewer_id": None,
            "review_action": None,
            "notes": None,
            "status": "pending_review",
            "decision": case_data.get("decision", "unresolved"),
            "agent_recommendation": case_data.get("agent_recommendation", "REFER_TO_HUMAN"),
            "dossier_summary": case_data.get("dossier_summary", ""),
            "tool_calls_trace": case_data.get("tool_calls_trace", []),
            "signals": {
                "deepfake_score": case_data.get("deepfake_score", 0.08),
                "cosine_similarity_score": case_data.get("cosine_similarity_score", 0.91),
                "duplicate_verification_check": 1,
                "blink_rate_bpm": case_data.get("blink_rate_bpm", 14.0),
                "av_sync_ms": case_data.get("av_sync_ms", 0.0),
                "webrtc_jitter_ms": case_data.get("webrtc_jitter_ms", 12.0),
            },
        }

        line = json.dumps(entry, sort_keys=True) + "\n"
        with open(p, "a", encoding="utf-8") as f:
            f.write(line)

        log.info("review_queue.enqueued", case_id=case_id, session_id=entry["session_id"])
        return case_id


def _map_verification_session_to_case(session: Any) -> Dict[str, Any]:
    """Map a stateful VerificationSession into the unified ReviewCase schema."""
    # Status mapping
    if session.status in {"VERIFIED", "ALREADY_VERIFIED"}:
        mapped_status = "resolved_approved"
        decision = "pass"
        recommendation = "APPROVE"
    elif session.status == "NOT_VERIFIED":
        mapped_status = "resolved_rejected"
        decision = "fail"
        recommendation = "REJECT"
    else:  # UNDER_REVIEW, IN_PROGRESS
        mapped_status = "pending_review"
        decision = "borderline"
        recommendation = "REFER_TO_HUMAN"

    resolved_at = session.updated_at if mapped_status != "pending_review" else None

    dossier = (
        session.final_reason
        or f"10-signal breakdown: OTP={session.decision_table.phone_otp}, "
        f"Liveness={session.decision_table.liveness}, Deepfake={session.decision_table.deepfake_analysis}"
    )

    trace = getattr(session, "agent_reasoning_trace", None)

    return {
        "case_id": session.reference_id,
        "session_id": session.reference_id,
        "kin_token": session.ckyc_number,
        "legal_name": session.legal_name,
        "device_id": "client-device-" + session.reference_id[-4:],
        "created_at": session.created_at,
        "resolved_at": resolved_at,
        "reviewer_id": "System Auto-Evaluator" if mapped_status != "pending_review" else None,
        "review_action": "approve" if mapped_status == "resolved_approved" else ("reject" if mapped_status == "resolved_rejected" else None),
        "notes": session.final_reason,
        "status": mapped_status,
        "decision": decision,
        "agent_recommendation": recommendation,
        "dossier_summary": dossier,
        "tool_calls_trace": [trace] if trace else [],
        "agent_reasoning_trace": trace,
        "retry_count": getattr(session, "retry_count", 0),
        "retry_requested": getattr(session, "retry_requested", False),
        "retry_note": getattr(session, "retry_note", None),
        "signals": {
            "deepfake_score": getattr(session, "deepfake_score", 0.08),
            "cosine_similarity_score": getattr(session, "face_similarity_score", 0.91),
            "duplicate_verification_check": 1,
            "blink_rate_bpm": 14.2,
            "av_sync_ms": 0.0,
            "webrtc_jitter_ms": 12.5,
        },
        "decision_table": session.decision_table.model_dump() if hasattr(session, "decision_table") else None,
    }


def list_pending_cases(
    status: Optional[str] = "pending_review",
    queue_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """
    List all cases matching the specified status across both review_queue.jsonl
    and stateful verification sessions.
    """
    cases = []
    seen_ids = set()

    # 1. Load from review_queue.jsonl
    with _QUEUE_LOCK:
        p = Path(queue_path) if queue_path else get_queue_path()
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        cid = entry.get("case_id") or entry.get("session_id")
                        if cid:
                            seen_ids.add(cid)
                        if status is None or status.lower() in {"all", "*"} or entry.get("status") == status:
                            cases.append(entry)
                    except Exception:
                        pass

    # 2. Bridge all sessions from VerificationService (verification_sessions.json) only for default production queue
    if queue_path is None and not os.getenv("REVIEW_QUEUE_PATH"):
        try:
            from app.services.verification_service import get_verification_service
            v_service = get_verification_service()
            for session in v_service._sessions.values():
                if session.reference_id not in seen_ids:
                    mapped = _map_verification_session_to_case(session)
                    if status is None or status.lower() in {"all", "*"} or mapped.get("status") == status:
                        cases.append(mapped)
                        seen_ids.add(session.reference_id)
        except Exception as exc:
            log.warning("review_queue.bridge_sessions_failed", error=str(exc))

    # Sort descending by creation date
    cases.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return cases


def get_case(
    case_id: str,
    queue_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve a specific case by case_id or session_id across all sources.
    """
    cases = list_pending_cases(status=None, queue_path=queue_path)
    clean_id = case_id.strip().upper()
    for c in cases:
        if (
            str(c.get("case_id")).strip().upper() == clean_id
            or str(c.get("session_id")).strip().upper() == clean_id
        ):
            return c
    return None


def resolve_case(
    case_id: str,
    action: str,
    reviewer_id: str,
    notes: Optional[str] = None,
    ip: str = "unknown",
    queue_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """
    Submit a reviewer decision on a case:
      1. Validates action ("approve" | "reject").
      2. Updates case status to "resolved_approved" or "resolved_rejected".
      3. Updates underlying verification session & registry if applicable.
      4. Automatically seals the human review decision into the unified hash chain.
    """
    act = action.strip().lower()
    if act not in {"approve", "reject"}:
        raise ValueError(f"Invalid review action {action!r}. Must be 'approve' or 'reject'.")

    new_status = "resolved_approved" if act == "approve" else "resolved_rejected"
    now_iso = datetime.now(timezone.utc).isoformat()

    # Check if target belongs to VerificationService
    try:
        from app.services.verification_service import get_verification_service
        from app.services.kyc_registry import get_kyc_registry
        v_service = get_verification_service()
        v_session = v_service.get_session(case_id)
        if v_session:
            v_session.status = "VERIFIED" if act == "approve" else "NOT_VERIFIED"
            v_session.final_decision = v_session.status
            v_session.final_reason = f"Human Reviewer Decision ({act.upper()}): {notes or 'No notes provided'}"
            v_session.updated_at = now_iso
            v_service._save_sessions()

            if act == "approve":
                get_kyc_registry().update_verification_status(
                    v_session.ckyc_number,
                    status="VERIFIED",
                    face_reference={"verified_by_human": reviewer_id, "timestamp": now_iso},
                )
    except Exception as exc:
        log.warning("review_queue.resolve_session_sync_failed", error=str(exc))

    target_case = None
    with _QUEUE_LOCK:
        p = Path(queue_path) if queue_path else get_queue_path()
        if p.exists():
            all_cases = []
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("case_id") == case_id or entry.get("session_id") == case_id:
                            entry["status"] = new_status
                            entry["resolved_at"] = now_iso
                            entry["reviewer_id"] = reviewer_id
                            entry["review_action"] = act
                            entry["notes"] = notes or ""
                            target_case = entry
                        all_cases.append(entry)
                    except Exception:
                        pass

            if target_case:
                with open(p, "w", encoding="utf-8") as f:
                    for c in all_cases:
                        f.write(json.dumps(c, sort_keys=True) + "\n")

    if target_case is None:
        # Construct resolved representation from session
        target_case = get_case(case_id, queue_path=queue_path)
        if target_case is None:
            raise KeyError(f"Case {case_id!r} not found.")
        target_case["status"] = new_status
        target_case["resolved_at"] = now_iso
        target_case["reviewer_id"] = reviewer_id
        target_case["review_action"] = act
        target_case["notes"] = notes or ""

    # Step 4: Seal into unified cryptographic hash chain
    from app.services.audit import (
        get_latest_agent_decision_hash,
        log_human_review_event,
        log_reviewer_decision_event,
    )
    
    parent_hash = get_latest_agent_decision_hash(target_case["session_id"])
    if parent_hash:
        log_reviewer_decision_event(
            session_id=target_case["session_id"],
            reviewer_id=reviewer_id,
            verdict="VERIFIED" if act == "approve" else "NOT_VERIFIED",
            note=notes or "",
            parent_decision_hash=parent_hash,
            ip=ip,
        )
    else:
        log_human_review_event(
            case_id=target_case["case_id"],
            session_id=target_case["session_id"],
            reviewer_id=reviewer_id,
            action=act,
            notes=notes or "",
            ip=ip,
        )

    log.info(
        "review_queue.resolved",
        case_id=case_id,
        action=act,
        status=new_status,
        reviewer_id=reviewer_id,
    )

    return target_case

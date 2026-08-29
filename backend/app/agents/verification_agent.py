"""
verification_agent.py — LangGraph Agentic Reasoning & Escalation Layer
──────────────────────────────────────────────────────────────────────
Integrates an agentic reasoning and escalation layer on top of the deterministic
verification pipeline. The deterministic vision, biometric, OCR, and liveness
pipelines remain the ground-truth signal sources; this agent consumes their structured
outputs, evaluates configurable borderline gates, performs grounded natural-language
reasoning, and dynamically manages one-time liveness challenge retries and final session verdicts.

Architecture:
  [collect_signals] ──▶ [reason_over_signals] ──▶ [decide_escalation]
                                                          │
                                      ┌───────────────────┴───────────────────┐
                          (borderline & retry_count == 0)              (otherwise)
                                      │                                       │
                                      ▼                                       ▼
                               [request_retry]                            [finalize]
                                      │                                       │
                                      ▼                                       ▼
                                     END                                     END
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.models.verification import DecisionTable, VerificationSession
from app.services.audit import log_agent_decision_event, log_agent_retry_event
from app.services.identity import get_identity_config
from app.services.liveness import get_liveness_config
from app.services.review_queue import enqueue_case_for_review
from app.services.verification_service import generate_challenge_sequence
from app.utils.logging import get_logger

log = get_logger(__name__)


# ─── State Definition ─────────────────────────────────────────────────────────

class VerificationAgentState(TypedDict):
    session_id: str
    reference_id: str
    ckyc_number: str
    legal_name: str
    ip: str

    # Raw deterministic signals & configuration bounds
    raw_signals: Dict[str, Any]
    decision_table: Dict[str, Any]
    thresholds: Dict[str, Any]

    # Deterministic Hard-Fail & Borderline evaluations
    has_hard_fail: bool
    hard_fail_reasons: List[str]
    is_borderline: bool
    borderline_signals: List[str]
    borderline_deltas: Dict[str, float]

    # LLM Agent Reasoning & Classification
    agent_classification: Literal["VERIFIED", "NOT_VERIFIED", "UNDER_REVIEW"]
    final_decision: Literal["VERIFIED", "NOT_VERIFIED", "UNDER_REVIEW"]
    final_reason: str
    agent_reasoning_trace: Dict[str, Any]

    # Retry & Escalation Tracking
    retry_count: int
    retry_requested: bool
    escalation_triggered: bool
    retry_note: Optional[str]
    new_challenge_sequence: Optional[List[str]]

    # Telemetry
    llm_latency_ms: float
    total_latency_ms: float
    start_time: float


# ─── Node 1: Collect Signals & Config Bounds ─────────────────────────────────

def node_collect_signals(state: VerificationAgentState) -> Dict[str, Any]:
    """
    Gathers the session's decision_table and raw numeric scores.
    Dynamically loads threshold cutoffs directly from identity_config.yaml
    and liveness_config.yaml and evaluates hard-fail and borderline flags.
    """
    raw = state.get("raw_signals", {})
    dt = state.get("decision_table", {})

    # Load thresholds directly from YAML configuration sources
    id_cfg = get_identity_config()
    id_thresh = id_cfg.get("thresholds", {})
    sim_pass = float(id_thresh.get("similarity_pass", 0.50))
    sim_fail = float(id_thresh.get("similarity_fail", 0.35))

    live_cfg = get_liveness_config()
    live_thresh = live_cfg.get("thresholds", {})
    df_fail = float(live_thresh.get("deepfake_fail", 0.75))
    df_borderline = float(live_thresh.get("deepfake_borderline", 0.40))
    anomaly_fail = float(live_thresh.get("anomaly_fail", 0.70))
    anomaly_borderline = float(live_thresh.get("anomaly_borderline", 0.40))

    thresholds = {
        "similarity_pass": sim_pass,
        "similarity_fail": sim_fail,
        "deepfake_fail": df_fail,
        "deepfake_borderline": df_borderline,
        "anomaly_fail": anomaly_fail,
        "anomaly_borderline": anomaly_borderline,
    }

    face_sim = float(raw.get("face_similarity_score", 0.0))
    deepfake_score = float(raw.get("deepfake_score", 0.0))
    challenge_match = bool(raw.get("challenge_match", False))
    phone_verified = bool(raw.get("phone_verified", False))
    document_match = bool(raw.get("document_match", False))
    ocr_conf = float(raw.get("ocr_confidence", 1.0))

    hard_fail_reasons: List[str] = []
    borderline_signals: List[str] = []
    borderline_deltas: Dict[str, float] = {}

    # 1. Deterministic Hard Fails
    retry_count = int(state.get("retry_count", 0))

    # Liveness challenge failure is retryable on attempt 1 (retry_count == 0).
    # Only after exhausting retry limit (retry_count >= 1) does it become a hard failure.
    if dt.get("liveness") == "FAILED" or (not challenge_match and dt.get("liveness") not in {"CONFIRMED", "UNCERTAIN"}):
        if retry_count >= 1:
            hard_fail_reasons.append("Liveness challenge gesture match failed across multiple retry attempts.")
        else:
            borderline_signals.append("liveness_challenge")
            borderline_deltas["liveness_challenge"] = 1.0

    if not phone_verified or dt.get("phone_otp") == "FAILED":
        hard_fail_reasons.append("Cryptographic phone OTP verification failed.")
    if not document_match or dt.get("document") == "NO_MATCH":
        hard_fail_reasons.append("ID document OCR or identity details mismatch against CKYC record.")
    if dt.get("document_face") == "NO_MATCH":
        hard_fail_reasons.append("No valid face portrait could be extracted from the uploaded ID document.")
    if dt.get("live_face") == "NO_MATCH" or (dt.get("live_face") not in {"MATCH", "UNCERTAIN"} and face_sim < sim_fail):
        hard_fail_reasons.append(
            f"Face biometric similarity ({face_sim:.4f}) is below the minimum fail cutoff ({sim_fail:.2f})."
        )
    df_upper_band = round(df_borderline + 0.05, 4)  # 0.45
    df_lower_band = round(df_borderline - 0.05, 4)  # 0.35
    if deepfake_score >= df_fail or deepfake_score > df_upper_band or dt.get("deepfake_analysis") == "FLAGGED" and deepfake_score > df_upper_band:
        hard_fail_reasons.append(
            f"Deepfake anomaly score ({deepfake_score:.4f}) exceeded allowable threshold ({df_upper_band:.2f})."
        )
    if (
        dt.get("identity_record") == "NO_MATCH"
        or dt.get("name") == "NO_MATCH"
        or dt.get("dob") == "NO_MATCH"
        or dt.get("ckyc_number") == "NO_MATCH"
    ):
        hard_fail_reasons.append("CKYC registry identity record check failed.")

    has_hard_fail = len(hard_fail_reasons) > 0

    # 2. Config-Driven Borderline Gate Evaluation
    # Deepfake score in strict symmetric borderline band [df_borderline - 0.05, df_borderline + 0.05] -> [0.35, 0.45]
    if df_lower_band <= deepfake_score <= df_upper_band:
        borderline_signals.append("deepfake_score")
        borderline_deltas["deepfake_delta_from_borderline"] = round(deepfake_score - df_borderline, 4)

    # Face similarity strictly in uncertain zone [sim_fail, sim_pass) -> [0.28, 0.40)
    if sim_fail <= face_sim < sim_pass:
        borderline_signals.append("face_similarity")
        borderline_deltas["similarity_delta_from_pass"] = round(face_sim - sim_pass, 4)

    # OCR confidence borderline
    if 0.70 <= ocr_conf <= 0.85:
        borderline_signals.append("ocr_confidence")
        borderline_deltas["ocr_confidence"] = ocr_conf

    # Categorical uncertain statuses from decision table
    if dt.get("liveness") == "UNCERTAIN":
        if "liveness_uncertain" not in borderline_signals:
            borderline_signals.append("liveness_uncertain")
    if dt.get("live_face") == "UNCERTAIN":
        if "live_face_uncertain" not in borderline_signals:
            borderline_signals.append("live_face_uncertain")

    is_borderline = len(borderline_signals) > 0

    log.info(
        "agent.signals_collected",
        reference_id=state.get("reference_id"),
        has_hard_fail=has_hard_fail,
        is_borderline=is_borderline,
        borderline_signals=borderline_signals,
    )

    return {
        **state,
        "thresholds": thresholds,
        "has_hard_fail": has_hard_fail,
        "hard_fail_reasons": hard_fail_reasons,
        "is_borderline": is_borderline,
        "borderline_signals": borderline_signals,
        "borderline_deltas": borderline_deltas,
    }


# ─── Node 2: Reason Over Signals with LLM ────────────────────────────────────

def _generate_rule_based_explanation(
    state: VerificationAgentState,
    classification: str,
) -> str:
    """Deterministic fallback reasoning generator referencing exact session numeric scores."""
    raw = state.get("raw_signals", {})
    thresh = state.get("thresholds", {})
    sim = float(raw.get("face_similarity_score", 0.0))
    df = float(raw.get("deepfake_score", 0.0))
    pass_sim = float(thresh.get("similarity_pass", 0.50))
    df_border = float(thresh.get("deepfake_borderline", 0.40))

    if classification == "NOT_VERIFIED":
        reasons_str = " | ".join(state.get("hard_fail_reasons", []))
        return f"Verification failed. Deterministic hard-fail conditions detected: {reasons_str}"

    if classification == "UNDER_REVIEW":
        border_cues = []
        if "face_similarity" in state.get("borderline_signals", []):
            border_cues.append(f"Face similarity {sim:.4f} is within borderline band (pass threshold: {pass_sim:.2f})")
        if "deepfake_score" in state.get("borderline_signals", []):
            border_cues.append(f"Deepfake anomaly score {df:.4f} straddles calibrated boundary ({df_border:.2f})")
        if not border_cues:
            border_cues.append(f"Inconclusive biometric cues ({', '.join(state.get('borderline_signals', []))})")
        return f"Escalated for review: {'; '.join(border_cues)}."

    # VERIFIED
    return (
        f"All 10 identity, document OCR, cryptographic OTP, and physiological liveness signals verified successfully. "
        f"Biometric similarity {sim:.4f} exceeds pass threshold ({pass_sim:.2f}) and deepfake anomaly score {df:.4f} is nominal."
    )


def node_reason_over_signals(state: VerificationAgentState) -> Dict[str, Any]:
    """
    Constructs a structured prompt containing only raw numbers and config thresholds
    (zero raw video/image bytes) and executes the LLM reasoning step.
    Enforces Fail-Closed Override Protection: If has_hard_fail is True,
    the classification is strictly locked to NOT_VERIFIED.
    """
    t0 = time.perf_counter()
    raw = state.get("raw_signals", {})
    thresh = state.get("thresholds", {})
    has_hard_fail = state.get("has_hard_fail", False)
    is_borderline = state.get("is_borderline", False)

    # Preliminary deterministic classification
    if has_hard_fail:
        tentative_class: Literal["VERIFIED", "NOT_VERIFIED", "UNDER_REVIEW"] = "NOT_VERIFIED"
    elif is_borderline:
        tentative_class = "UNDER_REVIEW"
    else:
        tentative_class = "VERIFIED"

    final_class = tentative_class
    explanation = ""

    # Attempt Google Gemini / OpenAI reasoning if API key configured
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or getattr(settings, "GEMINI_API_KEY", None) or ""
    openai_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None) or ""

    system_prompt = (
        "You are an expert KYC & Anti-Spoofing Verification Adjudication Agent. "
        "You receive ONLY numeric telemetry scores, decision matrix statuses, and configured policy thresholds. "
        "CRITICAL SECURITY RULES:\n"
        "1. If has_hard_fail is true, you MUST output classification 'NOT_VERIFIED'. Never override a hard failure.\n"
        "2. If is_borderline is true and has_hard_fail is false, output classification 'UNDER_REVIEW'.\n"
        "3. If all signals are nominal without hard fails or borderline signals, output classification 'VERIFIED'.\n"
        "4. Output format must be valid JSON: {\"classification\": \"VERIFIED\"|\"NOT_VERIFIED\"|\"UNDER_REVIEW\", \"reason\": \"<grounded explanation referencing exact scores>\"}"
    )
    user_payload = {
        "reference_id": state.get("reference_id"),
        "raw_signals": raw,
        "decision_table": state.get("decision_table"),
        "thresholds": thresh,
        "has_hard_fail": has_hard_fail,
        "hard_fail_reasons": state.get("hard_fail_reasons"),
        "is_borderline": is_borderline,
        "borderline_signals": state.get("borderline_signals"),
        "borderline_deltas": state.get("borderline_deltas"),
    }

    content = ""
    # Tier 1: Google Gemini (if GEMINI_API_KEY / GOOGLE_API_KEY configured)
    if str(gemini_key).strip() and not str(gemini_key).startswith("placeholder"):
        gemini_model = os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite"
        try:
            import httpx
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={gemini_key}"
            resp = httpx.post(
                gemini_url,
                headers={"x-goog-api-key": gemini_key, "Content-Type": "application/json"},
                json={
                    "contents": [{
                        "parts": [{
                            "text": f"{system_prompt}\n\nEvaluate the following verification telemetry:\n{user_payload}"
                        }]
                    }],
                    "generationConfig": {
                        "temperature": 0.0,
                        "responseMimeType": "application/json",
                    }
                },
                timeout=4.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = str(data["candidates"][0]["content"]["parts"][0]["text"]).strip()
            else:
                log.warning("agent.gemini_api_status", status=resp.status_code, error=resp.text[:120])
        except Exception as gemini_exc:
            log.warning("agent.gemini_call_failed", error=str(gemini_exc))

    # Tier 2: OpenAI (if OPENAI_API_KEY configured and content not already obtained)
    if not content and str(openai_key).strip() and not str(openai_key).startswith("sk-placeholder") and openai_key != "sk-...":
        openai_model = os.getenv("AGENT_MODEL_NAME") or "gpt-4o-mini"
        try:
            import httpx
            resp = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json={
                    "model": openai_model,
                    "temperature": 0.0,
                    "max_tokens": 250,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Evaluate the following verification telemetry:\n{user_payload}"},
                    ],
                },
                timeout=3.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = str(data["choices"][0]["message"]["content"]).strip()
            else:
                log.warning("agent.openai_api_status", status=resp.status_code, error=resp.text[:120])
        except Exception as openai_exc:
            log.warning("agent.openai_call_failed", error=str(openai_exc))

    if content:
        try:
            import json
            clean_c = content.strip()
            if clean_c.startswith("```"):
                clean_c = clean_c.split("```")[1]
                if clean_c.startswith("json"):
                    clean_c = clean_c[4:]
                clean_c = clean_c.strip()

            parsed = json.loads(clean_c)
            llm_class = parsed.get("classification", tentative_class).strip().upper()
            if llm_class in {"VERIFIED", "NOT_VERIFIED", "UNDER_REVIEW"}:
                final_class = llm_class
            explanation = parsed.get("reason", "")
        except Exception as parse_exc:
            log.warning("agent.llm_parse_error", error=str(parse_exc), content=content[:100])

    # Fail-Closed Override Protection: LLM can never override hard failures into VERIFIED
    if has_hard_fail and final_class == "VERIFIED":
        log.warning("agent.fail_closed_override_blocked", original_class=final_class)
        final_class = "NOT_VERIFIED"

    if not explanation:
        explanation = _generate_rule_based_explanation(state, final_class)

    llm_latency = round((time.perf_counter() - t0) * 1000, 3)

    trace = {
        "agent_version": "v2.0-langgraph-escalation",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "signals_evaluated": raw,
        "thresholds_applied": thresh,
        "has_hard_fail": has_hard_fail,
        "hard_fail_reasons": state.get("hard_fail_reasons", []),
        "is_borderline": is_borderline,
        "borderline_signals": state.get("borderline_signals", []),
        "borderline_deltas": state.get("borderline_deltas", {}),
        "classification": final_class,
        "model_rationale": explanation,
        "llm_latency_ms": llm_latency,
    }

    return {
        **state,
        "agent_classification": final_class,
        "final_reason": explanation,
        "agent_reasoning_trace": trace,
        "llm_latency_ms": llm_latency,
    }


# ─── Conditional Edge: Decide Escalation ─────────────────────────────────────

def edge_decide_escalation(state: VerificationAgentState) -> str:
    """
    Deterministic Escalation Gate:
      If session is borderline AND retry_count < 1 AND no non-retryable hard fail:
        -> route to 'request_retry'
      Otherwise:
        -> route to 'finalize'
    """
    is_borderline = state.get("is_borderline", False)
    retry_count = state.get("retry_count", 0)
    has_hard_fail = state.get("has_hard_fail", False)

    if is_borderline and retry_count < 1 and not has_hard_fail:
        log.info("agent.routing_to_retry", reference_id=state.get("reference_id"), retry_count=retry_count)
        return "request_retry"

    log.info("agent.routing_to_finalize", reference_id=state.get("reference_id"), retry_count=retry_count)
    return "finalize"


# ─── Node 3: Request Retry (One-Time Challenge Refresh) ──────────────────────

def node_request_retry(state: VerificationAgentState) -> Dict[str, Any]:
    """
    Increments retry_count, assigns a fresh challenge sequence, compiles
    reviewer note, and immediately seals an agent_retry_requested audit event.
    """
    ref_id = state["reference_id"]
    new_retry_count = state.get("retry_count", 0) + 1
    new_seq = generate_challenge_sequence(3)

    borderline_signals = state.get("borderline_signals", [])
    deltas = state.get("borderline_deltas", {})
    delta_str = ", ".join(f"{k}={v}" for k, v in deltas.items()) or "borderline score boundary"
    retry_note = (
        f"Automated challenge retry requested on attempt {new_retry_count}. "
        f"Triggered by borderline signals: {', '.join(borderline_signals)} ({delta_str})."
    )

    reason = (
        f"Verification inconclusive due to borderline biometric signals ({', '.join(borderline_signals)}). "
        f"A fresh {len(new_seq)}-step liveness challenge has been generated."
    )

    # Immediately seal the retry escalation into the cryptographic audit hash chain
    log_agent_retry_event(
        session_id=ref_id,
        retry_count=new_retry_count,
        borderline_reasons=borderline_signals,
        retry_note=retry_note,
        new_challenge_sequence=new_seq,
        raw_signals=state.get("raw_signals", {}),
        ip=state.get("ip", "unknown"),
    )

    total_ms = round((time.perf_counter() - state.get("start_time", time.perf_counter())) * 1000, 3)

    return {
        **state,
        "retry_count": new_retry_count,
        "retry_requested": True,
        "escalation_triggered": True,
        "retry_note": retry_note,
        "new_challenge_sequence": new_seq,
        "final_decision": "UNDER_REVIEW",
        "final_reason": reason,
        "total_latency_ms": total_ms,
    }


# ─── Node 4: Finalize Verdict & Enqueue ───────────────────────────────────────

def node_finalize(state: VerificationAgentState) -> Dict[str, Any]:
    """
    Writes the final decision, seals agent_decision audit block, and enqueues to
    review queue if decision is UNDER_REVIEW.
    """
    ref_id = state["reference_id"]
    final_verdict = state.get("agent_classification", "NOT_VERIFIED")
    final_reason = state.get("final_reason", "")
    trace = state.get("agent_reasoning_trace", {})

    # Cryptographically seal agent decision into audit chain
    log_agent_decision_event(
        session_id=ref_id,
        final_decision=final_verdict,
        final_reason=final_reason,
        agent_classification=state.get("agent_classification", final_verdict),
        has_hard_fail=state.get("has_hard_fail", False),
        is_borderline=state.get("is_borderline", False),
        agent_reasoning_trace=trace,
        raw_signals=state.get("raw_signals", {}),
        decision_table=state.get("decision_table", {}),
        ip=state.get("ip", "unknown"),
    )

    # If decision is UNDER_REVIEW, automatically enqueue into review_queue.jsonl
    if final_verdict == "UNDER_REVIEW":
        raw = state.get("raw_signals", {})
        enqueue_case_for_review({
            "session_id": ref_id,
            "kin_token": state.get("ckyc_number", "unknown"),
            "legal_name": state.get("legal_name", "Anonymous"),
            "device_id": f"client-{ref_id[-6:]}",
            "decision": "borderline",
            "agent_recommendation": "REFER_TO_HUMAN",
            "dossier_summary": final_reason,
            "tool_calls_trace": [trace],
            "deepfake_score": raw.get("deepfake_score", 0.0),
            "cosine_similarity_score": raw.get("face_similarity_score", 0.0),
            "retry_count": state.get("retry_count", 0),
            "retry_note": state.get("retry_note"),
        })

    total_ms = round((time.perf_counter() - state.get("start_time", time.perf_counter())) * 1000, 3)

    return {
        **state,
        "final_decision": final_verdict,
        "retry_requested": False,
        "total_latency_ms": total_ms,
    }


# ─── Graph Compilation ────────────────────────────────────────────────────────

def _build_verification_graph():
    graph = StateGraph(VerificationAgentState)

    graph.add_node("collect_signals", node_collect_signals)
    graph.add_node("reason_over_signals", node_reason_over_signals)
    graph.add_node("request_retry", node_request_retry)
    graph.add_node("finalize", node_finalize)

    graph.set_entry_point("collect_signals")
    graph.add_edge("collect_signals", "reason_over_signals")
    graph.add_conditional_edges(
        "reason_over_signals",
        edge_decide_escalation,
        {
            "request_retry": "request_retry",
            "finalize": "finalize",
        },
    )
    graph.add_edge("request_retry", END)
    graph.add_edge("finalize", END)

    return graph.compile()


_verification_graph = _build_verification_graph()


# ─── Public Runner ────────────────────────────────────────────────────────────

def run_verification_agent(
    session: VerificationSession,
    ip: str = "unknown",
) -> Dict[str, Any]:
    """
    Synchronous execution wrapper for the LangGraph Verification Agent.
    Consumes stateful session, evaluates configurable borderline gates,
    manages one-time challenge retries, and returns the final decision trace.
    """
    start_t = time.perf_counter()

    raw_signals = {
        "face_similarity_score": getattr(session, "face_similarity_score", 0.0),
        "deepfake_score": getattr(session, "deepfake_score", 0.0),
        "challenge_match": getattr(session, "challenge_match", False),
        "phone_verified": getattr(session, "phone_verified", False),
        "document_match": getattr(session, "document_match", False),
        "detection_mode": getattr(session, "detection_mode", "heuristic_fallback"),
        "ocr_confidence": session.document_details.get("ocr_confidence", 1.0) if session.document_details else 1.0,
        "expected_sequence": getattr(session, "challenge_sequence", None),
        "detected_sequence": getattr(session, "detected_sequence", None),
    }

    initial_state: VerificationAgentState = {
        "session_id": session.reference_id,
        "reference_id": session.reference_id,
        "ckyc_number": session.ckyc_number,
        "legal_name": session.legal_name,
        "ip": ip,
        "raw_signals": raw_signals,
        "decision_table": session.decision_table.model_dump(),
        "thresholds": {},
        "has_hard_fail": False,
        "hard_fail_reasons": [],
        "is_borderline": False,
        "borderline_signals": [],
        "borderline_deltas": {},
        "agent_classification": "NOT_VERIFIED",
        "final_decision": "NOT_VERIFIED",
        "final_reason": "",
        "agent_reasoning_trace": {},
        "retry_count": getattr(session, "retry_count", 0),
        "retry_requested": False,
        "escalation_triggered": getattr(session, "escalation_triggered", False),
        "retry_note": getattr(session, "retry_note", None),
        "new_challenge_sequence": None,
        "llm_latency_ms": 0.0,
        "total_latency_ms": 0.0,
        "start_time": start_t,
    }

    final_state = _verification_graph.invoke(initial_state)
    return final_state

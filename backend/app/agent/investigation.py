"""
investigation.py
────────────────
Stage 3: LangGraph Autonomous Investigation Agent.

State Graph:
  [start] ──▶ [investigate_signals] ──▶ [execute_tools] ──▶ [synthesize_dossier] ──▶ [seal_audit] ──▶ [route_queue] ──▶ [end]

Trace Faithfulness:
  The audit log records the exact tool calls and their raw numeric/structured return values,
  NOT only the LLM's summary narrative.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.agent.sandbox import (
    AgentInvestigationResult,
    SanitizedOnboardingRecord,
    ToolCallTraceEntry,
)
from app.agent.tools import check_device_id_history, query_registry_velocity
from app.services.audit import log_investigation_event
from app.services.review_queue import enqueue_case_for_review
from app.utils.logging import get_logger

log = get_logger(__name__)


# ─── Investigation Graph State ────────────────────────────────────────────────

class InvestigationState(TypedDict):
    # Inputs
    record: SanitizedOnboardingRecord
    ip: str

    # Intermediate Tool Calls
    tool_calls_trace: List[Dict[str, Any]]
    device_history: Optional[Dict[str, Any]]
    velocity_info: Optional[Dict[str, Any]]

    # Outputs & Decisions
    decision: Literal["resolved", "unresolved"]
    agent_recommendation: Literal["APPROVE", "REFER_TO_HUMAN", "REJECT"]
    dossier_summary: str
    enqueued_for_review: bool

    # Latencies
    llm_latency_ms: float
    tool_latency_ms: float
    total_latency_ms: float
    start_time: float


# ─── Node Implementations ─────────────────────────────────────────────────────

def node_investigate_signals(state: InvestigationState) -> Dict[str, Any]:
    """Analyze sanitized signals to plan required tool inquiries."""
    rec = state["record"]
    log.info(
        "agent.investigate_signals",
        session_id=rec.session_id,
        kin_token=rec.kin_token,
        deepfake_score=rec.deepfake_score,
        cosine_similarity=rec.cosine_similarity_score,
    )
    return state


def node_execute_tools(state: InvestigationState) -> Dict[str, Any]:
    """
    Execute exactly the 2 bound tools and record raw trace faithfully.
    """
    t_start = time.perf_counter()
    rec = state["record"]
    traces = list(state.get("tool_calls_trace", []))

    # Tool 1: Check device ID history
    t0 = time.perf_counter()
    dev_history = check_device_id_history(rec.device_id)
    dur_dev = round((time.perf_counter() - t0) * 1000, 3)
    now_iso = datetime.now(timezone.utc).isoformat()
    traces.append({
        "tool_name": "check_device_id_history",
        "args": {"device_id": rec.device_id},
        "return_value": dev_history,
        "timestamp": now_iso,
        "duration_ms": dur_dev,
    })

    # Tool 2: Query central registry velocity
    t1 = time.perf_counter()
    vel_info = query_registry_velocity(rec.kin_token)
    dur_vel = round((time.perf_counter() - t1) * 1000, 3)
    traces.append({
        "tool_name": "query_registry_velocity",
        "args": {"kin_token": rec.kin_token},
        "return_value": vel_info,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_ms": dur_vel,
    })

    tool_latency = round((time.perf_counter() - t_start) * 1000, 3)

    return {
        **state,
        "tool_calls_trace": traces,
        "device_history": dev_history,
        "velocity_info": vel_info,
        "tool_latency_ms": tool_latency,
    }


def node_synthesize_dossier(state: InvestigationState) -> Dict[str, Any]:
    """
    Synthesize case findings into structured decision + plain-text human dossier.

    Decision Rules:
      - Resolved -> APPROVE:  signals explainable, isolated device, zero prior fraud, genuine face match.
      - Resolved -> REJECT:   confirmed syndicate attack, multi-identity device reuse, high prior failures.
      - Unresolved -> REFER_TO_HUMAN: ambiguous borderlines, conflicting cues, high AV sync offset with borderline liveness.
    """
    t0 = time.perf_counter()
    rec = state["record"]
    dev = state.get("device_history") or {}
    vel = state.get("velocity_info") or {}

    total_attempts = dev.get("total_attempts", 1)
    prior_failures = dev.get("prior_failures", 0)
    vel_6hr = vel.get("registry_velocity_6hr", 1)

    reasons: List[str] = []
    decision: Literal["resolved", "unresolved"] = "unresolved"
    rec_decision: Literal["APPROVE", "REFER_TO_HUMAN", "REJECT"] = "REFER_TO_HUMAN"

    # Evaluate syndication / burst attack
    if total_attempts >= 6 or prior_failures >= 2 or vel_6hr >= 6:
        decision = "resolved"
        rec_decision = "REJECT"
        reasons.append(
            f"Syndicate device reuse detected: {total_attempts} attempts on device {rec.device_id[:8]}... "
            f"with {prior_failures} prior rejections."
        )
    # Evaluate genuine clean onboarding (resolvable anomaly e.g. minor network jitter)
    elif (
        total_attempts <= 2
        and prior_failures == 0
        and vel_6hr <= 2
        and rec.deepfake_score < 0.40
        and rec.cosine_similarity_score >= 0.60
    ):
        decision = "resolved"
        rec_decision = "APPROVE"
        reasons.append(
            "Device and registry checks nominal. Minor signal deviations attributed to network jitter."
        )
    else:
        # Ambiguous / Conflicting cues requiring human review
        decision = "unresolved"
        rec_decision = "REFER_TO_HUMAN"
        if rec.deepfake_score >= 0.40:
            reasons.append(f"Borderline deepfake anomaly score ({rec.deepfake_score:.2f}).")
        if rec.cosine_similarity_score < 0.60:
            reasons.append(f"Borderline face embedding similarity ({rec.cosine_similarity_score:.2f}).")
        if abs(rec.av_sync_ms) > 80:
            reasons.append(f"Audio-video sync offset drift ({rec.av_sync_ms:.1f}ms).")
        if total_attempts >= 3 or vel_6hr >= 3:
            reasons.append(f"Elevated velocity detected ({vel_6hr} attempts in 6hr window).")

    dossier_lines = [
        f"INVESTIGATION DOSSIER — CASE {rec.session_id[:8]}",
        f"Applicant: {rec.legal_name} | KIN: {rec.kin_token[:12]}... | Device: {rec.device_id[:12]}...",
        f"Autonomous Resolution: {decision.upper()} | Advisory Recommendation: {rec_decision}",
        "",
        "Signal Breakdown:",
        f"  - Deepfake Probability : {rec.deepfake_score * 100:.1f}%",
        f"  - Identity Cosine Match: {rec.cosine_similarity_score:.4f}",
        f"  - 6-Hour Velocity      : {vel_6hr} attempts",
        f"  - Device History Count : {total_attempts} attempts ({prior_failures} prior fails)",
        f"  - Audio-Video Offset   : {rec.av_sync_ms:.1f}ms",
        f"  - WebRTC Jitter        : {rec.webrtc_jitter_ms:.1f}ms",
        "",
        "Investigative Findings:",
    ]
    for r in reasons:
        dossier_lines.append(f"  • {r}")

    dossier_summary = "\n".join(dossier_lines)
    llm_latency = round((time.perf_counter() - t0) * 1000, 3)

    return {
        **state,
        "decision": decision,
        "agent_recommendation": rec_decision,
        "dossier_summary": dossier_summary,
        "llm_latency_ms": llm_latency,
    }


def node_seal_audit(state: InvestigationState) -> Dict[str, Any]:
    """
    Seal the investigation event into the unified audit hash chain.
    Faithfully records raw tool call sequences and numeric outputs.
    """
    rec = state["record"]
    log_investigation_event(
        session_id=rec.session_id,
        kin_token=rec.kin_token,
        decision=state["decision"],
        agent_recommendation=state["agent_recommendation"],
        dossier_summary=state["dossier_summary"],
        tool_calls_trace=state["tool_calls_trace"],
        ip=state.get("ip", "unknown"),
    )
    return state


def node_route_queue(state: InvestigationState) -> Dict[str, Any]:
    """
    Handoff to Phase 5: If unresolved or referral recommended, enqueue to review queue.
    """
    rec = state["record"]
    enqueued = False

    if state["decision"] == "unresolved" or state["agent_recommendation"] == "REFER_TO_HUMAN":
        enqueue_case_for_review({
            "session_id": rec.session_id,
            "kin_token": rec.kin_token,
            "legal_name": rec.legal_name,
            "device_id": rec.device_id,
            "decision": state["decision"],
            "agent_recommendation": state["agent_recommendation"],
            "dossier_summary": state["dossier_summary"],
            "tool_calls_trace": state["tool_calls_trace"],
            "deepfake_score": rec.deepfake_score,
            "cosine_similarity_score": rec.cosine_similarity_score,
            "registry_velocity_6hr": rec.registry_velocity_6hr,
            "blink_rate_bpm": rec.blink_rate_bpm,
            "av_sync_ms": rec.av_sync_ms,
            "webrtc_jitter_ms": rec.webrtc_jitter_ms,
        })
        enqueued = True

    total_ms = round((time.perf_counter() - state["start_time"]) * 1000, 3)

    return {
        **state,
        "enqueued_for_review": enqueued,
        "total_latency_ms": total_ms,
    }


# ─── Graph Assembly ───────────────────────────────────────────────────────────

def _build_investigation_graph():
    graph = StateGraph(InvestigationState)

    graph.add_node("investigate_signals", node_investigate_signals)
    graph.add_node("execute_tools", node_execute_tools)
    graph.add_node("synthesize_dossier", node_synthesize_dossier)
    graph.add_node("seal_audit", node_seal_audit)
    graph.add_node("route_queue", node_route_queue)

    graph.set_entry_point("investigate_signals")
    graph.add_edge("investigate_signals", "execute_tools")
    graph.add_edge("execute_tools", "synthesize_dossier")
    graph.add_edge("synthesize_dossier", "seal_audit")
    graph.add_edge("seal_audit", "route_queue")
    graph.add_edge("route_queue", END)

    return graph.compile()


_investigation_graph = _build_investigation_graph()


# ─── Public Runner ────────────────────────────────────────────────────────────

def run_investigation_agent(
    record: SanitizedOnboardingRecord,
    ip: str = "unknown",
) -> AgentInvestigationResult:
    """
    Synchronous execution wrapper for the Stage 3 LangGraph Investigation Agent.
    """
    start_t = time.perf_counter()
    initial_state: InvestigationState = {
        "record": record,
        "ip": ip,
        "tool_calls_trace": [],
        "device_history": None,
        "velocity_info": None,
        "decision": "unresolved",
        "agent_recommendation": "REFER_TO_HUMAN",
        "dossier_summary": "",
        "enqueued_for_review": False,
        "llm_latency_ms": 0.0,
        "tool_latency_ms": 0.0,
        "total_latency_ms": 0.0,
        "start_time": start_t,
    }

    final_state = _investigation_graph.invoke(initial_state)

    trace_entries = [
        ToolCallTraceEntry(**t) for t in final_state.get("tool_calls_trace", [])
    ]

    return AgentInvestigationResult(
        session_id=record.session_id,
        kin_token=record.kin_token,
        legal_name=record.legal_name,
        device_id=record.device_id,
        decision=final_state["decision"],
        agent_recommendation=final_state["agent_recommendation"],
        dossier_summary=final_state["dossier_summary"],
        tool_calls_trace=trace_entries,
        enqueued_for_review=final_state["enqueued_for_review"],
        llm_latency_ms=final_state.get("llm_latency_ms", 0.0),
        tool_latency_ms=final_state.get("tool_latency_ms", 0.0),
        total_latency_ms=final_state.get("total_latency_ms", 0.0),
    )

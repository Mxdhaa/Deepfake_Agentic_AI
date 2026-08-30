"""
audit.py
────────
Unified tamper-evident Hash Chain audit log for Phase 2 & Phase 5.

Architecture
────────────
Every critical event in the system — video uploads, liveness decisions, and reviewer
access events — is sealed into a single append-only cryptographic hash chain.

There are NO parallel audit tables or separate event logs.
Interleaving all event types into one sequence ensures:
  1. Access events and decision events share the exact same tamper-evident trail.
  2. No split-brain or drift between who made decisions and who accessed clips.
  3. Verification can walk the entire history sequentially and prove zero tampering.

Record Types (distinguished by the `record_type` field):
  - "upload":   Raw clip received and stored before scoring (with wire SHA-256)
  - "decision": Liveness scoring completed (decision, anomaly score, breakdown, weights)
  - "access":   Reviewer requested clip retrieval (presign or stream) with auth outcome

Block Schema
────────────
{
  "index":        0,
  "record_type":  "upload" | "decision" | "access",
  "session_id":   "...",
  "timestamp":    "2026-08-22T14:45:00.000000+00:00",  # UTC ISO-8601
  "payload":      { ... },
  "prev_hash":    "0000000000000000000000000000000000000000000000000000000000000000",
  "record_hash":  "3f8b1c4e..."                        # SHA-256(canonical JSON excluding record_hash)
}
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict

from app.utils.logging import get_logger

log = get_logger(__name__)

GENESIS_HASH = "0" * 64

# Thread lock — atomic sequence numbering and file appends
_chain_lock = threading.Lock()

# Cached tail state: (last_index, last_record_hash)
_tail_state: Optional[Tuple[int, str]] = None


class AuditEntry(TypedDict):
    index: int
    record_type: str
    session_id: str
    timestamp: str
    payload: Dict[str, Any]
    prev_hash: str
    record_hash: str


def _canonical_json(data: Any) -> str:
    """Deterministic JSON serializer with sorted keys and no unnecessary whitespace."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_entry_hash(
    *,
    index: int,
    record_type: str,
    session_id: str,
    timestamp: str,
    payload: Dict[str, Any],
    prev_hash: str,
) -> str:
    """
    Compute canonical SHA-256 digest of an audit entry.
    All fields except `record_hash` are included.
    """
    canonical_body = {
        "index": index,
        "payload": payload,
        "prev_hash": prev_hash,
        "record_type": record_type,
        "session_id": session_id,
        "timestamp": timestamp,
    }
    encoded = _canonical_json(canonical_body).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def get_audit_chain_path() -> Path:
    """Return path to the unified audit chain JSONL file."""
    env_path = os.getenv("AUDIT_CHAIN_PATH") or os.getenv("AUDIT_LOG_PATH")
    if env_path:
        return Path(env_path)
    backend_storage = Path("backend/data/storage/audit_chain.jsonl").resolve()
    if backend_storage.exists() and backend_storage.stat().st_size > 0:
        return backend_storage
    storage_root = Path(os.getenv("STORAGE_LOCAL_ROOT", "data/storage")).resolve()
    return storage_root / "audit_chain.jsonl"


def _read_tail_from_disk(path: Path) -> Tuple[int, str]:
    """Scan the audit chain file to find the latest index and hash."""
    if not path.exists() or path.stat().st_size == 0:
        return -1, GENESIS_HASH

    last_index = -1
    last_hash = GENESIS_HASH

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                last_index = entry["index"]
                last_hash = entry["record_hash"]
            except Exception as exc:
                log.error("audit.tail_read_error", error=str(exc), line=line)

    return last_index, last_hash


def seal_record(
    *,
    record_type: Literal["upload", "decision", "access"] | str,
    session_id: str,
    payload: Dict[str, Any],
    timestamp: Optional[str] = None,
) -> AuditEntry:
    """
    Append an entry to the unified hash chain.
    Thread-safe and guaranteed to link to the prior block's record_hash.
    """
    global _tail_state

    ts = timestamp or datetime.now(timezone.utc).isoformat()
    path = get_audit_chain_path()

    with _chain_lock:
        path.parent.mkdir(parents=True, exist_ok=True)

        _tail_state = _read_tail_from_disk(path)
        last_index, prev_hash = _tail_state
        next_index = last_index + 1

        record_hash = compute_entry_hash(
            index=next_index,
            record_type=record_type,
            session_id=session_id,
            timestamp=ts,
            payload=payload,
            prev_hash=prev_hash,
        )

        entry: AuditEntry = {
            "index": next_index,
            "record_type": record_type,
            "session_id": session_id,
            "timestamp": ts,
            "payload": payload,
            "prev_hash": prev_hash,
            "record_hash": record_hash,
        }

        # Write line to append-only file
        line = _canonical_json(entry) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)

        _tail_state = (next_index, record_hash)

        log.info(
            "audit.sealed",
            index=next_index,
            record_type=record_type,
            session_id=session_id,
            record_hash=record_hash[:16] + "...",
            prev_hash=prev_hash[:16] + "...",
        )

    return entry


# ─── Specialized event loggers (all forward to seal_record) ───────────────────

def log_upload_event(
    *,
    session_id: str,
    sha256: str,
    size_bytes: int,
    ip: str = "unknown",
) -> AuditEntry:
    """
    Record raw clip reception and storage.
    Called immediately upon upload receipt, before scoring runs.
    """
    return seal_record(
        record_type="upload",
        session_id=session_id,
        payload={
            "sha256": sha256,
            "size_bytes": size_bytes,
            "ip": ip,
        },
    )


def log_decision_event(
    *,
    session_id: str,
    decision: str,
    anomaly_score: float,
    breakdown: Dict[str, Any],
    video_sha256: str,
    config_version: str,
    ip: str = "unknown",
) -> AuditEntry:
    """
    Record final liveness scoring decision and contributing factors.
    """
    return seal_record(
        record_type="decision",
        session_id=session_id,
        payload={
            "decision": decision,
            "anomaly_score": anomaly_score,
            "breakdown": breakdown,
            "video_sha256": video_sha256,
            "config_version": config_version,
            "ip": ip,
        },
    )


def log_access_event(
    *,
    session_id: str,
    reviewer_id: str,
    action: Literal["presign", "stream"] | str,
    outcome: Literal["success", "denied"] | str,
    ip: str = "unknown",
) -> AuditEntry:
    """
    Record reviewer access attempts to a stored clip.
    Auth-gated at the review router layer.
    """
    return seal_record(
        record_type="access",
        session_id=session_id,
        payload={
            "reviewer_id": reviewer_id,
            "action": action,
            "outcome": outcome,
            "ip": ip,
        },
    )


def log_identity_event(
    *,
    session_id: str,
    cosine_similarity: float,
    registry_velocity: int,
    decision: str,
    decision_latency_ms: float,
    kin_token: Optional[str] = None,
    device_id: Optional[str] = None,
    live_sha256: Optional[str] = None,
    ckyc_sha256: Optional[str] = None,
    ip: str = "unknown",
) -> AuditEntry:
    """
    Record Stage 2 deterministic identity match decision into the unified hash chain.
    """
    return seal_record(
        record_type="identity",
        session_id=session_id,
        payload={
            "cosine_similarity": cosine_similarity,
            "registry_velocity": registry_velocity,
            "decision": decision,
            "decision_latency_ms": decision_latency_ms,
            "kin_token": kin_token or "none",
            "device_id": device_id or "none",
            "live_sha256": live_sha256 or "none",
            "ckyc_sha256": ckyc_sha256 or "none",
            "ip": ip,
        },
    )


def log_investigation_event(
    *,
    session_id: str,
    kin_token: str,
    decision: str,
    agent_recommendation: str,
    dossier_summary: str,
    tool_calls_trace: List[Dict[str, Any]],
    ip: str = "unknown",
) -> AuditEntry:
    """
    Record Stage 3 LangGraph agent investigation into the unified hash chain.
    Trace Faithfulness Guarantee: records exact tool call sequence and raw return values,
    NOT only the LLM's summary narrative.
    """
    return seal_record(
        record_type="investigation",
        session_id=session_id,
        payload={
            "kin_token": kin_token,
            "decision": decision,
            "agent_recommendation": agent_recommendation,
            "dossier_summary": dossier_summary,
            "tool_calls_trace": tool_calls_trace,
            "ip": ip,
        },
    )


def log_agent_retry_event(
    *,
    session_id: str,
    retry_count: int,
    borderline_reasons: List[str],
    retry_note: str,
    new_challenge_sequence: List[str],
    raw_signals: Dict[str, Any],
    ip: str = "unknown",
) -> AuditEntry:
    """
    Record an immediate agentic retry escalation event into the unified hash chain.
    """
    return seal_record(
        record_type="agent_retry_requested",
        session_id=session_id,
        payload={
            "retry_count": retry_count,
            "borderline_reasons": borderline_reasons,
            "retry_note": retry_note,
            "new_challenge_sequence": new_challenge_sequence,
            "raw_signals": raw_signals,
            "ip": ip,
        },
    )


def log_agent_decision_event(
    *,
    session_id: str,
    final_decision: str,
    final_reason: str,
    agent_classification: str,
    has_hard_fail: bool,
    is_borderline: bool,
    agent_reasoning_trace: Dict[str, Any],
    raw_signals: Dict[str, Any],
    decision_table: Dict[str, Any],
    ip: str = "unknown",
) -> AuditEntry:
    """
    Record the LangGraph agent final reasoning and classification event into the unified hash chain.
    """
    return seal_record(
        record_type="agent_decision",
        session_id=session_id,
        payload={
            "final_decision": final_decision,
            "final_reason": final_reason,
            "agent_classification": agent_classification,
            "has_hard_fail": has_hard_fail,
            "is_borderline": is_borderline,
            "agent_reasoning_trace": agent_reasoning_trace,
            "raw_signals": raw_signals,
            "decision_table": decision_table,
            "ip": ip,
        },
    )


def log_reviewer_decision_event(
    *,
    session_id: str,
    reviewer_id: str,
    verdict: str,
    note: str = "",
    parent_decision_hash: Optional[str] = None,
    ip: str = "unknown",
) -> AuditEntry:
    """
    Record Human-In-The-Loop reviewer decision linked cryptographically to the parent agent_decision hash.
    """
    return seal_record(
        record_type="reviewer_decision",
        session_id=session_id,
        payload={
            "reviewer_id": reviewer_id,
            "verdict": verdict,
            "note": note,
            "parent_decision_hash": parent_decision_hash or "none",
            "ip": ip,
        },
    )


def log_human_review_event(
    *,
    case_id: str,
    session_id: str,
    reviewer_id: str,
    action: str,
    notes: str = "",
    ip: str = "unknown",
) -> AuditEntry:
    """
    Record Stage 4 human review resolution into the unified hash chain.
    """
    return seal_record(
        record_type="human_review",
        session_id=session_id,
        payload={
            "case_id": case_id,
            "reviewer_id": reviewer_id,
            "action": action,
            "notes": notes,
            "ip": ip,
        },
    )


def get_latest_agent_decision_hash(session_id: str, chain_path: Optional[Path | str] = None) -> Optional[str]:
    """Retrieve the record_hash of the most recent agent_decision event for a session."""
    path = Path(chain_path) if chain_path else get_audit_chain_path()
    if not path.exists() or path.stat().st_size == 0:
        return None

    last_hash = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("session_id") == session_id and entry.get("record_type") == "agent_decision":
                    last_hash = entry.get("record_hash")
            except Exception:
                continue
    return last_hash


# ─── Chain Verification ───────────────────────────────────────────────────────

def verify_chain(chain_path: Optional[Path | str] = None) -> Tuple[bool, str, int]:
    """
    Walk the hash chain and verify cryptographic integrity:
      1. Entry 0 has prev_hash == GENESIS_HASH and index == 0
      2. Entry i has prev_hash == entry[i-1].record_hash and index == i
      3. For every entry, record_hash matches the recomputed canonical SHA-256
      4. Works across mixed record types (upload, decision, access) seamlessly.

    Returns:
        (is_valid, message, count)
    """
    path = Path(chain_path) if chain_path else get_audit_chain_path()
    if not path.exists() or path.stat().st_size == 0:
        return True, "Chain is empty (no entries recorded)", 0

    entries: List[AuditEntry] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception as exc:
                return False, f"JSON parse error on line {line_num}: {exc}", len(entries)

    expected_prev = GENESIS_HASH

    for i, entry in enumerate(entries):
        # 1. Index continuity
        if entry.get("index") != i:
            return (
                False,
                f"Index discontinuity at position {i}: entry has index {entry.get('index')}",
                i,
            )

        # 2. Previous hash linkage
        if entry.get("prev_hash") != expected_prev:
            return (
                False,
                f"Broken hash link at index {i} (type '{entry.get('record_type')}'): "
                f"prev_hash {entry.get('prev_hash')!r} != expected {expected_prev!r}",
                i,
            )

        # 3. Canonical hash recomputation
        recomputed = compute_entry_hash(
            index=entry["index"],
            record_type=entry["record_type"],
            session_id=entry["session_id"],
            timestamp=entry["timestamp"],
            payload=entry["payload"],
            prev_hash=entry["prev_hash"],
        )

        if entry.get("record_hash") != recomputed:
            return (
                False,
                f"Tamper detected at index {i} (type '{entry.get('record_type')}'): "
                f"record_hash {entry.get('record_hash')!r} != recomputed {recomputed!r}",
                i,
            )

        expected_prev = entry["record_hash"]

    return True, f"Verified {len(entries)} blocks successfully", len(entries)


def reset_chain() -> None:
    """Reset cached tail state (used in testing)."""
    global _tail_state
    with _chain_lock:
        _tail_state = None

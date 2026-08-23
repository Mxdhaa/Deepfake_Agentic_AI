"""
review_queue.py
───────────────
Persistent Review Queue Service for Unresolved / Escalated Cases.

Stores pending cases in append-only JSONL format on D: drive storage,
providing the handoff bridge between Stage 3 (LangGraph Investigation)
and Phase 5 (Human Reviewer Portal).
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
_DEFAULT_QUEUE_PATH = Path(r"D:\projects\Deepfake_agenticai\data\storage\review_queue.jsonl")


def get_queue_path() -> Path:
    env_path = os.getenv("REVIEW_QUEUE_PATH")
    if env_path:
        p = Path(env_path)
    else:
        p = _DEFAULT_QUEUE_PATH
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

    Returns:
        case_id (UUID string)
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
                "deepfake_score": case_data.get("deepfake_score"),
                "cosine_similarity_score": case_data.get("cosine_similarity_score"),
                "registry_velocity_6hr": case_data.get("registry_velocity_6hr"),
                "blink_rate_bpm": case_data.get("blink_rate_bpm"),
                "av_sync_ms": case_data.get("av_sync_ms"),
                "webrtc_jitter_ms": case_data.get("webrtc_jitter_ms"),
            },
        }

        line = json.dumps(entry, sort_keys=True) + "\n"
        with open(p, "a", encoding="utf-8") as f:
            f.write(line)

        log.info("review_queue.enqueued", case_id=case_id, session_id=entry["session_id"])
        return case_id


def list_pending_cases(
    status: Optional[str] = "pending_review",
    queue_path: Optional[Path | str] = None,
) -> List[Dict[str, Any]]:
    """
    List all cases matching the specified status.
    If status is None, 'all', or empty, returns all cases.
    """
    with _QUEUE_LOCK:
        p = Path(queue_path) if queue_path else get_queue_path()
        if not p.exists():
            return []

        cases = []
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if status is None or status.lower() in {"all", "*"} or entry.get("status") == status:
                        cases.append(entry)
                except Exception:
                    pass
        return cases


def get_case(
    case_id: str,
    queue_path: Optional[Path | str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve a specific case by case_id or session_id.
    """
    cases = list_pending_cases(status=None, queue_path=queue_path)
    for c in cases:
        if c.get("case_id") == case_id or c.get("session_id") == case_id:
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
      3. Records reviewer notes and timestamp.
      4. Automatically seals the human review decision into the unified hash chain.
    """
    act = action.strip().lower()
    if act not in {"approve", "reject"}:
        raise ValueError(f"Invalid review action {action!r}. Must be 'approve' or 'reject'.")

    new_status = "resolved_approved" if act == "approve" else "resolved_rejected"
    now_iso = datetime.now(timezone.utc).isoformat()

    with _QUEUE_LOCK:
        p = Path(queue_path) if queue_path else get_queue_path()
        if not p.exists():
            raise KeyError(f"Case {case_id!r} not found (queue empty).")

        all_cases = []
        target_case = None

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

        if target_case is None:
            raise KeyError(f"Case {case_id!r} not found.")

        # Atomically rewrite queue
        with open(p, "w", encoding="utf-8") as f:
            for c in all_cases:
                f.write(json.dumps(c, sort_keys=True) + "\n")

    # Step 4: Seal into unified cryptographic hash chain
    from app.services.audit import log_human_review_event
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

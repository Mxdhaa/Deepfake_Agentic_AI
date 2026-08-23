"""
sandbox.py
──────────
Stage 3: Sandbox Parser & Prompt Injection Defense.

Takes raw onboarding records and strips/validates them into strictly-typed
Pydantic variables. The LLM context never receives raw strings or unsanitized JSON.

Features:
  1. Prompt injection defense (strips instruction patterns: "ignore previous", "system:", etc.)
  2. Character whitelisting and length bounding.
  3. Type validation and numeric clamping.
  4. Structured schemas for audit trace faithfulness.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

from app.utils.logging import get_logger

log = get_logger(__name__)

# ─── Injection Defense Patterns ───────────────────────────────────────────────

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"system\s*(prompt|override|message)?:", re.IGNORECASE),
    re.compile(r"user\s*:", re.IGNORECASE),
    re.compile(r"assistant\s*:", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an)", re.IGNORECASE),
    re.compile(r"admin\s+override", re.IGNORECASE),
    re.compile(r"bypass\s+(security|check|verification)", re.IGNORECASE),
    re.compile(r"output\s+only\s+approve", re.IGNORECASE),
    re.compile(r"approve\s+this\s+request", re.IGNORECASE),
    re.compile(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"[<>{}\[\]\\]"),  # Control / template injection delimiters
]

_LEGAL_NAME_REGEX = re.compile(r"^[a-zA-Z\s\-\.\'\,\ ]+$")
_HEX_DEVICE_REGEX = re.compile(r"^[a-fA-F0-9]+$")


def sanitize_string_field(
    value: Any,
    field_name: str,
    max_length: int = 64,
    allowed_regex: Optional[re.Pattern] = None,
    default: str = "unknown",
) -> str:
    """
    Sanitize an incoming string:
      - Strips all control characters and injection patterns.
      - Enforces maximum character length.
      - Enforces whitelist regex if specified.
    """
    if value is None:
        return default

    s = str(value).strip()

    # Step 1: Strip known prompt injection directives
    original = s
    for pattern in _INJECTION_PATTERNS:
        s = pattern.sub("", s)

    # Step 2: Strip any non-printable ASCII or control characters
    s = "".join(ch for ch in s if ch.isprintable())

    # Step 3: Strip redundant whitespace
    s = " ".join(s.split())

    # Step 4: Truncate to maximum length
    if len(s) > max_length:
        s = s[:max_length].strip()

    # Step 5: Whitelist check
    if allowed_regex and s:
        if not allowed_regex.match(s):
            log.warning(
                "sandbox.whitelist_violation",
                field=field_name,
                raw=original[:30],
                sanitized=s[:30],
            )
            # Remove non-whitelisted characters
            s = "".join(ch for ch in s if allowed_regex.match(ch))

    if not s:
        return default

    if s != original:
        log.info(
            "sandbox.sanitized_field",
            field=field_name,
            original_len=len(original),
            sanitized=s,
        )

    return s


# ─── Pydantic Data Models ─────────────────────────────────────────────────────

class SanitizedOnboardingRecord(BaseModel):
    """
    Strictly-typed sanitized onboarding record.
    Safe for ingestion by LangGraph state machines and LLMs.
    """
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kin_token: str = Field(..., max_length=64)
    legal_name: str = Field(..., max_length=64)
    device_id: str = Field(..., max_length=64)
    webrtc_jitter_ms: float = Field(default=0.0, ge=0.0, le=5000.0)
    cosine_similarity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    registry_velocity_6hr: int = Field(default=1, ge=0, le=1000)
    challenge_match: bool = Field(default=True)
    deepfake_score: float = Field(default=0.0, ge=0.0, le=1.0)
    blink_rate_bpm: float = Field(default=15.0, ge=0.0, le=120.0)
    av_sync_ms: float = Field(default=0.0, ge=-2000.0, le=2000.0)
    stage1_decision: Optional[str] = Field(default=None)
    stage2_decision: Optional[str] = Field(default=None)


class ToolCallTraceEntry(BaseModel):
    """
    Deterministic trace entry for tool calls.
    Captures exact tool name, arguments, and raw numeric/structured return value.
    """
    tool_name: str
    args: Dict[str, Any]
    return_value: Dict[str, Any]
    timestamp: str
    duration_ms: float


class AgentInvestigationResult(BaseModel):
    """
    Output model for Stage 3 LangGraph investigation.
    """
    session_id: str
    kin_token: str
    legal_name: str
    device_id: str
    decision: Literal["resolved", "unresolved"]
    agent_recommendation: Literal["APPROVE", "REFER_TO_HUMAN", "REJECT"]
    dossier_summary: str
    tool_calls_trace: List[ToolCallTraceEntry]
    enqueued_for_review: bool
    llm_latency_ms: float
    tool_latency_ms: float
    total_latency_ms: float


# ─── Public Sanitizer Function ────────────────────────────────────────────────

def sanitize_onboarding_record(raw: Dict[str, Any]) -> SanitizedOnboardingRecord:
    """
    Main sandbox entrypoint.
    Takes a raw dict and returns a typed, injection-free SanitizedOnboardingRecord.
    """
    raw_name = raw.get("legal_name", "Anonymous Applicant")
    sanitized_name = sanitize_string_field(
        raw_name,
        field_name="legal_name",
        max_length=50,
        allowed_regex=_LEGAL_NAME_REGEX,
        default="Anonymous Applicant",
    )

    raw_dev = raw.get("device_id", "0000000000000000")
    sanitized_dev = sanitize_string_field(
        raw_dev,
        field_name="device_id",
        max_length=64,
        allowed_regex=_HEX_DEVICE_REGEX,
        default="0000000000000000",
    )

    raw_kin = raw.get("kin_token", str(uuid.uuid4()))
    sanitized_kin = sanitize_string_field(
        raw_kin,
        field_name="kin_token",
        max_length=64,
        default=str(uuid.uuid4()),
    )

    # Safe float/int conversions with clamping
    try:
        jitter = float(raw.get("webrtc_jitter_ms", 0.0))
        jitter = max(0.0, min(5000.0, jitter))
    except (ValueError, TypeError):
        jitter = 0.0

    try:
        cos_sim = float(raw.get("cosine_similarity_score", 0.0))
        cos_sim = max(0.0, min(1.0, cos_sim))
    except (ValueError, TypeError):
        cos_sim = 0.0

    try:
        vel = int(raw.get("registry_velocity_6hr", 1))
        vel = max(0, min(1000, vel))
    except (ValueError, TypeError):
        vel = 1

    try:
        df_score = float(raw.get("deepfake_score", 0.0))
        df_score = max(0.0, min(1.0, df_score))
    except (ValueError, TypeError):
        df_score = 0.0

    try:
        blink = float(raw.get("blink_rate_bpm", 15.0))
        blink = max(0.0, min(120.0, blink))
    except (ValueError, TypeError):
        blink = 15.0

    try:
        av_sync = float(raw.get("av_sync_ms", 0.0))
        av_sync = max(-2000.0, min(2000.0, av_sync))
    except (ValueError, TypeError):
        av_sync = 0.0

    challenge = bool(raw.get("challenge_match", True))
    sid = str(raw.get("session_id") or uuid.uuid4())

    return SanitizedOnboardingRecord(
        session_id=sid,
        kin_token=sanitized_kin,
        legal_name=sanitized_name,
        device_id=sanitized_dev,
        webrtc_jitter_ms=round(jitter, 2),
        cosine_similarity_score=round(cos_sim, 4),
        registry_velocity_6hr=vel,
        challenge_match=challenge,
        deepfake_score=round(df_score, 4),
        blink_rate_bpm=round(blink, 2),
        av_sync_ms=round(av_sync, 2),
        stage1_decision=raw.get("stage1_decision"),
        stage2_decision=raw.get("stage2_decision"),
    )

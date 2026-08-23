"""
review.py — API Router
──────────────────────
Mounts at: /api/v1/review

Endpoints:
    GET  /api/v1/review/queue                     — Auth-gated list of review cases (with status filter)
    GET  /api/v1/review/queue/{case_id}           — Auth-gated case dossier detail
    POST /api/v1/review/queue/{case_id}/decision  — Auth-gated reviewer decision (approve / reject)
    GET  /api/v1/review/{session_id}/clip         — Auth-gated; returns signed URL or redirect
    GET  /api/v1/review/{session_id}/stream       — Streams raw video bytes
    GET  /api/v1/review/audit-chain               — Auth-gated export of hash chain blocks
    POST /api/v1/review/audit-chain/verify        — Auth-gated thin wrapper calling verify_chain()
"""

from __future__ import annotations

import io
import json
import os
from collections import Counter
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.services.audit import get_audit_chain_path, log_access_event, verify_chain
from app.services.review_queue import get_case, list_pending_cases, resolve_case
from app.services.storage import get_storage, verify_stream_signature
from app.utils.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/review", tags=["Review"])

_SIGNED_URL_EXPIRY_SECONDS = int(os.getenv("REVIEW_URL_EXPIRY_SECONDS", "600"))  # 10 min


# ─── Auth helper ──────────────────────────────────────────────────────────────

def _get_reviewer_token() -> str:
    """Read expected reviewer token from env. Empty string = auth disabled (dev only)."""
    return os.getenv("REVIEWER_TOKEN") or os.getenv("REVIEWER_ACCESS_TOKEN", "")


def _authenticate(
    x_reviewer_token: Optional[str],
    request: Request,
) -> str:
    """
    Validate the X-Reviewer-Token header.
    Returns reviewer_id (token prefix, not the full token) for audit logging.
    Raises HTTP 401/403 on failure.
    """
    expected = _get_reviewer_token()

    if not expected:
        # Dev mode: auth disabled, warn loudly
        log.warning(
            "review.auth_disabled",
            note="Set REVIEWER_TOKEN or REVIEWER_ACCESS_TOKEN env var to enable access control",
        )
        return "dev_mode_no_auth"

    if not x_reviewer_token:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Reviewer-Token header.",
            headers={"WWW-Authenticate": "Token"},
        )

    if x_reviewer_token.strip() != expected.strip():
        log.warning(
            "review.auth_failed",
            ip=request.client.host if request.client else "unknown",
            token_prefix=x_reviewer_token[:6] + "...",
        )
        raise HTTPException(
            status_code=403,
            detail="Invalid reviewer token.",
        )

    return f"reviewer:{x_reviewer_token[:8]}..."


# ─── Schemas ──────────────────────────────────────────────────────────────────

class ClipAccessResponse(BaseModel):
    session_id: str
    url: str
    expires_in: int
    url_type: str   # "presigned_s3" | "internal_stream"
    sha256: str     # from stored metadata — caller can verify clip integrity


class ReviewDecisionRequest(BaseModel):
    action: Literal["approve", "reject"] = Field(..., description="Reviewer action: 'approve' or 'reject'")
    reviewer_id: Optional[str] = Field(None, description="Reviewer identifier or name")
    notes: Optional[str] = Field(None, description="Optional investigative notes")


class ReviewDecisionResponse(BaseModel):
    case_id: str
    session_id: str
    status: str
    review_action: str
    reviewer_id: str
    resolved_at: str
    notes: str


class ChainVerificationResponse(BaseModel):
    is_valid: bool
    message: str
    verified_count: int
    total_count: int
    block_breakdown: Dict[str, int]


# ─── Review Queue Endpoints ───────────────────────────────────────────────────

@router.get(
    "/queue",
    summary="List review queue cases (Auth-Gated)",
    description="Lists cases matching the specified status ('pending_review', 'resolved_approved', 'resolved_rejected', or 'all').",
)
async def list_queue(
    request: Request,
    status: Optional[str] = Query("pending_review", description="Filter by status ('pending_review', 'resolved_approved', 'resolved_rejected', 'all')"),
    x_reviewer_token: Optional[str] = Header(None, alias="X-Reviewer-Token"),
) -> List[Dict[str, Any]]:
    _authenticate(x_reviewer_token, request)
    filter_status = None if (status and status.lower() in {"all", "*"}) else status
    return list_pending_cases(status=filter_status)


@router.get(
    "/queue/{case_id}",
    summary="Get case dossier detail (Auth-Gated)",
)
async def get_queue_case(
    case_id: str,
    request: Request,
    x_reviewer_token: Optional[str] = Header(None, alias="X-Reviewer-Token"),
) -> Dict[str, Any]:
    _authenticate(x_reviewer_token, request)
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id!r} not found in review queue.")
    return case


@router.post(
    "/queue/{case_id}/decision",
    response_model=ReviewDecisionResponse,
    summary="Submit reviewer decision on a case (Auth-Gated)",
)
async def submit_decision(
    case_id: str,
    payload: ReviewDecisionRequest,
    request: Request,
    x_reviewer_token: Optional[str] = Header(None, alias="X-Reviewer-Token"),
) -> ReviewDecisionResponse:
    reviewer_id = _authenticate(x_reviewer_token, request)
    ip = request.client.host if request.client else "unknown"

    # Use provided reviewer_id name if passed, else authenticated token ID
    effective_reviewer = payload.reviewer_id or reviewer_id

    try:
        resolved = resolve_case(
            case_id=case_id,
            action=payload.action,
            reviewer_id=effective_reviewer,
            notes=payload.notes,
            ip=ip,
        )
        return ReviewDecisionResponse(
            case_id=resolved["case_id"],
            session_id=resolved["session_id"],
            status=resolved["status"],
            review_action=resolved["review_action"],
            reviewer_id=resolved["reviewer_id"],
            resolved_at=resolved["resolved_at"],
            notes=resolved.get("notes") or "",
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Case {case_id!r} not found.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ─── Media Review Endpoints ───────────────────────────────────────────────────

@router.get(
    "/{session_id}/clip",
    response_model=ClipAccessResponse,
    summary="Get a short-lived access URL for a stored clip",
)
async def get_clip_url(
    session_id: str,
    request: Request,
    x_reviewer_token: Optional[str] = Header(None, alias="X-Reviewer-Token"),
) -> ClipAccessResponse:
    reviewer_id = _authenticate(x_reviewer_token, request)
    ip = request.client.host if request.client else "unknown"

    storage = get_storage()
    if not storage.exists(session_id):
        log_access_event(
            session_id=session_id,
            reviewer_id=reviewer_id,
            action="presign",
            outcome="denied",
            ip=ip,
        )
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found.")

    log_access_event(
        session_id=session_id,
        reviewer_id=reviewer_id,
        action="presign",
        outcome="success",
        ip=ip,
    )

    url = storage.presign(session_id, expires_seconds=_SIGNED_URL_EXPIRY_SECONDS)
    url_type = "internal_stream" if url.startswith("/api/") else "presigned_s3"

    try:
        meta = storage.read_metadata(session_id)
        sha256 = meta.get("sha256", "unknown")
    except KeyError:
        sha256 = "metadata_unavailable"

    log.info(
        "review.clip_url_issued",
        session_id=session_id,
        reviewer_id=reviewer_id,
        url_type=url_type,
        expires_in=_SIGNED_URL_EXPIRY_SECONDS,
    )

    return ClipAccessResponse(
        session_id=session_id,
        url=url,
        expires_in=_SIGNED_URL_EXPIRY_SECONDS,
        url_type=url_type,
        sha256=sha256,
    )


@router.get(
    "/{session_id}/stream",
    summary="Stream raw clip bytes (Local backend via HMAC signed URL or Header Auth)",
)
async def stream_clip(
    session_id: str,
    request: Request,
    exp: Optional[int] = Query(None, description="Expiration timestamp (unix epoch) for signed stream URL"),
    sig: Optional[str] = Query(None, description="HMAC-SHA256 signature for signed stream URL"),
    x_reviewer_token: Optional[str] = Header(None, alias="X-Reviewer-Token"),
) -> StreamingResponse:
    ip = request.client.host if request.client else "unknown"
    expected_token = _get_reviewer_token()

    if exp is not None and sig is not None:
        # Validate HMAC-SHA256 signed URL
        if not verify_stream_signature(session_id, exp, sig):
            log_access_event(
                session_id=session_id,
                reviewer_id=f"signed_url:invalid_sig:{sig[:8] if sig else 'none'}",
                action="stream",
                outcome="denied",
                ip=ip,
            )
            log.warning("review.stream_signature_failed", session_id=session_id, ip=ip)
            raise HTTPException(status_code=403, detail="Invalid or expired stream signature.")
        reviewer_id = f"signed_url:exp={exp}"
    elif expected_token:
        # Fallback to direct X-Reviewer-Token header authentication
        reviewer_id = _authenticate(x_reviewer_token, request)
    else:
        # Dev mode without auth configured
        reviewer_id = "dev_mode_no_auth"

    storage = get_storage()
    try:
        clip_bytes = storage.read(session_id)
    except KeyError:
        log_access_event(
            session_id=session_id,
            reviewer_id=reviewer_id,
            action="stream",
            outcome="denied",
            ip=ip,
        )
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found.")

    log_access_event(
        session_id=session_id,
        reviewer_id=reviewer_id,
        action="stream",
        outcome="success",
        ip=ip,
    )

    return StreamingResponse(
        io.BytesIO(clip_bytes),
        media_type="video/mp4",
        headers={"Content-Disposition": f'inline; filename="{session_id}.mp4"'},
    )


# ─── Audit Chain Endpoints ────────────────────────────────────────────────────

@router.get(
    "/audit-chain",
    summary="Export sealed audit hash chain blocks (Auth-Gated)",
)
async def get_audit_chain_blocks(
    request: Request,
    x_reviewer_token: Optional[str] = Header(None, alias="X-Reviewer-Token"),
) -> List[Dict[str, Any]]:
    _authenticate(x_reviewer_token, request)
    chain_path = get_audit_chain_path()
    if not chain_path.exists():
        return []

    blocks = []
    with open(chain_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    blocks.append(json.loads(line))
                except Exception:
                    pass
    return blocks


@router.post(
    "/audit-chain/verify",
    response_model=ChainVerificationResponse,
    summary="Verify cryptographic integrity of the audit chain (Auth-Gated)",
    description="Direct thin wrapper calling verify_chain() from app.services.audit.",
)
async def verify_audit_chain_endpoint(
    request: Request,
    x_reviewer_token: Optional[str] = Header(None, alias="X-Reviewer-Token"),
) -> ChainVerificationResponse:
    _authenticate(x_reviewer_token, request)
    chain_path = get_audit_chain_path()

    is_valid, msg, verified_count = verify_chain(chain_path)

    total_count = 0
    breakdown: Counter = Counter()
    if chain_path.exists():
        with open(chain_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    total_count += 1
                    try:
                        entry = json.loads(line)
                        breakdown[entry.get("record_type", "unknown")] += 1
                    except Exception:
                        pass

    return ChainVerificationResponse(
        is_valid=is_valid,
        message=msg,
        verified_count=verified_count,
        total_count=total_count,
        block_breakdown=dict(breakdown),
    )

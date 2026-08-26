"""
liveness.py — API router
────────────────────────
Mounts at: /api/v1/liveness

Endpoints:
    POST /api/v1/liveness/analyze   — Upload clip, get anomaly score + decision
    GET  /api/v1/liveness/config    — Inspect current scoring weights/thresholds
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Form
from pydantic import BaseModel, Field

from app.services.liveness import analyze_liveness, get_config
from app.services.storage import get_storage, compute_sha256
from app.services.audit import log_upload_event, log_decision_event
from app.utils.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/liveness", tags=["Liveness"])

# Max clip size: 50 MB
_MAX_CLIP_BYTES = 50 * 1024 * 1024

_ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-msvideo",   # avi
    "application/octet-stream",  # some browsers send this for .webm
}


# ─── Response schemas ─────────────────────────────────────────────────────────

class AnomalyBreakdownSchema(BaseModel):
    deepfake_contribution:  float = Field(ge=0.0, le=1.0)
    challenge_contribution: float = Field(ge=0.0, le=1.0)
    blink_contribution:     float = Field(ge=0.0, le=1.0)
    av_sync_contribution:   float = Field(ge=0.0, le=1.0)


class LivenessResult(BaseModel):
    session_id:            str
    deepfake_score:        float   = Field(ge=0.0, le=1.0,
                                           description="Mean frame-level deepfake probability")
    challenge_match:       bool    = Field(description="True if sufficient motion detected")
    motion_frames:         int     = Field(ge=0,
                                           description="Frames with detectable inter-frame motion")
    mean_motion_magnitude: float   = Field(ge=0.0,
                                           description="Mean optical-flow magnitude across clip")
    blink_rate_bpm:        float   = Field(ge=0.0,
                                           description="Detected blink rate (blinks/min); 0 if unavailable")
    blink_count:           int     = Field(ge=0)
    av_sync_ms:            float   = Field(description="Audio-video sync offset in ms; 0 if no audio")
    anomaly_score:         float   = Field(ge=0.0, le=1.0,
                                           description="Weighted composite anomaly score [0,1]")
    decision:              str     = Field(description="pass | borderline | fail")
    breakdown:             AnomalyBreakdownSchema
    processing_time_ms:    float
    frame_count:           int     = Field(ge=0)
    config_version:        str
    detection_mode:        Optional[str] = "heuristic_fallback"
    detected_sequence:     Optional[list[str]] = None
    expected_sequence:     Optional[list[str]] = None
    video_sha256:          str     = Field(
        description=(
            "SHA-256 hex digest of the raw clip bytes as received, computed BEFORE "
            "any frame extraction or transcoding. Used to verify archival integrity. "
            "Matches the hash stored in object storage for this session."
        )
    )


class LivenessConfigResponse(BaseModel):
    config_version: str
    weights:        dict
    thresholds:     dict
    frame_sampling: dict
    motion:         dict


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post(
    "/analyze",
    response_model=LivenessResult,
    summary="Analyze a liveness clip",
    description=(
        "Upload a short video clip (5–10s) captured during a liveness challenge. "
        "Returns a deepfake score, motion-based challenge result, blink rate, "
        "AV sync offset, and a weighted composite anomaly score with a "
        "pass / borderline / fail decision."
    ),
)
async def analyze(
    request: Request,
    clip: UploadFile = File(..., description="Video clip from liveness session (mp4/webm/mov)"),
    challenge_type: Optional[str] = Form(None, description="Expected challenge identifier (e.g. blink_twice, turn_left, nod_head)"),
) -> LivenessResult:
    session_id = str(uuid.uuid4())
    t0 = time.perf_counter()
    ip = request.client.host if (request and request.client) else "unknown"

    # ── Content-type guard ─────────────────────────────────────────────────────
    ct = (clip.content_type or "").lower()
    if ct not in _ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported media type: '{ct}'. "
                f"Accepted: {sorted(_ALLOWED_VIDEO_TYPES)}"
            ),
        )

    # ── Size guard ─────────────────────────────────────────────────────────────
    clip_bytes = await clip.read()
    if len(clip_bytes) > _MAX_CLIP_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Clip too large ({len(clip_bytes) // 1024 // 1024} MB). Max 50 MB.",
        )
    if len(clip_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty clip received.")

    log.info(
        "liveness.analyze.received",
        session_id=session_id,
        filename=clip.filename,
        size_bytes=len(clip_bytes),
        content_type=ct,
        challenge_type=challenge_type,
    )

    # ── STEP 1: Hash raw bytes immediately — same buffer, before ANY processing ─
    # Python bytes are immutable; clip_bytes is the same object throughout.
    # The hash MUST be computed here, on the buffer as received over the wire,
    # before extract_frames(), transcoding, or any other operation touches it.
    video_sha256 = compute_sha256(clip_bytes)

    # ── STEP 2: Write to storage (archival) ────────────────────────────────────
    # Archival must complete before scoring starts so that a scoring failure
    # never causes a clip to be unarchived. Storage.write() uses the same
    # clip_bytes reference — same raw bytes, same hash.
    storage = get_storage()
    try:
        storage.write(
            session_id,
            clip_bytes,
            metadata={
                "sha256":   video_sha256,
                "filename": clip.filename or "clip",
                "content_type": ct,
                "challenge_type": challenge_type or "general_motion",
            },
        )
    except Exception as exc:
        log.error("liveness.storage_write_failed", session_id=session_id, error=str(exc))
        # Storage failure is a hard error — do not proceed without archival
        raise HTTPException(
            status_code=503,
            detail=f"Archival failed — clip not stored. Scoring aborted: {exc}",
        ) from exc

    # ── STEP 3: Audit log upload event (unified tamper-evident hash chain) ─────
    # Log upload event immediately after successful storage write.
    log_upload_event(
        session_id=session_id,
        sha256=video_sha256,
        size_bytes=len(clip_bytes),
        ip=ip,
    )

    # ── STEP 4: Run scoring pipeline ───────────────────────────────────────────
    # Scoring may fail — that's OK, the clip is already archived (Steps 1-3 done).
    # A scoring failure returns HTTP 500 but does NOT delete the stored clip.
    try:
        result = analyze_liveness(clip_bytes, expected_challenge=challenge_type)
    except Exception as exc:
        log.error("liveness.analyze.failed", session_id=session_id, error=str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Liveness analysis failed: {exc}",
        ) from exc

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

    # ── STEP 5: Audit log decision event (unified tamper-evident hash chain) ───
    log_decision_event(
        session_id=session_id,
        decision=result["decision"],
        anomaly_score=result["anomaly_score"],
        breakdown=result["breakdown"],
        video_sha256=video_sha256,
        config_version=result["config_version"],
        ip=ip,
    )

    log.info(
        "liveness.analyze.complete",
        session_id=session_id,
        decision=result["decision"],
        anomaly_score=result["anomaly_score"],
        deepfake_score=result["deepfake_score"],
        challenge_match=result["challenge_match"],
        elapsed_ms=elapsed_ms,
    )

    return LivenessResult(
        session_id=session_id,
        deepfake_score=result["deepfake_score"],
        challenge_match=result["challenge_match"],
        motion_frames=result["motion_frames"],
        mean_motion_magnitude=result["mean_motion_magnitude"],
        blink_rate_bpm=result["blink_rate_bpm"],
        blink_count=result["blink_count"],
        av_sync_ms=result["av_sync_ms"],
        anomaly_score=result["anomaly_score"],
        decision=result["decision"],
        breakdown=AnomalyBreakdownSchema(**result["breakdown"]),
        processing_time_ms=elapsed_ms,
        frame_count=result["frame_count"],
        config_version=result["config_version"],
        detection_mode=result.get("detection_mode", "heuristic_fallback"),
        detected_sequence=result.get("detected_sequence", []),
        expected_sequence=result.get("expected_sequence", []),
        video_sha256=video_sha256,
    )


@router.get(
    "/config",
    response_model=LivenessConfigResponse,
    summary="Inspect liveness scoring config",
    description=(
        "Returns the current scoring weights, decision thresholds, and frame-sampling "
        "settings. Useful for the frontend to display config and for auditors to verify "
        "which parameter set produced a given decision."
    ),
)
async def config_inspect() -> LivenessConfigResponse:
    cfg = get_config()
    return LivenessConfigResponse(
        config_version=cfg.get("config_version", "unknown"),
        weights=cfg.get("weights", {}),
        thresholds=cfg.get("thresholds", {}),
        frame_sampling=cfg.get("frame_sampling", {}),
        motion=cfg.get("motion", {}),
    )

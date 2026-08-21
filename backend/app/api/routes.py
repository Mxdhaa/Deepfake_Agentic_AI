"""
API Routes
──────────
POST /api/v1/detect    — Upload image/video, run detection pipeline
POST /api/v1/analyze   — Run full LangGraph agent analysis
GET  /api/v1/health    — Detailed health with model status
"""

import hashlib
import uuid
import time
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.agent.graph import run_detection_graph
from app.utils.logging import get_logger

log = get_logger(__name__)
router = APIRouter()


# ─── Response Schemas ─────────────────────────────────────────────────────────

class DetectionResult(BaseModel):
    request_id: str
    filename: str
    file_hash: str
    is_deepfake: bool
    confidence: float
    label: str                    # "REAL" | "FAKE" | "UNCERTAIN"
    processing_time_ms: float
    artifacts: list[str]          # detected manipulation artifacts
    agent_summary: Optional[str] = None


class HealthDetail(BaseModel):
    status: str
    version: str
    model_loaded: bool
    uptime_seconds: float


_START_TIME = time.time()


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/detect", response_model=DetectionResult, tags=["Detection"])
async def detect(file: UploadFile = File(...)):
    """
    Upload an image or video frame.
    Returns deepfake probability and a list of detected visual artifacts.
    """
    if file.content_type not in {
        "image/jpeg", "image/png", "image/webp",
        "video/mp4", "video/avi", "video/quicktime",
    }:
        raise HTTPException(status_code=415, detail="Unsupported media type.")

    request_id = str(uuid.uuid4())
    t0 = time.perf_counter()

    contents = await file.read()
    file_hash = hashlib.sha256(contents).hexdigest()

    log.info(
        "detect.received",
        request_id=request_id,
        filename=file.filename,
        size_bytes=len(contents),
        file_hash=file_hash[:16],
    )

    try:
        result = await run_detection_graph(
            request_id=request_id,
            filename=file.filename or "upload",
            file_bytes=contents,
            content_type=file.content_type or "image/jpeg",
        )
    except Exception as exc:
        log.error("detect.failed", request_id=request_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Detection failed: {exc}") from exc

    elapsed_ms = (time.perf_counter() - t0) * 1000
    log.info(
        "detect.complete",
        request_id=request_id,
        is_deepfake=result["is_deepfake"],
        confidence=result["confidence"],
        elapsed_ms=round(elapsed_ms, 2),
    )

    return DetectionResult(
        request_id=request_id,
        filename=file.filename or "upload",
        file_hash=file_hash,
        is_deepfake=result["is_deepfake"],
        confidence=result["confidence"],
        label=result["label"],
        processing_time_ms=round(elapsed_ms, 2),
        artifacts=result.get("artifacts", []),
        agent_summary=result.get("agent_summary"),
    )


@router.get("/health", response_model=HealthDetail, tags=["Meta"])
async def health_detail():
    """Detailed health endpoint including model status."""
    return HealthDetail(
        status="ok",
        version="0.1.0",
        model_loaded=False,   # TODO: update when model loader is wired in
        uptime_seconds=round(time.time() - _START_TIME, 1),
    )

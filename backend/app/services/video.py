"""
video.py
────────
Thin OpenCV wrapper for video ingestion.

Keeps all cv2 imports in one place so the rest of the codebase stays
decoupled from OpenCV internals.
"""

from __future__ import annotations

import io
import tempfile
import os
from pathlib import Path
from typing import List

import cv2
import numpy as np

from app.utils.logging import get_logger

log = get_logger(__name__)

# Use workspace-local tmp dir to avoid issues with full system TEMP (Windows)
# Falls back to data/tmp/ relative to the backend root.
_BACKEND_ROOT = Path(__file__).parent.parent.parent  # backend/
_LOCAL_TMP = _BACKEND_ROOT / "data" / "tmp"
_LOCAL_TMP.mkdir(parents=True, exist_ok=True)


def _tmp_dir() -> Path:
    """Return the temp dir to use. Respects TMPDIR env var."""
    env = os.getenv("TMPDIR")
    if env:
        return Path(env)
    return _LOCAL_TMP


def bytes_to_frames(
    video_bytes: bytes,
    max_frames: int = 16,
    resize: tuple[int, int] = (224, 224),
) -> List[np.ndarray]:
    """
    Decode a video from raw bytes and return up to `max_frames` RGB frames
    as float32 arrays normalised to [0, 1].

    Frames are uniformly subsampled across the clip so short and long
    videos are treated equivalently.

    Returns:
        List of (H, W, 3) float32 numpy arrays in RGB order.
        Empty list if decoding fails.
    """
    # OpenCV needs a file path — write to a named temp file on D: drive
    import uuid as _uuid
    tmp_path = str(_tmp_dir() / f"clip_{_uuid.uuid4().hex}.mp4")
    with open(tmp_path, "wb") as f:
        f.write(video_bytes)

    frames: List[np.ndarray] = []
    try:
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            log.warning("video.open_failed", path=tmp_path)
            return frames

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total <= 0:
            # Unknown frame count — read all and subsample after
            raw: List[np.ndarray] = []
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                raw.append(frame)
            cap.release()
            frames = _subsample_and_convert(raw, max_frames, resize)
        else:
            # Known count — seek to evenly-spaced positions
            indices = _sample_indices(total, max_frames)
            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ok, frame = cap.read()
                if ok and frame is not None:
                    frames.append(_bgr_to_rgb_float(frame, resize))
            cap.release()

        log.debug("video.extracted", n_frames=len(frames), total_frames=total)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return frames


def estimate_fps(video_bytes: bytes) -> float:
    """
    Return the video's reported FPS. Falls back to 30.0 on failure.
    Used by liveness.py to convert blink counts → blinks/min.
    """
    import uuid as _uuid
    tmp_path = str(_tmp_dir() / f"fps_{_uuid.uuid4().hex}.mp4")
    with open(tmp_path, "wb") as f:
        f.write(video_bytes)

    fps = 30.0
    try:
        cap = cv2.VideoCapture(tmp_path)
        if cap.isOpened():
            reported = cap.get(cv2.CAP_PROP_FPS)
            if reported and reported > 0:
                fps = float(reported)
        cap.release()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return fps


def estimate_duration_seconds(video_bytes: bytes) -> float:
    """Return clip duration in seconds. Falls back to 5.0."""
    import uuid as _uuid
    tmp_path = str(_tmp_dir() / f"dur_{_uuid.uuid4().hex}.mp4")
    with open(tmp_path, "wb") as f:
        f.write(video_bytes)

    duration = 5.0
    try:
        cap = cv2.VideoCapture(tmp_path)
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            if fps > 0 and frames > 0:
                duration = float(frames / fps)
        cap.release()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return duration


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _sample_indices(total: int, max_frames: int) -> List[int]:
    """Return up to max_frames evenly-spaced frame indices from [0, total)."""
    if total <= max_frames:
        return list(range(total))
    step = total / max_frames
    return [int(i * step) for i in range(max_frames)]


def _bgr_to_rgb_float(frame: np.ndarray, resize: tuple[int, int]) -> np.ndarray:
    """Convert BGR uint8 OpenCV frame → RGB float32 [0,1] at target size."""
    resized = cv2.resize(frame, resize, interpolation=cv2.INTER_LINEAR)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    return rgb.astype(np.float32) / 255.0


def _subsample_and_convert(
    raw: List[np.ndarray],
    max_frames: int,
    resize: tuple[int, int],
) -> List[np.ndarray]:
    indices = _sample_indices(len(raw), max_frames)
    return [_bgr_to_rgb_float(raw[i], resize) for i in indices]

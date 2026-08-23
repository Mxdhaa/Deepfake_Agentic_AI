"""
liveness.py
───────────
Core liveness analysis service for Stage 1.

This module is the single source of truth for everything that happens between
"received video bytes" and "produced anomaly score". All weights and thresholds
are read from liveness_config.yaml — nothing is hardcoded here.

Public API
──────────
    result = analyze_liveness(video_bytes)
    # result is a LivenessAnalysis TypedDict

Pipeline
────────
    video_bytes
        └─► extract_frames()          →  frames: list[np.ndarray]
        └─► score_deepfake()          →  deepfake_score: float
        └─► detect_motion()           →  motion: MotionResult
        └─► detect_blinks()           →  blinks: BlinkResult
        └─► compute_av_sync()         →  av_sync_ms: float
        └─► compute_anomaly_score()   →  decision + breakdown
"""

from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import TypedDict, Optional, List

import numpy as np
import yaml

from app.services.video import bytes_to_frames, estimate_fps, estimate_duration_seconds
from app.models.detector import DeepfakeDetector
from app.utils.logging import get_logger

log = get_logger(__name__)


# ─── Config loader (cached — reads YAML once per process) ─────────────────────

@functools.lru_cache(maxsize=1)
def _load_config() -> dict:
    """
    Load liveness_config.yaml. Path is resolved relative to this file so
    it works regardless of the working directory the server is started from.
    Also respects the LIVENESS_CONFIG_PATH env var for overrides.
    """
    env_path = os.getenv("LIVENESS_CONFIG_PATH")
    if env_path:
        config_path = Path(env_path)
    else:
        config_path = Path(__file__).parent.parent / "core" / "liveness_config.yaml"

    if not config_path.exists():
        log.warning("liveness.config_missing", path=str(config_path), using="defaults")
        return _default_config()

    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    log.info("liveness.config_loaded", path=str(config_path),
             version=cfg.get("config_version", "unknown"))
    return cfg


def _default_config() -> dict:
    """Fallback config if YAML file is missing (e.g. in CI)."""
    return {
        "config_version": "default",
        "weights": {"deepfake_score": 0.50, "challenge_match": 0.25,
                    "blink_rate": 0.15, "av_sync": 0.10},
        "thresholds": {"deepfake_fail": 0.75, "deepfake_borderline": 0.40,
                       "motion_min_frames": 3, "blink_min_bpm": 8.0,
                       "av_sync_borderline_ms": 80, "av_sync_fail_ms": 150,
                       "anomaly_fail": 0.65, "anomaly_borderline": 0.40},
        "frame_sampling": {"max_frames": 16, "resize": [224, 224]},
        "motion": {"min_delta_threshold": 4.0, "flow_magnitude_min": 0.8},
    }


def get_config() -> dict:
    """Public accessor — returns cached config dict."""
    return _load_config()


# ─── Result TypedDicts ────────────────────────────────────────────────────────

class MotionResult(TypedDict):
    motion_detected: bool
    motion_frames: int          # frames with delta above threshold
    mean_magnitude: float       # mean optical-flow magnitude across clip


class BlinkResult(TypedDict):
    blink_rate_bpm: float       # blinks per minute (0.0 if detection unavailable)
    blink_count: int
    detection_available: bool   # False if mediapipe not installed


class AnomalyBreakdown(TypedDict):
    deepfake_contribution: float
    challenge_contribution: float
    blink_contribution: float
    av_sync_contribution: float


class LivenessAnalysis(TypedDict):
    deepfake_score: float
    challenge_match: bool
    motion_frames: int
    mean_motion_magnitude: float
    blink_rate_bpm: float
    blink_count: int
    av_sync_ms: float
    anomaly_score: float
    decision: str               # "pass" | "borderline" | "fail"
    breakdown: AnomalyBreakdown
    frame_count: int
    config_version: str


# ─── Singleton detector ───────────────────────────────────────────────────────

_detector: Optional[DeepfakeDetector] = None


def _get_detector() -> DeepfakeDetector:
    global _detector
    if _detector is None:
        _detector = DeepfakeDetector()
    return _detector


# ─── Frame extraction ─────────────────────────────────────────────────────────

def extract_frames(video_bytes: bytes) -> List[np.ndarray]:
    """Extract subsampled frames from raw video bytes using config settings."""
    cfg = _load_config()
    fs = cfg.get("frame_sampling", {})
    max_frames = fs.get("max_frames", 16)
    resize_cfg = fs.get("resize", [224, 224])
    resize = (int(resize_cfg[0]), int(resize_cfg[1]))
    return bytes_to_frames(video_bytes, max_frames=max_frames, resize=resize)


# ─── Deepfake scoring ─────────────────────────────────────────────────────────

def score_deepfake(frames: List[np.ndarray]) -> float:
    """
    Run the pretrained deepfake detector on each frame.
    Returns the mean score across all frames (clip-level score).
    Returns 0.5 (uncertain) if no frames available.
    """
    if not frames:
        log.warning("liveness.no_frames_for_scoring")
        return 0.5

    detector = _get_detector()
    scores = []
    for frame in frames:
        try:
            s = detector.predict(frame)
            scores.append(s)
        except Exception as exc:
            log.warning("liveness.frame_score_failed", error=str(exc))

    if not scores:
        return 0.5

    mean_score = float(np.mean(scores))
    log.debug("liveness.deepfake_score",
              mean=round(mean_score, 4),
              n_frames=len(scores),
              min=round(min(scores), 4),
              max=round(max(scores), 4))
    return mean_score


# ─── Motion detection ─────────────────────────────────────────────────────────

def detect_motion(frames: List[np.ndarray]) -> MotionResult:
    """
    Detect inter-frame motion using frame-delta analysis.

    Algorithm:
      1. Convert consecutive frame pairs to grayscale
      2. Compute absolute pixel difference
      3. Count frames where mean delta > min_delta_threshold
      4. Optionally compute dense optical flow for magnitude estimate

    This is deliberately lightweight — no pose estimation, no MediaPipe.
    We just need to confirm that *something moved* in the clip.
    """
    cfg = _load_config()
    motion_cfg = cfg.get("motion", {})
    threshold = float(motion_cfg.get("min_delta_threshold", 4.0))

    if len(frames) < 2:
        return MotionResult(motion_detected=False, motion_frames=0, mean_magnitude=0.0)

    import cv2

    motion_frame_count = 0
    magnitudes: List[float] = []

    prev_gray: Optional[np.ndarray] = None

    for frame in frames:
        # Convert float32 RGB [0,1] → uint8 grayscale
        gray = (frame.mean(axis=2) * 255).astype(np.uint8)

        if prev_gray is not None:
            # Frame-delta: fast O(HW) check
            delta = np.abs(gray.astype(np.int16) - prev_gray.astype(np.int16))
            mean_delta = float(delta.mean())

            if mean_delta >= threshold:
                motion_frame_count += 1

            # Optical flow magnitude (Farneback — more accurate but heavier)
            try:
                flow = cv2.calcOpticalFlowFarneback(
                    prev_gray, gray,
                    None,
                    pyr_scale=0.5, levels=2, winsize=12,
                    iterations=2, poly_n=5, poly_sigma=1.1,
                    flags=0,
                )
                mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                magnitudes.append(float(mag.mean()))
            except Exception:
                magnitudes.append(mean_delta / 255.0)

        prev_gray = gray

    cfg_thresh = _load_config()["thresholds"]
    min_motion = int(cfg_thresh.get("motion_min_frames", 3))
    mean_mag = float(np.mean(magnitudes)) if magnitudes else 0.0

    result = MotionResult(
        motion_detected=motion_frame_count >= min_motion,
        motion_frames=motion_frame_count,
        mean_magnitude=round(mean_mag, 4),
    )
    log.debug("liveness.motion", **result)
    return result


# ─── Blink detection ──────────────────────────────────────────────────────────

def detect_blinks(frames: List[np.ndarray], duration_seconds: float = 5.0) -> BlinkResult:
    """
    Estimate blink rate from eye aspect ratio (EAR) using MediaPipe Face Mesh.

    If MediaPipe is not installed, returns a stub result with
    detection_available=False (the anomaly scorer treats missing data
    as neutral — no penalty applied).

    EAR threshold for blink: < 0.20 (standard value from Soukupova & Cech 2016).
    """
    try:
        import mediapipe as mp  # type: ignore
    except ImportError:
        log.info("liveness.blink_mediapipe_unavailable",
                 note="pip install mediapipe to enable blink detection")
        return BlinkResult(blink_rate_bpm=0.0, blink_count=0, detection_available=False)

    # MediaPipe Face Mesh landmark indices for left/right eye
    # Left eye: [362, 385, 387, 263, 373, 380]
    # Right eye: [33, 160, 158, 133, 153, 144]
    LEFT_EYE  = [362, 385, 387, 263, 373, 380]
    RIGHT_EYE = [33,  160, 158, 133, 153, 144]
    EAR_THRESHOLD = 0.20

    def _ear(landmarks, indices: list[int]) -> float:
        """Eye Aspect Ratio from 6 landmark points."""
        pts = [(landmarks[i].x, landmarks[i].y) for i in indices]
        # Vertical distances
        A = _dist(pts[1], pts[5])
        B = _dist(pts[2], pts[4])
        # Horizontal distance
        C = _dist(pts[0], pts[3])
        return (A + B) / (2.0 * C + 1e-6)

    def _dist(a: tuple, b: tuple) -> float:
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    mp_face_mesh = mp.solutions.face_mesh
    blink_count = 0
    eye_closed_prev = False

    try:
        with mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
        ) as face_mesh:
            for frame in frames:
                img_uint8 = (frame * 255).astype(np.uint8)
                result = face_mesh.process(img_uint8)
                if not result.multi_face_landmarks:
                    continue

                lm = result.multi_face_landmarks[0].landmark
                left_ear  = _ear(lm, LEFT_EYE)
                right_ear = _ear(lm, RIGHT_EYE)
                avg_ear = (left_ear + right_ear) / 2.0

                eye_closed = avg_ear < EAR_THRESHOLD
                if eye_closed and not eye_closed_prev:
                    blink_count += 1
                eye_closed_prev = eye_closed

        blink_rate_bpm = (blink_count / max(duration_seconds, 1.0)) * 60.0

        log.debug("liveness.blinks",
                  blink_count=blink_count,
                  duration_s=round(duration_seconds, 1),
                  bpm=round(blink_rate_bpm, 2))
        return BlinkResult(
            blink_rate_bpm=round(blink_rate_bpm, 2),
            blink_count=blink_count,
            detection_available=True,
        )

    except Exception as exc:
        log.warning("liveness.blink_detection_failed", error=str(exc))
        return BlinkResult(blink_rate_bpm=0.0, blink_count=0, detection_available=False)


# ─── AV sync estimation ───────────────────────────────────────────────────────

def compute_av_sync(video_bytes: bytes) -> float:
    """
    Estimate audio-video synchronisation offset in milliseconds.

    Full implementation would cross-correlate audio speech energy envelope
    with lip-motion signal from face landmarks. For Stage 1 this is a
    calibrated stub:
      - Clips with no audio track → 0.0ms (can't measure, neutral)
      - Clips with audio → placeholder 0.0ms (will be replaced in Stage 2)

    The stub never triggers the av_sync penalty so anomaly scores are
    driven by deepfake_score + motion + blinks only, which is correct
    for a day-2/3 scope.
    """
    # TODO Stage 2: implement real AV cross-correlation
    # Detect whether the clip has an audio track
    try:
        import subprocess, json as _json, uuid as _uuid, os
        _tmp = Path(__file__).parent.parent.parent / "data" / "tmp"
        _tmp.mkdir(parents=True, exist_ok=True)
        tmp_path = str(_tmp / f"av_{_uuid.uuid4().hex}.mp4")
        with open(tmp_path, "wb") as f:
            f.write(video_bytes)
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_streams", tmp_path],
                capture_output=True, text=True, timeout=5,
            )
            streams = _json.loads(probe.stdout).get("streams", [])
            has_audio = any(s.get("codec_type") == "audio" for s in streams)
        finally:
            os.unlink(tmp_path)

        if not has_audio:
            log.debug("liveness.av_sync", value_ms=0.0, reason="no_audio_track")
            return 0.0
        # Audio present but full cross-correlation not yet implemented
        log.debug("liveness.av_sync", value_ms=0.0, reason="stub_pending_stage2")
        return 0.0
    except Exception:
        return 0.0


# ─── Anomaly score computation ────────────────────────────────────────────────

def compute_anomaly_score(
    deepfake_score: float,
    challenge_match: bool,
    blink_rate_bpm: float,
    av_sync_ms: float,
    blink_available: bool = True,
) -> tuple[float, str, AnomalyBreakdown]:
    """
    Compute the weighted anomaly score from the four operational signals.

    Returns:
        (anomaly_score, decision, breakdown)
        decision ∈ {"pass", "borderline", "fail"}
    """
    cfg = _load_config()
    W = cfg["weights"]
    T = cfg["thresholds"]

    # ── Penalty functions ──────────────────────────────────────────────────────
    p_deepfake = float(np.clip(deepfake_score, 0.0, 1.0))

    p_challenge = 0.0 if challenge_match else 1.0

    # Blink: if detection unavailable treat as neutral (0.0) — no false penalty
    if not blink_available or blink_rate_bpm <= 0:
        p_blink = 0.0
    else:
        p_blink = 0.0 if blink_rate_bpm >= float(T["blink_min_bpm"]) else 1.0

    av_fail_ms = float(T["av_sync_fail_ms"])
    p_av_sync = float(np.clip(abs(av_sync_ms) / av_fail_ms, 0.0, 1.0))

    # ── Weighted sum ───────────────────────────────────────────────────────────
    w_d = float(W["deepfake_score"])
    w_c = float(W["challenge_match"])
    w_b = float(W["blink_rate"])
    w_a = float(W["av_sync"])

    c_deepfake   = w_d * p_deepfake
    c_challenge  = w_c * p_challenge
    c_blink      = w_b * p_blink
    c_av_sync    = w_a * p_av_sync

    anomaly_score = float(np.clip(c_deepfake + c_challenge + c_blink + c_av_sync, 0.0, 1.0))

    # ── Decision ───────────────────────────────────────────────────────────────
    if anomaly_score >= float(T["anomaly_fail"]):
        decision = "fail"
    elif anomaly_score >= float(T["anomaly_borderline"]):
        decision = "borderline"
    else:
        decision = "pass"

    breakdown = AnomalyBreakdown(
        deepfake_contribution=round(c_deepfake, 4),
        challenge_contribution=round(c_challenge, 4),
        blink_contribution=round(c_blink, 4),
        av_sync_contribution=round(c_av_sync, 4),
    )

    log.info(
        "liveness.anomaly_score",
        score=round(anomaly_score, 4),
        decision=decision,
        deepfake=round(p_deepfake, 4),
        challenge_passed=challenge_match,
        blink_bpm=round(blink_rate_bpm, 2),
        av_sync_ms=round(av_sync_ms, 2),
    )
    return round(anomaly_score, 4), decision, breakdown


# ─── Top-level pipeline ───────────────────────────────────────────────────────

def analyze_liveness(video_bytes: bytes) -> LivenessAnalysis:
    """
    Full liveness analysis pipeline.
    This is the only function the API router needs to call.

    Args:
        video_bytes: raw bytes of the uploaded video clip

    Returns:
        LivenessAnalysis TypedDict with all signals and final decision
    """
    cfg = _load_config()

    # 1. Extract frames
    frames = extract_frames(video_bytes)
    if not frames:
        log.error("liveness.no_frames_extracted")
        # Return a high-anomaly result — empty clip is suspicious
        return _error_result(cfg, reason="no_frames")

    # 2. Deepfake score
    deepfake_score = score_deepfake(frames)

    # 3. Motion / challenge
    duration = estimate_duration_seconds(video_bytes)
    motion = detect_motion(frames)
    challenge_match = motion["motion_detected"]

    # 4. Blinks
    blinks = detect_blinks(frames, duration_seconds=duration)

    # 5. AV sync
    av_sync_ms = compute_av_sync(video_bytes)

    # 6. Anomaly score
    anomaly_score, decision, breakdown = compute_anomaly_score(
        deepfake_score=deepfake_score,
        challenge_match=challenge_match,
        blink_rate_bpm=blinks["blink_rate_bpm"],
        av_sync_ms=av_sync_ms,
        blink_available=blinks["detection_available"],
    )

    return LivenessAnalysis(
        deepfake_score=round(deepfake_score, 4),
        challenge_match=challenge_match,
        motion_frames=motion["motion_frames"],
        mean_motion_magnitude=motion["mean_magnitude"],
        blink_rate_bpm=blinks["blink_rate_bpm"],
        blink_count=blinks["blink_count"],
        av_sync_ms=round(av_sync_ms, 2),
        anomaly_score=anomaly_score,
        decision=decision,
        breakdown=breakdown,
        frame_count=len(frames),
        config_version=cfg.get("config_version", "unknown"),
    )


def _error_result(cfg: dict, reason: str = "unknown") -> LivenessAnalysis:
    """Return a maximally suspicious result when pipeline fails."""
    log.error("liveness.pipeline_error", reason=reason)
    breakdown = AnomalyBreakdown(
        deepfake_contribution=0.5,
        challenge_contribution=0.25,
        blink_contribution=0.0,
        av_sync_contribution=0.0,
    )
    return LivenessAnalysis(
        deepfake_score=0.5,
        challenge_match=False,
        motion_frames=0,
        mean_motion_magnitude=0.0,
        blink_rate_bpm=0.0,
        blink_count=0,
        av_sync_ms=0.0,
        anomaly_score=0.75,
        decision="fail",
        breakdown=breakdown,
        frame_count=0,
        config_version=cfg.get("config_version", "unknown"),
    )

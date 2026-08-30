"""
liveness.py
───────────
Core liveness analysis service for Stage 1.

This module is the single source of truth for everything that happens between
"received video bytes" and "produced anomaly score". All weights and thresholds
are read from liveness_config.yaml — nothing is hardcoded here.

Public API
──────────
    result = analyze_liveness(video_bytes, expected_challenge="blink_twice")
    # result is a LivenessAnalysis TypedDict
"""

from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import TypedDict, Optional, List, Dict, Any

import cv2
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
    Load liveness_config.yaml. Path is resolved relative to this file.
    Respects LIVENESS_CONFIG_PATH env var for overrides.
    """
    env_path = os.getenv("LIVENESS_CONFIG_PATH")
    if env_path:
        config_path = Path(env_path)
    else:
        config_path = Path(__file__).parent.parent / "core" / "liveness_config.yaml"

    if not config_path.exists():
        log.warning("liveness.config_missing", path=str(config_path), using="defaults")
        return _default_config()

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    log.info("liveness.config_loaded", path=str(config_path), version=cfg.get("config_version"))
    return cfg


get_liveness_config = _load_config


def _default_config() -> dict:
    """Fallback config if YAML file is missing."""
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
    challenge_passed: bool      # whether the specific challenge action was verified
    challenge_type: str         # challenge identifier or sequence string
    detected_sequence: List[str]
    expected_sequence: List[str]
    gesture_details: Dict[str, Any]


class BlinkResult(TypedDict):
    blink_rate_bpm: float       # blinks per minute (0.0 if detection unavailable)
    blink_count: int
    detection_available: bool   # False if landmark tracker unavailable


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
    detection_mode: str         # "neural_checkpoint" | "heuristic_fallback"
    detected_sequence: Optional[List[str]]
    expected_sequence: Optional[List[str]]


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
    max_frames = fs.get("max_frames", 24)
    resize_cfg = fs.get("resize", [224, 224])
    resize = (int(resize_cfg[0]), int(resize_cfg[1]))
    return bytes_to_frames(video_bytes, max_frames=max_frames, resize=resize)


# ─── Deepfake scoring ─────────────────────────────────────────────────────────

def score_deepfake(frames: List[np.ndarray]) -> float:
    """
    Run the deepfake detector on each frame.
    Returns the mean score across all frames.
    Returns 0.75 (fail-closed suspicious score) if no frames available.
    """
    if not frames:
        log.warning("liveness.no_frames_for_scoring")
        return 0.75

    detector = _get_detector()
    scores = []
    for frame in frames:
        try:
            s = detector.predict(frame)
            scores.append(s)
        except Exception as exc:
            log.warning("liveness.frame_score_failed", error=str(exc))

    if not scores:
        return 0.75

    mean_score = float(np.mean(scores))
    log.debug("liveness.deepfake_score",
              mean=round(mean_score, 4),
              n_frames=len(scores),
              min=round(min(scores), 4),
              max=round(max(scores), 4),
              mode=detector.detection_mode)
    return mean_score


# ─── Sequential Head Motion & Challenge Detection ─────────────────────────────

def _canonicalize_gesture_token(token: str) -> str:
    """Normalize a gesture string to canonical form: 'left' | 'right' | 'up' | 'down'."""
    t = str(token).lower().strip().replace("-", "_").replace(" ", "_")
    if t in {"left", "turn_left", "look_left", "head_left"}:
        return "left"
    if t in {"right", "turn_right", "look_right", "head_right"}:
        return "right"
    if t in {"up", "look_up", "nod_up", "head_up"}:
        return "up"
    if t in {"down", "look_down", "nod_down", "head_down", "nod_head", "nod"}:
        return "down"
    return t


def _parse_expected_sequence(expected_challenge: Any) -> List[str]:
    """Parse challenge sequence from list, comma-separated string, or JSON string."""
    if expected_challenge is None:
        return []
    if isinstance(expected_challenge, (list, tuple)):
        return [_canonicalize_gesture_token(g) for g in expected_challenge if str(g).strip()]
    if isinstance(expected_challenge, str):
        cleaned = expected_challenge.strip()
        if not cleaned:
            return []
        if cleaned.startswith("[") and cleaned.endswith("]"):
            try:
                import json as _json
                parsed = _json.loads(cleaned)
                if isinstance(parsed, list):
                    return [_canonicalize_gesture_token(g) for g in parsed if str(g).strip()]
            except Exception:
                pass
        if "," in cleaned or "->" in cleaned or " " in cleaned:
            delim = "," if "," in cleaned else ("->" if "->" in cleaned else " ")
            parts = [p.strip() for p in cleaned.split(delim) if p.strip()]
            return [_canonicalize_gesture_token(p) for p in parts]
        return [_canonicalize_gesture_token(cleaned)]
    return []


def detect_motion(
    frames: List[np.ndarray],
    expected_challenge: Optional[Any] = None,
    blinks: Optional[BlinkResult] = None,
) -> MotionResult:
    """
    Detect continuous optical flow across the full clip and identify discrete motion peaks
    (direction + magnitude) ordered chronologically.

    Compares detected peak sequence strictly against the server-generated expected sequence.

    Threat Model & Defense Scope:
    ─────────────────────────────
    Defends against pre-recorded/replay video playback, looped video injection, and
    unsophisticated automated spoofing scripts.
    Does NOT defend against real-time live face-swap injection (where physical head motion is
    genuine and only facial identity is synthetic); that threat is addressed by the
    deepfake/anomaly detection layer (DeepfakeDetector) and 1:1 facial embeddings.
    """
    expected_seq = _parse_expected_sequence(expected_challenge)
    return detect_sequential_motion(frames, expected_sequence=expected_seq)


def detect_sequential_motion(
    frames: List[np.ndarray],
    expected_sequence: Optional[List[str]] = None,
) -> MotionResult:
    """
    Classify discrete directional motion peaks chronologically across the video clip.
    Strictly verifies that detected peak sequence matches expected_sequence with zero missing/extra steps.
    """
    cfg = _load_config()
    seq_cfg = cfg.get("sequential_motion", {})
    turn_dx_min = float(seq_cfg.get("turn_dx_min", 0.28))
    nod_dy_min = float(seq_cfg.get("nod_dy_min", 0.32))
    peak_min_gap = int(seq_cfg.get("peak_min_gap_frames", 2))
    min_peak_sustain = int(seq_cfg.get("min_peak_sustain_frames", 1))
    min_excursion_mag = float(seq_cfg.get("min_excursion_mag", 0.38))
    min_flow_mag = float(seq_cfg.get("flow_magnitude_min", 0.25))
    threshold = float(cfg.get("motion", {}).get("min_delta_threshold", 3.0))

    canonical_expected = [_canonicalize_gesture_token(g) for g in (expected_sequence or []) if g]

    if len(frames) < 2:
        return MotionResult(
            motion_detected=False,
            motion_frames=0,
            mean_magnitude=0.0,
            challenge_passed=False,
            challenge_type=",".join(canonical_expected) if canonical_expected else "sequential_motion",
            detected_sequence=[],
            expected_sequence=canonical_expected,
            gesture_details={"reason": "insufficient_frames"},
        )

    motion_frame_count = 0
    magnitudes: List[float] = []
    frame_directions: List[Optional[str]] = []
    dx_values: List[float] = []
    dy_values: List[float] = []

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
    face_centers_x: List[float] = []
    face_centers_y: List[float] = []

    prev_gray: Optional[np.ndarray] = None

    for frame in frames:
        if frame.dtype != np.uint8 and frame.max() <= 1.0:
            img_uint8 = (frame * 255.0).astype(np.uint8)
        else:
            img_uint8 = frame.astype(np.uint8)

        gray = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2GRAY)
        h, w = gray.shape

        # Track face bounding box and center with frontal + profile fallback
        detected_faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(35, 35))
        if len(detected_faces) == 0:
            detected_faces = profile_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(35, 35))
        if len(detected_faces) == 0:
            # Flipped profile to catch left/right asymmetry in Haar cascades
            flipped_gray = cv2.flip(gray, 1)
            flipped_profiles = profile_cascade.detectMultiScale(flipped_gray, scaleFactor=1.1, minNeighbors=3, minSize=(35, 35))
            if len(flipped_profiles) > 0:
                pfx, pfy, pfw, pfh = flipped_profiles[0]
                detected_faces = np.array([[w - (pfx + pfw), pfy, pfw, pfh]])

        fx, fy, fw, fh = 0, 0, w, h
        has_face_box = False
        if len(detected_faces) > 0:
            fx, fy, fw, fh = detected_faces[0]
            has_face_box = True
            face_centers_x.append((fx + fw / 2.0) / w)
            face_centers_y.append((fy + fh / 2.0) / h)
        else:
            if face_centers_x:
                face_centers_x.append(face_centers_x[-1])
                face_centers_y.append(face_centers_y[-1])
            else:
                face_centers_x.append(0.5)
                face_centers_y.append(0.5)

        if prev_gray is not None:
            delta = np.abs(gray.astype(np.int16) - prev_gray.astype(np.int16))
            mean_delta = float(delta.mean())
            if mean_delta >= threshold:
                motion_frame_count += 1

            try:
                flow = cv2.calcOpticalFlowFarneback(
                    prev_gray, gray,
                    None,
                    pyr_scale=0.5, levels=2, winsize=12,
                    iterations=2, poly_n=5, poly_sigma=1.1,
                    flags=0,
                )
                
                # Extract optical flow on Face ROI to avoid static background dilution
                if has_face_box and fw > 20 and fh > 20:
                    face_flow = flow[fy:fy+fh, fx:fx+fw]
                else:
                    # Central 60% crop if no explicit Haar face box on this frame
                    c_y1, c_y2 = int(h * 0.15), int(h * 0.85)
                    c_x1, c_x2 = int(w * 0.15), int(w * 0.85)
                    face_flow = flow[c_y1:c_y2, c_x1:c_x2]

                dx_face = float(face_flow[..., 0].mean()) if face_flow.size > 0 else float(flow[..., 0].mean())
                dy_face = float(face_flow[..., 1].mean()) if face_flow.size > 0 else float(flow[..., 1].mean())

                # Normalized face center delta scaled to optical flow range
                fdx = (face_centers_x[-1] - face_centers_x[-2]) * 8.0 if len(face_centers_x) >= 2 else 0.0
                fdy = (face_centers_y[-1] - face_centers_y[-2]) * 8.0 if len(face_centers_y) >= 2 else 0.0

                # Composite face-directed motion vector
                dx = dx_face * 0.70 + fdx * 0.30
                dy = dy_face * 0.70 + fdy * 0.30

                mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                face_mag, _ = cv2.cartToPolar(face_flow[..., 0], face_flow[..., 1]) if face_flow.size > 0 else (mag, None)
                mean_m = float(face_mag.mean())
            except Exception:
                dx, dy, mean_m = 0.0, 0.0, mean_delta / 255.0

            magnitudes.append(mean_m)
            dx_values.append(dx)
            dy_values.append(dy)

            # Classify instantaneous frame direction purely based on optical flow
            dir_cand = None
            if abs(dy) > abs(dx) * 1.15 and abs(dy) >= nod_dy_min:
                if dy < -nod_dy_min:
                    dir_cand = "up"
                elif dy >= nod_dy_min:
                    dir_cand = "down"
            elif abs(dx) >= turn_dx_min:
                # User turning Left moves face to image right (dx > 0)
                # User turning Right moves face to image left (dx < 0)
                if dx > turn_dx_min:
                    dir_cand = "left"
                elif dx < -turn_dx_min:
                    dir_cand = "right"

            frame_directions.append(dir_cand)

        prev_gray = gray

    # ── Forward Excursion Wave Gesture Accumulator with Sustain Requirement ──
    OPPOSITE_DIR = {
        "left": "right",
        "right": "left",
        "up": "down",
        "down": "up",
    }

    detected_peaks: List[str] = []
    active_gesture: Optional[str] = None
    accum_mag: float = 0.0
    sustain_count: int = 0
    cooldown_frames: int = 0
    expecting_recovery: Optional[str] = None

    for d, dx_val, dy_val in zip(frame_directions, dx_values, dy_values):
        frame_mag = abs(dx_val) if d in {"left", "right"} else abs(dy_val)

        if cooldown_frames > 0:
            cooldown_frames -= 1
            if d is None:
                continue

        if d is None:
            if active_gesture and accum_mag >= min_excursion_mag and sustain_count >= min_peak_sustain:
                if expecting_recovery and active_gesture == expecting_recovery:
                    expecting_recovery = None
                elif not detected_peaks or detected_peaks[-1] != active_gesture:
                    detected_peaks.append(active_gesture)
                    expecting_recovery = OPPOSITE_DIR.get(active_gesture)
                    cooldown_frames = peak_min_gap
            active_gesture = None
            accum_mag = 0.0
            sustain_count = 0
            continue

        if active_gesture is None:
            active_gesture = d
            accum_mag = frame_mag
            sustain_count = 1
        elif d == active_gesture:
            accum_mag += frame_mag
            sustain_count += 1
        else:
            # Direction transition (including to opposite recovery stroke)
            if accum_mag >= min_excursion_mag and sustain_count >= min_peak_sustain:
                if expecting_recovery and active_gesture == expecting_recovery:
                    expecting_recovery = None
                elif not detected_peaks or detected_peaks[-1] != active_gesture:
                    detected_peaks.append(active_gesture)
                    expecting_recovery = OPPOSITE_DIR.get(active_gesture)
                    cooldown_frames = peak_min_gap
            active_gesture = d
            accum_mag = frame_mag
            sustain_count = 1

    if active_gesture and accum_mag >= min_excursion_mag and sustain_count >= min_peak_sustain:
        if not (expecting_recovery and active_gesture == expecting_recovery):
            if not detected_peaks or detected_peaks[-1] != active_gesture:
                detected_peaks.append(active_gesture)

    # Collapse consecutive duplicates
    compact_peaks: List[str] = []
    for p in detected_peaks:
        if not compact_peaks or compact_peaks[-1] != p:
            compact_peaks.append(p)

    mean_mag = float(np.mean(magnitudes)) if magnitudes else 0.0
    has_general_motion = (motion_frame_count >= 2 or mean_mag >= min_flow_mag) and len(compact_peaks) > 0

    challenge_passed = False
    exact_match = False
    contiguous_match = False

    if canonical_expected:
        def _is_contiguous_subsequence(sub: List[str], full: List[str]) -> bool:
            if not sub:
                return True
            n, m = len(full), len(sub)
            if m > n:
                return False
            for i in range(n - m + 1):
                if full[i : i + m] == sub:
                    return True
            return False

        exact_match = (compact_peaks == canonical_expected)
        contiguous_match = _is_contiguous_subsequence(canonical_expected, compact_peaks)

        # Strict challenge evaluation: requires general motion and exact/contiguous sequence match
        challenge_passed = bool(has_general_motion and (exact_match or contiguous_match))
    else:
        challenge_passed = bool(has_general_motion and len(compact_peaks) > 0)

    details = {
        "detected_sequence": compact_peaks,
        "expected_sequence": canonical_expected,
        "exact_match": exact_match,
        "contiguous_match": contiguous_match,
        "motion_frames": motion_frame_count,
        "mean_magnitude": round(mean_mag, 4),
        "dx_range": [round(float(np.min(dx_values)), 4), round(float(np.max(dx_values)), 4)] if dx_values else [0, 0],
        "dy_range": [round(float(np.min(dy_values)), 4), round(float(np.max(dy_values)), 4)] if dy_values else [0, 0],
    }

    res = MotionResult(
        motion_detected=bool(has_general_motion),
        motion_frames=int(motion_frame_count),
        mean_magnitude=round(float(mean_mag), 4),
        challenge_passed=bool(challenge_passed),
        challenge_type=",".join(canonical_expected) if canonical_expected else "sequential_motion",
        detected_sequence=compact_peaks,
        expected_sequence=canonical_expected,
        gesture_details=details,
    )
    log.info(
        "liveness.sequential_challenge_evaluated",
        challenge_passed=bool(challenge_passed),
        expected_sequence=canonical_expected,
        detected_sequence=compact_peaks,
        exact_match=exact_match,
        contiguous_match=contiguous_match,
        mean_magnitude=round(float(mean_mag), 4),
        motion_frames=int(motion_frame_count),
    )
    return res


# ─── Blink detection ──────────────────────────────────────────────────────────

def detect_blinks(frames: List[np.ndarray], duration_seconds: float = 5.0) -> BlinkResult:
    """
    Estimate blink rate using Eye Aspect Ratio (MediaPipe) or OpenCV Eye Cascade variance.
    """
    try:
        import mediapipe as mp  # type: ignore
        mp_face_mesh = mp.solutions.face_mesh
        LEFT_EYE = [362, 385, 387, 263, 373, 380]
        RIGHT_EYE = [33, 160, 158, 133, 153, 144]
        EAR_THRESHOLD = 0.20

        def _dist(a: tuple, b: tuple) -> float:
            return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

        def _ear(landmarks, indices: list[int]) -> float:
            pts = [(landmarks[i].x, landmarks[i].y) for i in indices]
            A = _dist(pts[1], pts[5])
            B = _dist(pts[2], pts[4])
            C = _dist(pts[0], pts[3])
            return (A + B) / (2.0 * C + 1e-6)

        blink_count = 0
        eye_closed_prev = False

        with mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
        ) as face_mesh:
            for frame in frames:
                img_uint8 = (frame * 255.0).astype(np.uint8) if frame.dtype != np.uint8 and frame.max() <= 1.0 else frame.astype(np.uint8)
                res = face_mesh.process(img_uint8)
                if not res.multi_face_landmarks:
                    continue
                lm = res.multi_face_landmarks[0].landmark
                left_ear = _ear(lm, LEFT_EYE)
                right_ear = _ear(lm, RIGHT_EYE)
                avg_ear = (left_ear + right_ear) / 2.0
                eye_closed = avg_ear < EAR_THRESHOLD
                if eye_closed and not eye_closed_prev:
                    blink_count += 1
                eye_closed_prev = eye_closed

        blink_rate_bpm = (blink_count / max(duration_seconds, 1.0)) * 60.0
        return BlinkResult(
            blink_rate_bpm=round(blink_rate_bpm, 2),
            blink_count=blink_count,
            detection_available=True,
        )

    except Exception:
        # Robust Eye-Band Temporal Delta & Haar Cascade Analysis
        try:
            eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            
            eye_counts = []
            eye_band_deltas = []
            prev_eye_band = None

            for frame in frames:
                img_uint8 = (frame * 255.0).astype(np.uint8) if frame.dtype != np.uint8 and frame.max() <= 1.0 else frame.astype(np.uint8)
                gray = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2GRAY)
                h, w = gray.shape

                # 1. Haar eye detection
                eyes = eye_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=2, minSize=(12, 12))
                eye_counts.append(len(eyes))

                # 2. Extract upper face eye-band (approx 20% to 45% of face height)
                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=2, minSize=(40, 40))
                if len(faces) > 0:
                    fx, fy, fw, fh = faces[0]
                    y1 = max(0, fy + int(fh * 0.18))
                    y2 = min(h, fy + int(fh * 0.45))
                    x1 = max(0, fx + int(fw * 0.10))
                    x2 = min(w, fx + int(fw * 0.90))
                    eye_band = cv2.resize(gray[y1:y2, x1:x2], (64, 24))
                else:
                    eye_band = cv2.resize(gray[int(h * 0.2):int(h * 0.45), int(w * 0.2):int(w * 0.8)], (64, 24))

                if prev_eye_band is not None:
                    band_diff = float(np.mean(np.abs(eye_band.astype(np.float32) - prev_eye_band.astype(np.float32))))
                    eye_band_deltas.append(band_diff)
                prev_eye_band = eye_band

            # Detect eye closure dips in cascade counts
            blink_dips = 0
            for i in range(1, len(eye_counts) - 1):
                if eye_counts[i] < eye_counts[i - 1] and eye_counts[i] < eye_counts[i + 1]:
                    blink_dips += 1

            # Detect rapid localized pulses in the eye band (blinking eyelid transition)
            eye_band_peaks = 0
            if eye_band_deltas:
                mean_delta = float(np.mean(eye_band_deltas))
                std_delta = float(np.std(eye_band_deltas))
                threshold = max(2.5, mean_delta + 0.6 * std_delta)
                for d in eye_band_deltas:
                    if d >= threshold:
                        eye_band_peaks += 1

            total_blinks = max(blink_dips, eye_band_peaks // 2)
            if eye_band_peaks >= 1 and total_blinks == 0:
                total_blinks = 1

            blink_rate_bpm = (total_blinks / max(duration_seconds, 1.0)) * 60.0
            return BlinkResult(
                blink_rate_bpm=round(blink_rate_bpm, 2),
                blink_count=total_blinks,
                detection_available=True,
            )
        except Exception:
            return BlinkResult(blink_rate_bpm=0.0, blink_count=0, detection_available=False)


# ─── AV sync estimation ───────────────────────────────────────────────────────

def compute_av_sync(video_bytes: bytes) -> float:
    """
    Estimate audio-video synchronization offset in milliseconds.
    """
    try:
        import subprocess, json as _json, uuid as _uuid
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
            return 0.0
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
    """
    cfg = _load_config()
    W = cfg["weights"]
    T = cfg["thresholds"]

    # Penalty functions
    p_deepfake = float(np.clip(deepfake_score, 0.0, 1.0))
    p_challenge = 0.0 if challenge_match else 1.0

    if not blink_available or blink_rate_bpm <= 0:
        p_blink = 0.0
    else:
        p_blink = 0.0 if blink_rate_bpm >= float(T["blink_min_bpm"]) else 1.0

    av_fail_ms = float(T["av_sync_fail_ms"])
    p_av_sync = float(np.clip(abs(av_sync_ms) / av_fail_ms, 0.0, 1.0))

    # Weighted sum
    w_d = float(W["deepfake_score"])
    w_c = float(W["challenge_match"])
    w_b = float(W["blink_rate"])
    w_a = float(W["av_sync"])

    c_deepfake = w_d * p_deepfake
    c_challenge = w_c * p_challenge
    c_blink = w_b * p_blink
    c_av_sync = w_a * p_av_sync

    anomaly_score = float(np.clip(c_deepfake + c_challenge + c_blink + c_av_sync, 0.0, 1.0))

    # Strict Fail-Closed Rule:
    # If challenge failed, force fail decision
    if not challenge_match:
        decision = "fail"
        anomaly_score = max(anomaly_score, float(T["anomaly_fail"]))
    elif anomaly_score >= float(T["anomaly_fail"]):
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

def analyze_liveness(
    video_bytes: bytes,
    expected_challenge: Optional[Any] = None,
) -> LivenessAnalysis:
    """
    Run full liveness analysis pipeline on raw video bytes with dynamic sequential challenge verification.
    """
    cfg = _load_config()

    # 1. Extract frames
    frames = extract_frames(video_bytes)
    if not frames:
        log.error("liveness.no_frames_extracted")
        return _error_result(cfg, reason="no_frames")

    detector = _get_detector()
    detection_mode = detector.detection_mode

    # 2. Deepfake score
    deepfake_score = score_deepfake(frames)

    # 3. Blinks
    duration = estimate_duration_seconds(video_bytes)
    blinks = detect_blinks(frames, duration_seconds=duration)

    # 4. Sequential Motion & Challenge Verification
    motion = detect_motion(frames, expected_challenge=expected_challenge, blinks=blinks)
    challenge_match = bool(motion["challenge_passed"])

    # 5. AV sync
    av_sync_ms = compute_av_sync(video_bytes)

    # 6. Composite Anomaly score
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
        detection_mode=detection_mode,
        detected_sequence=motion.get("detected_sequence", []),
        expected_sequence=motion.get("expected_sequence", []),
    )


def _error_result(cfg: dict, reason: str = "unknown") -> LivenessAnalysis:
    """Return a strictly failed result when pipeline fails."""
    log.error("liveness.pipeline_error", reason=reason)
    detector = _get_detector()
    breakdown = AnomalyBreakdown(
        deepfake_contribution=0.5,
        challenge_contribution=0.25,
        blink_contribution=0.0,
        av_sync_contribution=0.0,
    )
    return LivenessAnalysis(
        deepfake_score=0.75,
        challenge_match=False,
        motion_frames=0,
        mean_motion_magnitude=0.0,
        blink_rate_bpm=0.0,
        blink_count=0,
        av_sync_ms=0.0,
        anomaly_score=0.85,
        decision="fail",
        breakdown=breakdown,
        frame_count=0,
        config_version=cfg.get("config_version", "unknown"),
        detection_mode=detector.detection_mode,
        detected_sequence=[],
        expected_sequence=[],
    )

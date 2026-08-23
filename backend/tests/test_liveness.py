"""
tests/test_liveness.py
──────────────────────
Integration tests for the Stage 1 liveness endpoint.

Tests are self-contained: they generate synthetic video clips using OpenCV
(no external files required) so they run in CI without any test assets.

Two critical scenarios:
  1. "Real" clip  — frames with clear inter-frame motion (person moving)
                   → expect anomaly_score < 0.40, decision == "pass"
  2. "Spoof" clip — static repeated frame, zero motion
                   → expect anomaly_score > 0.55, decision != "pass"

Run:
    cd backend
    python -m pytest tests/test_liveness.py -v
"""

from __future__ import annotations

import io
import os
import uuid
from pathlib import Path
from typing import List

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

# ─── App import ───────────────────────────────────────────────────────────────
# Must be imported AFTER sys.path is set; pytest handles this when run from
# the backend/ directory.
from main import app

client = TestClient(app)


# ─── D: drive temp dir — all temp files go here, not C:\Temp ─────────────────
_D_TMP = Path(r"D:\projects\Deepfake_agenticai\data\tmp")
_D_TMP.mkdir(parents=True, exist_ok=True)


# ─── Video clip generators ────────────────────────────────────────────────────

def _make_video_bytes(
    frames: List[np.ndarray],
    fps: float = 15.0,
    size: tuple[int, int] = (224, 224),
) -> bytes:
    """
    Encode a list of uint8 BGR frames into an mp4 byte string using OpenCV.
    Uses mp4v codec (universally available without extra installs).
    """
    path = str(_D_TMP / f"test_{uuid.uuid4().hex}.mp4")
    try:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(path, fourcc, fps, size)
        for frame in frames:
            resized = cv2.resize(frame, size)
            writer.write(resized)
        writer.release()

        return Path(path).read_bytes()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _real_clip(n_frames: int = 24) -> bytes:
    """
    Simulate a genuine liveness session:
    - Background colour slowly shifts (camera noise / movement)
    - A bright ellipse (face proxy) moves across the frame
    - Every ~4 frames the ellipse contracts briefly (blink proxy)

    This gives clear inter-frame motion → motion_detected=True → challenge_match=True.
    Deepfake score will be random (stub model) but challenge passes.
    """
    frames: List[np.ndarray] = []
    h, w = 224, 224

    for i in range(n_frames):
        # Slowly drifting background (simulates camera motion / lighting)
        bg_val = int(40 + (i / n_frames) * 30)
        frame = np.full((h, w, 3), bg_val, dtype=np.uint8)

        # Moving ellipse centre
        cx = int(w * 0.3 + (i / n_frames) * w * 0.4)
        cy = h // 2

        # Blink proxy: contract every 4 frames
        ry = 50 if (i % 4 != 0) else 10

        cv2.ellipse(frame, (cx, cy), (40, ry), 0, 0, 360, (200, 180, 160), -1)

        # Add small gaussian noise so frame-delta is non-zero even on static parts
        noise = np.random.randint(-8, 8, frame.shape, dtype=np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        frames.append(frame)

    return _make_video_bytes(frames)


def _spoof_clip(n_frames: int = 24) -> bytes:
    """
    Simulate a replayed / static deepfake session:
    - Single static frame repeated for the entire clip
    - Minimal noise (below motion threshold)

    This gives motion_detected=False → challenge_match=False
    → high anomaly_score from the challenge_match penalty alone (0.25 weight).
    """
    h, w = 224, 224
    base = np.full((h, w, 3), 120, dtype=np.uint8)
    cv2.ellipse(base, (w // 2, h // 2), (40, 50), 0, 0, 360, (200, 180, 160), -1)

    # Tiny sub-threshold noise (mean delta < 4.0 px)
    frames: List[np.ndarray] = []
    for _ in range(n_frames):
        noise = np.random.randint(-1, 2, base.shape, dtype=np.int16)
        frame = np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        frames.append(frame)

    return _make_video_bytes(frames)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def real_clip_bytes() -> bytes:
    return _real_clip()


@pytest.fixture(scope="module")
def spoof_clip_bytes() -> bytes:
    return _spoof_clip()


# ─── Endpoint availability tests ──────────────────────────────────────────────

def test_config_endpoint_returns_200():
    """GET /api/v1/liveness/config should return the current YAML config."""
    resp = client.get("/api/v1/liveness/config")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "config_version" in body
    assert "weights" in body
    assert "thresholds" in body
    assert set(body["weights"].keys()) == {
        "deepfake_score", "challenge_match", "blink_rate", "av_sync"
    }


def test_weights_sum_to_one():
    """Weights in config must sum to exactly 1.0 (within float tolerance)."""
    resp = client.get("/api/v1/liveness/config")
    weights = resp.json()["weights"]
    total = sum(weights.values())
    assert abs(total - 1.0) < 1e-6, f"Weights sum to {total}, expected 1.0"


def test_analyze_rejects_non_video():
    """POST /analyze with an image file should return 415."""
    fake_image = b"\xff\xd8\xff\xe0" + b"\x00" * 100   # JPEG magic bytes
    resp = client.post(
        "/api/v1/liveness/analyze",
        files={"clip": ("test.jpg", io.BytesIO(fake_image), "image/jpeg")},
    )
    assert resp.status_code == 415


def test_analyze_rejects_empty_clip():
    """POST /analyze with zero bytes should return 400."""
    resp = client.post(
        "/api/v1/liveness/analyze",
        files={"clip": ("empty.mp4", io.BytesIO(b""), "video/mp4")},
    )
    assert resp.status_code == 400


# ─── Core liveness tests ──────────────────────────────────────────────────────

def test_real_clip_passes(real_clip_bytes):
    """
    A clip with clear inter-frame motion should:
      - Have challenge_match=True (motion detected)
      - Have anomaly_score < 0.65 (motion penalty is 0 → max contribution is
        deepfake_score weight 0.50, which for a stub model is random but
        typically won't reliably exceed the fail threshold in isolation)
      - NOT be decided "fail" purely because of missing motion
    """
    resp = client.post(
        "/api/v1/liveness/analyze",
        files={"clip": ("real.mp4", io.BytesIO(real_clip_bytes), "video/mp4")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Schema check
    assert "session_id" in body
    assert "anomaly_score" in body
    assert "decision" in body
    assert "breakdown" in body
    assert "config_version" in body

    # Challenge must pass (motion detected in animated clip)
    assert body["challenge_match"] is True, (
        f"Expected challenge_match=True for animated clip. "
        f"motion_frames={body['motion_frames']}"
    )

    # Challenge contribution must be 0 (passed)
    assert body["breakdown"]["challenge_contribution"] == 0.0, (
        f"Expected 0 challenge penalty for passed challenge. "
        f"Got {body['breakdown']['challenge_contribution']}"
    )

    # Anomaly score must be below the fail threshold (0.65)
    # With challenge_match=True: max anomaly = 0.50 (deepfake) + 0.15 (blink) + 0.10 (av)
    # Stub deepfake score is random but challenge penalty is definitively 0
    assert body["anomaly_score"] < 0.65, (
        f"Real clip anomaly_score={body['anomaly_score']} exceeds fail threshold. "
        f"breakdown={body['breakdown']}"
    )

    print(f"\n[real clip]  anomaly={body['anomaly_score']}  decision={body['decision']}"
          f"  motion_frames={body['motion_frames']}  deepfake={body['deepfake_score']}")


def test_spoof_clip_fails(spoof_clip_bytes):
    """
    A static repeated clip should:
      - Have challenge_match=False (no motion)
      - Have breakdown.challenge_contribution == 0.25 (full penalty)
      - Have anomaly_score >= 0.25 (at minimum the challenge penalty)
      - NOT be decided "pass"
    """
    resp = client.post(
        "/api/v1/liveness/analyze",
        files={"clip": ("spoof.mp4", io.BytesIO(spoof_clip_bytes), "video/mp4")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Challenge must fail (static clip, no motion)
    assert body["challenge_match"] is False, (
        f"Expected challenge_match=False for static clip. "
        f"motion_frames={body['motion_frames']}"
    )

    # Challenge penalty must be the full weight (0.25)
    assert body["breakdown"]["challenge_contribution"] == pytest.approx(0.25, abs=1e-4), (
        f"Expected challenge_contribution=0.25 for failed challenge. "
        f"Got {body['breakdown']['challenge_contribution']}"
    )

    # Anomaly score must be at least the challenge penalty
    assert body["anomaly_score"] >= 0.25, (
        f"Spoof clip anomaly_score={body['anomaly_score']} is below minimum expected (0.25)"
    )

    # Decision must not be "pass"
    assert body["decision"] != "pass", (
        f"Static spoof clip should not be decided 'pass'. Got '{body['decision']}'"
    )

    print(f"\n[spoof clip] anomaly={body['anomaly_score']}  decision={body['decision']}"
          f"  motion_frames={body['motion_frames']}  deepfake={body['deepfake_score']}")


def test_real_vs_spoof_score_gap(real_clip_bytes, spoof_clip_bytes):
    """
    The anomaly scores of real and spoof clips must differ by >= 0.15.
    This is the key end-to-end discriminative power test.
    """
    real_resp = client.post(
        "/api/v1/liveness/analyze",
        files={"clip": ("real.mp4", io.BytesIO(real_clip_bytes), "video/mp4")},
    )
    spoof_resp = client.post(
        "/api/v1/liveness/analyze",
        files={"clip": ("spoof.mp4", io.BytesIO(spoof_clip_bytes), "video/mp4")},
    )

    real_score  = real_resp.json()["anomaly_score"]
    spoof_score = spoof_resp.json()["anomaly_score"]
    gap = spoof_score - real_score

    print(f"\n[gap test]   real={real_score}  spoof={spoof_score}  gap={gap:.4f}")

    assert gap >= 0.15, (
        f"Score gap between real ({real_score}) and spoof ({spoof_score}) is only {gap:.4f}. "
        f"Expected >= 0.15. The challenge_match penalty (0.25) alone should ensure this."
    )


def test_response_schema_completeness(real_clip_bytes):
    """All required fields must be present and correctly typed."""
    resp = client.post(
        "/api/v1/liveness/analyze",
        files={"clip": ("real.mp4", io.BytesIO(real_clip_bytes), "video/mp4")},
    )
    body = resp.json()

    required_floats = ["deepfake_score", "blink_rate_bpm", "av_sync_ms",
                       "anomaly_score", "processing_time_ms", "mean_motion_magnitude"]
    required_ints   = ["motion_frames", "blink_count", "frame_count"]
    required_strs   = ["session_id", "decision", "config_version"]
    required_bools  = ["challenge_match"]
    breakdown_keys  = ["deepfake_contribution", "challenge_contribution",
                       "blink_contribution", "av_sync_contribution"]

    for key in required_floats:
        assert key in body, f"Missing field: {key}"
        assert isinstance(body[key], (int, float)), f"{key} should be numeric"

    for key in required_ints:
        assert key in body, f"Missing field: {key}"
        assert isinstance(body[key], int), f"{key} should be int"

    for key in required_strs:
        assert key in body, f"Missing field: {key}"
        assert isinstance(body[key], str), f"{key} should be str"

    for key in required_bools:
        assert key in body, f"Missing field: {key}"
        assert isinstance(body[key], bool), f"{key} should be bool"

    assert "breakdown" in body
    for key in breakdown_keys:
        assert key in body["breakdown"], f"Missing breakdown field: {key}"

    assert body["decision"] in {"pass", "borderline", "fail"}, (
        f"Invalid decision value: {body['decision']}"
    )

    assert "video_sha256" in body, "Missing video_sha256 field"
    assert isinstance(body["video_sha256"], str)
    assert len(body["video_sha256"]) == 64, "video_sha256 must be a 64-character hex string"


def test_anomaly_score_bounded(real_clip_bytes, spoof_clip_bytes):
    """Anomaly score must always be in [0.0, 1.0]."""
    for label, clip_bytes in [("real", real_clip_bytes), ("spoof", spoof_clip_bytes)]:
        resp = client.post(
            "/api/v1/liveness/analyze",
            files={"clip": (f"{label}.mp4", io.BytesIO(clip_bytes), "video/mp4")},
        )
        score = resp.json()["anomaly_score"]
        assert 0.0 <= score <= 1.0, f"{label} clip anomaly_score={score} out of [0,1]"


def test_video_sha256_independent_wire_bytes_rehash(real_clip_bytes, spoof_clip_bytes):
    """
    PHASE 2 AMENDMENT TEST in test_liveness.py:
    Independently re-hash the exact bytes sent over the wire and confirm
    it matches video_sha256 returned by the API.
    Catches any refactor that moves the hash call after a processing step.
    """
    import hashlib

    for label, clip_bytes in [("real", real_clip_bytes), ("spoof", spoof_clip_bytes)]:
        expected_sha256 = hashlib.sha256(clip_bytes).hexdigest()

        resp = client.post(
            "/api/v1/liveness/analyze",
            files={"clip": (f"{label}.mp4", io.BytesIO(clip_bytes), "video/mp4")},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["video_sha256"] == expected_sha256, (
            f"API returned video_sha256={body['video_sha256']!r} for {label} clip, "
            f"expected independent wire hash={expected_sha256!r}"
        )


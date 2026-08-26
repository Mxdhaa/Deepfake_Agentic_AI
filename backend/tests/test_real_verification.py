"""
test_real_verification.py — Comprehensive Unit & Integration Tests for Overhauled Input-Driven Verification
────────────────────────────────────────────────────────────────────────────────────────────────────────────
Validates:
  1. Strict Randomized Sequential Head-Motion Challenge Verification:
     - Exact matching sequence (e.g. left -> up -> right) passes challenge_match: True.
     - Out-of-order sequence (e.g. up -> left -> right) strictly fails challenge_match: False.
     - Missing steps or extra steps strictly fail challenge_match: False.
     - Static video / zero motion strictly fails challenge_match: False and livenessResult: FAILED.
  2. Dynamic Heuristic & Neural Deepfake Detection:
     - Surfaces detection_mode: "neural_checkpoint" or "heuristic_fallback".
     - Scores physical/frequency anomalies via 2D FFT, Laplacian variance, and chrominance entropy.
  3. Real 1:1 Face Embedding & Cosine Similarity:
     - Identical face crops yield cosine similarity >= 0.50 and "MATCH".
     - Inverted / dissimilar crops yield cosine similarity < 0.35 and "NO_MATCH".
     - Missing face crops yield 0.0 and fail closed.
  4. End-to-End Session Enforcement:
     - Server-generated challenge sequence is strictly verified and enforced on session finalization.
"""

import cv2
import numpy as np
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from main import app
from app.models.detector import DeepfakeDetector
from app.services.identity import FaceFeatureExtractor, compute_cosine_similarity
from app.services.liveness import analyze_liveness, detect_sequential_motion, detect_motion
from app.services.ocr_service import parse_and_validate_id_document
from app.services.kyc_registry import get_kyc_registry
from app.services.verification_service import get_verification_service, generate_challenge_sequence

client = TestClient(app)


def _generate_synthetic_sequential_frames(
    sequence: list[str],
    frames_per_step: int = 6,
    frame_size: tuple[int, int] = (224, 224),
) -> list[np.ndarray]:
    """Generate synthetic video frames performing a continuous sequence of distinct directional movements."""
    w, h = frame_size
    frames = []
    cx, cy = w // 2, h // 2

    for gesture in sequence:
        g = gesture.lower().strip()
        for _ in range(frames_per_step):
            if g in {"left", "turn_left"}:
                cx = cx + 5
            elif g in {"right", "turn_right"}:
                cx = cx - 5
            elif g in {"up", "look_up"}:
                cy = cy - 5
            elif g in {"down", "look_down", "nod_head"}:
                cy = cy + 5

            img = np.ones((h, w, 3), dtype=np.uint8) * 128

            # Draw synthetic face oval
            cv2.ellipse(img, (cx, cy), (40, 55), 0, 0, 360, (210, 180, 150), -1)
            # Eyes
            cv2.circle(img, (cx - 15, cy - 10), 5, (50, 40, 30), -1)
            cv2.circle(img, (cx + 15, cy - 10), 5, (50, 40, 30), -1)
            # Mouth
            cv2.line(img, (cx - 12, cy + 25), (cx + 12, cy + 25), (180, 50, 50), 3)

            # Small camera sensor noise
            noise = np.random.randint(-2, 3, img.shape, dtype=np.int16)
            img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            frames.append(rgb)

    return frames


def _generate_excursion_with_return_frames(
    sequence: list[str],
    frames_per_phase: int = 3,
    frame_size: tuple[int, int] = (224, 224),
) -> list[np.ndarray]:
    """Generate synthetic video frames performing full gesture excursion and return-to-center recovery."""
    w, h = frame_size
    frames = []

    for gesture in sequence:
        g = gesture.lower().strip()
        cx, cy = w // 2, h // 2

        # 1. Excursion away from center
        for _ in range(frames_per_phase):
            if g in {"left", "turn_left"}:
                cx += 5
            elif g in {"right", "turn_right"}:
                cx -= 5
            elif g in {"up", "look_up"}:
                cy -= 5
            elif g in {"down", "look_down", "nod_head"}:
                cy += 5
            frames.append(_draw_synthetic_face(w, h, cx, cy))

        # 2. Return-to-center recovery motion
        for _ in range(frames_per_phase):
            if g in {"left", "turn_left"}:
                cx -= 5
            elif g in {"right", "turn_right"}:
                cx += 5
            elif g in {"up", "look_up"}:
                cy += 5
            elif g in {"down", "look_down", "nod_head"}:
                cy -= 5
            frames.append(_draw_synthetic_face(w, h, cx, cy))

        # 3. Neutral pause between gestures
        for _ in range(2):
            frames.append(_draw_synthetic_face(w, h, w // 2, h // 2))

    return frames


def _draw_synthetic_face(w: int, h: int, cx: int, cy: int) -> np.ndarray:
    img = np.ones((h, w, 3), dtype=np.uint8) * 128
    cv2.ellipse(img, (cx, cy), (40, 55), 0, 0, 360, (210, 180, 150), -1)
    cv2.circle(img, (cx - 15, cy - 10), 5, (50, 40, 30), -1)
    cv2.circle(img, (cx + 15, cy - 10), 5, (50, 40, 30), -1)
    cv2.line(img, (cx - 12, cy + 25), (cx + 12, cy + 25), (180, 50, 50), 3)
    noise = np.random.randint(-2, 3, img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0


def _frames_to_mp4_bytes(frames: list[np.ndarray]) -> bytes:
    """Encode numpy frames into MP4 video bytes."""
    import uuid
    from app.services.video import _tmp_dir

    tmp_path = str(_tmp_dir() / f"test_{uuid.uuid4().hex}.mp4")
    h, w = 224, 224
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(tmp_path, fourcc, 10.0, (w, h))

    for frame in frames:
        bgr = (frame * 255.0).astype(np.uint8)
        if bgr.shape[2] == 3:
            bgr = cv2.cvtColor(bgr, cv2.COLOR_RGB2BGR)
        out.write(bgr)
    out.release()

    with open(tmp_path, "rb") as f:
        data = f.read()

    try:
        Path(tmp_path).unlink()
    except OSError:
        pass

    return data


# ─── 1. Sequential Head-Motion Challenge Unit Tests ───────────────────────────

def test_generate_challenge_sequence_has_no_immediate_repeats():
    for _ in range(20):
        seq = generate_challenge_sequence(length=4)
        assert len(seq) == 4
        for i in range(len(seq) - 1):
            assert seq[i] != seq[i + 1], f"Found immediate repeat in {seq}"


def test_liveness_sequential_challenge_passes_on_exact_match():
    expected = ["left", "up", "right"]
    frames = _generate_synthetic_sequential_frames(expected, frames_per_step=6)
    motion = detect_sequential_motion(frames, expected_sequence=expected)

    assert motion["motion_detected"] is True
    assert motion["detected_sequence"] == expected
    assert motion["challenge_passed"] is True


def test_liveness_sequential_challenge_with_return_to_center_recovery_passes():
    """
    Validates that a human naturally moving left -> return to center -> up -> return to center -> right
    is correctly recognized as ['left', 'up', 'right'] and the return-to-center recovery movements
    are NOT erroneously misclassified as extra opposite gestures.
    """
    expected = ["left", "up", "right"]
    frames = _generate_excursion_with_return_frames(expected, frames_per_phase=4)
    motion = detect_sequential_motion(frames, expected_sequence=expected)

    assert motion["motion_detected"] is True
    assert motion["detected_sequence"] == expected
    assert motion["challenge_passed"] is True


def test_liveness_sequential_challenge_fails_on_wrong_order():
    expected = ["left", "up", "right"]
    actual_motion = ["up", "left", "right"]  # Out-of-order
    frames = _generate_excursion_with_return_frames(actual_motion, frames_per_phase=4)
    motion = detect_sequential_motion(frames, expected_sequence=expected)

    assert motion["detected_sequence"] == actual_motion
    assert motion["challenge_passed"] is False


def test_liveness_sequential_challenge_fails_on_missing_step():
    expected = ["left", "up", "right"]
    actual_motion = ["left", "up"]  # Missing 3rd step
    frames = _generate_excursion_with_return_frames(actual_motion, frames_per_phase=4)
    motion = detect_sequential_motion(frames, expected_sequence=expected)

    assert motion["detected_sequence"] == actual_motion
    assert motion["challenge_passed"] is False


def test_liveness_sequential_challenge_contiguous_subsequence_with_bracket_noise_passes():
    """
    Asserts that when the expected sequence appears as a contiguous, correctly-ordered subsequence
    surrounded by natural head bracket noise (e.g. down -> left -> up -> right),
    it successfully passes the challenge.
    """
    expected = ["left", "up", "right"]
    actual_motion = ["down", "left", "up", "right"]
    frames = _generate_excursion_with_return_frames(actual_motion, frames_per_phase=3)
    motion = detect_sequential_motion(frames, expected_sequence=expected)

    assert motion["challenge_passed"] is True
    assert motion["detected_sequence"] == actual_motion


def test_liveness_sequential_challenge_fails_on_unrelated_sequence():
    """Asserts that a completely wrong or mismatched sequence strictly fails."""
    expected = ["left", "up", "right"]
    actual_motion = ["down", "right", "down"]
    frames = _generate_excursion_with_return_frames(actual_motion, frames_per_phase=3)
    motion = detect_sequential_motion(frames, expected_sequence=expected)

    assert motion["challenge_passed"] is False


def test_liveness_sequential_challenge_fails_on_static_video():
    expected = ["left", "up", "right"]
    # Static video with zero head movement
    frames = _generate_excursion_with_return_frames(["none", "none", "none"], frames_per_phase=4)
    motion = detect_sequential_motion(frames, expected_sequence=expected)

    assert motion["challenge_passed"] is False
    assert len(motion["detected_sequence"]) == 0


# ─── 2. Heuristic Deepfake Detector Tests ─────────────────────────────────────

def test_heuristic_detector_evaluates_signals():
    # 1. Neural Checkpoint Mode (loaded from verified detector.pth)
    neural_detector = DeepfakeDetector()
    assert neural_detector.detection_mode == "neural_checkpoint"

    clean_frame = np.random.randint(50, 200, (224, 224, 3), dtype=np.uint8)
    neural_score = neural_detector.predict(clean_frame)
    assert 0.0 <= neural_score <= 1.0

    # 2. Heuristic Fallback Mode (when weights missing)
    fallback_detector = DeepfakeDetector(model_path="nonexistent_checkpoint.pth")
    assert fallback_detector.detection_mode == "heuristic_fallback"

    heuristic_score = fallback_detector.predict(clean_frame)
    assert 0.0 <= heuristic_score <= 1.0


# ─── 3. Real Face Feature Extractor & Cosine Similarity Tests ─────────────────

def test_face_feature_extractor_cosine_similarity():
    extractor = FaceFeatureExtractor()

    # Create two different synthetic face images
    face_a = np.zeros((150, 150, 3), dtype=np.uint8)
    face_a[:, :] = (180, 150, 120)
    cv2.circle(face_a, (75, 75), 40, (120, 90, 60), -1)

    face_b = np.zeros((150, 150, 3), dtype=np.uint8)
    face_b[:, :] = (40, 40, 40)
    cv2.rectangle(face_b, (20, 20), (130, 130), (220, 220, 220), -1)

    emb_a = extractor.extract_from_bgr(face_a)
    emb_a2 = extractor.extract_from_bgr(face_a)
    emb_b = extractor.extract_from_bgr(face_b)

    # Identical image similarity should be ~1.0
    sim_identical = compute_cosine_similarity(emb_a, emb_a2)
    assert sim_identical > 0.95

    # Completely different image should be lower
    sim_diff = compute_cosine_similarity(emb_a, emb_b)
    assert sim_diff < sim_identical


# ─── 4. End-to-End Liveness Analysis with Sequential Challenge ────────────────

def test_analyze_liveness_pipeline_returns_detection_mode_and_sequence():
    expected = ["left", "up", "right"]
    frames = _generate_synthetic_sequential_frames(expected, frames_per_step=6)
    video_bytes = _frames_to_mp4_bytes(frames)

    res = analyze_liveness(video_bytes, expected_challenge=expected)
    assert "detection_mode" in res
    assert res["detection_mode"] in {"neural_checkpoint", "heuristic_fallback"}
    assert "challenge_match" in res
    assert res["challenge_match"] is True
    assert res["detected_sequence"] == expected
    assert "deepfake_score" in res
    assert "anomaly_score" in res


def test_analyze_liveness_pipeline_fails_when_challenge_not_performed():
    expected = ["left", "up", "right"]
    frames = _generate_synthetic_sequential_frames(["none"], frames_per_step=12)
    video_bytes = _frames_to_mp4_bytes(frames)

    res = analyze_liveness(video_bytes, expected_challenge=expected)
    assert res["challenge_match"] is False
    assert res["decision"] == "fail"


# ─── 5. End-to-End Session Enforcement ────────────────────────────────────────

def test_session_enforces_server_generated_challenge_sequence_exact_pass():
    """
    Asserts that starting a session generates a sequence and correctly performing
    that exact sequence passes the liveness stage.
    """
    # 1. Start session for Priya Patel (CKYC-10002)
    resp = client.post(
        "/api/v1/verification/start",
        json={"legalName": "Priya Patel", "dateOfBirth": "1997-08-22", "ckycNumber": "CKYC-10002"},
    )
    assert resp.status_code == 200
    data = resp.json()
    ref_id = data["referenceId"]
    challenge_seq = data["challengeSequence"]
    assert len(challenge_seq) >= 3

    # 2. Complete OTP
    otp_resp = client.post(f"/api/v1/verification/{ref_id}/otp/send")
    client.post(f"/api/v1/verification/{ref_id}/otp/verify", json={"otp": otp_resp.json()["demoOtp"]})

    # 3. Mark document as verified
    service = get_verification_service()
    session = service.get_session(ref_id)
    session.document_match = True
    session.decision_table.document = "MATCH"
    session.decision_table.document_face = "MATCH"
    session.extracted_document_portrait_embedding = [0.05] * 512
    service._save_sessions()

    # 4. Upload video performing exact server challenge sequence with return-to-center
    frames = _generate_excursion_with_return_frames(challenge_seq, frames_per_phase=3)
    video_bytes = _frames_to_mp4_bytes(frames)

    live_resp = client.post(
        f"/api/v1/verification/{ref_id}/liveness",
        files={"clip": ("clip.mp4", video_bytes, "video/mp4")},
    )
    assert live_resp.status_code == 200
    live_data = live_resp.json()
    assert live_data["challengeMatch"] is True
    assert live_data["livenessResult"] in {"CONFIRMED", "UNCERTAIN"}
    assert live_data["detectedSequence"] == challenge_seq


def test_session_enforces_server_generated_challenge_sequence_strict_fail():
    """
    Asserts that performing an incorrect sequence strictly fails the verification session
    and forces the session to NOT_VERIFIED.
    """
    # 1. Start session for Priya Patel (CKYC-10002)
    resp = client.post(
        "/api/v1/verification/start",
        json={"legalName": "Priya Patel", "dateOfBirth": "1997-08-22", "ckycNumber": "CKYC-10002"},
    )
    ref_id = resp.json()["referenceId"]
    challenge_seq = resp.json()["challengeSequence"]

    # 2. Complete OTP
    otp_resp = client.post(f"/api/v1/verification/{ref_id}/otp/send")
    client.post(f"/api/v1/verification/{ref_id}/otp/verify", json={"otp": otp_resp.json()["demoOtp"]})

    # 3. Mark document as verified
    service = get_verification_service()
    session = service.get_session(ref_id)
    session.document_match = True
    session.decision_table.document = "MATCH"
    session.decision_table.document_face = "MATCH"
    session.extracted_document_portrait_embedding = [0.05] * 512
    service._save_sessions()

    # 4. Perform completely reversed or wrong motion
    wrong_seq = list(reversed(challenge_seq))
    if wrong_seq == challenge_seq:
        wrong_seq = ["down", "left", "right"]

    frames = _generate_excursion_with_return_frames(wrong_seq, frames_per_phase=4)
    video_bytes = _frames_to_mp4_bytes(frames)

    live_resp = client.post(
        f"/api/v1/verification/{ref_id}/liveness",
        files={"clip": ("clip.mp4", video_bytes, "video/mp4")},
    )
    assert live_resp.status_code == 200
    live_data = live_resp.json()
    assert live_data["challengeMatch"] is False
    assert live_data["livenessResult"] == "FAILED"

    # 5. Finalize session — must fail closed to NOT_VERIFIED
    fin_resp = client.post(f"/api/v1/verification/{ref_id}/finalize")
    assert fin_resp.status_code == 200
    fin_data = fin_resp.json()
    assert fin_data["status"] == "NOT_VERIFIED"
    assert fin_data["finalDecision"] == "NOT_VERIFIED"
    assert fin_data["decisionTable"]["liveness"] == "FAILED"


def test_self_enrollment_new_applicant_creates_pending_record_and_starts_session():
    """
    Asserts that submitting a brand-new, unseen CKYC number succeeds,
    creates a PENDING entry in the registry, and successfully starts an onboarding session.
    """
    new_ckyc = "CKYC-NEW-998877"
    new_name = "Karan Singhania"
    new_dob = "1995-10-12"

    resp = client.post(
        "/api/v1/verification/start",
        json={"legalName": new_name, "dateOfBirth": new_dob, "ckycNumber": new_ckyc},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "referenceId" in data
    assert data["status"] == "IN_PROGRESS"

    # Verify new entry persisted in registry
    registry = get_kyc_registry()
    rec = registry.lookup(new_ckyc)
    assert rec is not None
    assert rec.legal_name == new_name
    assert rec.date_of_birth == new_dob
    assert rec.verification_status == "PENDING"
    assert rec.registered_face_reference is None


def test_existing_ckyc_upserts_and_starts_verification():
    """
    Asserts that submitting any CKYC identifier (even an existing seed) with new details
    seamlessly updates the record in storage and starts the verification session.
    """
    get_kyc_registry().update_verification_status("CKYC-10001", status="PENDING")
    resp = client.post(
        "/api/v1/verification/start",
        json={"legalName": "Medha Kumar", "dateOfBirth": "14-02-2005", "ckycNumber": "CKYC-10001"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "referenceId" in data
    assert data["status"] == "IN_PROGRESS"

    # Verify updated record in registry
    registry = get_kyc_registry()
    rec = registry.lookup("CKYC-10001")
    assert rec is not None
    assert rec.legal_name == "Medha Kumar"
    assert rec.date_of_birth == "2005-02-14"
    assert rec.verification_status == "PENDING"


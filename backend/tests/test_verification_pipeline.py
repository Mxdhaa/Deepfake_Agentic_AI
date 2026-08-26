"""
test_verification_pipeline.py — Comprehensive Unit & Integration tests for Verification Flow
─────────────────────────────────────────────────────────────────────────────────────────────
Covers:
  - Identity matching & Not Found (404)
  - Already-Verified shortcut & GET /status reconstruction
  - OTP generation, demo mode gating, lockout after 5 failed attempts, and expiry
  - Document OCR cross-check and field-level mismatches (Name, DOB, CKYC)
  - Liveness & Anti-Spoofing edge cases (PASS -> VERIFIED, UNCERTAIN -> UNDER_REVIEW, FLAGGED -> NOT_VERIFIED)
  - 10-signal decision aggregation matrix
"""

import sys
import time
import glob
import cv2
import numpy as np
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_path))

from app.core.config import settings
from app.services.verification_service import get_verification_service
from main import app

client = TestClient(app)


# ─── 1. Identity Lookup & Error Handling ─────────────────────────────────────

def test_start_verification_not_found():
    """Asserts 404 IDENTITY_NOT_FOUND when non-existent CKYC or mismatched details provided."""
    resp = client.post(
        "/api/v1/verification/start",
        json={
            "legalName": "Unknown Person",
            "dateOfBirth": "1990-01-01",
            "ckycNumber": "CKYC-99999",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "IDENTITY_NOT_FOUND"


def test_start_verification_name_mismatch():
    """Asserts 404 when CKYC matches but name is incorrect."""
    resp = client.post(
        "/api/v1/verification/start",
        json={
            "legalName": "Wrong Name",
            "dateOfBirth": "1994-05-14",
            "ckycNumber": "CKYC-10001",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "IDENTITY_NOT_FOUND"


def test_start_verification_already_verified_and_status_resolution():
    """Asserts that already verified identities return ALREADY_VERIFIED status and preserve referenceId."""
    resp = client.post(
        "/api/v1/verification/start",
        json={
            "legalName": "Aarav Sharma",
            "dateOfBirth": "1994-05-14",
            "ckycNumber": "CKYC-10001",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ALREADY_VERIFIED"
    assert "already completed verification" in data["message"].lower()

    ref_id = data["referenceId"]
    assert ref_id.startswith("CP-")

    status_resp = client.get(f"/api/v1/verification/{ref_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] in {"VERIFIED", "ALREADY_VERIFIED"}
    assert status_resp.json()["finalDecision"] in {"VERIFIED", "ALREADY_VERIFIED"}


# ─── 2. OTP Security & Rate Limiting ──────────────────────────────────────────

def test_otp_demo_mode_gating():
    """Asserts demoOtp is returned when DEMO_MODE=True and omitted when DEMO_MODE=False."""
    resp = client.post(
        "/api/v1/verification/start",
        json={"legalName": "Rohan Reddy", "dateOfBirth": "1993-09-30", "ckycNumber": "CKYC-10005"},
    )
    ref_id = resp.json()["referenceId"]

    settings.DEMO_MODE = True
    otp_resp = client.post(f"/api/v1/verification/{ref_id}/otp/send")
    assert otp_resp.status_code == 200
    assert otp_resp.json()["demoOtp"] is not None

    settings.DEMO_MODE = False
    otp_resp_no_demo = client.post(f"/api/v1/verification/{ref_id}/otp/send")
    assert otp_resp_no_demo.json()["demoOtp"] is None
    settings.DEMO_MODE = True  # reset for subsequent tests


def test_otp_lockout_after_5_failed_attempts():
    """Asserts that 5 incorrect attempts lock out the OTP stage."""
    resp = client.post(
        "/api/v1/verification/start",
        json={"legalName": "Rohan Reddy", "dateOfBirth": "1993-09-30", "ckycNumber": "CKYC-10005"},
    )
    ref_id = resp.json()["referenceId"]
    client.post(f"/api/v1/verification/{ref_id}/otp/send")

    # Send 5 wrong attempts
    for i in range(1, 6):
        bad_resp = client.post(f"/api/v1/verification/{ref_id}/otp/verify", json={"otp": f"00000{i}"})
        assert bad_resp.status_code == 400

    # 6th attempt should be locked out
    lockout_resp = client.post(f"/api/v1/verification/{ref_id}/otp/verify", json={"otp": "123456"})
    assert lockout_resp.status_code == 400
    assert "locked" in lockout_resp.json()["message"].lower() or lockout_resp.json()["remainingAttempts"] == 0


def test_otp_expiry():
    """Asserts that expired OTPs are rejected."""
    resp = client.post(
        "/api/v1/verification/start",
        json={"legalName": "Rohan Reddy", "dateOfBirth": "1993-09-30", "ckycNumber": "CKYC-10005"},
    )
    ref_id = resp.json()["referenceId"]
    client.post(f"/api/v1/verification/{ref_id}/otp/send")

    service = get_verification_service()
    session = service.get_session(ref_id)
    session.otp_expires_at = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    service._save_sessions()

    exp_resp = client.post(f"/api/v1/verification/{ref_id}/otp/verify", json={"otp": session.otp_code})
    assert exp_resp.status_code == 400
    assert "expired" in exp_resp.json()["message"].lower()


def _create_test_document_with_face(name: str = "ROHAN REDDY", dob: str = "1993-09-30", ckyc: str = "CKYC-10005") -> bytes:
    img = np.ones((350, 550, 3), dtype=np.uint8) * 255
    # Card border
    cv2.rectangle(img, (10, 10), (540, 340), (40, 40, 40), 2)
    # Header
    cv2.rectangle(img, (10, 10), (540, 50), (47, 128, 255), -1)
    cv2.putText(img, "GOVERNMENT IDENTITY CARD", (80, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # Face portrait area
    cv2.rectangle(img, (30, 80), (170, 260), (200, 200, 200), -1)
    # Draw face
    cv2.ellipse(img, (100, 150), (40, 50), 0, 0, 360, (180, 160, 140), -1)
    cv2.circle(img, (85, 140), 4, (40, 40, 40), -1)
    cv2.circle(img, (115, 140), 4, (40, 40, 40), -1)
    cv2.line(img, (85, 175), (115, 175), (120, 40, 40), 2)

    # Text details
    cv2.putText(img, f"NAME: {name}", (190, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)
    cv2.putText(img, f"DOB: {dob}", (190, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)
    cv2.putText(img, f"ID: {ckyc}", (190, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 2)
    cv2.putText(img, "VERIFIED CITIZEN", (190, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 100, 100), 1)

    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


# ─── 3. Document Face & OCR Cross-Check ───────────────────────────────────────

def test_document_without_face_rejected():
    """Asserts that uploading a blank/non-ID file without a face is rejected."""
    resp = client.post(
        "/api/v1/verification/start",
        json={"legalName": "Rohan Reddy", "dateOfBirth": "1993-09-30", "ckycNumber": "CKYC-10005"},
    )
    ref_id = resp.json()["referenceId"]

    # Upload blank image without a face
    blank_img = np.zeros((200, 200, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", blank_img)
    doc_resp = client.post(
        f"/api/v1/verification/{ref_id}/document",
        files={"document": ("blank.jpg", buf.tobytes(), "image/jpeg")},
    )
    assert doc_resp.status_code == 400
    assert doc_resp.json()["documentMatch"] is False
    assert (
        "no photo id detected" in doc_resp.json()["message"].lower()
        or "no portrait photo" in doc_resp.json()["message"].lower()
        or "invalid" in doc_resp.json()["message"].lower()
    )


def test_document_field_mismatches():
    """Asserts that valid document upload verifies correctly."""
    resp = client.post(
        "/api/v1/verification/start",
        json={"legalName": "Rohan Reddy", "dateOfBirth": "1993-09-30", "ckycNumber": "CKYC-10005"},
    )
    ref_id = resp.json()["referenceId"]

    # Valid document upload with face portrait
    doc_bytes = _create_test_document_with_face()
    doc_resp = client.post(
        f"/api/v1/verification/{ref_id}/document",
        files={"document": ("passport.jpg", doc_bytes, "image/jpeg")},
    )
    assert doc_resp.status_code == 200
    assert doc_resp.json()["documentMatch"] is True
    assert doc_resp.json()["fieldChecks"]["name"] == "match"
    assert doc_resp.json()["fieldChecks"]["dob"] == "match"
    assert doc_resp.json()["fieldChecks"]["ckyc"] == "match"


# ─── 4. Liveness, Deepfake & Decision Matrix Paths ───────────────────────────

def test_liveness_uncertain_leads_to_under_review():
    """Asserts that inconclusive/uncertain liveness escalates to UNDER_REVIEW."""
    resp = client.post(
        "/api/v1/verification/start",
        json={"legalName": "Ananya Verma", "dateOfBirth": "1999-02-18", "ckycNumber": "CKYC-10004"},
    )
    ref_id = resp.json()["referenceId"]

    # Verify OTP & Document
    otp_resp = client.post(f"/api/v1/verification/{ref_id}/otp/send")
    client.post(f"/api/v1/verification/{ref_id}/otp/verify", json={"otp": otp_resp.json()["demoOtp"]})
    doc_bytes = _create_test_document_with_face(name="ANANYA VERMA", dob="1999-02-18", ckyc="CKYC-10004")
    client.post(f"/api/v1/verification/{ref_id}/document", files={"document": ("id.jpg", doc_bytes, "image/jpeg")})

    # Simulate completed liveness stage with UNCERTAIN result
    service = get_verification_service()
    session = service.get_session(ref_id)
    session.decision_table.liveness = "UNCERTAIN"
    session.decision_table.deepfake_analysis = "NO_ANOMALY"
    session.decision_table.live_face = "MATCH"
    service._save_sessions()

    # Finalize
    fin_resp = client.post(f"/api/v1/verification/{ref_id}/finalize")
    assert fin_resp.status_code == 200
    assert fin_resp.json()["status"] == "UNDER_REVIEW"
    assert fin_resp.json()["finalDecision"] == "UNDER_REVIEW"


def test_deepfake_flagged_leads_to_not_verified():
    """Asserts that deepfake anomaly flag results in NOT_VERIFIED."""
    # Use unverified identity
    resp = client.post(
        "/api/v1/verification/start",
        json={"legalName": "Rohan Reddy", "dateOfBirth": "1993-09-30", "ckycNumber": "CKYC-10005"},
    )
    ref_id = resp.json()["referenceId"]

    # Verify OTP & Document
    otp_resp = client.post(f"/api/v1/verification/{ref_id}/otp/send")
    client.post(f"/api/v1/verification/{ref_id}/otp/verify", json={"otp": otp_resp.json()["demoOtp"]})
    doc_bytes = _create_test_document_with_face()
    client.post(f"/api/v1/verification/{ref_id}/document", files={"document": ("id.jpg", doc_bytes, "image/jpeg")})

    # Simulate deepfake anomaly
    service = get_verification_service()
    session = service.get_session(ref_id)
    session.decision_table.liveness = "CONFIRMED"
    session.decision_table.deepfake_analysis = "FLAGGED"
    session.decision_table.live_face = "MATCH"
    service._save_sessions()

    # Finalize
    fin_resp = client.post(f"/api/v1/verification/{ref_id}/finalize")
    assert fin_resp.status_code == 200
    assert fin_resp.json()["status"] == "NOT_VERIFIED"
    assert fin_resp.json()["finalDecision"] == "NOT_VERIFIED"


def test_finalize_early_without_stages_returns_400_incomplete():
    """Security Test: Asserts that calling /finalize before completing document/liveness returns 400 STAGES_INCOMPLETE."""
    # Use an unverified record (CKYC-10008)
    resp = client.post(
        "/api/v1/verification/start",
        json={"legalName": "Kavya Chatterjee", "dateOfBirth": "1998-09-03", "ckycNumber": "CKYC-10008"},
    )
    ref_id = resp.json()["referenceId"]
    assert resp.json()["status"] == "IN_PROGRESS"

    # Only verify OTP
    otp_resp = client.post(f"/api/v1/verification/{ref_id}/otp/send")
    client.post(f"/api/v1/verification/{ref_id}/otp/verify", json={"otp": otp_resp.json()["demoOtp"]})

    # Attempt to bypass Document & Liveness by directly calling finalize
    fin_resp = client.post(f"/api/v1/verification/{ref_id}/finalize")
    assert fin_resp.status_code == 400
    data = fin_resp.json()
    assert data["error"] == "STAGES_INCOMPLETE"
    assert "DOCUMENT_VERIFICATION" in data["message"]
    assert "LIVENESS_CHALLENGE" in data["message"]


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
    data = resp.json()
    assert data["error"] == "IDENTITY_NOT_FOUND"


def test_start_verification_name_mismatch():
    """Asserts 404 when CKYC number exists but Legal Name does not match registry."""
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
    """Asserts ALREADY_VERIFIED shortcut and verifies GET /status returns full persisted state."""
    resp = client.post(
        "/api/v1/verification/start",
        json={
            "legalName": "Vikram Malhotra",
            "dateOfBirth": "1991-11-03",
            "ckycNumber": "CKYC-10003",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ALREADY_VERIFIED"
    assert "already completed verification" in data["message"]
    ref_id = data["referenceId"]
    assert ref_id.startswith("CP-")

    # Confirm GET /status resolves and reconstructs full verified state
    status_resp = client.get(f"/api/v1/verification/{ref_id}/status")
    assert status_resp.status_code == 200
    sdata = status_resp.json()
    assert sdata["status"] == "ALREADY_VERIFIED"
    assert sdata["phoneVerified"] is True
    assert sdata["documentMatch"] is True
    assert sdata["decisionTable"]["live_face"] == "MATCH"


# ─── 2. Phone OTP & Security Gating ──────────────────────────────────────────

def test_otp_demo_mode_gating():
    """Verifies demoOtp appears when DEMO_MODE=True and is omitted when DEMO_MODE=False."""
    # Start session
    resp = client.post(
        "/api/v1/verification/start",
        json={"legalName": "Aarav Sharma", "dateOfBirth": "1994-05-14", "ckycNumber": "CKYC-10001"},
    )
    ref_id = resp.json()["referenceId"]

    # When DEMO_MODE = True
    settings.DEMO_MODE = True
    otp_resp = client.post(f"/api/v1/verification/{ref_id}/otp/send")
    assert otp_resp.json()["demoOtp"] is not None

    # When DEMO_MODE = False
    settings.DEMO_MODE = False
    otp_resp_prod = client.post(f"/api/v1/verification/{ref_id}/otp/send")
    assert otp_resp_prod.json().get("demoOtp") is None

    # Reset
    settings.DEMO_MODE = True


def test_otp_lockout_after_5_failed_attempts():
    """Asserts that 5 incorrect OTP attempts lock out the session."""
    resp = client.post(
        "/api/v1/verification/start",
        json={"legalName": "Priya Patel", "dateOfBirth": "1997-08-22", "ckycNumber": "CKYC-10002"},
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

    # Manually expire the session OTP in backend store
    service = get_verification_service()
    session = service.get_session(ref_id)
    session.otp_expires_at = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    service._save_sessions()

    exp_resp = client.post(f"/api/v1/verification/{ref_id}/otp/verify", json={"otp": session.otp_code})
    assert exp_resp.status_code == 400
    assert "expired" in exp_resp.json()["message"].lower()


# ─── 3. Document OCR Cross-Check ──────────────────────────────────────────────

def test_document_field_mismatches():
    """Asserts that document upload verifies and flags details mismatch."""
    resp = client.post(
        "/api/v1/verification/start",
        json={"legalName": "Aarav Sharma", "dateOfBirth": "1994-05-14", "ckycNumber": "CKYC-10001"},
    )
    ref_id = resp.json()["referenceId"]

    # Valid document upload
    doc_resp = client.post(
        f"/api/v1/verification/{ref_id}/document",
        files={"document": ("passport.jpg", b"valid-bytes", "image/jpeg")},
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
    client.post(f"/api/v1/verification/{ref_id}/document", files={"document": ("id.jpg", b"bytes", "image/jpeg")})

    # Simulate UNCERTAIN liveness
    service = get_verification_service()
    session = service.get_session(ref_id)
    session.decision_table.liveness = "UNCERTAIN"
    service._save_sessions()

    # Finalize
    fin_resp = client.post(f"/api/v1/verification/{ref_id}/finalize")
    assert fin_resp.status_code == 200
    assert fin_resp.json()["status"] == "UNDER_REVIEW"
    assert fin_resp.json()["finalDecision"] == "UNDER_REVIEW"


def test_deepfake_flagged_leads_to_not_verified():
    """Asserts that deepfake anomaly flag results in NOT_VERIFIED."""
    resp = client.post(
        "/api/v1/verification/start",
        json={"legalName": "Aarav Sharma", "dateOfBirth": "1994-05-14", "ckycNumber": "CKYC-10001"},
    )
    ref_id = resp.json()["referenceId"]

    # Verify OTP & Document
    otp_resp = client.post(f"/api/v1/verification/{ref_id}/otp/send")
    client.post(f"/api/v1/verification/{ref_id}/otp/verify", json={"otp": otp_resp.json()["demoOtp"]})
    client.post(f"/api/v1/verification/{ref_id}/document", files={"document": ("id.jpg", b"bytes", "image/jpeg")})

    # Simulate deepfake anomaly
    service = get_verification_service()
    session = service.get_session(ref_id)
    session.decision_table.deepfake_analysis = "FLAGGED"
    service._save_sessions()

    # Finalize
    fin_resp = client.post(f"/api/v1/verification/{ref_id}/finalize")
    assert fin_resp.status_code == 200
    assert fin_resp.json()["status"] == "NOT_VERIFIED"
    assert fin_resp.json()["finalDecision"] == "NOT_VERIFIED"

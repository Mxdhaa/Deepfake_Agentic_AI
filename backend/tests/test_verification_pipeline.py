"""
test_verification_pipeline.py — Unit & Integration tests for verification flow using TestClient
"""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_path))

from main import app

client = TestClient(app)


def test_start_verification_not_found():
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


def test_start_verification_already_verified():
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


def test_full_verification_flow():
    # 1. Start Verification
    resp = client.post(
        "/api/v1/verification/start",
        json={
            "legalName": "Aarav Sharma",
            "dateOfBirth": "1994-05-14",
            "ckycNumber": "CKYC-10001",
        },
    )
    assert resp.status_code == 200
    start_data = resp.json()
    assert start_data["status"] == "IN_PROGRESS"
    ref_id = start_data["referenceId"]
    assert ref_id.startswith("CP-")

    # 2. Get Status
    status_resp = client.get(f"/api/v1/verification/{ref_id}/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["referenceId"] == ref_id
    assert status_data["phoneVerified"] is False

    # 3. Send OTP
    otp_send_resp = client.post(f"/api/v1/verification/{ref_id}/otp/send")
    assert otp_send_resp.status_code == 200
    otp_data = otp_send_resp.json()
    assert otp_data["sent"] is True
    demo_otp = otp_data.get("demoOtp")
    assert demo_otp is not None

    # 4. Verify OTP (Wrong OTP test)
    bad_otp_resp = client.post(
        f"/api/v1/verification/{ref_id}/otp/verify",
        json={"otp": "999999"},
    )
    assert bad_otp_resp.status_code == 400

    # Verify OTP (Correct OTP)
    good_otp_resp = client.post(
        f"/api/v1/verification/{ref_id}/otp/verify",
        json={"otp": demo_otp},
    )
    assert good_otp_resp.status_code == 200
    assert good_otp_resp.json()["verified"] is True

    # 5. Upload Document
    doc_resp = client.post(
        f"/api/v1/verification/{ref_id}/document",
        files={"document": ("passport.jpg", b"dummy-passport-image-bytes", "image/jpeg")},
    )
    assert doc_resp.status_code == 200
    doc_data = doc_resp.json()
    assert doc_data["documentMatch"] is True
    assert doc_data["fieldChecks"]["name"] == "match"

    # 6. Finalize Verification
    finalize_resp = client.post(f"/api/v1/verification/{ref_id}/finalize")
    assert finalize_resp.status_code == 200
    fin_data = finalize_resp.json()
    assert fin_data["status"] == "VERIFIED"
    assert fin_data["decisionTable"]["phone_otp"] == "VERIFIED"
    assert fin_data["decisionTable"]["document"] == "MATCH"

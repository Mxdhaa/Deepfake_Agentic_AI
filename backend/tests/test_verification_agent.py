"""
tests/test_verification_agent.py
─────────────────────────────────
Unit and integration tests for the LangGraph Agentic Reasoning & Escalation Layer:
  1. Clean Pass: Deterministic signals strong -> VERIFIED, no retry, registry updated.
  2. Hard Fail Immutability: challenge_match=False, deepfake=0.82, or sim=0.15 -> NOT_VERIFIED, override blocked.
  3. Borderline Attempt 1: face_sim=0.47 (straddling 0.50) / deepfake=0.38 (straddling 0.40) -> request_retry with fresh sequence.
  4. Borderline Attempt 2: retry_count=1 -> UNDER_REVIEW, enqueued in review_queue.
  5. Terminal State Guard: Late-arriving retry clip on closed session returns 409 Conflict.
  6. Reviewer Decision Linkage: Reviewer approval seals reviewer_decision linking parent agent_decision hash.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from app.agents.verification_agent import run_verification_agent
from app.models.verification import DecisionTable, VerificationSession
from app.services.audit import get_audit_chain_path, get_latest_agent_decision_hash, reset_chain, verify_chain
from app.services.kyc_registry import get_kyc_registry
from app.services.review_queue import get_case, list_pending_cases, reset_queue
from app.services.verification_service import get_verification_service

client = TestClient(app)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_env(tmp_path):
    chain_file = tmp_path / "audit_chain_agent_test.jsonl"
    queue_file = tmp_path / "review_queue_agent_test.jsonl"
    sessions_file = tmp_path / "verification_sessions_test.json"

    with patch.dict(os.environ, {
        "AUDIT_CHAIN_PATH": str(chain_file),
        "REVIEW_QUEUE_PATH": str(queue_file),
        "STORAGE_LOCAL_ROOT": str(tmp_path),
        "REVIEWER_TOKEN": "test-reviewer-token-xyz",
    }):
        reset_chain()
        reset_queue(queue_file)
        yield {
            "chain_file": chain_file,
            "queue_file": queue_file,
            "sessions_file": sessions_file,
        }
        reset_chain()
        reset_queue(queue_file)


def _create_mock_session(
    reference_id: str = "CP-TEST-001",
    face_sim: float = 0.75,
    deepfake_score: float = 0.05,
    challenge_match: bool = True,
    phone_verified: bool = True,
    document_match: bool = True,
    retry_count: int = 0,
    status: str = "IN_PROGRESS",
) -> VerificationSession:
    dt = DecisionTable(
        identity_record="MATCH",
        name="MATCH",
        dob="MATCH",
        ckyc_number="MATCH",
        phone_otp="VERIFIED" if phone_verified else "FAILED",
        document="MATCH" if document_match else "NO_MATCH",
        document_face="MATCH" if document_match else "NO_MATCH",
        live_face="MATCH" if face_sim >= 0.50 else ("UNCERTAIN" if face_sim >= 0.35 else "NO_MATCH"),
        liveness="CONFIRMED" if challenge_match else "FAILED",
        deepfake_analysis="NO_ANOMALY" if deepfake_score < 0.40 else "FLAGGED",
    )

    return VerificationSession(
        reference_id=reference_id,
        ckyc_number="CKYC-10001",
        legal_name="Medha Kumar",
        date_of_birth="2005-02-14",
        registered_phone="+919876543210",
        status=status,
        created_at="2026-08-26T10:00:00.000000+00:00",
        updated_at="2026-08-26T10:00:00.000000+00:00",
        phone_verified=phone_verified,
        document_match=document_match,
        document_details={"ocr_confidence": 0.98},
        face_match=dt.live_face,
        face_similarity_score=face_sim,
        liveness_result=dt.liveness,
        deepfake_result=dt.deepfake_analysis,
        deepfake_score=deepfake_score,
        challenge_match=challenge_match,
        challenge_sequence=["left", "up", "right"],
        decision_table=dt,
        retry_count=retry_count,
    )


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_clean_pass_verified(tmp_env):
    """
    Test clean verification: strong biometric match, nominal deepfake score, verified challenge.
    Agent output -> VERIFIED, no retry requested, agent_decision audit block sealed.
    """
    session = _create_mock_session(
        reference_id="CP-CLEAN-PASS",
        face_sim=0.78,
        deepfake_score=0.06,
        challenge_match=True,
    )

    res = run_verification_agent(session)

    assert res["agent_classification"] == "VERIFIED"
    assert res["final_decision"] == "VERIFIED"
    assert res["has_hard_fail"] is False
    assert res["is_borderline"] is False
    assert res["retry_requested"] is False
    assert "verified successfully" in res["final_reason"].lower()

    # Verify audit chain has agent_decision block
    is_valid, msg, count = verify_chain(tmp_env["chain_file"])
    assert is_valid is True
    assert count == 1

    entry = json.loads(tmp_env["chain_file"].read_text(encoding="utf-8").strip())
    assert entry["record_type"] == "agent_decision"
    assert entry["payload"]["final_decision"] == "VERIFIED"


def test_hard_fail_prevent_override(tmp_env):
    """
    Test fail-closed immutability:
    If challenge_match is False or face similarity is below fail cutoff (< 0.35),
    the agent classification is strictly locked to NOT_VERIFIED.
    """
    # 1. Challenge match failure
    session_challenge_fail = _create_mock_session(
        reference_id="CP-HARD-FAIL-1",
        face_sim=0.82,
        deepfake_score=0.08,
        challenge_match=False,
    )
    res1 = run_verification_agent(session_challenge_fail)
    assert res1["has_hard_fail"] is True
    assert res1["agent_classification"] == "NOT_VERIFIED"
    assert res1["final_decision"] == "NOT_VERIFIED"
    assert res1["retry_requested"] is False

    # 2. Biometric similarity failure (e.g. 0.18 < 0.35)
    session_face_fail = _create_mock_session(
        reference_id="CP-HARD-FAIL-2",
        face_sim=0.18,
        deepfake_score=0.08,
        challenge_match=True,
    )
    res2 = run_verification_agent(session_face_fail)
    assert res2["has_hard_fail"] is True
    assert res2["agent_classification"] == "NOT_VERIFIED"
    assert res2["final_decision"] == "NOT_VERIFIED"


def test_borderline_attempt_1_triggers_retry(tmp_env):
    """
    Test borderline evaluation on attempt 1 (retry_count=0):
    Face similarity 0.47 (straddling similarity_pass = 0.50 within +-0.05).
    Agent triggers request_retry -> new sequence generated, retry_count=1,
    agent_retry_requested audit event sealed immediately.
    """
    session = _create_mock_session(
        reference_id="CP-BORDERLINE-1",
        face_sim=0.47,
        deepfake_score=0.12,
        challenge_match=True,
        retry_count=0,
    )

    res = run_verification_agent(session)

    assert res["is_borderline"] is True
    assert "face_similarity" in res["borderline_signals"]
    assert res["retry_requested"] is True
    assert res["retry_count"] == 1
    assert res["new_challenge_sequence"] is not None
    assert len(res["new_challenge_sequence"]) == 3
    assert res["final_decision"] == "UNDER_REVIEW"

    # Verify audit chain contains agent_retry_requested record
    is_valid, msg, count = verify_chain(tmp_env["chain_file"])
    assert is_valid is True
    assert count == 1

    entry = json.loads(tmp_env["chain_file"].read_text(encoding="utf-8").strip())
    assert entry["record_type"] == "agent_retry_requested"
    assert entry["payload"]["retry_count"] == 1
    assert len(entry["payload"]["new_challenge_sequence"]) == 3


def test_borderline_deepfake_attempt_1_triggers_retry(tmp_env):
    """
    Test deepfake borderline score 0.38 (straddling deepfake_borderline = 0.40 within +-0.05 [0.35, 0.45]):
    Agent triggers request_retry on attempt 1.
    """
    session = _create_mock_session(
        reference_id="CP-DF-BORDERLINE-1",
        face_sim=0.72,
        deepfake_score=0.38,
        challenge_match=True,
        retry_count=0,
    )

    res = run_verification_agent(session)

    assert res["is_borderline"] is True
    assert "deepfake_score" in res["borderline_signals"]
    assert res["retry_requested"] is True
    assert res["retry_count"] == 1


def test_borderline_deepfake_upper_band_triggers_retry(tmp_env):
    """
    Test deepfake borderline score 0.43 (in upper symmetric band [0.35, 0.45] around 0.40):
    Agent triggers request_retry on attempt 1.
    """
    session = _create_mock_session(
        reference_id="CP-DF-BORDERLINE-UPPER",
        face_sim=0.72,
        deepfake_score=0.43,
        challenge_match=True,
        retry_count=0,
    )

    res = run_verification_agent(session)

    assert res["is_borderline"] is True
    assert "deepfake_score" in res["borderline_signals"]
    assert res["retry_requested"] is True
    assert res["retry_count"] == 1


def test_deepfake_above_borderline_band_hard_fails(tmp_env):
    """
    Test deepfake score 0.60 (above the tight [0.35, 0.45] band):
    Must NOT be treated as borderline retry; it must strictly hard-fail as NOT_VERIFIED.
    """
    session = _create_mock_session(
        reference_id="CP-DF-HARD-FAIL-60",
        face_sim=0.72,
        deepfake_score=0.60,
        challenge_match=True,
        retry_count=0,
    )

    res = run_verification_agent(session)

    assert res["has_hard_fail"] is True
    assert res["is_borderline"] is False
    assert res["final_decision"] == "NOT_VERIFIED"
    assert res["retry_requested"] is False


@pytest.mark.parametrize(
    "score,expected_borderline,expected_hard_fail,expected_decision,expected_retry",
    [
        (0.34, False, False, "VERIFIED", False),       # Clean pass below lower threshold
        (0.35, True, False, "UNDER_REVIEW", True),     # Lower exact boundary of borderline band
        (0.40, True, False, "UNDER_REVIEW", True),     # Midpoint of borderline band
        (0.45, True, False, "UNDER_REVIEW", True),     # Upper exact boundary of borderline band
        (0.46, False, True, "NOT_VERIFIED", False),    # Just above borderline band -> hard fail
        (0.60, False, True, "NOT_VERIFIED", False),    # Mid-high deepfake score -> hard fail
        (0.74, False, True, "NOT_VERIFIED", False),    # High deepfake score -> hard fail
        (0.75, False, True, "NOT_VERIFIED", False),    # Critical deepfake fail cutoff -> hard fail
    ],
)
def test_deepfake_borderline_boundary_pinning_matrix(
    tmp_env, score, expected_borderline, expected_hard_fail, expected_decision, expected_retry
):
    """
    Regression gate: Pins exact numeric boundaries for deepfake evaluation:
      - Clean pass: score < 0.35
      - Symmetric borderline band: 0.35 <= score <= 0.45
      - Hard fail: score > 0.45 (strictly NOT_VERIFIED, no retry)
    """
    session = _create_mock_session(
        reference_id=f"CP-DF-PIN-{int(score*100)}",
        face_sim=0.72,
        deepfake_score=score,
        challenge_match=True,
        retry_count=0,
    )

    res = run_verification_agent(session)

    assert res["is_borderline"] is expected_borderline, f"Failed is_borderline for score={score}"
    assert res["has_hard_fail"] is expected_hard_fail, f"Failed has_hard_fail for score={score}"
    assert res["final_decision"] == expected_decision, f"Failed final_decision for score={score}"
    assert res["retry_requested"] is expected_retry, f"Failed retry_requested for score={score}"


def test_borderline_attempt_2_escalates_to_hitl(tmp_env):
    """
    Test borderline evaluation on attempt 2 (retry_count=1):
    Second borderline attempt cannot trigger another retry (retry limit = 1).
    Agent routes directly to finalize -> UNDER_REVIEW, enqueues to review_queue.jsonl,
    and seals agent_decision block.
    """
    session = _create_mock_session(
        reference_id="CP-BORDERLINE-2",
        face_sim=0.47,
        deepfake_score=0.12,
        challenge_match=True,
        retry_count=1,
    )

    res = run_verification_agent(session)

    assert res["is_borderline"] is True
    assert res["retry_requested"] is False
    assert res["final_decision"] == "UNDER_REVIEW"

    # Verify audit chain contains agent_decision with UNDER_REVIEW
    is_valid, msg, count = verify_chain(tmp_env["chain_file"])
    assert is_valid is True
    assert count == 1

    entry = json.loads(tmp_env["chain_file"].read_text(encoding="utf-8").strip())
    assert entry["record_type"] == "agent_decision"
    assert entry["payload"]["final_decision"] == "UNDER_REVIEW"

    # Verify enqueued in review queue
    cases = list_pending_cases(status="pending_review", queue_path=tmp_env["queue_file"])
    assert len(cases) >= 1
    target = next((c for c in cases if c.get("session_id") == "CP-BORDERLINE-2"), None)
    assert target is not None
    assert target["legal_name"] == "Medha Kumar"


def test_terminal_state_guard_409(tmp_env):
    """
    Test that once a session is in a terminal state (VERIFIED, NOT_VERIFIED, ALREADY_VERIFIED),
    any late-arriving retry clip submission returns HTTP 409 Conflict (SESSION_ALREADY_CLOSED).
    """
    service = get_verification_service()
    service._path = tmp_env["sessions_file"]
    service._sessions = {}

    # Seed a verified session
    session = _create_mock_session(
        reference_id="CP-ALREADY-CLOSED",
        status="VERIFIED",
    )
    session.final_decision = "VERIFIED"
    service._sessions[session.reference_id] = session
    service._save_sessions()

    # Attempt late liveness upload on closed session
    dummy_video = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 200
    r = client.post(
        f"/api/v1/verification/{session.reference_id}/liveness",
        files={"clip": ("retry_liveness.mp4", dummy_video, "video/mp4")},
    )
    assert r.status_code == 409
    data = r.json()
    assert data["error"] == "SESSION_ALREADY_CLOSED"


def test_reviewer_decision_parent_hash_linkage(tmp_env):
    """
    Test that when a human reviewer adjudicates an UNDER_REVIEW case,
    the sealed reviewer_decision audit block links cryptographically to the
    parent agent_decision block's record_hash.
    """
    service = get_verification_service()
    service._path = tmp_env["sessions_file"]
    service._sessions = {}

    # 1. Seed an UNDER_REVIEW session
    session = _create_mock_session(
        reference_id="CP-REVIEW-LINK-01",
        face_sim=0.46,
        deepfake_score=0.10,
        challenge_match=True,
        retry_count=1,
        status="UNDER_REVIEW",
    )
    service._sessions[session.reference_id] = session
    service._save_sessions()

    # 2. Run agent finalization to seal agent_decision into audit chain
    run_verification_agent(session)
    agent_decision_hash = get_latest_agent_decision_hash(session.reference_id, tmp_env["chain_file"])
    assert agent_decision_hash is not None

    # 3. Submit human reviewer approval
    headers = {"X-Reviewer-Token": "test-reviewer-token-xyz"}
    r = client.post(
        f"/api/v1/review/{session.reference_id}/decision",
        headers=headers,
        json={
            "action": "approve",
            "reviewer_id": "Auditor Priya",
            "notes": "Verified manual driver license photo matches video frame.",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "resolved_approved"

    # 4. Verify audit chain cryptographic integrity & parent hash linkage
    is_valid, msg, count = verify_chain(tmp_env["chain_file"])
    assert is_valid is True
    assert count >= 2  # agent_decision + reviewer_decision + human_review

    # Check reviewer_decision block payload
    with open(tmp_env["chain_file"], "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    reviewer_entry = next((e for e in lines if e.get("record_type") == "reviewer_decision"), None)
    assert reviewer_entry is not None
    assert reviewer_entry["payload"]["parent_decision_hash"] == agent_decision_hash
    assert reviewer_entry["payload"]["verdict"] == "VERIFIED"
    assert reviewer_entry["payload"]["reviewer_id"] == "Auditor Priya"

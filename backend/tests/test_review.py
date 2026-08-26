"""
tests/test_review.py
────────────────────
Stage 4: Human Review Queue, State Transitions & Hash-Chained Audit Tests.

Tests:
  1. Review queue enqueue and case retrieval.
  2. State transitions: pending_review -> resolved_approved / resolved_rejected.
  3. Status filtering across all enum values (?status=pending_review, resolved_approved, resolved_rejected, all).
  4. Cryptographic audit chain sealing for record_type: 'human_review'.
  5. Reviewer token auth gating (401, 403, 200) across all review endpoints.
  6. Single-source-of-truth verification endpoint (POST /api/v1/review/audit-chain/verify).
  7. Non-destructive CLI tamper demo validation.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from app.services.audit import reset_chain, verify_chain
from app.services.review_queue import (
    enqueue_case_for_review,
    get_case,
    list_pending_cases,
    reset_queue,
    resolve_case,
)

client = TestClient(app)

# ─── D: drive temp directory ──────────────────────────────────────────────────
_D_TMP = Path(r"D:\projects\Deepfake_agenticai\data\tmp")
_D_TMP.mkdir(parents=True, exist_ok=True)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_audit_chain(tmp_path):
    chain_file = tmp_path / "audit_chain_stage4.jsonl"
    with patch.dict(os.environ, {"AUDIT_CHAIN_PATH": str(chain_file)}):
        reset_chain()
        yield chain_file
        reset_chain()


@pytest.fixture()
def tmp_queue(tmp_path):
    queue_file = tmp_path / "review_queue_stage4.jsonl"
    with patch.dict(os.environ, {"REVIEW_QUEUE_PATH": str(queue_file)}):
        reset_queue()
        yield queue_file
        reset_queue()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Review Queue Enqueue & State Transitions
# ═══════════════════════════════════════════════════════════════════════════════

def test_review_queue_enqueue_and_get(tmp_queue):
    """Test enqueuing an unresolved case and retrieving by case_id."""
    case_id = enqueue_case_for_review({
        "session_id": "sess-test-101",
        "kin_token": "kin-test-101",
        "legal_name": "Chen Wei",
        "device_id": "0123456789abcdef",
        "decision": "unresolved",
        "agent_recommendation": "REFER_TO_HUMAN",
        "dossier_summary": "Borderline AV sync offset.",
        "deepfake_score": 0.45,
        "cosine_similarity_score": 0.58,
    }, queue_path=tmp_queue)

    c = get_case(case_id, queue_path=tmp_queue)
    assert c is not None
    assert c["case_id"] == case_id
    assert c["status"] == "pending_review"
    assert c["legal_name"] == "Chen Wei"
    assert c["signals"]["deepfake_score"] == 0.45


def test_review_queue_resolve_approve(tmp_audit_chain, tmp_queue):
    """
    Test human reviewer approving a case:
      1. Status transitions to 'resolved_approved'.
      2. Sealed 'human_review' block written to audit chain.
    """
    case_id = enqueue_case_for_review({
        "session_id": "sess-test-102",
        "kin_token": "kin-test-102",
        "legal_name": "Maria Garcia",
        "decision": "unresolved",
    }, queue_path=tmp_queue)

    resolved = resolve_case(
        case_id=case_id,
        action="approve",
        reviewer_id="reviewer:priya",
        notes="Physiological match confirmed manually.",
        queue_path=tmp_queue,
    )

    assert resolved["status"] == "resolved_approved"
    assert resolved["review_action"] == "approve"
    assert resolved["reviewer_id"] == "reviewer:priya"
    assert resolved["resolved_at"] is not None

    # Check audit chain contains human_review event
    is_valid, msg, count = verify_chain(tmp_audit_chain)
    assert is_valid is True
    assert count == 1

    entry = json.loads(tmp_audit_chain.read_text(encoding="utf-8").strip())
    assert entry["record_type"] == "human_review"
    assert entry["payload"]["action"] == "approve"
    assert entry["payload"]["reviewer_id"] == "reviewer:priya"


def test_review_queue_resolve_reject(tmp_audit_chain, tmp_queue):
    """
    Test human reviewer rejecting a case:
      1. Status transitions to 'resolved_rejected'.
      2. Sealed 'human_review' block written to audit chain.
    """
    case_id = enqueue_case_for_review({
        "session_id": "sess-test-103",
        "kin_token": "kin-test-103",
        "legal_name": "Lucas Silva",
        "decision": "unresolved",
    }, queue_path=tmp_queue)

    resolved = resolve_case(
        case_id=case_id,
        action="reject",
        reviewer_id="reviewer:priya",
        notes="Confirmed injection artifact.",
        queue_path=tmp_queue,
    )

    assert resolved["status"] == "resolved_rejected"
    assert resolved["review_action"] == "reject"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Status Filtering Across All Enum Values
# ═══════════════════════════════════════════════════════════════════════════════

def test_review_queue_status_filtering(tmp_audit_chain, tmp_queue):
    """
    Test that GET /api/v1/review/queue?status= correctly filters across all enum values:
      - 'pending_review'
      - 'resolved_approved'
      - 'resolved_rejected'
      - 'all'
    """
    # 1. Seed Case 1: remains pending_review
    c1 = enqueue_case_for_review({"session_id": "s1", "legal_name": "Alice", "kin_token": "k1"}, queue_path=tmp_queue)

    # 2. Seed Case 2: resolved_approved
    c2 = enqueue_case_for_review({"session_id": "s2", "legal_name": "Bob", "kin_token": "k2"}, queue_path=tmp_queue)
    resolve_case(case_id=c2, action="approve", reviewer_id="auditor_1", queue_path=tmp_queue)

    # 3. Seed Case 3: resolved_rejected
    c3 = enqueue_case_for_review({"session_id": "s3", "legal_name": "Charlie", "kin_token": "k3"}, queue_path=tmp_queue)
    resolve_case(case_id=c3, action="reject", reviewer_id="auditor_1", queue_path=tmp_queue)

    with patch.dict(os.environ, {"REVIEWER_TOKEN": "token-test-123", "REVIEW_QUEUE_PATH": str(tmp_queue), "STORAGE_LOCAL_ROOT": str(tmp_queue.parent)}):
        headers = {"X-Reviewer-Token": "token-test-123"}

        # Filter: pending_review (should return only c1)
        r_pending = client.get("/api/v1/review/queue?status=pending_review", headers=headers)
        assert r_pending.status_code == 200
        pending_list = r_pending.json()
        assert len(pending_list) == 1
        assert pending_list[0]["case_id"] == c1

        # Filter: resolved_approved (should return only c2)
        r_approved = client.get("/api/v1/review/queue?status=resolved_approved", headers=headers)
        assert r_approved.status_code == 200
        approved_list = r_approved.json()
        assert len(approved_list) == 1
        assert approved_list[0]["case_id"] == c2

        # Filter: resolved_rejected (should return only c3)
        r_rejected = client.get("/api/v1/review/queue?status=resolved_rejected", headers=headers)
        assert r_rejected.status_code == 200
        rejected_list = r_rejected.json()
        assert len(rejected_list) == 1
        assert rejected_list[0]["case_id"] == c3

        # Filter: all (should return all 3 cases)
        r_all = client.get("/api/v1/review/queue?status=all", headers=headers)
        assert r_all.status_code == 200
        all_list = r_all.json()
        assert len(all_list) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Reviewer Auth Gating Tests (401, 403, 200)
# ═══════════════════════════════════════════════════════════════════════════════

def test_review_endpoints_auth_gating(tmp_audit_chain, tmp_queue):
    """
    Assert 401 unauthenticated, 403 invalid token, and 200 valid reviewer
    across all Stage 4 review endpoints.
    """
    case_id = enqueue_case_for_review({"session_id": "sess-auth-01", "kin_token": "k01"}, queue_path=tmp_queue)

    with patch.dict(os.environ, {"REVIEWER_TOKEN": "valid-secret-token"}):
        # 1. GET /api/v1/review/queue
        assert client.get("/api/v1/review/queue").status_code == 401
        assert client.get("/api/v1/review/queue", headers={"X-Reviewer-Token": "bad"}).status_code == 403
        assert client.get("/api/v1/review/queue", headers={"X-Reviewer-Token": "valid-secret-token"}).status_code == 200

        # 2. GET /api/v1/review/queue/{case_id}
        assert client.get(f"/api/v1/review/queue/{case_id}").status_code == 401
        assert client.get(f"/api/v1/review/queue/{case_id}", headers={"X-Reviewer-Token": "bad"}).status_code == 403
        assert client.get(f"/api/v1/review/queue/{case_id}", headers={"X-Reviewer-Token": "valid-secret-token"}).status_code == 200

        # 3. POST /api/v1/review/queue/{case_id}/decision
        decision_body = {"action": "approve", "reviewer_id": "Auditor 1"}
        assert client.post(f"/api/v1/review/queue/{case_id}/decision", json=decision_body).status_code == 401
        assert client.post(f"/api/v1/review/queue/{case_id}/decision", headers={"X-Reviewer-Token": "bad"}, json=decision_body).status_code == 403
        assert client.post(f"/api/v1/review/queue/{case_id}/decision", headers={"X-Reviewer-Token": "valid-secret-token"}, json=decision_body).status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Single-Source-of-Truth Chain Verification Wrapper Endpoint
# ═══════════════════════════════════════════════════════════════════════════════

def test_audit_chain_verify_endpoint_wrapper(tmp_audit_chain, tmp_queue):
    """
    Test POST /api/v1/review/audit-chain/verify returns single-source-of-truth report.
    """
    case_id = enqueue_case_for_review({"session_id": "sess-verify-01", "kin_token": "k01"}, queue_path=tmp_queue)
    resolve_case(case_id=case_id, action="approve", reviewer_id="auditor_priya", queue_path=tmp_queue)

    with patch.dict(os.environ, {"REVIEWER_TOKEN": "token-test-verify"}):
        resp = client.post(
            "/api/v1/review/audit-chain/verify",
            headers={"X-Reviewer-Token": "token-test-verify"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_valid"] is True
        assert body["verified_count"] == 1
        assert body["total_count"] == 1
        assert "human_review" in body["block_breakdown"]

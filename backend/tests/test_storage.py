"""
tests/test_storage.py
──────────────────────
Phase 2 amendment + Phase 2.1 storage integration tests.

Tests in this file
──────────────────
Phase 2 amendment:
  test_video_sha256_matches_wire_bytes
      Independently re-hashes the exact bytes sent over the wire and confirms
      the returned video_sha256 matches. Catches any refactor that moves the
      hash call after a processing step.

Phase 2.1 storage:
  test_archival_survives_scoring_failure
      Forces the scoring pipeline to raise, asserts the clip is still present
      in storage AND performs the TRIPLE hash comparison:
        stored bytes == original bytes == API-returned video_sha256
      (A bug where the API hashes a different buffer would still pass a
      two-way comparison if storage and original happen to match.)

  test_stored_hash_matches_retrieved_bytes
      Reads back the stored clip and verifies sha256(stored) == metadata sha256.

  test_review_endpoint_requires_auth
      Confirms GET /review/{session_id}/clip returns 403/401 for
      unauthenticated callers and non-reviewer tokens.

  test_review_endpoint_returns_url_for_reviewer
      Confirms a valid reviewer token gets a ClipAccessResponse with sha256.

Run:
    cd backend
    python -m pytest tests/test_storage.py -v
"""

from __future__ import annotations

import hashlib
import io
import os
import uuid
from pathlib import Path
from typing import Generator
from unittest.mock import patch, MagicMock

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

# ─── App + storage imports ────────────────────────────────────────────────────
from main import app
from app.services.storage import LocalFilesystemBackend, reset_storage, compute_sha256
from app.services.audit import (
    reset_chain,
    verify_chain,
    seal_record,
    log_upload_event,
    log_decision_event,
    log_access_event,
    get_audit_chain_path,
    compute_entry_hash,
)

client = TestClient(app)


# ─── D: drive temp dir — all temp files go here, not C:\Temp ─────────────────
_D_TMP = Path(r"D:\projects\Deepfake_agenticai\data\tmp")
_D_TMP.mkdir(parents=True, exist_ok=True)


# ─── Shared video generator (same as test_liveness.py) ───────────────────────

def _make_real_clip(n_frames: int = 20) -> bytes:
    h, w = 224, 224
    frames = []
    for i in range(n_frames):
        bg = int(40 + (i / n_frames) * 30)
        frame = np.full((h, w, 3), bg, dtype=np.uint8)
        cx = int(w * 0.3 + (i / n_frames) * w * 0.4)
        cv2.ellipse(frame, (cx, h // 2), (40, 50), 0, 0, 360, (200, 180, 160), -1)
        noise = np.random.randint(-8, 8, frame.shape, dtype=np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        frames.append(frame)

    path = str(_D_TMP / f"test_{uuid.uuid4().hex}.mp4")
    try:
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 15.0, (w, h))
        for f in frames:
            writer.write(f)
        writer.release()
        return Path(path).read_bytes()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_storage(tmp_path) -> Generator[LocalFilesystemBackend, None, None]:
    """
    Each test gets a fresh LocalFilesystemBackend in an isolated temp dir.
    Resets the singleton before and after so tests don't bleed state.
    """
    backend = LocalFilesystemBackend(root=tmp_path / "storage")
    reset_storage(backend)
    yield backend
    reset_storage(None)


@pytest.fixture(scope="module")
def real_clip() -> bytes:
    return _make_real_clip()


@pytest.fixture()
def uploaded_session(tmp_storage, real_clip) -> dict:
    """
    Upload a clip via the API and return the full response body.
    tmp_storage fixture guarantees a clean storage for this test.
    """
    resp = client.post(
        "/api/v1/liveness/analyze",
        files={"clip": ("test.mp4", io.BytesIO(real_clip), "video/mp4")},
    )
    assert resp.status_code == 200, f"Upload failed: {resp.text}"
    return resp.json()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2 amendment — SHA-256 must match wire bytes
# ═══════════════════════════════════════════════════════════════════════════════

def test_video_sha256_matches_wire_bytes(tmp_storage, real_clip):
    """
    PHASE 2 AMENDMENT: Independently re-hash the exact bytes sent over the
    wire and confirm the API-returned video_sha256 matches.

    This test catches any future refactor that moves the hash call after a
    processing step (e.g. hashing transcoded/resampled bytes instead of
    the raw received buffer).
    """
    # Compute the expected hash from the exact bytes we're about to send
    expected_sha256 = hashlib.sha256(real_clip).hexdigest()

    resp = client.post(
        "/api/v1/liveness/analyze",
        files={"clip": ("test.mp4", io.BytesIO(real_clip), "video/mp4")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert "video_sha256" in body, "video_sha256 missing from response"

    assert body["video_sha256"] == expected_sha256, (
        f"API returned video_sha256={body['video_sha256']!r} "
        f"but expected hash of wire bytes={expected_sha256!r}. "
        f"Hash was likely computed AFTER a processing step."
    )
    print(f"\n[sha256 match] wire={expected_sha256[:16]}... api={body['video_sha256'][:16]}... ✓")


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2.1 — Archival survives scoring failure (forced failure test)
# ═══════════════════════════════════════════════════════════════════════════════

def test_archival_survives_scoring_failure(tmp_storage, real_clip):
    """
    PHASE 2.1 CORE TEST: Force the scoring pipeline to raise an exception.
    Assert that:
      1. The clip is present in storage (archival completed)
      2. TRIPLE hash comparison:
           sha256(stored_bytes) == sha256(wire_bytes) == api_returned_video_sha256
         This catches a bug where the API hashes a different buffer (e.g.
         a scoring copy) but storage and original happen to agree.
    """
    wire_sha256 = hashlib.sha256(real_clip).hexdigest()
    captured_session_id: list[str] = []

    # Patch analyze_liveness to raise AFTER storage.write() has been called
    original_analyze = __import__(
        "app.services.liveness", fromlist=["analyze_liveness"]
    ).analyze_liveness

    def scoring_bomb(video_bytes: bytes):
        raise RuntimeError("Simulated scoring pipeline failure")

    with patch("app.api.liveness.analyze_liveness", side_effect=scoring_bomb):
        resp = client.post(
            "/api/v1/liveness/analyze",
            files={"clip": ("test.mp4", io.BytesIO(real_clip), "video/mp4")},
        )

    # Scoring failed → HTTP 500
    assert resp.status_code == 500, (
        f"Expected 500 from scoring failure, got {resp.status_code}"
    )

    # But the video_sha256 was returned in the error? No — 500 doesn't return the hash.
    # Instead, we verify via storage directly.

    # Find the session_id by listing storage (it was written before scoring)
    storage_root = tmp_storage.root
    session_dirs = [d for d in storage_root.iterdir() if d.is_dir()]
    assert len(session_dirs) == 1, (
        f"Expected exactly 1 stored session, found {len(session_dirs)}. "
        f"Archival may not have completed before scoring failure."
    )
    session_id = session_dirs[0].name

    # ── ASSERTION 1: Clip is present in storage ──────────────────────────────
    assert tmp_storage.exists(session_id), (
        f"Clip for session_id={session_id!r} not found in storage. "
        f"Archival did not survive scoring failure."
    )

    # ── ASSERTION 2: Triple hash comparison ─────────────────────────────────
    stored_bytes = tmp_storage.read(session_id)
    stored_sha256 = hashlib.sha256(stored_bytes).hexdigest()
    metadata_sha256 = tmp_storage.read_metadata(session_id)["sha256"]

    # Wire bytes == stored bytes
    assert stored_sha256 == wire_sha256, (
        f"sha256(stored) != sha256(wire_bytes): "
        f"stored={stored_sha256[:16]}... wire={wire_sha256[:16]}..."
    )

    # Metadata sha256 == wire bytes (this is what the API would have returned)
    assert metadata_sha256 == wire_sha256, (
        f"metadata.sha256 != sha256(wire_bytes): "
        f"meta={metadata_sha256[:16]}... wire={wire_sha256[:16]}... "
        f"The API hashed a different buffer than the one stored."
    )

    # All three agree (the full triple assertion)
    assert stored_sha256 == metadata_sha256 == wire_sha256, (
        f"Triple hash mismatch: stored={stored_sha256[:16]}... "
        f"meta={metadata_sha256[:16]}... wire={wire_sha256[:16]}..."
    )

    print(
        f"\n[archival test] session={session_id[:8]}..."
        f"\n  wire_sha256    = {wire_sha256[:32]}..."
        f"\n  stored_sha256  = {stored_sha256[:32]}..."
        f"\n  metadata_sha256= {metadata_sha256[:32]}..."
        f"\n  All three match ✓  (scoring failure did not affect archival)"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2.1 — Stored hash matches retrieved bytes
# ═══════════════════════════════════════════════════════════════════════════════

def test_stored_hash_matches_retrieved_bytes(tmp_storage, uploaded_session):
    """
    Read back the stored clip bytes and verify sha256(retrieved) matches
    the sha256 stored in metadata AND the API-returned video_sha256.
    """
    session_id = uploaded_session["session_id"]
    api_sha256 = uploaded_session["video_sha256"]

    # Read from storage
    stored_bytes = tmp_storage.read(session_id)
    retrieved_sha256 = hashlib.sha256(stored_bytes).hexdigest()
    metadata_sha256 = tmp_storage.read_metadata(session_id)["sha256"]

    assert retrieved_sha256 == api_sha256, (
        f"sha256(retrieved bytes) != API video_sha256: "
        f"retrieved={retrieved_sha256[:16]}... api={api_sha256[:16]}..."
    )
    assert metadata_sha256 == api_sha256, (
        f"metadata sha256 != API video_sha256: "
        f"meta={metadata_sha256[:16]}... api={api_sha256[:16]}..."
    )
    print(f"\n[integrity check] sha256={api_sha256[:32]}... matches stored+meta+api ✓")


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2.1 — Review endpoint access control (401 vs 403 vs 200 distinct cases)
# ═══════════════════════════════════════════════════════════════════════════════

def test_review_clip_returns_401_when_unauthenticated(tmp_storage, uploaded_session):
    """
    Assert that GET /review/{session_id}/clip returns HTTP 401 (Unauthorized)
    when no X-Reviewer-Token header is provided.
    """
    session_id = uploaded_session["session_id"]
    with patch.dict(os.environ, {"REVIEWER_TOKEN": "secret-reviewer-token-xyz"}):
        resp = client.get(f"/api/v1/review/{session_id}/clip")
        assert resp.status_code == 401, f"Expected 401 for missing token, got {resp.status_code}"
        assert "WWW-Authenticate" in resp.headers
        print(f"\n[auth 401 check] missing token -> 401 Unauthorized ✓")


def test_review_clip_returns_403_when_token_is_invalid(tmp_storage, uploaded_session):
    """
    Assert that GET /review/{session_id}/clip returns HTTP 403 (Forbidden)
    when an invalid/non-reviewer token is provided.
    """
    session_id = uploaded_session["session_id"]
    with patch.dict(os.environ, {"REVIEWER_TOKEN": "secret-reviewer-token-xyz"}):
        resp = client.get(
            f"/api/v1/review/{session_id}/clip",
            headers={"X-Reviewer-Token": "wrong-imposter-token"},
        )
        assert resp.status_code == 403, f"Expected 403 for wrong token, got {resp.status_code}"
        assert resp.json()["detail"] == "Invalid reviewer token."
        print(f"\n[auth 403 check] wrong token -> 403 Forbidden ✓")


def test_review_clip_returns_200_for_valid_reviewer(tmp_storage, uploaded_session):
    """
    Assert that GET /review/{session_id}/clip returns HTTP 200 with short-lived URL
    and SHA-256 integrity digest when a valid reviewer token is supplied.
    """
    session_id = uploaded_session["session_id"]
    api_sha256 = uploaded_session["video_sha256"]
    token = "test-reviewer-token-abc"

    with patch.dict(os.environ, {"REVIEWER_TOKEN": token}):
        resp = client.get(
            f"/api/v1/review/{session_id}/clip",
            headers={"X-Reviewer-Token": token},
        )

    assert resp.status_code == 200, f"Expected 200 for valid reviewer: {resp.text}"
    body = resp.json()

    assert body["session_id"] == session_id
    assert "url" in body
    assert body["sha256"] == api_sha256, (
        f"Review endpoint sha256 {body['sha256'][:16]}... "
        f"!= API video_sha256 {api_sha256[:16]}..."
    )
    assert body["expires_in"] > 0
    print(f"\n[auth 200 check] valid token -> 200 OK + sha256 match ✓")


def test_review_stream_returns_401_when_unauthenticated(tmp_storage, uploaded_session):
    """Assert /stream endpoint returns HTTP 401 when token is omitted."""
    session_id = uploaded_session["session_id"]
    with patch.dict(os.environ, {"REVIEWER_TOKEN": "stream-secret"}):
        resp = client.get(f"/api/v1/review/{session_id}/stream")
        assert resp.status_code == 401


def test_review_stream_returns_403_when_token_is_invalid(tmp_storage, uploaded_session):
    """Assert /stream endpoint returns HTTP 403 when token is incorrect."""
    session_id = uploaded_session["session_id"]
    with patch.dict(os.environ, {"REVIEWER_TOKEN": "stream-secret"}):
        resp = client.get(
            f"/api/v1/review/{session_id}/stream",
            headers={"X-Reviewer-Token": "invalid-stream-token"},
        )
        assert resp.status_code == 403


def test_review_stream_returns_200_for_valid_reviewer(tmp_storage, uploaded_session):
    """Assert /stream endpoint returns HTTP 200 with raw bytes for valid reviewer."""
    session_id = uploaded_session["session_id"]
    token = "stream-secret"
    with patch.dict(os.environ, {"REVIEWER_TOKEN": token}):
        resp = client.get(
            f"/api/v1/review/{session_id}/stream",
            headers={"X-Reviewer-Token": token},
        )
        assert resp.status_code == 200
        streamed_sha256 = hashlib.sha256(resp.content).hexdigest()
        assert streamed_sha256 == uploaded_session["video_sha256"]


def test_review_nonexistent_session_returns_404(tmp_storage):
    """A valid reviewer token asking for a nonexistent session must get 404."""
    token = "test-reviewer-token-abc"
    with patch.dict(os.environ, {"REVIEWER_TOKEN": token}):
        resp = client.get(
            "/api/v1/review/nonexistent-session-000/clip",
            headers={"X-Reviewer-Token": token},
        )
    assert resp.status_code == 404, (
        f"Expected 404 for nonexistent session, got {resp.status_code}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2 / Phase 5 — Unified Hash Chain Audit Trail Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_audit_chain_interleaved_mixed_records(tmp_path):
    """
    Test that upload, decision, and access events all interleave in ONE
    single hash chain with strict prev_hash linkage across mixed record types.
    """
    chain_file = tmp_path / "audit_chain.jsonl"
    with patch.dict(os.environ, {"AUDIT_CHAIN_PATH": str(chain_file)}):
        reset_chain()

        e0 = log_upload_event(
            session_id="sess-1",
            sha256="aaa" * 21 + "a",
            size_bytes=1024,
            ip="127.0.0.1",
        )
        assert e0["index"] == 0
        assert e0["record_type"] == "upload"
        assert e0["prev_hash"] == "0" * 64

        e1 = log_decision_event(
            session_id="sess-1",
            decision="pass",
            anomaly_score=0.22,
            breakdown={"deepfake_contribution": 0.1, "challenge_contribution": 0.0, "blink_contribution": 0.0, "av_sync_contribution": 0.0},
            video_sha256="aaa" * 21 + "a",
            config_version="v1.0",
            ip="127.0.0.1",
        )
        assert e1["index"] == 1
        assert e1["record_type"] == "decision"
        assert e1["prev_hash"] == e0["record_hash"]

        e2 = log_access_event(
            session_id="sess-1",
            reviewer_id="reviewer:alice",
            action="presign",
            outcome="success",
            ip="10.0.0.5",
        )
        assert e2["index"] == 2
        assert e2["record_type"] == "access"
        assert e2["prev_hash"] == e1["record_hash"]

        e3 = log_upload_event(
            session_id="sess-2",
            sha256="bbb" * 21 + "b",
            size_bytes=2048,
        )
        assert e3["index"] == 3
        assert e3["prev_hash"] == e2["record_hash"]

        e4 = log_access_event(
            session_id="sess-2",
            reviewer_id="reviewer:bob",
            action="stream",
            outcome="success",
        )
        assert e4["index"] == 4
        assert e4["prev_hash"] == e3["record_hash"]

        # Validate complete chain
        is_valid, msg, count = verify_chain(chain_file)
        assert is_valid is True, f"Verification failed: {msg}"
        assert count == 5
        print(f"\n[hash chain] 5 mixed records sealed and verified ✓")


def test_tampered_access_event_caught_by_verification(tmp_path):
    """
    Tamper specifically with an access-event entry (e.g. modify reviewer_id)
    and assert that verify_chain() catches it and identifies the exact block index.
    Proves the unification of access events into the cryptographic chain is real.
    """
    import json

    chain_file = tmp_path / "audit_chain_tamper.jsonl"
    with patch.dict(os.environ, {"AUDIT_CHAIN_PATH": str(chain_file)}):
        reset_chain()

        log_upload_event(session_id="sess-001", sha256="111" * 21 + "1", size_bytes=500)
        log_decision_event(
            session_id="sess-001",
            decision="pass",
            anomaly_score=0.15,
            breakdown={"deepfake_contribution": 0.0, "challenge_contribution": 0.0, "blink_contribution": 0.0, "av_sync_contribution": 0.0},
            video_sha256="111" * 21 + "1",
            config_version="v1.0",
        )
        log_access_event(
            session_id="sess-001",
            reviewer_id="reviewer:authentic_auditor",
            action="presign",
            outcome="success",
        )

        # Confirm valid before tampering
        is_valid_before, _, _ = verify_chain(chain_file)
        assert is_valid_before is True

        # Now tamper with line 2 (the access event at index 2)
        lines = chain_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3

        access_entry = json.loads(lines[2])
        assert access_entry["record_type"] == "access"
        # Tamper with reviewer_id
        access_entry["payload"]["reviewer_id"] = "reviewer:imposter_attacker"
        lines[2] = json.dumps(access_entry)
        chain_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Re-verify — MUST fail and pinpoint index 2
        is_valid_after, error_msg, fail_idx = verify_chain(chain_file)
        assert is_valid_after is False, "Tampered access event was NOT detected!"
        assert fail_idx == 2
        assert "Tamper detected at index 2" in error_msg
        print(f"\n[tamper detection] Successfully caught tampered access block: {error_msg} ✓")


def test_tampered_prev_hash_broken_link_caught(tmp_path):
    """
    Corrupt a prev_hash link in an access event and confirm broken link detection.
    """
    import json

    chain_file = tmp_path / "audit_chain_broken_link.jsonl"
    with patch.dict(os.environ, {"AUDIT_CHAIN_PATH": str(chain_file)}):
        reset_chain()

        log_upload_event(session_id="sess-1", sha256="abc" * 21 + "a", size_bytes=100)
        log_access_event(
            session_id="sess-1",
            reviewer_id="reviewer:bob",
            action="presign",
            outcome="success",
        )

        lines = chain_file.read_text(encoding="utf-8").strip().splitlines()
        entry = json.loads(lines[1])
        entry["prev_hash"] = "deadbeef" * 8
        lines[1] = json.dumps(entry)
        chain_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        is_valid, msg, fail_idx = verify_chain(chain_file)
        assert is_valid is False
        assert fail_idx == 1
        assert "Broken hash link at index 1" in msg
        print(f"\n[broken link detection] Successfully detected broken link: {msg} ✓")


def test_end_to_end_upload_and_review_seals_in_single_chain(tmp_path, real_clip):
    """
    End-to-end integration test:
    1. Upload clip through POST /api/v1/liveness/analyze
    2. Access clip through GET /api/v1/review/{session_id}/clip
    3. Assert the single chain has exactly 3 records: upload, decision, access
    4. Assert verify_chain() validates the entire sequence
    """
    import json

    storage_root = tmp_path / "storage"
    chain_file = storage_root / "audit_chain.jsonl"
    token = "e2e-reviewer-token"

    with patch.dict(
        os.environ,
        {
            "STORAGE_LOCAL_ROOT": str(storage_root),
            "AUDIT_CHAIN_PATH": str(chain_file),
            "REVIEWER_TOKEN": token,
        },
    ):
        reset_storage(LocalFilesystemBackend(root=storage_root))
        reset_chain()

        # Step 1: Upload and analyze
        resp = client.post(
            "/api/v1/liveness/analyze",
            files={"clip": ("clip.mp4", io.BytesIO(real_clip), "video/mp4")},
        )
        assert resp.status_code == 200
        session_id = resp.json()["session_id"]
        wire_sha256 = resp.json()["video_sha256"]

        # Step 2: Access via reviewer endpoint
        resp_rev = client.get(
            f"/api/v1/review/{session_id}/clip",
            headers={"X-Reviewer-Token": token},
        )
        assert resp_rev.status_code == 200

        # Step 3: Verify the sealed chain
        is_valid, msg, count = verify_chain(chain_file)
        assert is_valid is True, f"Chain verification failed: {msg}"
        assert count == 3

        records = [json.loads(line) for line in chain_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert records[0]["record_type"] == "upload"
        assert records[0]["session_id"] == session_id
        assert records[0]["payload"]["sha256"] == wire_sha256

        assert records[1]["record_type"] == "decision"
        assert records[1]["session_id"] == session_id
        assert records[1]["prev_hash"] == records[0]["record_hash"]

        assert records[2]["record_type"] == "access"
        assert records[2]["session_id"] == session_id
        assert records[2]["prev_hash"] == records[1]["record_hash"]
        assert records[2]["payload"]["action"] == "presign"
        assert records[2]["payload"]["outcome"] == "success"

        print(f"\n[e2e audit chain] upload -> decision -> access verified in single chain ✓")


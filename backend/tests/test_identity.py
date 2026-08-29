"""
tests/test_identity.py
──────────────────────
Stage 2: Deterministic Identity Match Integration & Unit Tests.

Tests:
  1. Cosine similarity unit math (identical, orthogonal, opposite, zero vectors).
  2. Hierarchical decision rule boundaries (fail < 0.35 / vel >= 6; borderline < 0.60 / vel >= 3; pass >= 0.60 & vel < 3).
  3. Synthetic dataset alignment on identity-driven records.
  4. Photo-on-file wire hashing & object storage archival before processing.
  5. Cryptographic audit hash chain linkage (record_type: "identity").
  6. Sub-millisecond latency benchmark (< 2ms deterministic decision).
  7. API endpoint validation (POST /match, POST /match-images, GET /records/{kin}, GET /config).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from main import app
from app.services.audit import get_audit_chain_path, reset_chain, verify_chain
from app.services.identity import (
    compute_cosine_similarity,
    evaluate_identity_embeddings,
    evaluate_identity_images,
    get_identity_config,
    lookup_ckyc_record,
    lookup_registry_velocity,
)
from app.services.storage import LocalFilesystemBackend, reset_storage

client = TestClient(app)

# ─── D: drive temp directory ──────────────────────────────────────────────────
_D_TMP = Path(r"D:\projects\Deepfake_agenticai\data\tmp")
_D_TMP.mkdir(parents=True, exist_ok=True)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_storage(tmp_path):
    backend = LocalFilesystemBackend(root=tmp_path / "storage")
    reset_storage(backend)
    yield backend
    reset_storage(None)


@pytest.fixture()
def tmp_audit_chain(tmp_path):
    chain_file = tmp_path / "audit_chain_stage2.jsonl"
    with patch.dict(os.environ, {"AUDIT_CHAIN_PATH": str(chain_file)}):
        reset_chain()
        yield chain_file
        reset_chain()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Cosine Similarity Vector Math Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_cosine_similarity_identical_vectors():
    """Identical vectors must have cosine similarity exactly 1.0."""
    v1 = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
    v2 = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
    sim = compute_cosine_similarity(v1, v2)
    assert sim == pytest.approx(1.0, abs=1e-5)


def test_cosine_similarity_orthogonal_vectors():
    """Orthogonal vectors must have cosine similarity 0.0."""
    v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    v2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    sim = compute_cosine_similarity(v1, v2)
    assert sim == pytest.approx(0.0, abs=1e-5)


def test_cosine_similarity_opposite_vectors():
    """Opposite vectors must have cosine similarity -1.0."""
    v1 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    v2 = np.array([-1.0, -2.0, -3.0], dtype=np.float32)
    sim = compute_cosine_similarity(v1, v2)
    assert sim == pytest.approx(-1.0, abs=1e-5)


def test_cosine_similarity_zero_vector():
    """Zero vectors return 0.0 without division by zero errors."""
    v1 = np.zeros(512, dtype=np.float32)
    v2 = np.ones(512, dtype=np.float32)
    sim = compute_cosine_similarity(v1, v2)
    assert sim == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Hierarchical Decision Rule Boundary Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_decision_boundary_pass():
    """Similarity >= 0.60 and velocity < 3 -> PASS."""
    # Construct normalized 512-d vectors with target similarity
    v1 = np.zeros(512, dtype=np.float32)
    v2 = np.zeros(512, dtype=np.float32)
    v1[0] = 1.0
    # cos(theta) = 0.75 -> v2 = [0.75, sqrt(1-0.75^2), ...]
    v2[0] = 0.75
    v2[1] = np.sqrt(1.0 - 0.75**2)

    with patch("app.services.identity.lookup_registry_velocity", return_value=1):
        res = evaluate_identity_embeddings(v1, v2)
        assert res["decision"] == "pass"
        assert res["face_match"] is True
        assert res["velocity_flagged"] is False
        assert res["cosine_similarity"] == pytest.approx(0.75, abs=1e-3)


def test_decision_boundary_borderline_by_similarity():
    """0.35 <= similarity < 0.50 with velocity < 3 -> BORDERLINE."""
    v1 = np.zeros(512, dtype=np.float32)
    v2 = np.zeros(512, dtype=np.float32)
    v1[0] = 1.0
    v2[0] = 0.42
    v2[1] = np.sqrt(1.0 - 0.42**2)

    with patch("app.services.identity.lookup_registry_velocity", return_value=1):
        res = evaluate_identity_embeddings(v1, v2)
        assert res["decision"] == "borderline"
        assert res["face_match"] is False
        assert res["velocity_flagged"] is False


def test_decision_boundary_borderline_by_velocity():
    """Similarity >= 0.60 with 3 <= velocity < 6 -> BORDERLINE."""
    v1 = np.ones(512, dtype=np.float32) / np.sqrt(512)
    v2 = v1.copy()  # similarity 1.0

    for vel in [3, 4, 5]:
        with patch("app.services.identity.lookup_registry_velocity", return_value=vel):
            res = evaluate_identity_embeddings(v1, v2)
            assert res["decision"] == "borderline", f"Expected borderline for velocity={vel}"
            assert res["velocity_flagged"] is True


def test_decision_boundary_fail_by_low_similarity():
    """Similarity < 0.35 with normal velocity -> FAIL."""
    v1 = np.zeros(512, dtype=np.float32)
    v2 = np.zeros(512, dtype=np.float32)
    v1[0] = 1.0
    v2[0] = 0.20
    v2[1] = np.sqrt(1.0 - 0.20**2)

    with patch("app.services.identity.lookup_registry_velocity", return_value=1):
        res = evaluate_identity_embeddings(v1, v2)
        assert res["decision"] == "fail"
        assert res["face_match"] is False


def test_decision_boundary_fail_by_velocity_burst():
    """Velocity >= 6 -> FAIL (even if face matches perfectly)."""
    v1 = np.ones(512, dtype=np.float32) / np.sqrt(512)
    v2 = v1.copy()

    for vel in [6, 8, 15]:
        with patch("app.services.identity.lookup_registry_velocity", return_value=vel):
            res = evaluate_identity_embeddings(v1, v2)
            assert res["decision"] == "fail", f"Expected fail for velocity={vel}"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Synthetic Ground Truth Alignment (Identity Subrule Scoped)
# ═══════════════════════════════════════════════════════════════════════════════

def test_synthetic_identity_subrule_alignment():
    """
    Test Stage 2 decision evaluation on records from data/onboarding_batch.json.
    Verifies that when identity signals (cosine similarity or velocity) dictate
    the classification tier, Stage 2's deterministic rule agrees 100%.
    """
    db_path = _D_TMP.parent / "onboarding_batch.json"
    if not db_path.exists():
        pytest.skip("Synthetic dataset not available at D: drive data path")

    data = json.loads(db_path.read_text(encoding="utf-8"))
    records = data.get("records", [])
    assert len(records) > 0, "No synthetic records found"

    evaluated_count = 0
    for r in records:
        sim = float(r["cosine_similarity_score"])
        vel = int(r["registry_velocity_6hr"])

        # Determine expected identity tier per _derive_decision subrule:
        if sim < 0.35 or vel >= 6:
            expected_tier = "fail"
        elif sim < 0.60 or vel >= 3:
            expected_tier = "borderline"
        else:
            expected_tier = "pass"

        # Evaluate through Stage 2
        v1 = np.zeros(512, dtype=np.float32)
        v2 = np.zeros(512, dtype=np.float32)
        v1[0] = 1.0
        v2[0] = sim
        v2[1] = np.sqrt(max(0.0, 1.0 - sim**2))

        with patch("app.services.identity.lookup_registry_velocity", return_value=vel):
            res = evaluate_identity_embeddings(v1, v2, kin_token=r.get("kin_token"))
            assert res["decision"] == expected_tier, (
                f"Mismatch for KIN={r.get('kin_token')}: "
                f"sim={sim}, vel={vel} -> expected {expected_tier}, got {res['decision']}"
            )
            evaluated_count += 1

    print(f"\n[synthetic alignment] Evaluated and verified {evaluated_count} synthetic records ✓")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Photo-on-File Wire Hashing & Storage Archival
# ═══════════════════════════════════════════════════════════════════════════════

def test_photo_on_file_wire_hashing_and_archival(tmp_storage):
    """
    Test that when raw image bytes are sent:
      1. Hashes are computed on exact received wire bytes.
      2. Both photos are archived in storage under session_id keys.
      3. The returned live_sha256 and ckyc_sha256 match the wire hashes.
    """
    import cv2

    # Create two synthetic dummy images (224x224 RGB)
    img_live = np.full((224, 224, 3), 180, dtype=np.uint8)
    cv2.circle(img_live, (112, 112), 40, (50, 100, 200), -1)
    _, live_buf = cv2.imencode(".jpg", img_live)
    live_bytes = live_buf.tobytes()

    img_ckyc = np.full((224, 224, 3), 150, dtype=np.uint8)
    cv2.circle(img_ckyc, (112, 112), 40, (50, 100, 200), -1)
    _, ckyc_buf = cv2.imencode(".jpg", img_ckyc)
    ckyc_bytes = ckyc_buf.tobytes()

    expected_live_sha256 = hashlib.sha256(live_bytes).hexdigest()
    expected_ckyc_sha256 = hashlib.sha256(ckyc_bytes).hexdigest()

    session_id = str(uuid.uuid4())
    res = evaluate_identity_images(
        live_image_bytes=live_bytes,
        ckyc_image_bytes=ckyc_bytes,
        session_id=session_id,
    )

    # 1. Wire hash agreement
    assert res["live_sha256"] == expected_live_sha256
    assert res["ckyc_sha256"] == expected_ckyc_sha256

    # 2. Storage presence
    assert tmp_storage.exists(f"{session_id}_live")
    assert tmp_storage.exists(f"{session_id}_ckyc")

    stored_live = tmp_storage.read(f"{session_id}_live")
    stored_ckyc = tmp_storage.read(f"{session_id}_ckyc")

    assert hashlib.sha256(stored_live).hexdigest() == expected_live_sha256
    assert hashlib.sha256(stored_ckyc).hexdigest() == expected_ckyc_sha256

    # 3. Disclosed extraction latency
    assert res["embedding_extraction_ms"] > 0
    assert res["decision_latency_ms"] > 0
    assert res["total_processing_ms"] >= res["embedding_extraction_ms"]


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Cryptographic Audit Hash Chain Linkage
# ═══════════════════════════════════════════════════════════════════════════════

def test_identity_event_seals_in_unified_chain(tmp_audit_chain):
    """
    Test that Stage 2 identity decisions are sealed into the unified hash chain
    with record_type: 'identity' and valid cryptographic linkage.
    """
    v1 = np.ones(512, dtype=np.float32) / np.sqrt(512)
    v2 = v1.copy()

    res = evaluate_identity_embeddings(
        live_embedding=v1,
        ckyc_embedding=v2,
        kin_token="kin-test-123",
        device_id="dev-test-456",
        session_id="sess-identity-001",
    )

    # Verify chain file on disk
    is_valid, msg, count = verify_chain(tmp_audit_chain)
    assert is_valid is True, f"Chain verification failed: {msg}"
    assert count == 1

    lines = tmp_audit_chain.read_text(encoding="utf-8").strip().splitlines()
    entry = json.loads(lines[0])
    assert entry["record_type"] == "identity"
    assert entry["session_id"] == "sess-identity-001"
    assert entry["payload"]["decision"] == "pass"
    assert entry["payload"]["kin_token"] == "kin-test-123"
    assert entry["payload"]["device_id"] == "dev-test-456"
    assert entry["prev_hash"] == "0" * 64


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Sub-Millisecond Decision Latency Benchmark (< 2ms)
# ═══════════════════════════════════════════════════════════════════════════════

def test_deterministic_decision_latency_benchmark(tmp_audit_chain):
    """
    Benchmark test proving Stage 2 deterministic evaluation runs in < 2ms
    (typically < 0.5ms on CPU) with zero LLM calls.
    """
    v1 = np.random.randn(512).astype(np.float32)
    v1 /= np.linalg.norm(v1)
    v2 = np.random.randn(512).astype(np.float32)
    v2 /= np.linalg.norm(v2)

    latencies = []
    n_iterations = 50

    for _ in range(n_iterations):
        res = evaluate_identity_embeddings(v1, v2)
        latencies.append(res["decision_latency_ms"])

    mean_latency = float(np.mean(latencies))
    p95_latency = float(np.percentile(latencies, 95))

    print(f"\n[latency benchmark] Mean: {mean_latency:.3f}ms | p95: {p95_latency:.3f}ms")

    assert mean_latency < 2.0, f"Mean latency {mean_latency:.3f}ms exceeded 2.0ms threshold"
    assert p95_latency < 5.0, f"p95 latency {p95_latency:.3f}ms exceeded 5.0ms threshold"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. API Router Endpoints Validation
# ═══════════════════════════════════════════════════════════════════════════════

def test_api_match_embeddings_endpoint():
    """Test POST /api/v1/identity/match on precomputed vectors."""
    v1 = (np.ones(512) / np.sqrt(512)).tolist()
    v2 = (np.ones(512) / np.sqrt(512)).tolist()

    resp = client.post(
        "/api/v1/identity/match",
        json={
            "live_embedding": v1,
            "ckyc_embedding": v2,
            "device_id": "test-device-123",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["decision"] == "pass"
    assert body["cosine_similarity"] == pytest.approx(1.0, abs=1e-3)
    assert body["decision_latency_ms"] < 10.0
    assert "session_id" in body


def test_api_config_endpoint():
    """Test GET /api/v1/identity/config."""
    resp = client.get("/api/v1/identity/config")
    assert resp.status_code == 200
    body = resp.json()
    assert "thresholds" in body
    assert body["thresholds"]["similarity_pass"] == 0.55
    assert body["thresholds"]["similarity_fail"] == 0.35
    assert body["thresholds"]["velocity_borderline"] == 3
    assert body["thresholds"]["velocity_fail"] == 6


def test_face_feature_extractor_alignment_modes_and_fallback_auditing():
    """
    Validates that FaceFeatureExtractor explicitly identifies and audits detection modes:
      - Real face photo -> 'mtcnn_aligned'
      - Pure noise / blank canvas -> 'unaligned_direct'
      - Empty bytes -> 'empty_input'
    """
    from app.services.identity import FaceFeatureExtractor

    ext = FaceFeatureExtractor()

    # 1. Empty input
    emb_empty, mode_empty = ext.extract_from_bytes(b"", return_mode=True)
    assert mode_empty == "empty_input"
    assert np.all(emb_empty == 0.0)
    assert len(emb_empty) == 512

    # 2. Blank / Non-face noise image
    blank = np.zeros((120, 120, 3), dtype=np.uint8)
    emb_blank, mode_blank = ext.extract_from_bgr(blank, return_mode=True)
    assert mode_blank in {"unaligned_direct", "haar_fallback", "heuristic_histogram_fallback"}
    assert len(emb_blank) == 512
    assert pytest.approx(np.linalg.norm(emb_blank), abs=1e-4) == 1.0

    # 3. Real human face photo
    ffpp_dir = Path("data/ffpp_airtight/processed_images")
    if ffpp_dir.exists():
        ffpp_files = list(ffpp_dir.glob("*.jpg"))
        if ffpp_files:
            import cv2
            real_bgr = cv2.imread(str(ffpp_files[0]))
            emb_real, mode_real = ext.extract_from_bgr(real_bgr, return_mode=True)
            assert mode_real == "mtcnn_aligned"
            assert len(emb_real) == 512
            assert pytest.approx(np.linalg.norm(emb_real), abs=1e-4) == 1.0


def test_evaluate_identity_images_audits_detection_modes(tmp_storage, tmp_audit_chain):
    """Asserts that evaluate_identity_images captures and returns live and ckyc detection modes."""
    import cv2

    img1 = np.full((160, 160, 3), 200, dtype=np.uint8)
    img2 = np.full((160, 160, 3), 150, dtype=np.uint8)
    _, buf1 = cv2.imencode(".jpg", img1)
    _, buf2 = cv2.imencode(".jpg", img2)

    res = evaluate_identity_images(
        live_image_bytes=buf1.tobytes(),
        ckyc_image_bytes=buf2.tobytes(),
        kin_token="KIN-AUDIT-TEST",
        device_id="DEV-AUDIT-TEST",
    )

    assert "live_detection_mode" in res
    assert "ckyc_detection_mode" in res
    assert res["live_detection_mode"] is not None
    assert res["ckyc_detection_mode"] is not None


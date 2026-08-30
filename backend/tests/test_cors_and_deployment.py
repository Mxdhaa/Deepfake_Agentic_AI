"""
test_cors_and_deployment.py
────────────────────────────
Comprehensive test suite verifying:
1. Strict Pinned CORS (positive allowed origins, Vercel preview regex, negative rejection of malicious origins).
2. Elimination of wildcard '*' origins.
3. Health check probe endpoints (/health and /api/v1/health).
4. Ephemeral HMAC-SHA256 signed video stream URLs (happy path, expiry, tampering).
5. Dual-path stream access (signed URL vs X-Reviewer-Token header) and audit logging.
6. Reviewer auth gating (401 on missing, 403 on invalid, 200 on valid).
"""

import hashlib
import hmac
import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from app.core.config import Settings, settings
from app.services.storage import (
    LocalFilesystemBackend,
    generate_stream_signature,
    verify_stream_signature,
)
from app.services.audit import get_audit_chain_path


@pytest.fixture
def client():
    return TestClient(app)


# ─── 1. CORS Configuration & Header Tests ─────────────────────────────────────

class TestCORSConfiguration:
    def test_cors_allowed_localhost_options(self, client: TestClient):
        """Preflight OPTIONS request from localhost:3000 should receive Access-Control-Allow-Origin."""
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_cors_allowed_127_0_0_1_options(self, client: TestClient):
        """Preflight OPTIONS from 127.0.0.1:3000 should be allowed."""
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://127.0.0.1:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"

    def test_cors_allowed_vercel_preview(self, client: TestClient):
        """Vercel preview deployment matching VERCEL_PREVIEW_REGEX should be allowed."""
        preview_origin = "https://deepfake-agentic-preview-7x9a.vercel.app"
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": preview_origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == preview_origin

    def test_cors_rejected_malicious_origin_options(self, client: TestClient):
        """Preflight OPTIONS request from malicious origin must NOT return Access-Control-Allow-Origin."""
        malicious_origin = "https://malicious-attacker.com"
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": malicious_origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        # FastAPIs CORSMiddleware does not include access-control-allow-origin for rejected origins
        allowed_header = response.headers.get("access-control-allow-origin")
        assert allowed_header != malicious_origin
        assert allowed_header is None or allowed_header == ""

    def test_cors_rejected_malicious_origin_get(self, client: TestClient):
        """Standard GET request with malicious Origin header must NOT receive Access-Control-Allow-Origin."""
        malicious_origin = "https://evil-phishing-site.org"
        response = client.get(
            "/api/v1/health",
            headers={"Origin": malicious_origin},
        )
        assert response.status_code == 200
        allowed_header = response.headers.get("access-control-allow-origin")
        assert allowed_header != malicious_origin
        assert allowed_header is None

    def test_settings_filters_out_wildcards(self):
        """Pydantic Settings must purge wildcard '*' from allowed origins."""
        s = Settings(ALLOWED_ORIGINS="*,http://localhost:3000,http://example.com")
        assert "*" not in s.ALLOWED_ORIGINS
        assert "http://localhost:3000" in s.ALLOWED_ORIGINS
        assert "http://example.com" in s.ALLOWED_ORIGINS

        # Test JSON string parsing
        s_json = Settings(ALLOWED_ORIGINS='["*", "https://safe.app"]')
        assert "*" not in s_json.ALLOWED_ORIGINS
        assert "https://safe.app" in s_json.ALLOWED_ORIGINS

    def test_get_effective_origins_includes_frontend_url(self):
        """get_effective_origins should incorporate FRONTEND_URL when provided."""
        s = Settings(
            ALLOWED_ORIGINS=["http://localhost:3000"],
            FRONTEND_URL="https://deepfake-ai.vercel.app/",
        )
        effective = s.get_effective_origins()
        assert "http://localhost:3000" in effective
        assert "https://deepfake-ai.vercel.app" in effective


# ─── 2. Health Check Probes ───────────────────────────────────────────────────

class TestHealthChecks:
    def test_root_health_check(self, client: TestClient):
        """GET /health must return status ok for load balancers."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        assert "version" in data

    def test_api_v1_health_check(self, client: TestClient):
        """GET /api/v1/health must return detailed system health."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        assert "model_loaded" in data
        assert "uptime_seconds" in data


# ─── 3. Ephemeral HMAC Signed Video Streams & Log Privacy ─────────────────────

class TestSignedVideoStreams:
    @pytest.fixture
    def test_session_clip(self, tmp_path, monkeypatch):
        """Fixture that configures local storage and creates a dummy clip."""
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("STORAGE_BACKEND", "local")
        monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(storage_dir))
        monkeypatch.setenv("REVIEWER_TOKEN", "super_secret_reviewer_token")
        monkeypatch.setenv("STREAM_SIGNING_KEY", "dedicated_stream_signing_key_492")
        monkeypatch.setattr(settings, "REVIEWER_TOKEN", "super_secret_reviewer_token")
        monkeypatch.setattr(settings, "STREAM_SIGNING_KEY", "dedicated_stream_signing_key_492")

        session_id = "test-session-stream-001"
        clip_data = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
        meta = {
            "session_id": session_id,
            "sha256": hashlib.sha256(clip_data).hexdigest(),
        }

        backend = LocalFilesystemBackend(root=storage_dir)
        backend.write(session_id, clip_data, meta)

        # Patch get_storage to return our test backend
        with patch("app.api.review.get_storage", return_value=backend), \
             patch("app.services.storage.get_storage", return_value=backend):
            yield session_id, clip_data, backend

    def test_clip_endpoint_returns_signed_url(self, client: TestClient, test_session_clip):
        """GET /api/v1/review/{session_id}/clip returns a valid HMAC-signed URL with exp and sig."""
        session_id, _, _ = test_session_clip
        response = client.get(
            f"/api/v1/review/{session_id}/clip",
            headers={"X-Reviewer-Token": "super_secret_reviewer_token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert "exp=" in data["url"]
        assert "sig=" in data["url"]
        assert data["url_type"] == "internal_stream"
        assert "sha256" in data

    def test_signed_stream_playback_success(self, client: TestClient, test_session_clip):
        """Video stream can be played via valid HMAC signature without master reviewer token."""
        session_id, expected_bytes, _ = test_session_clip
        exp, sig = generate_stream_signature(session_id, expires_seconds=300, key="dedicated_stream_signing_key_492")

        response = client.get(f"/api/v1/review/{session_id}/stream?exp={exp}&sig={sig}")
        assert response.status_code == 200
        assert response.content == expected_bytes
        assert response.headers.get("content-type") == "video/mp4"

    def test_signed_stream_tampered_signature_rejected(self, client: TestClient, test_session_clip):
        """Tampering with the HMAC signature returns 403 Forbidden."""
        session_id, _, _ = test_session_clip
        exp, sig = generate_stream_signature(session_id, expires_seconds=300, key="dedicated_stream_signing_key_492")
        tampered_sig = sig[:-4] + "ffff"

        response = client.get(f"/api/v1/review/{session_id}/stream?exp={exp}&sig={tampered_sig}")
        assert response.status_code == 403
        assert "Invalid or expired stream signature" in response.text

    def test_signed_stream_expired_timestamp_rejected(self, client: TestClient, test_session_clip):
        """Expired stream signature timestamp returns 403 Forbidden."""
        session_id, _, _ = test_session_clip
        expired_exp = int(time.time()) - 60  # expired 1 minute ago
        key = "dedicated_stream_signing_key_492"
        sig = hmac.new(key.encode("utf-8"), f"{session_id}:{expired_exp}".encode("utf-8"), hashlib.sha256).hexdigest()

        response = client.get(f"/api/v1/review/{session_id}/stream?exp={expired_exp}&sig={sig}")
        assert response.status_code == 403
        assert "Invalid or expired stream signature" in response.text

    def test_stream_header_auth_fallback(self, client: TestClient, test_session_clip):
        """Stream endpoint also allows direct header authentication without query params."""
        session_id, expected_bytes, _ = test_session_clip
        response = client.get(
            f"/api/v1/review/{session_id}/stream",
            headers={"X-Reviewer-Token": "super_secret_reviewer_token"},
        )
        assert response.status_code == 200
        assert response.content == expected_bytes

    def test_stream_unauthorized_rejected(self, client: TestClient, test_session_clip):
        """Stream endpoint rejects unauthenticated access when neither signature nor header is provided."""
        session_id, _, _ = test_session_clip
        response = client.get(f"/api/v1/review/{session_id}/stream")
        assert response.status_code in (401, 403)

    def test_stream_access_audit_logging(self, client: TestClient, test_session_clip, tmp_path, monkeypatch):
        """Both signed URL stream and header stream access write audit events."""
        session_id, _, _ = test_session_clip
        chain_path = tmp_path / "audit_chain.jsonl"
        monkeypatch.setattr("app.api.review.get_audit_chain_path", lambda: chain_path)
        monkeypatch.setattr("app.services.audit.get_audit_chain_path", lambda: chain_path)

        # 1. Access via signed URL
        exp, sig = generate_stream_signature(session_id, expires_seconds=300, key="dedicated_stream_signing_key_492")
        res1 = client.get(f"/api/v1/review/{session_id}/stream?exp={exp}&sig={sig}")
        assert res1.status_code == 200

        # 2. Access via header
        res2 = client.get(
            f"/api/v1/review/{session_id}/stream",
            headers={"X-Reviewer-Token": "super_secret_reviewer_token"},
        )
        assert res2.status_code == 200

        # Assert audit trail contains access events
        assert chain_path.exists()
        lines = [json.loads(line) for line in chain_path.read_text(encoding="utf-8").strip().split("\n") if line.strip()]
        access_events = [entry for entry in lines if entry.get("record_type") == "access"]
        assert len(access_events) >= 2


# ─── 4. Reviewer Authentication Gating ────────────────────────────────────────

class TestReviewerAuthGating:
    def test_queue_missing_auth_header(self, client: TestClient, monkeypatch):
        """GET /api/v1/review/queue without token returns 401 Unauthorized."""
        monkeypatch.setenv("REVIEWER_TOKEN", "prod_token_xyz")
        response = client.get("/api/v1/review/queue")
        assert response.status_code == 401

    def test_queue_invalid_auth_header(self, client: TestClient, monkeypatch):
        """GET /api/v1/review/queue with invalid token returns 403 Forbidden."""
        monkeypatch.setenv("REVIEWER_TOKEN", "prod_token_xyz")
        response = client.get(
            "/api/v1/review/queue",
            headers={"X-Reviewer-Token": "wrong_token"},
        )
        assert response.status_code == 403

    def test_queue_valid_auth_header(self, client: TestClient, monkeypatch):
        """GET /api/v1/review/queue with valid token returns 200 OK."""
        monkeypatch.setenv("REVIEWER_TOKEN", "prod_token_xyz")
        response = client.get(
            "/api/v1/review/queue",
            headers={"X-Reviewer-Token": "prod_token_xyz"},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

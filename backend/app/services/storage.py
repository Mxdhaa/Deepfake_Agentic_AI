"""
storage.py
──────────
Abstract storage backend for raw session clips.

Design
──────
Every upload is written IMMEDIATELY on receipt — before any scoring runs.
The storage write and the sha256 hash both operate on the exact same raw
byte buffer that arrived over the wire. Scoring gets the same Python `bytes`
object (immutable), but conceptually the archival contract is independent
of the scoring pipeline.

Two concrete backends:

  LocalFilesystemBackend (STORAGE_BACKEND=local, default for dev/test)
    – Writes to data/storage/<session_id>/clip.<ext>
    – Presign returns a /api/v1/review/{session_id}/stream URL (served
      by the review router, not a real signed URL)

  MinioBackend (STORAGE_BACKEND=minio)
    – Writes to a MinIO / Cloudflare R2 bucket
    – Presign returns a real time-limited pre-signed GET URL
    – R2 swap: set MINIO_ENDPOINT to your R2 endpoint, credentials in env

Both implement the StorageBackend Protocol so the rest of the codebase
never imports a concrete class.

Security note
─────────────
The frontend MUST never receive bucket credentials directly.
All retrieval is mediated through GET /api/v1/review/{session_id}/clip
which auth-gates, logs the access event, then returns a short-lived URL
or streams bytes. The bucket is inaccessible from the public internet.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from app.utils.logging import get_logger

log = get_logger(__name__)


def get_stream_signing_key() -> str:
    """Read stream signing secret from config / env, falling back to REVIEWER_TOKEN or a static salt."""
    from app.core.config import settings
    key = settings.STREAM_SIGNING_KEY or os.getenv("STREAM_SIGNING_KEY") or settings.REVIEWER_TOKEN or os.getenv("REVIEWER_TOKEN") or "dev_stream_signing_secret_salt_39184"
    return key.strip()


def generate_stream_signature(session_id: str, expires_seconds: int = 600, key: Optional[str] = None) -> tuple[int, str]:
    """Generates (exp, sig) for an ephemeral HMAC-SHA256 signed video stream URL."""
    signing_key = key or get_stream_signing_key()
    exp = int(time.time()) + expires_seconds
    message = f"{session_id}:{exp}".encode("utf-8")
    sig = hmac.new(signing_key.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return exp, sig


def verify_stream_signature(session_id: str, exp: int, sig: str, key: Optional[str] = None) -> bool:
    """Verifies that the HMAC signature is valid and not expired."""
    current_time = int(time.time())
    if exp < current_time:
        return False
    signing_key = key or get_stream_signing_key()
    message = f"{session_id}:{exp}".encode("utf-8")
    expected_sig = hmac.new(signing_key.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_sig, sig)


# ─── Protocol (interface) ──────────────────────────────────────────────────────

@runtime_checkable
class StorageBackend(Protocol):
    def write(
        self,
        session_id: str,
        data: bytes,
        metadata: dict,
    ) -> str:
        """
        Write raw bytes under key=session_id. Returns the storage key.
        metadata is stored alongside the object (at minimum: sha256, timestamp).
        Must be called BEFORE any processing of data.
        """
        ...

    def read(self, session_id: str) -> bytes:
        """Return raw bytes for session_id. Raises KeyError if not found."""
        ...

    def presign(self, session_id: str, expires_seconds: int = 600) -> str:
        """
        Return a short-lived URL (or backend-mediated URL) for the stored clip.
        For LocalFilesystemBackend this is an internal API URL.
        For MinioBackend this is a real pre-signed S3 URL.
        """
        ...

    def exists(self, session_id: str) -> bool:
        """Return True if a clip for session_id exists in storage."""
        ...

    def read_metadata(self, session_id: str) -> dict:
        """Return the metadata dict stored alongside the clip."""
        ...


# ─── SHA-256 helper (used by both backends and the API layer) ─────────────────

def compute_sha256(data: bytes) -> str:
    """Return hex digest of SHA-256 of data. Call this on raw bytes BEFORE processing."""
    return hashlib.sha256(data).hexdigest()


# ─── Local Filesystem Backend ─────────────────────────────────────────────────

class LocalFilesystemBackend:
    """
    Stores clips as files under STORAGE_LOCAL_ROOT (default: data/storage/).
    Layout:
        data/storage/{session_id}/clip.bin       ← raw bytes
        data/storage/{session_id}/metadata.json  ← sha256, timestamp, filename, etc.

    Presign returns an internal API path — the review router streams the bytes.
    This backend requires no external services and is the default for dev/CI.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        env_root = os.getenv("STORAGE_LOCAL_ROOT")
        self.root = Path(root or env_root or "data/storage").resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        log.info("storage.local.init", root=str(self.root))

    def _clip_path(self, session_id: str) -> Path:
        return self.root / session_id / "clip.bin"

    def _meta_path(self, session_id: str) -> Path:
        return self.root / session_id / "metadata.json"

    def write(self, session_id: str, data: bytes, metadata: dict) -> str:
        session_dir = self.root / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # Write raw bytes atomically (temp → rename)
        clip_path = self._clip_path(session_id)
        tmp_path = clip_path.with_suffix(".tmp")
        tmp_path.write_bytes(data)
        tmp_path.rename(clip_path)

        # Write metadata
        full_meta = {
            **metadata,
            "session_id": session_id,
            "stored_at": datetime.now(timezone.utc).isoformat(),
            "size_bytes": len(data),
            "backend": "local",
        }
        self._meta_path(session_id).write_text(
            json.dumps(full_meta, indent=2), encoding="utf-8"
        )

        log.info(
            "storage.local.written",
            session_id=session_id,
            size_bytes=len(data),
            sha256=metadata.get("sha256", "?")[:16] + "...",
        )
        return session_id

    def read(self, session_id: str) -> bytes:
        path = self._clip_path(session_id)
        if not path.exists():
            raise KeyError(f"No clip found for session_id={session_id!r}")
        return path.read_bytes()

    def presign(self, session_id: str, expires_seconds: int = 600) -> str:
        """
        Returns an internal API URL with an ephemeral HMAC-SHA256 signature and expiry timestamp.
        """
        if not self.exists(session_id):
            raise KeyError(f"No clip found for session_id={session_id!r}")
        exp, sig = generate_stream_signature(session_id, expires_seconds)
        return f"/api/v1/review/{session_id}/stream?exp={exp}&sig={sig}"

    def exists(self, session_id: str) -> bool:
        return self._clip_path(session_id).exists()

    def read_metadata(self, session_id: str) -> dict:
        path = self._meta_path(session_id)
        if not path.exists():
            raise KeyError(f"No metadata found for session_id={session_id!r}")
        return json.loads(path.read_text(encoding="utf-8"))


# ─── MinIO / Cloudflare R2 Backend ────────────────────────────────────────────

class MinioBackend:
    """
    Stores clips in a MinIO bucket (or Cloudflare R2 via S3-compatible API).

    Environment variables:
        MINIO_ENDPOINT      e.g. localhost:9000 or <account>.r2.cloudflarestorage.com
        MINIO_ACCESS_KEY    access key / client ID
        MINIO_SECRET_KEY    secret key
        MINIO_BUCKET        bucket name (default: liveness-clips)
        MINIO_SECURE        true | false (default: false for local MinIO)

    Presign returns a real time-limited pre-signed GET URL from MinIO/R2.

    Bucket access policy: DENY * from public internet.
    Only the backend service principal's credentials can read/write.
    Enforce this via bucket policy in MinIO Console or R2 dashboard.
    """

    def __init__(self) -> None:
        try:
            from minio import Minio  # type: ignore
            from minio.error import S3Error  # type: ignore
        except ImportError:
            raise RuntimeError(
                "MinIO backend requires 'minio' package. "
                "pip install minio  — or switch to STORAGE_BACKEND=local"
            )

        self._Minio = Minio
        self._S3Error = S3Error
        endpoint  = os.environ["MINIO_ENDPOINT"]
        access    = os.environ["MINIO_ACCESS_KEY"]
        secret    = os.environ["MINIO_SECRET_KEY"]
        self.bucket = os.getenv("MINIO_BUCKET", "liveness-clips")
        secure = os.getenv("MINIO_SECURE", "false").lower() == "true"

        self.client = Minio(endpoint, access_key=access, secret_key=secret, secure=secure)
        self._ensure_bucket()
        log.info("storage.minio.init", endpoint=endpoint, bucket=self.bucket)

    def _ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
            log.info("storage.minio.bucket_created", bucket=self.bucket)

    def _clip_key(self, session_id: str) -> str:
        return f"clips/{session_id}/clip.bin"

    def _meta_key(self, session_id: str) -> str:
        return f"clips/{session_id}/metadata.json"

    def write(self, session_id: str, data: bytes, metadata: dict) -> str:
        import io
        full_meta = {
            **metadata,
            "session_id": session_id,
            "stored_at": datetime.now(timezone.utc).isoformat(),
            "size_bytes": len(data),
            "backend": "minio",
        }

        # Write raw bytes
        buf = io.BytesIO(data)
        self.client.put_object(
            self.bucket, self._clip_key(session_id),
            buf, length=len(data),
            content_type="application/octet-stream",
            metadata={"x-amz-meta-sha256": metadata.get("sha256", "")},
        )

        # Write metadata as JSON object
        meta_bytes = json.dumps(full_meta, indent=2).encode()
        self.client.put_object(
            self.bucket, self._meta_key(session_id),
            io.BytesIO(meta_bytes), length=len(meta_bytes),
            content_type="application/json",
        )

        log.info(
            "storage.minio.written",
            session_id=session_id,
            size_bytes=len(data),
            sha256=metadata.get("sha256", "?")[:16] + "...",
        )
        return session_id

    def read(self, session_id: str) -> bytes:
        try:
            resp = self.client.get_object(self.bucket, self._clip_key(session_id))
            return resp.read()
        except self._S3Error as e:
            if e.code == "NoSuchKey":
                raise KeyError(f"No clip found for session_id={session_id!r}")
            raise

    def presign(self, session_id: str, expires_seconds: int = 600) -> str:
        from datetime import timedelta
        url = self.client.presigned_get_object(
            self.bucket,
            self._clip_key(session_id),
            expires=timedelta(seconds=expires_seconds),
        )
        return url

    def exists(self, session_id: str) -> bool:
        try:
            self.client.stat_object(self.bucket, self._clip_key(session_id))
            return True
        except self._S3Error:
            return False

    def read_metadata(self, session_id: str) -> dict:
        try:
            resp = self.client.get_object(self.bucket, self._meta_key(session_id))
            return json.loads(resp.read().decode())
        except self._S3Error as e:
            if e.code == "NoSuchKey":
                raise KeyError(f"No metadata found for session_id={session_id!r}")
            raise


# ─── Backend factory (singleton) ──────────────────────────────────────────────

_backend: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """
    Return the active storage backend singleton.
    Selected by STORAGE_BACKEND env var: "local" (default) or "minio".
    """
    global _backend
    if _backend is None:
        backend_type = os.getenv("STORAGE_BACKEND", "local").lower()
        if backend_type == "minio":
            _backend = MinioBackend()
        else:
            _backend = LocalFilesystemBackend()
        log.info("storage.backend_selected", type=backend_type)
    return _backend


def reset_storage(backend: StorageBackend | None = None) -> None:
    """
    Override the singleton — used in tests to inject an in-memory backend
    or a fresh LocalFilesystemBackend pointed at a temp directory.
    """
    global _backend
    _backend = backend

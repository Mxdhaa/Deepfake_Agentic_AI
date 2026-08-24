"""
App configuration using pydantic-settings.
Values are read from environment variables / .env file.
"""

import json
from typing import List, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── General ───────────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # ── CORS ──────────────────────────────────────────────────────────────────
    FRONTEND_URL: Optional[str] = None
    ALLOWED_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    VERCEL_PREVIEW_REGEX: str = r"^https:\/\/.*\.vercel\.app$"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Union[str, List[str], None]) -> List[str]:
        if v is None:
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return ["http://localhost:3000", "http://127.0.0.1:3000"]
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        filtered = [str(item).strip() for item in parsed if str(item).strip() and str(item).strip() != "*"]
                        return filtered if filtered else ["http://localhost:3000", "http://127.0.0.1:3000"]
                except Exception:
                    pass
            filtered = [orig.strip() for orig in v.split(",") if orig.strip() and orig.strip() != "*"]
            return filtered if filtered else ["http://localhost:3000", "http://127.0.0.1:3000"]
        elif isinstance(v, list):
            filtered = [str(orig).strip() for orig in v if str(orig).strip() and str(orig).strip() != "*"]
            return filtered if filtered else ["http://localhost:3000", "http://127.0.0.1:3000"]
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    def get_effective_origins(self) -> List[str]:
        """Returns ALLOWED_ORIGINS plus FRONTEND_URL if specified."""
        origins = list(self.ALLOWED_ORIGINS)
        if self.FRONTEND_URL and self.FRONTEND_URL.strip() and self.FRONTEND_URL.strip() != "*":
            clean_frontend = self.FRONTEND_URL.strip().rstrip("/")
            if clean_frontend not in origins:
                origins.append(clean_frontend)
        return origins

    # ── Model ─────────────────────────────────────────────────────────────────
    MODEL_PATH: str = "models/detector.pth"
    MODEL_DEVICE: str = "cpu"          # "cuda" | "mps" | "cpu"
    CONFIDENCE_THRESHOLD: float = 0.5

    # ── Liveness ──────────────────────────────────────────────────────────────
    LIVENESS_CONFIG_PATH: str = ""     # leave blank to use bundled liveness_config.yaml

    # ── Storage (Phase 2.1) ───────────────────────────────────────────────────
    STORAGE_BACKEND: str = "local"     # "local" | "minio"
    STORAGE_LOCAL_ROOT: str = "data/storage"
    MINIO_ENDPOINT: str = ""
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "liveness-clips"
    MINIO_SECURE: str = "false"

    # ── Access control ────────────────────────────────────────────────────────
    REVIEWER_TOKEN: str = ""           # set in .env; empty = auth disabled (dev only)
    STREAM_SIGNING_KEY: str = ""       # dedicated HMAC key for short-lived stream tokens (falls back to REVIEWER_TOKEN)
    REVIEW_URL_EXPIRY_SECONDS: int = 600

    # ── LangChain / LLM (optional enrichment) ─────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # ── Upload limits ─────────────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 50


settings = Settings()


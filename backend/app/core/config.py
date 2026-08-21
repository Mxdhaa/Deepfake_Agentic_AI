"""
App configuration using pydantic-settings.
Values are read from environment variables / .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


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
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # ── Model ─────────────────────────────────────────────────────────────────
    MODEL_PATH: str = "models/detector.pth"
    MODEL_DEVICE: str = "cpu"          # "cuda" | "mps" | "cpu"
    CONFIDENCE_THRESHOLD: float = 0.5

    # ── LangChain / LLM (optional enrichment) ─────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # ── Upload limits ─────────────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 50


settings = Settings()

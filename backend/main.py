"""
Deepfake Agentic AI — FastAPI Entry Point
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api.routes import router
from app.api.liveness import router as liveness_router
from app.api.review import router as review_router
from app.api.identity import router as identity_router
from app.api.agent import router as agent_router
from app.api.verification import router as verification_router
from app.utils.logging import get_logger, setup_logging
from app.core.config import settings

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup → yield → shutdown."""
    setup_logging()
    log.info("deepfake_agent.startup", version="0.1.0", env=settings.ENVIRONMENT)
    
    # Pre-warm OCR reader in background so user requests don't hit cold-start timeouts
    try:
        import threading
        from app.services.ocr_service import _get_ocr_reader
        threading.Thread(target=_get_ocr_reader, daemon=True).start()
    except Exception as exc:
        log.warning("ocr.prewarm_failed", error=str(exc))

    yield
    log.info("deepfake_agent.shutdown")


app = FastAPI(
    title="Deepfake Agentic AI",
    description=(
        "LangGraph-powered deepfake detection API. "
        "Upload an image or video and get a structured analysis report."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_effective_origins(),
    allow_origin_regex=settings.VERCEL_PREVIEW_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(router,              prefix="/api/v1")
app.include_router(liveness_router,     prefix="/api/v1")
app.include_router(review_router,       prefix="/api/v1")
app.include_router(identity_router,     prefix="/api/v1")
app.include_router(agent_router,        prefix="/api/v1")
app.include_router(verification_router, prefix="/api/v1")
app.include_router(verification_router)  # root mount for /verification/start directly


@app.get("/", tags=["Meta"])
async def root():
    """Root endpoint for probe verification."""
    return {
        "status": "online",
        "service": "ChainProof Deepfake Agentic AI Backend",
        "version": "0.1.0",
        "health": "/health",
        "docs": "/docs",
    }


@app.get("/health", tags=["Meta"])
async def health_check():
    """Quick liveness probe for load balancers / Vercel rewrites."""
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )

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
from app.utils.logging import get_logger, setup_logging
from app.core.config import settings

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup → yield → shutdown."""
    setup_logging()
    log.info("deepfake_agent.startup", version="0.1.0", env=settings.ENVIRONMENT)
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
app.include_router(router,          prefix="/api/v1")
app.include_router(liveness_router, prefix="/api/v1")
app.include_router(review_router,   prefix="/api/v1")
app.include_router(identity_router, prefix="/api/v1")
app.include_router(agent_router,    prefix="/api/v1")


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

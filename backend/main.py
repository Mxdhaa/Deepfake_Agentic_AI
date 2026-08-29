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
    
    # Load and explicitly log active runtime configuration to prevent silent config drift
    try:
        from app.services.liveness import get_liveness_config
        from app.services.identity import get_identity_config
        live_cfg = get_liveness_config()
        id_cfg = get_identity_config()
        
        seq_motion = live_cfg.get("sequential_motion", {})
        live_thresh = live_cfg.get("thresholds", {})
        id_thresh = id_cfg.get("thresholds", {})
        
        log.info(
            "config.active_runtime_thresholds",
            config_versions={"liveness": live_cfg.get("config_version"), "identity": id_cfg.get("config_version")},
            sequential_motion={
                "turn_dx_min": seq_motion.get("turn_dx_min"),
                "nod_dy_min": seq_motion.get("nod_dy_min"),
                "min_excursion_mag": seq_motion.get("min_excursion_mag"),
                "min_peak_sustain_frames": seq_motion.get("min_peak_sustain_frames"),
                "flow_magnitude_min": seq_motion.get("flow_magnitude_min"),
            },
            biometric_cutoffs={
                "similarity_pass": id_thresh.get("similarity_pass"),
                "similarity_fail": id_thresh.get("similarity_fail"),
            },
            anomaly_cutoffs={
                "deepfake_borderline": live_thresh.get("deepfake_borderline"),
                "deepfake_fail": live_thresh.get("deepfake_fail"),
            },
        )
    except Exception as cfg_exc:
        log.warning("config.startup_inspect_failed", error=str(cfg_exc))

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
    """Quick liveness probe with runtime config snapshot to prevent silent drift."""
    try:
        from app.services.liveness import get_liveness_config
        from app.services.identity import get_identity_config
        live_cfg = get_liveness_config()
        id_cfg = get_identity_config()
        return {
            "status": "ok",
            "version": "0.1.0",
            "active_thresholds": {
                "sequential_motion": live_cfg.get("sequential_motion", {}),
                "liveness_thresholds": live_cfg.get("thresholds", {}),
                "identity_thresholds": id_cfg.get("thresholds", {}),
            }
        }
    except Exception as exc:
        return {"status": "ok", "version": "0.1.0", "config_error": str(exc)}


@app.get("/api/v1/config/active", tags=["Meta"])
async def get_active_config():
    """Exposes fully resolved runtime YAML configurations for pre-demo sanity validation."""
    from app.services.liveness import get_liveness_config
    from app.services.identity import get_identity_config
    return {
        "liveness": get_liveness_config(),
        "identity": get_identity_config(),
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )

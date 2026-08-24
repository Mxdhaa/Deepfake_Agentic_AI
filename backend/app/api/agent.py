"""
agent.py — Stage 3 Agent & Pipeline API Router
──────────────────────────────────────────────
Mounts at: /api/v1/agent and /api/v1/pipeline

Endpoints:
    POST /api/v1/agent/investigate     — Run Stage 3 LangGraph investigation on raw record
    GET  /api/v1/agent/review-queue    — Auth-gated list of cases pending human review
    GET  /api/v1/agent/review-queue/{id}— Auth-gated case detail lookup
    POST /api/v1/pipeline/evaluate     — Full multi-stage pipeline evaluation
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.agent.investigation import run_investigation_agent
from app.agent.sandbox import (
    AgentInvestigationResult,
    sanitize_onboarding_record,
)
from app.services.pipeline import evaluate_onboarding_pipeline
from app.services.review_queue import get_case, list_pending_cases
from app.utils.logging import get_logger

log = get_logger(__name__)
router = APIRouter(tags=["Agent & Pipeline"])


# ─── Auth Helper ──────────────────────────────────────────────────────────────

def _authenticate_reviewer(token_header: Optional[str]) -> str:
    """
    Reviewer auth gate:
      - Returns reviewer ID if valid.
      - Raises 401 if token is missing.
      - Raises 403 if token is present but does not match REVIEWER_ACCESS_TOKEN.
    """
    configured_token = os.getenv("REVIEWER_ACCESS_TOKEN")
    if not configured_token:
        # Dev fallback when auth is disabled in dev environment
        return "reviewer:default"

    if not token_header:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide 'X-Reviewer-Token' header.",
        )

    if token_header.strip() != configured_token.strip():
        raise HTTPException(
            status_code=403,
            detail="Forbidden. Invalid reviewer token.",
        )

    return "reviewer:authorized"


# ─── Schemas ──────────────────────────────────────────────────────────────────

class RawRecordPayload(BaseModel):
    session_id: Optional[str] = None
    kin_token: Optional[str] = None
    legal_name: Optional[str] = None
    device_id: Optional[str] = None
    webrtc_jitter_ms: Optional[float] = None
    cosine_similarity_score: Optional[float] = None
    registry_velocity_6hr: Optional[int] = None
    challenge_match: Optional[bool] = None
    deepfake_score: Optional[float] = None
    blink_rate_bpm: Optional[float] = None
    av_sync_ms: Optional[float] = None
    stage1_decision: Optional[str] = None
    stage2_decision: Optional[str] = None


class PipelineEvaluateResponse(BaseModel):
    session_id: str
    kin_token: str
    legal_name: str
    stage1_decision: str
    stage2_decision: str
    escalated_to_stage3: bool
    stage3_result: Optional[Dict[str, Any]] = None
    status: str
    final_decision: str
    reason: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post(
    "/agent/investigate",
    response_model=AgentInvestigationResult,
    summary="Run Stage 3 LangGraph Investigation Agent",
    description=(
        "Sanitizes raw record via the sandbox parser, executes the 2 bound tools, "
        "synthesizes human dossier, seals audit trace into the hash chain, and routes to queue if unresolved."
    ),
)
async def investigate_endpoint(
    payload: RawRecordPayload,
    request: Request,
) -> AgentInvestigationResult:
    ip = request.client.host if (request and request.client) else "unknown"
    sanitized = sanitize_onboarding_record(payload.model_dump(exclude_none=True))
    result = run_investigation_agent(sanitized, ip=ip)
    return result


@router.get(
    "/agent/review-queue",
    summary="List pending human review cases (Auth-Gated)",
)
async def list_review_queue_endpoint(
    x_reviewer_token: Optional[str] = Header(None, alias="X-Reviewer-Token"),
) -> List[Dict[str, Any]]:
    _authenticate_reviewer(x_reviewer_token)
    return list_pending_cases(status="pending_review")


@router.get(
    "/agent/review-queue/{case_id}",
    summary="Get case details by ID (Auth-Gated)",
)
async def get_review_case_endpoint(
    case_id: str,
    x_reviewer_token: Optional[str] = Header(None, alias="X-Reviewer-Token"),
) -> Dict[str, Any]:
    _authenticate_reviewer(x_reviewer_token)
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id!r} not found in review queue.")
    return case


@router.post(
    "/agent/evaluate",
    response_model=PipelineEvaluateResponse,
    summary="Evaluate full multi-stage onboarding pipeline",
)
@router.post(
    "/pipeline/evaluate",
    response_model=PipelineEvaluateResponse,
    summary="Evaluate full multi-stage onboarding pipeline",
)
async def evaluate_pipeline_endpoint(
    payload: RawRecordPayload,
    request: Request,
) -> PipelineEvaluateResponse:
    ip = request.client.host if (request and request.client) else "unknown"
    result = evaluate_onboarding_pipeline(payload.model_dump(exclude_none=True), ip=ip)
    return PipelineEvaluateResponse(**result)

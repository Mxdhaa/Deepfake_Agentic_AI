"""
verification.py — Verification REST API Router
───────────────────────────────────────────────
Mounts at: /api/v1/verification and /verification

Endpoints:
    POST /verification/start               — Initialize session with CKYC lookup & Already-verified shortcut
    GET  /verification/{referenceId}/status — Retrieve full session state for UI reconstruction
    GET  /verification/lookup              — Find session by CKYC number
    POST /verification/{referenceId}/otp/send    — Send 6-digit phone OTP
    POST /verification/{referenceId}/otp/verify  — Validate phone OTP
    POST /verification/{referenceId}/document    — Upload ID document with OCR cross-check
    POST /verification/{referenceId}/liveness    — Submit live camera challenge & 1:1 face match
    POST /verification/{referenceId}/finalize    — 10-signal decision aggregation & registry update
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from app.models.verification import (
    DocumentVerificationResponse,
    FinalizeVerificationResponse,
    LivenessVerificationResponse,
    SendOtpResponse,
    StartVerificationRequest,
    StartVerificationResponse,
    VerificationStatusResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
)
from app.services.kyc_registry import get_kyc_registry
from app.services.verification_service import get_verification_service
from app.utils.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/verification", tags=["Identity Verification"])


# ── 1. Start Verification ─────────────────────────────────────────────────────

@router.post(
    "/start",
    response_model=StartVerificationResponse,
    summary="Initialize verification session with CKYC lookup",
    responses={
        404: {
            "description": "Identity not found in CKYC registry",
            "content": {
                "application/json": {
                    "example": {
                        "error": "IDENTITY_NOT_FOUND",
                        "message": "We couldn't find a matching identity record. Please check your details.",
                    }
                }
            },
        }
    },
)
async def start_verification(payload: StartVerificationRequest) -> Any:
    legal_name = payload.get_legal_name()
    dob = payload.get_date_of_birth()
    ckyc = payload.get_ckyc_number()

    if not legal_name or not dob or not ckyc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_PAYLOAD",
                "message": "Legal name, date of birth (YYYY-MM-DD), and CKYC number are required.",
            },
        )

    registry = get_kyc_registry()
    matched_record = registry.match_identity(legal_name, dob, ckyc)

    if not matched_record:
        log.warning("verification.start.identity_not_found", ckyc=ckyc, name=legal_name)
        return JSONResponse(
            status_code=404,
            content={
                "error": "IDENTITY_NOT_FOUND",
                "message": "We couldn't find a matching identity record. Please check your details.",
            },
        )

    service = get_verification_service()

    # CHANGE 1 — Already-verified shortcut
    if matched_record.verification_status == "VERIFIED":
        log.info("verification.start.already_verified", ckyc=ckyc)
        verified_session = service.create_verified_session(matched_record)
        return {
            "referenceId": verified_session.reference_id,
            "status": "ALREADY_VERIFIED",
            "message": "This identity has already completed verification. No further KYC is required.",
            "maskedPhone": matched_record.registered_phone[:4] + " ******" + matched_record.registered_phone[-4:],
            "stages_completed": ["IDENTITY_MATCH", "PHONE_OTP", "DOCUMENT", "LIVENESS", "VERIFIED"],
        }

    # Create new IN_PROGRESS session
    session = service.create_session(matched_record)
    masked_phone = session.registered_phone[:4] + " ******" + session.registered_phone[-4:]

    return {
        "referenceId": session.reference_id,
        "status": session.status,
        "message": "Identity record confirmed. Proceed to OTP verification.",
        "maskedPhone": masked_phone,
    }


# ── 2. Get Verification Status ────────────────────────────────────────────────

@router.get(
    "/{reference_id}/status",
    response_model=VerificationStatusResponse,
    summary="Retrieve session state for UI reconstruction",
)
async def get_session_status(reference_id: str) -> Any:
    service = get_verification_service()
    session = service.get_session(reference_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail={"error": "SESSION_NOT_FOUND", "message": f"Verification session '{reference_id}' not found."},
        )

    return {
        "referenceId": session.reference_id,
        "ckycNumber": session.ckyc_number,
        "legalName": session.legal_name,
        "status": session.status,
        "createdAt": session.created_at,
        "updatedAt": session.updated_at,
        "phoneVerified": session.phone_verified,
        "documentMatch": session.document_match,
        "faceMatch": session.face_match,
        "livenessResult": session.liveness_result,
        "deepfakeResult": session.deepfake_result,
        "finalDecision": session.final_decision,
        "finalReason": session.final_reason,
        "decisionTable": session.decision_table,
        "documentDetails": session.document_details,
    }


# ── 3. Lookup Session by CKYC ─────────────────────────────────────────────────

@router.get(
    "/lookup",
    summary="Lookup active verification session by CKYC number",
)
async def lookup_by_ckyc(ckycNumber: str = Query(..., description="CKYC Number e.g. CKYC-10001")) -> Any:
    registry = get_kyc_registry()
    rec = registry.lookup(ckycNumber)
    if not rec:
        raise HTTPException(status_code=404, detail={"error": "IDENTITY_NOT_FOUND", "message": "CKYC record not found."})

    service = get_verification_service()
    session = service.lookup_session_by_ckyc(ckycNumber)

    return {
        "ckycNumber": rec.ckyc_number,
        "legalName": rec.legal_name,
        "registryStatus": rec.verification_status,
        "referenceId": session.reference_id if session else None,
        "sessionStatus": session.status if session else rec.verification_status,
    }


# ── 4. OTP Endpoints ──────────────────────────────────────────────────────────

@router.post(
    "/{reference_id}/otp/send",
    response_model=SendOtpResponse,
    summary="Generate and send 6-digit phone OTP",
)
async def send_otp(reference_id: str) -> Any:
    service = get_verification_service()
    try:
        sent, masked, demo_otp = service.send_otp(reference_id)
        return {
            "sent": sent,
            "maskedPhone": masked,
            "demoOtp": demo_otp,
            "expiresInSeconds": 300,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "SESSION_NOT_FOUND", "message": str(exc)})


@router.post(
    "/{reference_id}/otp/verify",
    response_model=VerifyOtpResponse,
    summary="Verify submitted 6-digit phone OTP",
)
async def verify_otp(reference_id: str, payload: VerifyOtpRequest) -> Any:
    service = get_verification_service()
    try:
        verified, remaining, msg = service.verify_otp(reference_id, payload.otp)
        session = service.get_session(reference_id)
        status = session.status if session else "IN_PROGRESS"

        if not verified:
            return JSONResponse(
                status_code=400,
                content={
                    "verified": False,
                    "status": status,
                    "remainingAttempts": remaining,
                    "error": "INVALID_OTP",
                    "message": msg,
                },
            )

        return {
            "verified": True,
            "status": status,
            "remainingAttempts": remaining,
            "message": msg,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "SESSION_NOT_FOUND", "message": str(exc)})


# ── 5. Document Upload & OCR Cross-Check ──────────────────────────────────────

@router.post(
    "/{reference_id}/document",
    response_model=DocumentVerificationResponse,
    summary="Upload ID document and run OCR cross-check",
)
async def upload_document(
    reference_id: str,
    document: UploadFile = File(..., description="Passport, Driving License, or ID Card image"),
) -> Any:
    service = get_verification_service()
    file_bytes = await document.read()

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail={"error": "EMPTY_FILE", "message": "Uploaded document is empty."})

    try:
        matched, extracted, checks, err_msg = service.process_document(
            reference_id,
            file_bytes=file_bytes,
            filename=document.filename or "document.jpg",
        )

        if not matched:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "IDENTITY_DETAILS_MISMATCH",
                    "message": err_msg or "Document identity details mismatch with CKYC record.",
                    "referenceId": reference_id,
                    "documentMatch": False,
                    "extractedFields": extracted,
                    "fields": checks,
                },
            )

        return {
            "referenceId": reference_id,
            "documentMatch": True,
            "extractedFields": extracted,
            "fieldChecks": checks,
            "message": "Document verified and matched with CKYC registry.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "SESSION_NOT_FOUND", "message": str(exc)})


# ── 6. Liveness & Face Match ──────────────────────────────────────────────────

@router.post(
    "/{reference_id}/liveness",
    response_model=LivenessVerificationResponse,
    summary="Submit live camera challenge & 1:1 face match",
)
async def upload_liveness(
    reference_id: str,
    clip: UploadFile = File(..., description="Recorded video clip from liveness challenge"),
    challenge_type: Optional[str] = Form("blink_twice"),
) -> Any:
    service = get_verification_service()
    clip_bytes = await clip.read()

    if len(clip_bytes) == 0:
        raise HTTPException(status_code=400, detail={"error": "EMPTY_CLIP", "message": "Uploaded clip is empty."})

    try:
        res = service.process_liveness(reference_id, clip_bytes, challenge_type=challenge_type)
        return {
            "referenceId": res["referenceId"],
            "faceMatch": res["faceMatch"],
            "faceSimilarityScore": res["faceSimilarityScore"],
            "livenessResult": res["livenessResult"],
            "deepfakeResult": res["deepfakeResult"],
            "deepfakeScore": res["deepfakeScore"],
            "challengeMatch": res["challengeMatch"],
            "message": "Liveness analysis and face template matching completed.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "SESSION_NOT_FOUND", "message": str(exc)})


# ── 7. Finalize Verification ──────────────────────────────────────────────────

@router.post(
    "/{reference_id}/finalize",
    response_model=FinalizeVerificationResponse,
    summary="10-signal decision aggregation & registry update",
)
async def finalize_verification(reference_id: str) -> Any:
    service = get_verification_service()
    try:
        final_status, final_reason, dt, verified_at = service.finalize(reference_id)
        session = service.get_session(reference_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")

        return {
            "referenceId": session.reference_id,
            "ckycNumber": session.ckyc_number,
            "legalName": session.legal_name,
            "status": final_status,
            "finalDecision": final_status,
            "finalReason": final_reason,
            "decisionTable": dt,
            "verifiedAt": verified_at,
        }
    except ValueError as exc:
        err_msg = str(exc)
        if "STAGES_INCOMPLETE" in err_msg:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "STAGES_INCOMPLETE",
                    "message": err_msg,
                    "referenceId": reference_id,
                },
            )
        raise HTTPException(status_code=404, detail={"error": "SESSION_NOT_FOUND", "message": err_msg})

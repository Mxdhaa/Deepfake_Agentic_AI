"""
verification.py — Verification Data Models & Schemas
────────────────────────────────────────────────────
Defines CKYC Registry Record, Verification Session, Decision Matrix,
and all Request/Response contracts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


VerificationStatus = Literal[
    "NOT_STARTED",
    "PENDING",
    "IN_PROGRESS",
    "UNDER_REVIEW",
    "VERIFIED",
    "NOT_VERIFIED",
    "ALREADY_VERIFIED",
]

SignalStatus = Literal[
    "MATCH",
    "NO_MATCH",
    "VERIFIED",
    "FAILED",
    "NOT_ATTEMPTED",
    "CONFIRMED",
    "UNCERTAIN",
    "NO_ANOMALY",
    "FLAGGED",
]


class CkycRecord(BaseModel):
    ckyc_number: str = Field(..., description="Unique CKYC Identifier e.g. CKYC-10001")
    legal_name: str
    date_of_birth: str = Field(..., description="YYYY-MM-DD")
    registered_phone: str
    registered_face_reference: Optional[Dict[str, Any]] = None
    verification_status: VerificationStatus = "NOT_STARTED"
    created_at: str
    updated_at: str


class DecisionTable(BaseModel):
    identity_record: Literal["MATCH", "NO_MATCH", "NOT_ATTEMPTED"] = "NOT_ATTEMPTED"
    name: Literal["MATCH", "NO_MATCH", "NOT_ATTEMPTED"] = "NOT_ATTEMPTED"
    dob: Literal["MATCH", "NO_MATCH", "NOT_ATTEMPTED"] = "NOT_ATTEMPTED"
    ckyc_number: Literal["MATCH", "NO_MATCH", "NOT_ATTEMPTED"] = "NOT_ATTEMPTED"
    phone_otp: Literal["VERIFIED", "FAILED", "NOT_ATTEMPTED"] = "NOT_ATTEMPTED"
    document: Literal["MATCH", "NO_MATCH", "NOT_ATTEMPTED"] = "NOT_ATTEMPTED"
    document_face: Literal["MATCH", "NO_MATCH", "NOT_ATTEMPTED"] = "NOT_ATTEMPTED"
    live_face: Literal["MATCH", "UNCERTAIN", "NO_MATCH", "NOT_ATTEMPTED"] = "NOT_ATTEMPTED"
    liveness: Literal["CONFIRMED", "UNCERTAIN", "FAILED", "NOT_ATTEMPTED"] = "NOT_ATTEMPTED"
    deepfake_analysis: Literal["NO_ANOMALY", "FLAGGED", "NOT_ATTEMPTED"] = "NOT_ATTEMPTED"


class VerificationSession(BaseModel):
    reference_id: str = Field(..., description="Server-generated unique reference e.g. CP-A8B9C0D1")
    ckyc_number: str
    legal_name: str
    date_of_birth: str
    registered_phone: str
    status: VerificationStatus = "IN_PROGRESS"
    created_at: str
    updated_at: str
    
    # Stage 1: Identity & OTP
    otp_code: Optional[str] = None
    otp_expires_at: Optional[str] = None
    otp_attempts: int = 0
    otp_max_attempts: int = 5
    phone_verified: bool = False
    
    # Stage 2: Document Verification
    document_match: bool = False
    document_details: Optional[Dict[str, Any]] = None
    extracted_document_portrait_sha256: Optional[str] = None
    extracted_document_portrait_embedding: Optional[List[float]] = None
    
    # Stage 3: Liveness & Face Match
    face_match: Literal["MATCH", "UNCERTAIN", "NO_MATCH", "NOT_ATTEMPTED"] = "NOT_ATTEMPTED"
    face_similarity_score: float = 0.0
    liveness_result: Literal["CONFIRMED", "UNCERTAIN", "FAILED", "NOT_ATTEMPTED"] = "NOT_ATTEMPTED"
    deepfake_result: Literal["NO_ANOMALY", "FLAGGED", "NOT_ATTEMPTED"] = "NOT_ATTEMPTED"
    deepfake_score: float = 0.0
    detection_mode: Optional[str] = "heuristic_fallback"
    challenge_type: Optional[str] = None
    challenge_sequence: Optional[List[str]] = None
    detected_sequence: Optional[List[str]] = None
    challenge_match: bool = False
    
    # Decision Matrix & Finalization
    decision_table: DecisionTable = Field(default_factory=DecisionTable)
    final_decision: Optional[str] = None
    final_reason: Optional[str] = None

    # Agentic Reasoning & Escalation Layer
    retry_count: int = 0
    escalation_triggered: bool = False
    retry_requested: bool = False
    retry_note: Optional[str] = None
    agent_reasoning_trace: Optional[Dict[str, Any]] = None


# ─── API Request & Response Schemas ───────────────────────────────────────────

class StartVerificationRequest(BaseModel):
    legalName: Optional[str] = None
    legal_name: Optional[str] = None
    dateOfBirth: Optional[str] = None
    date_of_birth: Optional[str] = None
    ckycNumber: Optional[str] = None
    ckyc_number: Optional[str] = None

    def get_legal_name(self) -> str:
        return (self.legalName or self.legal_name or "").strip()

    def get_date_of_birth(self) -> str:
        return (self.dateOfBirth or self.date_of_birth or "").strip()

    def get_ckyc_number(self) -> str:
        return (self.ckycNumber or self.ckyc_number or "").strip().upper()


class StartVerificationResponse(BaseModel):
    referenceId: str
    status: VerificationStatus
    message: Optional[str] = None
    maskedPhone: Optional[str] = None
    stages_completed: Optional[List[str]] = None
    challengeSequence: Optional[List[str]] = None


class VerificationStatusResponse(BaseModel):
    referenceId: str
    ckycNumber: str
    legalName: str
    status: VerificationStatus
    createdAt: str
    updatedAt: str
    phoneVerified: bool
    documentMatch: bool
    faceMatch: str
    livenessResult: str
    deepfakeResult: str
    finalDecision: Optional[str] = None
    finalReason: Optional[str] = None
    decisionTable: DecisionTable
    documentDetails: Optional[Dict[str, Any]] = None
    detectionMode: Optional[str] = None
    challengeSequence: Optional[List[str]] = None
    retryCount: int = 0
    retryRequested: bool = False
    retryNote: Optional[str] = None
    agentReasoningTrace: Optional[Dict[str, Any]] = None


class SendOtpResponse(BaseModel):
    sent: bool
    maskedPhone: str
    demoOtp: Optional[str] = None
    expiresInSeconds: int = 300


class VerifyOtpRequest(BaseModel):
    otp: str


class VerifyOtpResponse(BaseModel):
    verified: bool
    status: VerificationStatus
    remainingAttempts: int
    message: Optional[str] = None


class DocumentVerificationResponse(BaseModel):
    referenceId: str
    documentMatch: bool
    extractedFields: Dict[str, Any]
    fieldChecks: Dict[str, Literal["match", "mismatch"]]
    message: str


class LivenessVerificationResponse(BaseModel):
    referenceId: str
    faceMatch: Literal["MATCH", "UNCERTAIN", "NO_MATCH"]
    faceSimilarityScore: float
    livenessResult: Literal["CONFIRMED", "UNCERTAIN", "FAILED"]
    deepfakeResult: Literal["NO_ANOMALY", "FLAGGED"]
    deepfakeScore: float
    challengeMatch: bool
    detectionMode: Optional[str] = "heuristic_fallback"
    detectedSequence: Optional[List[str]] = None
    expectedSequence: Optional[List[str]] = None
    message: str


class FinalizeVerificationResponse(BaseModel):
    referenceId: str
    ckycNumber: str
    legalName: str
    status: VerificationStatus
    finalDecision: str
    finalReason: str
    decisionTable: DecisionTable
    verifiedAt: Optional[str] = None
    retryRequested: bool = False
    retryCount: int = 0
    retryNote: Optional[str] = None
    challengeSequence: Optional[List[str]] = None
    agentReasoningTrace: Optional[Dict[str, Any]] = None

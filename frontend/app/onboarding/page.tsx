"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  FileCheck2,
  ScanFace,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  Upload,
  Camera,
  RotateCcw,
  ShieldCheck,
  Smartphone,
  KeyRound,
  RefreshCw,
  ExternalLink,
} from "lucide-react";
import {
  startVerification,
  getVerificationStatus,
  sendVerificationOtp,
  verifyVerificationOtp,
  uploadVerificationDocument,
  submitVerificationLiveness,
  finalizeVerification,
  VerificationSessionState,
  DecisionTable,
} from "@/lib/api";
import { useCamera } from "@/hooks/useCamera";

const GESTURE_INFO: Record<string, { label: string; instruction: string; icon: string }> = {
  left: { label: "Turn Left", instruction: "Turn head left and return to center.", icon: "⬅️" },
  right: { label: "Turn Right", instruction: "Turn head right and return to center.", icon: "➡️" },
  up: { label: "Look Up", instruction: "Tilt head upward and return to center.", icon: "⬆️" },
  down: { label: "Nod Down", instruction: "Tilt head downward and return to center.", icon: "⬇️" },
};

export default function OnboardingPage() {
  const [step, setStep] = useState<"details" | "otp" | "document" | "liveness" | "processing" | "result">("details");

  // Form State (Clean defaults for real applicants)
  const [legalName, setLegalName] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [ckycNumber, setCkycNumber] = useState("");
  const [referenceId, setReferenceId] = useState<string>("");
  const [maskedPhone, setMaskedPhone] = useState<string>("");
  const [otpInput, setOtpInput] = useState<string>("");
  const [demoOtp, setDemoOtp] = useState<string | null>(null);
  const [otpError, setOtpError] = useState<string | null>(null);
  const [remainingOtpAttempts, setRemainingOtpAttempts] = useState<number>(5);

  const [docFile, setDocFile] = useState<File | null>(null);
  const [documentResult, setDocumentResult] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [retryNotice, setRetryNotice] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Server-generated Sequential Challenge State
  const [challengeSequence, setChallengeSequence] = useState<string[]>(["left", "up", "right"]);

  // Dedicated Hardware Camera Hook with automatic track cleanup
  const {
    videoRef,
    isActive: streamActive,
    isRecording,
    recordedBlob,
    countdown,
    error: cameraError,
    startCamera,
    stopCamera,
    startRecording,
    setRecordedBlob,
  } = useCamera();

  // Full Server Session State (Restored on mount / refresh)
  const [sessionState, setSessionState] = useState<VerificationSessionState | null>(null);

  // 1. Reconstruct server state on mount if referenceId exists in sessionStorage
  useEffect(() => {
    try {
      const storedRef = sessionStorage.getItem("cp_reference_id");
      if (storedRef) {
        getVerificationStatus(storedRef)
          .then((state) => {
            setSessionState(state);
            setReferenceId(state.referenceId);
            setLegalName(state.legalName);
            setCkycNumber(state.ckycNumber);
            if (state.challengeSequence && state.challengeSequence.length > 0) {
              setChallengeSequence(state.challengeSequence);
            }

            if (state.status === "VERIFIED" || state.status === "NOT_VERIFIED" || state.status === "UNDER_REVIEW" || state.status === "ALREADY_VERIFIED") {
              setStep("result");
            } else if (!state.phoneVerified) {
              setStep("otp");
            } else if (!state.documentMatch) {
              setStep("document");
            } else {
              setStep("liveness");
            }
          })
          .catch((err) => console.warn("Could not restore verification session:", err));
      }
    } catch {}
  }, []);

  // Handle hardware camera activation on step change
  useEffect(() => {
    if (step === "liveness") {
      startCamera();
    } else {
      stopCamera();
    }
  }, [step, startCamera, stopCamera]);

  // ── Step 1: Start Verification ──────────────────────────────────────────────
  const handleStartVerification = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setIsSubmitting(true);

    try {
      const res = await startVerification({
        legalName: legalName.trim(),
        dateOfBirth: dateOfBirth.trim(),
        ckycNumber: ckycNumber.trim().toUpperCase(),
      });

      setReferenceId(res.referenceId);
      sessionStorage.setItem("cp_reference_id", res.referenceId);
      if (res.challengeSequence && res.challengeSequence.length > 0) {
        setChallengeSequence(res.challengeSequence);
      }

      // CHANGE 1: Already-verified shortcut
      if (res.status === "ALREADY_VERIFIED") {
        setSessionState({
          referenceId: res.referenceId,
          ckycNumber: ckycNumber.trim().toUpperCase(),
          legalName: legalName.trim(),
          status: "ALREADY_VERIFIED",
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          phoneVerified: true,
          documentMatch: true,
          faceMatch: "MATCH",
          livenessResult: "CONFIRMED",
          deepfakeResult: "NO_ANOMALY",
          finalDecision: "ALREADY_VERIFIED",
          finalReason: "This identity has already completed verification. No further KYC is required.",
          decisionTable: {
            identity_record: "MATCH",
            name: "MATCH",
            dob: "MATCH",
            ckyc_number: "MATCH",
            phone_otp: "VERIFIED",
            document: "MATCH",
            document_face: "MATCH",
            live_face: "MATCH",
            liveness: "CONFIRMED",
            deepfake_analysis: "NO_ANOMALY",
          },
        });
        setStep("result");
        return;
      }

      // Proceed with IN_PROGRESS flow -> Trigger Phone OTP
      setMaskedPhone(res.maskedPhone || "+91 ******4821");
      const otpRes = await sendVerificationOtp(res.referenceId);
      if (otpRes.demoOtp) {
        setDemoOtp(otpRes.demoOtp);
      }
      setStep("otp");
    } catch (err: any) {
      if (err.status === 404 || err.error === "IDENTITY_NOT_FOUND") {
        setErrorMsg("We couldn't find a matching identity record. Please check your Legal Name, Date of Birth, and CKYC Number.");
      } else {
        setErrorMsg(err.message || "Failed to initialize verification session. Please check your backend connection.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // ── Step 2: Verify OTP ──────────────────────────────────────────────────────
  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!otpInput.trim()) {
      setOtpError("Please enter the 6-digit OTP code.");
      return;
    }
    setOtpError(null);
    setIsSubmitting(true);

    try {
      const res = await verifyVerificationOtp(referenceId, otpInput.trim());
      if (res.verified) {
        setStep("document");
      }
    } catch (err: any) {
      setOtpError(err.message || "Invalid OTP code. Please try again.");
      if (err.remainingAttempts !== undefined) {
        setRemainingOtpAttempts(err.remainingAttempts);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResendOtp = async () => {
    setOtpError(null);
    try {
      const res = await sendVerificationOtp(referenceId);
      if (res.demoOtp) {
        setDemoOtp(res.demoOtp);
      }
    } catch (err: any) {
      setOtpError("Could not resend OTP. Please try again.");
    }
  };

  // ── Step 3: Document Upload & OCR Cross-Check ──────────────────────────────
  const handleDocumentSubmit = async () => {
    if (!docFile) {
      setErrorMsg("Please select an ID document image.");
      return;
    }
    setErrorMsg(null);
    setIsSubmitting(true);

    try {
      const res = await uploadVerificationDocument(referenceId, docFile);
      setDocumentResult(res);
      setStep("liveness");
    } catch (err: any) {
      setErrorMsg(err.message || "Document verification failed. Please ensure you upload a valid ID card containing a clear face portrait.");
    } finally {
      setIsSubmitting(false);
    }
  };

  // ── Step 4: Liveness & Finalization ─────────────────────────────────────────
  const handleSubmitLiveness = async () => {
    stopCamera();
    setStep("processing");
    setErrorMsg(null);

    try {
      // 1. Submit Liveness recording (server verifies against stored challengeSequence)
      if (recordedBlob) {
        await submitVerificationLiveness(referenceId, recordedBlob);
      }

      // 2. Finalize verification & aggregate 10-signal decision
      const finalRes = await finalizeVerification(referenceId);

      // Check if LangGraph agent triggered a one-time challenge retry
      if (finalRes.retryRequested && finalRes.challengeSequence) {
        setChallengeSequence(finalRes.challengeSequence);
        setRecordedBlob(null);
        setRetryNotice(
          finalRes.retryNote ||
            "Borderline biometric signals detected. A one-time retry challenge sequence has been generated. Please follow the new motion sequence."
        );
        setStep("liveness");
        return;
      }

      // 3. Refresh full session state
      const state = await getVerificationStatus(referenceId);
      setSessionState(state);
      setStep("result");
    } catch (err: any) {
      console.error("Verification error:", err);
      // Reconstruct state regardless
      try {
        const state = await getVerificationStatus(referenceId);
        setSessionState(state);
      } catch {}
      setStep("result");
    }
  };

  const handleRestart = () => {
    sessionStorage.removeItem("cp_reference_id");
    setReferenceId("");
    setSessionState(null);
    setRecordedBlob(null);
    setDocFile(null);
    setOtpInput("");
    setDemoOtp(null);
    setRetryNotice(null);
    setStep("details");
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: "#000000",
        color: "#FFFFFF",
        paddingTop: "6rem",
        paddingBottom: "5rem",
        paddingLeft: "6vw",
        paddingRight: "6vw",
      }}
    >
      <div style={{ maxWidth: "680px", margin: "0 auto" }}>
        {/* Header */}
        <div style={{ marginBottom: "2.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem" }}>
            <div>
              <span className="tech-pill" style={{ color: "#2F80FF", borderColor: "rgba(47, 128, 255, 0.3)" }}>
                STAGE-BASED IDENTITY RESOLUTION
              </span>
              <h1 style={{ fontSize: "2.25rem", fontWeight: 700, letterSpacing: "-0.03em", marginTop: "0.5rem" }}>
                Verify Your Identity
              </h1>
            </div>
            {referenceId && (
              <div style={{ background: "rgba(255,255,255,0.05)", padding: "6px 12px", borderRadius: "6px", border: "1px solid var(--border-color)", fontSize: "0.75rem", fontFamily: "var(--font-mono)" }}>
                REF: <strong style={{ color: "#2F80FF" }}>{referenceId}</strong>
              </div>
            )}
          </div>
          <p style={{ color: "var(--text-muted)", fontSize: "0.95rem", marginTop: "0.5rem" }}>
            Deterministic CKYC Registry Match • OTP Authentication • Biometric Anti-Spoofing
          </p>
        </div>

        {/* Stepper Navigation */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: "0.5rem",
            marginBottom: "2rem",
          }}
        >
          {[
            { id: "details", label: "01 DETAILS" },
            { id: "otp", label: "02 PHONE OTP" },
            { id: "document", label: "03 ID DOCUMENT" },
            { id: "liveness", label: "04 LIVENESS" },
          ].map((s, idx) => {
            const stepOrder = ["details", "otp", "document", "liveness", "processing", "result"];
            const currentIdx = stepOrder.indexOf(step);
            const isCompleted = currentIdx > idx;
            const isCurrent = step === s.id;

            return (
              <div
                key={s.id}
                style={{
                  padding: "0.6rem 0.5rem",
                  background: isCurrent ? "rgba(47, 128, 255, 0.1)" : "rgba(255, 255, 255, 0.02)",
                  border: isCurrent
                    ? "1px solid #2F80FF"
                    : isCompleted
                    ? "1px solid rgba(16, 185, 129, 0.4)"
                    : "1px solid var(--border-color)",
                  borderRadius: "4px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  fontSize: "0.72rem",
                  fontFamily: "var(--font-mono)",
                  color: isCurrent ? "#2F80FF" : isCompleted ? "#10B981" : "var(--text-muted)",
                }}
              >
                <span>{s.label}</span>
                {isCompleted && <CheckCircle2 size={12} style={{ color: "#10B981" }} />}
              </div>
            );
          })}
        </div>

        {/* ── STEP 1: IDENTITY DETAILS ────────────────────────────────────── */}
        {step === "details" && (
          <form
            onSubmit={handleStartVerification}
            style={{
              background: "#0a0a0a",
              border: "1px solid var(--border-color)",
              borderRadius: "6px",
              padding: "2rem",
              display: "flex",
              flexDirection: "column",
              gap: "1.5rem",
            }}
          >
            <div>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 600, color: "#FFFFFF", marginBottom: "0.35rem" }}>
                Identity Registration & Verification
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                Enter your full legal name, date of birth, and identity number as they appear on your government photo ID.
              </p>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.4rem" }}>
                Full Legal Name
              </label>
              <input
                type="text"
                required
                value={legalName}
                onChange={(e) => setLegalName(e.target.value)}
                placeholder="e.g. Medha Kumar"
                style={{
                  width: "100%",
                  background: "#000000",
                  border: "1px solid var(--border-color)",
                  borderRadius: "4px",
                  padding: "0.75rem 1rem",
                  color: "#FFFFFF",
                  fontSize: "0.9rem",
                  outline: "none",
                }}
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.4rem" }}>
                  Date of Birth
                </label>
                <input
                  type="text"
                  required
                  value={dateOfBirth}
                  onChange={(e) => setDateOfBirth(e.target.value)}
                  placeholder="YYYY-MM-DD (e.g. 2005-02-14)"
                  style={{
                    width: "100%",
                    background: "#000000",
                    border: "1px solid var(--border-color)",
                    borderRadius: "4px",
                    padding: "0.75rem 1rem",
                    color: "#FFFFFF",
                    fontSize: "0.9rem",
                    outline: "none",
                  }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.4rem" }}>
                  CKYC / National ID Number
                </label>
                <input
                  type="text"
                  required
                  value={ckycNumber}
                  onChange={(e) => setCkycNumber(e.target.value)}
                  placeholder="e.g. CKYC-10001"
                  style={{
                    width: "100%",
                    background: "#000000",
                    border: "1px solid var(--border-color)",
                    borderRadius: "4px",
                    padding: "0.75rem 1rem",
                    color: "#FFFFFF",
                    fontSize: "0.9rem",
                    fontFamily: "var(--font-mono)",
                    outline: "none",
                  }}
                />
              </div>
            </div>

            {errorMsg && (
              <div style={{ color: "#EF4444", fontSize: "0.825rem", display: "flex", alignItems: "center", gap: "8px", background: "rgba(239, 68, 68, 0.1)", padding: "10px 12px", borderRadius: "4px", border: "1px solid rgba(239, 68, 68, 0.3)" }}>
                <AlertCircle size={16} /> {errorMsg}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="btn-primary-blue"
              style={{ justifyContent: "center", padding: "0.85rem" }}
            >
              <span>{isSubmitting ? "Matching Registry..." : "Start Verification Session"}</span>
              <ArrowRight size={16} />
            </button>
          </form>
        )}

        {/* ── STEP 2: PHONE OTP VERIFICATION ──────────────────────────────── */}
        {step === "otp" && (
          <form
            onSubmit={handleVerifyOtp}
            style={{
              background: "#0a0a0a",
              border: "1px solid var(--border-color)",
              borderRadius: "6px",
              padding: "2rem",
              display: "flex",
              flexDirection: "column",
              gap: "1.5rem",
            }}
          >
            <div>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 600, color: "#FFFFFF", marginBottom: "0.35rem" }}>
                Phone Number Verification (MFA)
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                We sent a 6-digit one-time passcode to your registered phone number: <strong style={{ color: "#FFFFFF" }}>{maskedPhone}</strong>
              </p>
            </div>

            {demoOtp && (
              <div style={{ background: "rgba(47, 128, 255, 0.1)", border: "1px solid rgba(47, 128, 255, 0.4)", padding: "10px 14px", borderRadius: "6px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ fontSize: "0.8rem", color: "#93c5fd" }}>
                  🧪 <strong>Demo Mode OTP:</strong> <code>{demoOtp}</code>
                </div>
                <button
                  type="button"
                  onClick={() => setOtpInput(demoOtp)}
                  style={{ background: "#2F80FF", color: "white", border: "none", borderRadius: "4px", padding: "4px 8px", fontSize: "0.72rem", cursor: "pointer" }}
                >
                  Auto-fill
                </button>
              </div>
            )}

            <div>
              <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.4rem" }}>
                Enter 6-Digit Passcode
              </label>
              <input
                type="text"
                maxLength={6}
                required
                value={otpInput}
                onChange={(e) => setOtpInput(e.target.value.replace(/\D/g, ""))}
                placeholder="• • • • • •"
                style={{
                  width: "100%",
                  background: "#000000",
                  border: "1px solid var(--border-color)",
                  borderRadius: "4px",
                  padding: "0.75rem 1rem",
                  color: "#FFFFFF",
                  fontSize: "1.25rem",
                  textAlign: "center",
                  letterSpacing: "0.3em",
                  fontFamily: "var(--font-mono)",
                  outline: "none",
                }}
              />
            </div>

            {otpError && (
              <div style={{ color: "#EF4444", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "6px" }}>
                <AlertCircle size={14} /> {otpError}
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <button
                type="button"
                onClick={handleResendOtp}
                style={{ background: "transparent", border: "none", color: "#2F80FF", fontSize: "0.8rem", cursor: "pointer" }}
              >
                Resend Code
              </button>
              <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                {remainingOtpAttempts} attempts remaining
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting || otpInput.length < 6}
              className="btn-primary-blue"
              style={{ justifyContent: "center", padding: "0.85rem" }}
            >
              <span>{isSubmitting ? "Verifying..." : "Confirm & Proceed to Document Check"}</span>
              <ArrowRight size={16} />
            </button>
          </form>
        )}

        {/* ── STEP 3: ID DOCUMENT UPLOAD ──────────────────────────────────── */}
        {step === "document" && (
          <div
            style={{
              background: "#0a0a0a",
              border: "1px solid var(--border-color)",
              borderRadius: "6px",
              padding: "2rem",
              display: "flex",
              flexDirection: "column",
              gap: "1.5rem",
            }}
          >
            <div>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 600, color: "#FFFFFF", marginBottom: "0.35rem" }}>
                Government Photo ID
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                Upload your passport, national identity card, or driver's license for OCR matching.
              </p>
            </div>

            <label
              style={{
                border: "2px dashed var(--border-color)",
                borderRadius: "6px",
                padding: "2.5rem 1.5rem",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: "0.75rem",
                cursor: "pointer",
                backgroundColor: "rgba(255, 255, 255, 0.01)",
              }}
            >
              <input
                type="file"
                accept="image/*"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    setDocFile(e.target.files[0]);
                  }
                }}
                style={{ display: "none" }}
              />
              <div
                style={{
                  width: "48px",
                  height: "48px",
                  borderRadius: "50%",
                  background: "rgba(255, 255, 255, 0.05)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#FFFFFF",
                }}
              >
                <Upload size={20} />
              </div>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: "0.9rem", color: docFile ? "#FFFFFF" : "var(--text-muted)", fontWeight: 500 }}>
                  {docFile ? docFile.name : "Click to upload identity document"}
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginTop: "2px" }}>
                  PNG, JPG, or WebP up to 10MB
                </div>
              </div>
            </label>

            <div style={{ display: "flex", gap: "1rem" }}>
              <button
                onClick={() => setStep("otp")}
                className="btn-secondary"
                style={{ flex: 1 }}
              >
                ← Back
              </button>
              <button
                onClick={handleDocumentSubmit}
                disabled={isSubmitting || !docFile}
                className="btn-primary-blue"
                style={{ flex: 2, justifyContent: "center" }}
              >
                <span>{isSubmitting ? "Running OCR..." : "Continue to Liveness Check"}</span>
                <ArrowRight size={16} />
              </button>
            </div>

            {errorMsg && (
              <div style={{ color: "#EF4444", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "6px" }}>
                <AlertCircle size={14} /> {errorMsg}
              </div>
            )}
          </div>
        )}

        {/* ── STEP 4: CAMERA LIVENESS & ANTI-SPOOFING ─────────────────────── */}
        {step === "liveness" && (
          <div
            style={{
              background: "#0a0a0a",
              border: "1px solid var(--border-color)",
              borderRadius: "6px",
              padding: "2rem",
              display: "flex",
              flexDirection: "column",
              gap: "1.5rem",
            }}
          >
            <div>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 600, color: "#FFFFFF", marginBottom: "0.35rem" }}>
                Live Presence & Anti-Spoofing Challenge
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                Position your face inside the guide and perform the prompted action during the 5-second recording.
              </p>
            </div>

            {retryNotice && (
              <div
                style={{
                  background: "rgba(245, 158, 11, 0.12)",
                  border: "1px solid rgba(245, 158, 11, 0.4)",
                  borderRadius: "6px",
                  padding: "12px 14px",
                  fontSize: "0.85rem",
                  color: "#fbbf24",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <span>⚠️</span>
                <div>
                  <strong>Challenge Retry Active:</strong> {retryNotice}
                </div>
              </div>
            )}

            {/* Interactive Dynamic Sequential Challenge Card */}
            <div
              style={{
                background: "rgba(47, 128, 255, 0.08)",
                border: "1px solid rgba(47, 128, 255, 0.35)",
                borderRadius: "6px",
                padding: "1.25rem",
                display: "flex",
                flexDirection: "column",
                gap: "1rem",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
                <span className="tech-pill" style={{ padding: "2px 8px", fontSize: "0.65rem", color: "#2F80FF", borderColor: "rgba(47, 128, 255, 0.4)" }}>
                  RANDOMIZED SEQUENTIAL CHALLENGE ({challengeSequence.length} STEPS)
                </span>
                <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                  Perform in exact chronological order
                </span>
              </div>

              {/* Step Badges */}
              <div style={{ display: "grid", gridTemplateColumns: `repeat(${challengeSequence.length}, 1fr)`, gap: "0.75rem" }}>
                {challengeSequence.map((stepKey, idx) => {
                  const info = GESTURE_INFO[stepKey.toLowerCase()] || { label: stepKey, instruction: `Move ${stepKey}`, icon: "🔄" };
                  return (
                    <div
                      key={idx}
                      style={{
                        background: "rgba(255, 255, 255, 0.03)",
                        border: "1px solid rgba(255, 255, 255, 0.1)",
                        borderRadius: "6px",
                        padding: "0.75rem",
                        textAlign: "center",
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        gap: "4px",
                      }}
                    >
                      <span style={{ fontSize: "0.65rem", color: "#2F80FF", fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                        STEP {idx + 1}
                      </span>
                      <span style={{ fontSize: "1.5rem" }}>{info.icon}</span>
                      <strong style={{ fontSize: "0.85rem", color: "#FFFFFF" }}>{info.label}</strong>
                    </div>
                  );
                })}
              </div>

              <p style={{ fontSize: "0.8rem", color: "var(--text-readable)", margin: 0, textAlign: "center" }}>
                👉 Look directly at the camera, then perform smoothly in order:{" "}
                {challengeSequence.map((s, i) => `${i + 1}. ${(GESTURE_INFO[s.toLowerCase()]?.label || s)}`).join(" ➔ ")}
              </p>
            </div>

            {/* Video Box */}
            <div
              style={{
                position: "relative",
                width: "100%",
                height: "280px",
                background: "#000000",
                borderRadius: "4px",
                border: "1px solid var(--border-color)",
                overflow: "hidden",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                  transform: "scaleX(-1)",
                }}
              />

              <div
                style={{
                  position: "absolute",
                  width: "180px",
                  height: "230px",
                  border: isRecording ? "2px solid #2F80FF" : "2px dashed rgba(255, 255, 255, 0.3)",
                  borderRadius: "50%",
                  boxShadow: isRecording ? "0 0 25px rgba(47, 128, 255, 0.4)" : "none",
                  pointerEvents: "none",
                }}
              />

              {isRecording && (
                <>
                  <div
                    style={{
                      position: "absolute",
                      top: "1rem",
                      right: "1rem",
                      background: "rgba(239, 68, 68, 0.9)",
                      color: "#FFFFFF",
                      padding: "4px 10px",
                      borderRadius: "4px",
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <span className="animate-ping" style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#FFFFFF" }} />
                    RECORDING 00:0{countdown}
                  </div>

                  <div
                    style={{
                      position: "absolute",
                      bottom: "1rem",
                      left: "1.5rem",
                      right: "1.5rem",
                      background: "rgba(3, 7, 18, 0.85)",
                      border: "1px solid #2F80FF",
                      color: "#FFFFFF",
                      padding: "6px 12px",
                      borderRadius: "4px",
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.78rem",
                      textAlign: "center",
                      backdropFilter: "blur(8px)",
                      boxShadow: "0 0 15px rgba(47, 128, 255, 0.3)",
                    }}
                  >
                    Required Sequence:{" "}
                    <strong style={{ color: "#2F80FF" }}>
                      {challengeSequence.map((s, i) => `${i + 1}. ${(GESTURE_INFO[s.toLowerCase()]?.label || s)} ${GESTURE_INFO[s.toLowerCase()]?.icon || ""}`).join(" ➔ ")}
                    </strong>
                  </div>
                </>
              )}
            </div>

            {/* Controls */}
            <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
              {!recordedBlob && (
                <button
                  onClick={startRecording}
                  disabled={isRecording || !streamActive}
                  className="btn-primary-blue"
                  style={{ flex: 1, justifyContent: "center" }}
                >
                  <Camera size={16} />
                  <span>{isRecording ? `Recording (${countdown}s)...` : "Start 5s Challenge"}</span>
                </button>
              )}

              {recordedBlob && (
                <div style={{ display: "flex", gap: "1rem", width: "100%" }}>
                  <button
                    onClick={() => {
                      setRecordedBlob(null);
                      startCamera();
                    }}
                    className="btn-secondary"
                    style={{ display: "flex", alignItems: "center", gap: "6px" }}
                  >
                    <RotateCcw size={14} /> Retake
                  </button>
                  <button
                    onClick={handleSubmitLiveness}
                    className="btn-primary-blue"
                    style={{ flex: 1, justifyContent: "center" }}
                  >
                    <span>Finalize Verification</span>
                    <ArrowRight size={16} />
                  </button>
                </div>
              )}
            </div>

            {(errorMsg || cameraError) && (
              <div style={{ color: "#EF4444", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "6px" }}>
                <AlertCircle size={14} /> {errorMsg || cameraError}
              </div>
            )}
          </div>
        )}

        {/* ── STEP 5: PROCESSING ─────────────────────────────────────────── */}
        {step === "processing" && (
          <div
            style={{
              background: "#0a0a0a",
              border: "1px solid var(--border-color)",
              borderRadius: "6px",
              padding: "4rem 2rem",
              textAlign: "center",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "1.5rem",
            }}
          >
            <div
              style={{
                width: "48px",
                height: "48px",
                border: "3px solid rgba(47, 128, 255, 0.2)",
                borderTopColor: "#2F80FF",
                borderRadius: "50%",
                animation: "spin 1s linear infinite",
              }}
            />
            <div>
              <h3 style={{ fontSize: "1.25rem", fontWeight: 600, color: "#FFFFFF", marginBottom: "0.5rem" }}>
                Aggregating 10-Signal Decision
              </h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", maxWidth: "400px", margin: "0 auto" }}>
                Verifying facial embeddings, evaluating anti-spoofing challenge, and sealing record into the cryptographic registry.
              </p>
            </div>
          </div>
        )}

        {/* ── STEP 6: VERIFICATION RESULT & DOSSIER ───────────────────────── */}
        {step === "result" && sessionState && (
          <div
            style={{
              background: "#0a0a0a",
              border: "1px solid var(--border-color)",
              borderRadius: "6px",
              padding: "2.5rem 2rem",
              display: "flex",
              flexDirection: "column",
              gap: "2rem",
            }}
          >
            {/* Top Status Banner */}
            <div style={{ textAlign: "center" }}>
              <div
                style={{
                  width: "56px",
                  height: "56px",
                  borderRadius: "50%",
                  background:
                    sessionState.status === "VERIFIED" || sessionState.status === "ALREADY_VERIFIED"
                      ? "rgba(16, 185, 129, 0.1)"
                      : sessionState.status === "UNDER_REVIEW"
                      ? "rgba(245, 158, 11, 0.1)"
                      : "rgba(239, 68, 68, 0.1)",
                  color:
                    sessionState.status === "VERIFIED" || sessionState.status === "ALREADY_VERIFIED"
                      ? "#10B981"
                      : sessionState.status === "UNDER_REVIEW"
                      ? "#F59E0B"
                      : "#EF4444",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 1rem auto",
                }}
              >
                {sessionState.status === "VERIFIED" || sessionState.status === "ALREADY_VERIFIED" ? (
                  <CheckCircle2 size={32} />
                ) : sessionState.status === "UNDER_REVIEW" ? (
                  <ShieldCheck size={32} />
                ) : (
                  <AlertCircle size={32} />
                )}
              </div>

              <h2 style={{ fontSize: "1.75rem", fontWeight: 700, letterSpacing: "-0.02em", color: "#FFFFFF", marginBottom: "0.5rem" }}>
                {sessionState.status === "VERIFIED"
                  ? "You're verified"
                  : sessionState.status === "ALREADY_VERIFIED"
                  ? "Already Verified"
                  : sessionState.status === "UNDER_REVIEW"
                  ? "We're reviewing your application"
                  : "We couldn't verify you"}
              </h2>

              <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", maxWidth: "460px", margin: "0 auto" }}>
                {sessionState.finalReason || "All identity parameters, cryptographic OTP, and physiological liveness signals processed."}
              </p>
            </div>

            {/* 10-Signal Decision Table Breakdown */}
            <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid var(--border-color)", borderRadius: "6px", padding: "1.25rem" }}>
              <div style={{ fontSize: "0.8rem", fontFamily: "var(--font-mono)", color: "var(--text-muted)", marginBottom: "1rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                System Decision Breakdown (10 Signals)
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                {[
                  { label: "Identity Record", val: sessionState.decisionTable.identity_record },
                  { label: "Legal Name Match", val: sessionState.decisionTable.name },
                  { label: "Date of Birth Match", val: sessionState.decisionTable.dob },
                  { label: "CKYC Number Check", val: sessionState.decisionTable.ckyc_number },
                  { label: "Phone OTP", val: sessionState.decisionTable.phone_otp },
                  { label: "Document Authenticity", val: sessionState.decisionTable.document },
                  { label: "Document Face Crop", val: sessionState.decisionTable.document_face },
                  { label: "Live Face Match", val: sessionState.decisionTable.live_face },
                  { label: "Liveness Challenge", val: sessionState.decisionTable.liveness },
                  { label: "Deepfake Analysis", val: sessionState.decisionTable.deepfake_analysis },
                ].map(({ label, val }) => {
                  const isPass = val === "MATCH" || val === "VERIFIED" || val === "CONFIRMED" || val === "NO_ANOMALY";
                  const isUncertain = val === "UNCERTAIN";
                  return (
                    <div
                      key={label}
                      style={{
                        padding: "8px 12px",
                        background: "rgba(0,0,0,0.4)",
                        border: "1px solid rgba(255,255,255,0.05)",
                        borderRadius: "4px",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{label}</span>
                      <span
                        style={{
                          fontSize: "0.72rem",
                          fontFamily: "var(--font-mono)",
                          fontWeight: 600,
                          color: isPass ? "#10B981" : isUncertain ? "#F59E0B" : "#EF4444",
                        }}
                      >
                        {val}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Action Buttons */}
            <div style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
              <button onClick={handleRestart} className="btn-secondary">
                Verify Another Identity
              </button>
              <Link href="/review" className="btn-primary-blue">
                <span>View in Reviewer Console</span>
                <ExternalLink size={14} />
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

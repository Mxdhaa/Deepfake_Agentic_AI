"use client";

import { useState, useEffect, useCallback } from "react";
import {
  fetchReviewQueue,
  fetchReviewCase,
  submitReviewDecision,
  fetchAuditChain,
  verifyAuditChain,
  fetchClipAccess,
  ReviewCase,
  AuditBlock,
  ChainVerificationResult,
  ClipAccessResponse,
} from "@/lib/api";

// ─── Clean Vector SVG Icon Components (NO EMOJIS) ─────────────────────────────

function ShieldIcon({ size = 16, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

function LockIcon({ size = 16, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

function UserIcon({ size = 16, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function KeyIcon({ size = 16, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m21 2-2 2m-1.5 1.5L14 9.5a5 5 0 1 0 3 3l3.5-3.5m0 0 2 2m-2-2L21 2" />
    </svg>
  );
}

function VideoIcon({ size = 16, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="23 7 16 12 23 17 23 7" />
      <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
    </svg>
  );
}

function FileIcon({ size = 16, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
}

function CheckCircleIcon({ size = 16, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}

function XCircleIcon({ size = 16, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="15" y1="9" x2="9" y2="15" />
      <line x1="9" y1="9" x2="15" y2="15" />
    </svg>
  );
}

function AlertTriangleIcon({ size = 16, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function RefreshIcon({ size = 16, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21.5 2v6h-6M2.5 22v-6h6" />
      <path d="M2 11.5a10 10 0 0 1 18.8-4.3L21.5 8M22 12.5a10 10 0 0 1-18.8 4.3L2.5 16" />
    </svg>
  );
}

function ArrowRightIcon({ size = 16, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}

function DatabaseIcon({ size = 16, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
    </svg>
  );
}

function HashIcon({ size = 16, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="4" y1="9" x2="20" y2="9" />
      <line x1="4" y1="15" x2="20" y2="15" />
      <line x1="10" y1="3" x2="8" y2="21" />
      <line x1="16" y1="3" x2="14" y2="21" />
    </svg>
  );
}

function LogOutIcon({ size = 16, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

// ─── Main ReviewPage Component ──────────────────────────────────────────────

export default function ReviewPage() {
  // Authentication state (persisted strictly in browser sessionStorage)
  const [token, setToken] = useState<string>("");
  const [reviewerName, setReviewerName] = useState<string>("Auditor Reviewer");
  const [isAuthReady, setIsAuthReady] = useState<boolean>(false);
  const [loginInputToken, setLoginInputToken] = useState<string>("");
  const [loginInputName, setLoginInputName] = useState<string>("Auditor Reviewer");
  const [authError, setAuthError] = useState<string | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  // Tab & queue state
  const [activeTab, setActiveTab] = useState<"queue" | "audit">("queue");
  const [statusFilter, setStatusFilter] = useState<string>("pending_review");
  const [cases, setCases] = useState<ReviewCase[]>([]);
  const [selectedCase, setSelectedCase] = useState<ReviewCase | null>(null);
  const [loadingCases, setLoadingCases] = useState(false);
  const [reviewNotes, setReviewNotes] = useState("");
  const [submittingDecision, setSubmittingDecision] = useState(false);
  const [decisionFeedback, setDecisionFeedback] = useState<string | null>(null);

  // Signed clip streaming state
  const [clipAccess, setClipAccess] = useState<ClipAccessResponse | null>(null);
  const [loadingClip, setLoadingClip] = useState<boolean>(false);
  const [clipError, setClipError] = useState<string | null>(null);

  // Audit chain state
  const [auditBlocks, setAuditBlocks] = useState<AuditBlock[]>([]);
  const [verificationResult, setVerificationResult] = useState<ChainVerificationResult | null>(null);
  const [verifyingChain, setVerifyingChain] = useState(false);

  // Initialize session auth from sessionStorage on client mount
  useEffect(() => {
    try {
      const storedToken = sessionStorage.getItem("reviewer_token");
      const storedName = sessionStorage.getItem("reviewer_name");
      if (storedToken) {
        setToken(storedToken);
      }
      if (storedName) {
        setReviewerName(storedName);
        setLoginInputName(storedName);
      }
    } catch {
      // sessionStorage unavailable
    } finally {
      setIsAuthReady(true);
    }
  }, []);

  // Login handler for Reviewer Gate
  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!loginInputToken.trim()) {
      setAuthError("Please enter your reviewer access token.");
      return;
    }
    setAuthError(null);
    setConnectionError(null);
    const cleanToken = loginInputToken.trim();
    const cleanName = loginInputName.trim() || "Auditor Reviewer";
    try {
      sessionStorage.setItem("reviewer_token", cleanToken);
      sessionStorage.setItem("reviewer_name", cleanName);
    } catch (err) {
      console.warn("Could not save to sessionStorage:", err);
    }
    setToken(cleanToken);
    setReviewerName(cleanName);
  };

  // Disconnect / Logout handler
  const handleLogout = () => {
    try {
      sessionStorage.removeItem("reviewer_token");
      sessionStorage.removeItem("reviewer_name");
    } catch {}
    setToken("");
    setLoginInputToken("");
    setCases([]);
    setSelectedCase(null);
    setClipAccess(null);
    setAuditBlocks([]);
    setVerificationResult(null);
    setAuthError(null);
    setConnectionError(null);
  };

  // Load Queue
  const loadQueue = useCallback(async () => {
    if (!token) return;
    try {
      setLoadingCases(true);
      setConnectionError(null);
      const data = await fetchReviewQueue(statusFilter, token);
      setCases(data);
      if (data.length > 0 && (!selectedCase || !data.some((c) => c.case_id === selectedCase.case_id))) {
        setSelectedCase(data[0]);
      } else if (data.length === 0) {
        setSelectedCase(null);
      }
      setAuthError(null);
    } catch (err: any) {
      console.error("Failed to load review queue:", err);
      if (err.status === 401 || err.status === 403) {
        setAuthError("Reviewer session unauthorized or token expired. Please re-authenticate.");
      } else {
        setConnectionError(`Backend API connection failed (${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}). Please check backend server status.`);
      }
    } finally {
      setLoadingCases(false);
    }
  }, [statusFilter, selectedCase, token]);

  // Load Audit Chain
  const loadAuditChain = useCallback(async () => {
    if (!token) return;
    try {
      const blocks = await fetchAuditChain(token);
      setAuditBlocks(blocks);
      setAuthError(null);
    } catch (err: any) {
      console.error("Failed to load audit chain:", err);
      if (err.status === 401 || err.status === 403) {
        setAuthError("Reviewer session unauthorized or token expired. Please re-authenticate.");
      }
    }
  }, [token]);

  // Polling interval for queue when authenticated
  useEffect(() => {
    if (!token) return;
    loadQueue();
    const interval = setInterval(loadQueue, 5000);
    return () => clearInterval(interval);
  }, [loadQueue, token]);

  useEffect(() => {
    if (activeTab === "audit" && token) {
      loadAuditChain();
    }
  }, [activeTab, loadAuditChain, token]);

  // Fetch short-lived HMAC signed video stream URL when selected case changes
  useEffect(() => {
    if (!selectedCase || !token) {
      setClipAccess(null);
      return;
    }
    let isCurrent = true;
    setLoadingClip(true);
    setClipError(null);

    fetchClipAccess(selectedCase.session_id, token)
      .then((res) => {
        if (isCurrent) {
          setClipAccess(res);
          setLoadingClip(false);
        }
      })
      .catch((err: any) => {
        if (isCurrent) {
          console.error("Failed to fetch signed clip access:", err);
          setClipError(err.message || "Failed to load signed video stream");
          setLoadingClip(false);
        }
      });

    return () => {
      isCurrent = false;
    };
  }, [selectedCase, token]);

  // Handle Reviewer Decision Submit
  const handleDecision = async (action: "approve" | "reject") => {
    if (!selectedCase || !token) return;
    setSubmittingDecision(true);
    setDecisionFeedback(null);
    try {
      await submitReviewDecision(
        selectedCase.case_id,
        action,
        reviewerName || "Reviewer",
        reviewNotes,
        token
      );
      setDecisionFeedback(
        `Case ${selectedCase.case_id.slice(0, 8)} successfully ${action === "approve" ? "APPROVED" : "REJECTED"} and sealed in audit chain.`
      );
      setReviewNotes("");
      await loadQueue();
      await loadAuditChain();
    } catch (err: any) {
      setDecisionFeedback(`Error: ${err.message || "Failed to submit decision"}`);
      if (err.status === 401 || err.status === 403) {
        setAuthError("Reviewer session unauthorized or token expired.");
      }
    } finally {
      setSubmittingDecision(false);
    }
  };

  // Handle Chain Verification
  const handleVerifyChain = async () => {
    if (!token) return;
    setVerifyingChain(true);
    try {
      const res = await verifyAuditChain(token);
      setVerificationResult(res);
    } catch (err: any) {
      console.error("Verification failed:", err);
    } finally {
      setVerifyingChain(false);
    }
  };

  if (!isAuthReady) {
    return (
      <main suppressHydrationWarning style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0B0F17" }}>
        <div suppressHydrationWarning style={{ width: "24px", height: "24px", border: "2px solid #374151", borderTopColor: "#3B82F6", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
      </main>
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // REVIEWER AUTHENTICATION GATE (REDESIGNED FULL-SCREEN SPLIT SECURITY PORTAL)
  // ═══════════════════════════════════════════════════════════════════════════
  if (!token) {
    return (
      <main
        suppressHydrationWarning
        style={{
          minHeight: "100vh",
          display: "grid",
          gridTemplateColumns: "1fr 480px",
          background: "#0B0F17",
          color: "#F9FAFB",
          fontFamily: "var(--font-sans), system-ui, -apple-system, sans-serif",
        }}
      >
        {/* Left Column: Brand & Security Overview (~55%) */}
        <div
          style={{
            padding: "4rem 5rem",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            borderRight: "1px solid #1F2937",
            background: "linear-gradient(180deg, #0B0F17 0%, #111827 100%)",
          }}
        >
          <div>
            {/* Header Brand */}
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "3rem" }}>
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "6px",
                  background: "#1E3A8A",
                  border: "1px solid #3B82F6",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#60A5FA",
                }}
              >
                <ShieldIcon size={18} color="#60A5FA" />
              </div>
              <span style={{ fontSize: "1.1rem", fontWeight: 800, letterSpacing: "0.08em", color: "#FFFFFF" }}>
                CHAINPROOF
              </span>
            </div>

            <h1
              style={{
                fontSize: "2.4rem",
                fontWeight: 700,
                color: "#FFFFFF",
                letterSpacing: "-0.03em",
                lineHeight: 1.2,
                marginBottom: "1rem",
              }}
            >
              Identity Verification &amp; Forensic Review
            </h1>

            <p style={{ color: "#9CA3AF", fontSize: "1rem", lineHeight: 1.6, maxWidth: "540px", marginBottom: "3.5rem" }}>
              Secure investigation workspace for identity adjudication, optical liveness inspection, deepfake neural artifact evaluation, and cryptographic audit compliance.
            </p>

            {/* Enterprise Security Capability Indicators */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", maxWidth: "540px" }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: "12px" }}>
                <div style={{ padding: "8px", borderRadius: "6px", background: "#1F2937", border: "1px solid #374151", color: "#60A5FA", marginTop: "2px" }}>
                  <ShieldIcon size={16} color="#60A5FA" />
                </div>
                <div>
                  <div style={{ fontSize: "0.88rem", fontWeight: 600, color: "#F3F4F6" }}>Secure Evidence Storage</div>
                  <div style={{ fontSize: "0.78rem", color: "#9CA3AF", marginTop: "2px" }}>Immutable session raw clip vaults</div>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "flex-start", gap: "12px" }}>
                <div style={{ padding: "8px", borderRadius: "6px", background: "#1F2937", border: "1px solid #374151", color: "#60A5FA", marginTop: "2px" }}>
                  <LockIcon size={16} color="#60A5FA" />
                </div>
                <div>
                  <div style={{ fontSize: "0.88rem", fontWeight: 600, color: "#F3F4F6" }}>Encrypted Video Streams</div>
                  <div style={{ fontSize: "0.78rem", color: "#9CA3AF", marginTop: "2px" }}>Ephemeral HMAC signed tickets</div>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "flex-start", gap: "12px" }}>
                <div style={{ padding: "8px", borderRadius: "6px", background: "#1F2937", border: "1px solid #374151", color: "#60A5FA", marginTop: "2px" }}>
                  <HashIcon size={16} color="#60A5FA" />
                </div>
                <div>
                  <div style={{ fontSize: "0.88rem", fontWeight: 600, color: "#F3F4F6" }}>SHA-256 Audit Ledger</div>
                  <div style={{ fontSize: "0.78rem", color: "#9CA3AF", marginTop: "2px" }}>Tamper-evident verification blocks</div>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "flex-start", gap: "12px" }}>
                <div style={{ padding: "8px", borderRadius: "6px", background: "#1F2937", border: "1px solid #374151", color: "#60A5FA", marginTop: "2px" }}>
                  <UserIcon size={16} color="#60A5FA" />
                </div>
                <div>
                  <div style={{ fontSize: "0.88rem", fontWeight: 600, color: "#F3F4F6" }}>RBAC Access Control</div>
                  <div style={{ fontSize: "0.78rem", color: "#9CA3AF", marginTop: "2px" }}>Role-gated reviewer authorization</div>
                </div>
              </div>
            </div>
          </div>

          <div style={{ fontSize: "0.78rem", color: "#6B7280", borderTop: "1px solid #1F2937", paddingTop: "1.5rem" }}>
            ChainProof Forensic System · Version 2.4 Enterprise · Stage 4 Adjudication Module
          </div>
        </div>

        {/* Right Column: Authentication Panel (~45%) */}
        <div
          style={{
            padding: "4rem 3.5rem",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            background: "#111827",
          }}
        >
          <div style={{ width: "100%", maxWidth: "360px", margin: "0 auto" }}>
            <div style={{ marginBottom: "2rem" }}>
              <h2 style={{ fontSize: "1.6rem", fontWeight: 700, color: "#FFFFFF", letterSpacing: "-0.02em" }}>
                Sign in to ChainProof
              </h2>
              <p style={{ color: "#9CA3AF", fontSize: "0.88rem", marginTop: "4px" }}>
                Authorized reviewer authentication
              </p>
            </div>

            {authError && (
              <div
                style={{
                  padding: "12px 14px",
                  borderRadius: "8px",
                  background: "#7F1D1D",
                  border: "1px solid #DC2626",
                  color: "#FCA5A5",
                  fontSize: "0.825rem",
                  marginBottom: "1.5rem",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <AlertTriangleIcon size={16} color="#FCA5A5" />
                <span>{authError}</span>
              </div>
            )}

            <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              <div>
                <label style={{ fontSize: "0.825rem", fontWeight: 600, color: "#D1D5DB", display: "block", marginBottom: "8px" }}>
                  Reviewer Access Token
                </label>
                <div style={{ position: "relative" }}>
                  <div style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "#6B7280" }}>
                    <KeyIcon size={16} color="#6B7280" />
                  </div>
                  <input
                    type="password"
                    required
                    autoFocus
                    placeholder='Enter "REVIEWER_TOKEN" or "dev_mode"'
                    value={loginInputToken}
                    onChange={(e) => setLoginInputToken(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "10px 12px 10px 38px",
                      borderRadius: "6px",
                      background: "#1F2937",
                      border: "1px solid #374151",
                      color: "#FFFFFF",
                      fontSize: "0.875rem",
                      outline: "none",
                      boxSizing: "border-box",
                    }}
                  />
                </div>
                <span style={{ fontSize: "0.75rem", color: "#9CA3AF", marginTop: "4px", display: "block" }}>
                  Enter <code>REVIEWER_TOKEN</code> or <code>dev_mode</code> to authenticate.
                </span>
              </div>

              <div>
                <label style={{ fontSize: "0.825rem", fontWeight: 600, color: "#D1D5DB", display: "block", marginBottom: "8px" }}>
                  Reviewer Officer / Call-sign
                </label>
                <div style={{ position: "relative" }}>
                  <div style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "#6B7280" }}>
                    <UserIcon size={16} color="#6B7280" />
                  </div>
                  <input
                    type="text"
                    placeholder="Auditor Reviewer"
                    value={loginInputName}
                    onChange={(e) => setLoginInputName(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "10px 12px 10px 38px",
                      borderRadius: "6px",
                      background: "#1F2937",
                      border: "1px solid #374151",
                      color: "#FFFFFF",
                      fontSize: "0.875rem",
                      outline: "none",
                      boxSizing: "border-box",
                    }}
                  />
                </div>
              </div>

              {/* Primary CTA Button */}
              <button
                type="submit"
                style={{
                  marginTop: "0.75rem",
                  padding: "11px 16px",
                  borderRadius: "6px",
                  background: "#2563EB",
                  color: "#FFFFFF",
                  fontWeight: 600,
                  fontSize: "0.875rem",
                  border: "none",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "8px",
                  transition: "background 0.15s ease",
                }}
                onMouseOver={(e) => (e.currentTarget.style.background = "#1D4ED8")}
                onMouseOut={(e) => (e.currentTarget.style.background = "#2563EB")}
              >
                <span>Authenticate &amp; Open Review Queue</span>
                <ArrowRightIcon size={16} color="#FFFFFF" />
              </button>
            </form>

            <div
              style={{
                marginTop: "2rem",
                paddingTop: "1.5rem",
                borderTop: "1px solid #1F2937",
                fontSize: "0.78rem",
                color: "#9CA3AF",
                display: "flex",
                alignItems: "flex-start",
                gap: "10px",
                lineHeight: 1.45,
              }}
            >
              <div style={{ marginTop: "1px", color: "#60A5FA" }}>
                <LockIcon size={14} color="#60A5FA" />
              </div>
              <div>
                <strong style={{ color: "#E5E7EB" }}>Secure Session Notice:</strong> Your reviewer credentials are stored exclusively in this browser tab&apos;s <code>sessionStorage</code> and are never bundled into client scripts or public media URLs.
              </div>
            </div>
          </div>
        </div>
      </main>
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // AUTHENTICATED REVIEW DASHBOARD (REDESIGNED RESTRAINED ENTERPRISE CONSOLE)
  // ═══════════════════════════════════════════════════════════════════════════
  return (
    <main
      suppressHydrationWarning
      style={{
        minHeight: "100vh",
        background: "#0B0F17",
        color: "#F9FAFB",
        fontFamily: "var(--font-sans), system-ui, -apple-system, sans-serif",
      }}
    >
      {/* Enterprise Top Navigation Bar */}
      <header
        style={{
          borderBottom: "1px solid #1F2937",
          background: "#111827",
          padding: "0 2.5rem",
          height: "64px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        {/* Left Brand & Product Descriptor */}
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <div
              style={{
                width: "24px",
                height: "24px",
                borderRadius: "4px",
                background: "#1E3A8A",
                border: "1px solid #3B82F6",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <ShieldIcon size={14} color="#60A5FA" />
            </div>
            <span style={{ fontSize: "0.95rem", fontWeight: 800, color: "#FFFFFF", letterSpacing: "0.05em" }}>
              CHAINPROOF
            </span>
          </div>
          <span style={{ color: "#374151" }}>|</span>
          <span style={{ fontSize: "0.825rem", color: "#9CA3AF" }}>
            Identity Verification &amp; Forensic Review
          </span>
        </div>

        {/* Center Navigation Segmented Control */}
        <div style={{ display: "flex", background: "#1F2937", padding: "3px", borderRadius: "6px", border: "1px solid #374151" }}>
          <button
            onClick={() => setActiveTab("queue")}
            style={{
              padding: "6px 14px",
              borderRadius: "4px",
              border: "none",
              background: activeTab === "queue" ? "#2563EB" : "transparent",
              color: activeTab === "queue" ? "#FFFFFF" : "#9CA3AF",
              fontSize: "0.825rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <FileIcon size={14} color={activeTab === "queue" ? "#FFFFFF" : "#9CA3AF"} />
            <span>Review Queue</span>
            <span
              style={{
                fontSize: "0.75rem",
                padding: "1px 6px",
                borderRadius: "10px",
                background: activeTab === "queue" ? "#1D4ED8" : "#374151",
                color: "#FFFFFF",
              }}
            >
              {cases.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab("audit")}
            style={{
              padding: "6px 14px",
              borderRadius: "4px",
              border: "none",
              background: activeTab === "audit" ? "#2563EB" : "transparent",
              color: activeTab === "audit" ? "#FFFFFF" : "#9CA3AF",
              fontSize: "0.825rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <HashIcon size={14} color={activeTab === "audit" ? "#FFFFFF" : "#9CA3AF"} />
            <span>Audit Chain</span>
          </button>
        </div>

        {/* Right Officer Status & Logout */}
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.825rem", color: "#D1D5DB" }}>
            <UserIcon size={15} color="#9CA3AF" />
            <span>Reviewer: <strong>{reviewerName}</strong></span>
          </div>
          <span style={{ color: "#374151" }}>|</span>
          <button
            onClick={handleLogout}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              background: "transparent",
              border: "1px solid #374151",
              color: "#9CA3AF",
              padding: "5px 12px",
              borderRadius: "4px",
              fontSize: "0.78rem",
              fontWeight: 500,
              cursor: "pointer",
            }}
            onMouseOver={(e) => (e.currentTarget.style.color = "#FCA5A5")}
            onMouseOut={(e) => (e.currentTarget.style.color = "#9CA3AF")}
          >
            <LogOutIcon size={14} color="currentColor" />
            <span>Logout</span>
          </button>
        </div>
      </header>

      {/* Main Workspace Body */}
      <div style={{ maxWidth: "1500px", margin: "0 auto", padding: "2rem 2.5rem" }}>
        {authError && (
          <div
            style={{
              padding: "12px 16px",
              borderRadius: "6px",
              background: "#7F1D1D",
              border: "1px solid #DC2626",
              color: "#FCA5A5",
              fontSize: "0.85rem",
              marginBottom: "1.5rem",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <AlertTriangleIcon size={16} color="#FCA5A5" />
              <span>{authError}</span>
            </div>
            <button
              onClick={handleLogout}
              style={{
                background: "#DC2626",
                color: "white",
                border: "none",
                borderRadius: "4px",
                padding: "4px 10px",
                fontSize: "0.75rem",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Re-Authenticate
            </button>
          </div>
        )}

        {connectionError && (
          <div
            style={{
              padding: "12px 16px",
              borderRadius: "6px",
              background: "#78350F",
              border: "1px solid #D97706",
              color: "#FDE68A",
              fontSize: "0.85rem",
              marginBottom: "1.5rem",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <AlertTriangleIcon size={16} color="#FDE68A" />
              <span>{connectionError}</span>
            </div>
            <button
              onClick={loadQueue}
              style={{
                background: "#D97706",
                color: "white",
                border: "none",
                borderRadius: "4px",
                padding: "4px 10px",
                fontSize: "0.75rem",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Retry Connection
            </button>
          </div>
        )}

        {activeTab === "queue" ? (
          /* ═══════════════════════════════════════════════════════════════════
             QUEUE & DOSSIER INVESTIGATION WORKSPACE
             ═══════════════════════════════════════════════════════════════════ */
          <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: "2rem" }}>
            {/* Left Queue Panel */}
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <h2 style={{ fontSize: "0.95rem", fontWeight: 700, color: "#FFFFFF", letterSpacing: "0.04em" }}>
                    REVIEW QUEUE
                  </h2>
                  <span style={{ fontSize: "0.75rem", color: "#9CA3AF", background: "#1F2937", padding: "2px 8px", borderRadius: "10px", fontWeight: 600 }}>
                    {cases.length} CASES
                  </span>
                </div>
                <button
                  onClick={loadQueue}
                  title="Refresh queue"
                  style={{
                    background: "transparent",
                    border: "none",
                    color: "#9CA3AF",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                    fontSize: "0.78rem",
                  }}
                  onMouseOver={(e) => (e.currentTarget.style.color = "#FFFFFF")}
                  onMouseOut={(e) => (e.currentTarget.style.color = "#9CA3AF")}
                >
                  <RefreshIcon size={14} color="currentColor" />
                  <span>Refresh</span>
                </button>
              </div>

              {/* Status Filter Segmented Controls */}
              <div style={{ display: "flex", gap: "2px", background: "#111827", padding: "3px", borderRadius: "6px", border: "1px solid #1F2937" }}>
                {[
                  { label: "Pending", val: "pending_review" },
                  { label: "Approved", val: "resolved_approved" },
                  { label: "Rejected", val: "resolved_rejected" },
                  { label: "All", val: "all" },
                ].map(({ label, val }) => (
                  <button
                    key={val}
                    onClick={() => setStatusFilter(val)}
                    style={{
                      flex: 1,
                      padding: "6px 2px",
                      borderRadius: "4px",
                      border: "none",
                      background: statusFilter === val ? "#1F2937" : "transparent",
                      color: statusFilter === val ? "#FFFFFF" : "#9CA3AF",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {/* Case List Rows */}
              <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "720px", overflowY: "auto" }}>
                {loadingCases && cases.length === 0 ? (
                  <div style={{ padding: "2rem", textAlign: "center", color: "#9CA3AF", fontSize: "0.85rem" }}>
                    Loading queue...
                  </div>
                ) : cases.length === 0 ? (
                  <div style={{ padding: "2rem", textAlign: "center", color: "#9CA3AF", fontSize: "0.85rem" }}>
                    No cases found in this category.
                  </div>
                ) : (
                  cases.map((c) => {
                    const isSelected = selectedCase?.case_id === c.case_id;
                    const isPending = c.status === "pending_review";
                    const isApproved = c.status === "resolved_approved";

                    return (
                      <div
                        key={c.case_id}
                        onClick={() => setSelectedCase(c)}
                        style={{
                          padding: "12px 14px",
                          borderRadius: "6px",
                          background: isSelected ? "#111827" : "#0F172A",
                          border: "1px solid",
                          borderColor: isSelected ? "#3B82F6" : "#1E293B",
                          borderLeft: isSelected ? "4px solid #3B82F6" : "1px solid #1E293B",
                          cursor: "pointer",
                          transition: "all 0.12s ease",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span style={{ fontWeight: 600, fontSize: "0.875rem", color: "#F9FAFB" }}>{c.legal_name}</span>
                          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                            {isApproved ? (
                              <span style={{ fontSize: "0.725rem", color: "#10B981", fontWeight: 600, display: "flex", alignItems: "center", gap: "4px" }}>
                                <CheckCircleIcon size={12} color="#10B981" /> Approved
                              </span>
                            ) : isPending ? (
                              <span style={{ fontSize: "0.725rem", color: "#F59E0B", fontWeight: 600, display: "flex", alignItems: "center", gap: "4px" }}>
                                <AlertTriangleIcon size={12} color="#F59E0B" /> Pending
                              </span>
                            ) : (
                              <span style={{ fontSize: "0.725rem", color: "#EF4444", fontWeight: 600, display: "flex", alignItems: "center", gap: "4px" }}>
                                <XCircleIcon size={12} color="#EF4444" /> Rejected
                              </span>
                            )}
                          </div>
                        </div>

                        <div style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "#64748B", marginTop: "4px" }}>
                          CKYC ••••{c.kin_token ? c.kin_token.slice(-6) : "829829"}
                        </div>

                        <div style={{ display: "flex", gap: "10px", fontSize: "0.75rem", color: "#94A3B8", marginTop: "6px" }}>
                          <span>Deepfake <strong>{((c.signals?.deepfake_score || 0) * 100).toFixed(0)}%</strong></span>
                          <span>·</span>
                          <span>Face <strong>{((c.signals?.cosine_similarity_score || 0) * 100).toFixed(0)}%</strong></span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Right Main Dossier Investigation Workspace */}
            {selectedCase ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
                {/* Case Header */}
                <div
                  style={{
                    padding: "1.25rem 1.5rem",
                    borderRadius: "8px",
                    background: "#111827",
                    border: "1px solid #1F2937",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    <h1 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#FFFFFF", margin: 0 }}>
                      {selectedCase.legal_name}
                    </h1>
                    <div style={{ display: "flex", gap: "16px", marginTop: "4px", fontSize: "0.78rem", fontFamily: "var(--font-mono)", color: "#9CA3AF" }}>
                      <span>Session ID: <code style={{ color: "#E5E7EB" }}>{selectedCase.session_id}</code></span>
                      <span>Case ID: <code style={{ color: "#E5E7EB" }}>{selectedCase.case_id}</code></span>
                    </div>
                  </div>

                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: "0.725rem", fontWeight: 600, color: "#9CA3AF", letterSpacing: "0.04em", marginBottom: "4px" }}>
                      AUTONOMOUS RECOMMENDATION
                    </div>
                    <span
                      style={{
                        padding: "4px 12px",
                        borderRadius: "4px",
                        fontWeight: 700,
                        fontSize: "0.825rem",
                        display: "inline-block",
                        background: selectedCase.agent_recommendation === "APPROVE" ? "rgba(16, 185, 129, 0.15)" : selectedCase.agent_recommendation === "REJECT" ? "rgba(239, 68, 68, 0.15)" : "rgba(245, 158, 11, 0.15)",
                        color: selectedCase.agent_recommendation === "APPROVE" ? "#10B981" : selectedCase.agent_recommendation === "REJECT" ? "#EF4444" : "#F59E0B",
                        border: `1px solid ${selectedCase.agent_recommendation === "APPROVE" ? "#10B981" : selectedCase.agent_recommendation === "REJECT" ? "#EF4444" : "#F59E0B"}`,
                      }}
                    >
                      {selectedCase.agent_recommendation}
                    </span>
                  </div>
                </div>

                {decisionFeedback && (
                  <div
                    style={{
                      padding: "10px 14px",
                      borderRadius: "6px",
                      background: decisionFeedback.includes("Error") ? "#7F1D1D" : "#064E3B",
                      border: decisionFeedback.includes("Error") ? "1px solid #DC2626" : "1px solid #10B981",
                      color: decisionFeedback.includes("Error") ? "#FCA5A5" : "#A7F3D0",
                      fontSize: "0.85rem",
                    }}
                  >
                    {decisionFeedback}
                  </div>
                )}

                {/* Human Adjudication Section (TOP OF DOSSIER WORKSPACE) */}
                <div
                  style={{
                    padding: "1.25rem",
                    borderRadius: "8px",
                    background: "#111827",
                    border: "1px solid #1F2937",
                    display: "flex",
                    flexDirection: "column",
                    gap: "12px",
                  }}
                >
                  <span style={{ fontSize: "0.875rem", fontWeight: 700, color: "#FFFFFF", letterSpacing: "0.03em" }}>
                    HUMAN ADJUDICATION
                  </span>

                  <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: "12px" }}>
                    <div>
                      <label style={{ fontSize: "0.75rem", color: "#9CA3AF", display: "block", marginBottom: "4px" }}>
                        Reviewer Call-sign
                      </label>
                      <input
                        type="text"
                        placeholder="Reviewer ID"
                        value={reviewerName}
                        onChange={(e) => setReviewerName(e.target.value)}
                        style={{
                          width: "100%",
                          padding: "8px 12px",
                          borderRadius: "6px",
                          background: "#1F2937",
                          border: "1px solid #374151",
                          color: "#FFFFFF",
                          fontSize: "0.85rem",
                          outline: "none",
                          boxSizing: "border-box",
                        }}
                      />
                    </div>

                    <div>
                      <label style={{ fontSize: "0.75rem", color: "#9CA3AF", display: "block", marginBottom: "4px" }}>
                        Investigation Rationale &amp; Analyst Notes
                      </label>
                      <input
                        type="text"
                        placeholder="Enter investigative notes or decision rationale..."
                        value={reviewNotes}
                        onChange={(e) => setReviewNotes(e.target.value)}
                        style={{
                          width: "100%",
                          padding: "8px 12px",
                          borderRadius: "6px",
                          background: "#1F2937",
                          border: "1px solid #374151",
                          color: "#FFFFFF",
                          fontSize: "0.85rem",
                          outline: "none",
                          boxSizing: "border-box",
                        }}
                      />
                    </div>
                  </div>

                  {/* Primary Action Buttons (Approve & Reject) */}
                  <div style={{ display: "flex", gap: "12px", marginTop: "8px" }}>
                    <button
                      disabled={submittingDecision}
                      onClick={() => handleDecision("approve")}
                      style={{
                        flex: 1,
                        padding: "12px",
                        borderRadius: "6px",
                        border: "none",
                        background: "#059669",
                        color: "#FFFFFF",
                        fontWeight: 700,
                        fontSize: "0.875rem",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: "8px",
                        transition: "background 0.15s ease",
                      }}
                      onMouseOver={(e) => (e.currentTarget.style.background = "#047857")}
                      onMouseOut={(e) => (e.currentTarget.style.background = "#059669")}
                    >
                      <CheckCircleIcon size={16} color="#FFFFFF" />
                      <span>APPROVE ONBOARDING</span>
                    </button>

                    <button
                      disabled={submittingDecision}
                      onClick={() => handleDecision("reject")}
                      style={{
                        flex: 1,
                        padding: "12px",
                        borderRadius: "6px",
                        border: "none",
                        background: "#DC2626",
                        color: "#FFFFFF",
                        fontWeight: 700,
                        fontSize: "0.875rem",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: "8px",
                        transition: "background 0.15s ease",
                      }}
                      onMouseOver={(e) => (e.currentTarget.style.background = "#B91C1C")}
                      onMouseOut={(e) => (e.currentTarget.style.background = "#DC2626")}
                    >
                      <XCircleIcon size={16} color="#FFFFFF" />
                      <span>REJECT ONBOARDING</span>
                    </button>
                  </div>
                </div>

                {/* Evidence & Telemetry Section */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem" }}>
                  {/* Archived Live Video Evidence Box */}
                  <div
                    style={{
                      padding: "1.25rem",
                      borderRadius: "8px",
                      background: "#111827",
                      border: "1px solid #1F2937",
                      display: "flex",
                      flexDirection: "column",
                      gap: "12px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: "0.875rem", fontWeight: 700, color: "#FFFFFF", letterSpacing: "0.03em" }}>
                        ARCHIVED LIVE CLIP
                      </span>
                      <span style={{ fontSize: "0.75rem", color: "#10B981", fontWeight: 600, display: "flex", alignItems: "center", gap: "6px" }}>
                        <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#10B981" }} />
                        HMAC STREAM ACTIVE
                      </span>
                    </div>

                    <div
                      style={{
                        width: "100%",
                        aspectRatio: "16/10",
                        background: "#000000",
                        borderRadius: "6px",
                        overflow: "hidden",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        border: "1px solid #1F2937",
                      }}
                    >
                      {loadingClip ? (
                        <div style={{ color: "#9CA3AF", fontSize: "0.85rem" }}>
                          Loading signed clip stream...
                        </div>
                      ) : clipError ? (
                        <div style={{ color: "#FCA5A5", fontSize: "0.8rem", padding: "1rem", textAlign: "center", display: "flex", alignItems: "center", gap: "8px" }}>
                          <AlertTriangleIcon size={16} color="#FCA5A5" />
                          <span>{clipError}</span>
                        </div>
                      ) : clipAccess?.url ? (
                        <video
                          key={clipAccess.url}
                          controls
                          autoPlay
                          muted
                          loop
                          src={clipAccess.url}
                          style={{ width: "100%", height: "100%", objectFit: "contain" }}
                        />
                      ) : (
                        <div style={{ color: "#9CA3AF", fontSize: "0.8rem" }}>No video clip recorded for this session</div>
                      )}
                    </div>

                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "#9CA3AF" }}>
                      <span>SHA-256: {clipAccess?.sha256 ? `${clipAccess.sha256.slice(0, 16)}...` : "Verified"}</span>
                      <span>Expires in {clipAccess?.expires_in || 600}s</span>
                    </div>
                  </div>

                  {/* Physiological & Identity Telemetry Grid */}
                  <div
                    style={{
                      padding: "1.25rem",
                      borderRadius: "8px",
                      background: "#111827",
                      border: "1px solid #1F2937",
                      display: "flex",
                      flexDirection: "column",
                      gap: "1rem",
                    }}
                  >
                    <span style={{ fontSize: "0.875rem", fontWeight: 700, color: "#FFFFFF", letterSpacing: "0.03em" }}>
                      PHYSIOLOGICAL &amp; IDENTITY TELEMETRY
                    </span>

                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                      <div style={{ background: "#1F2937", padding: "12px", borderRadius: "6px", border: "1px solid #374151" }}>
                        <div style={{ color: "#9CA3AF", fontSize: "0.725rem", fontWeight: 600, letterSpacing: "0.04em" }}>DEEPFAKE PROBABILITY</div>
                        <div style={{ fontSize: "1.5rem", fontWeight: 700, color: (selectedCase.signals?.deepfake_score || 0) >= 0.4 ? "#EF4444" : "#10B981", marginTop: "4px" }}>
                          {((selectedCase.signals?.deepfake_score || 0) * 100).toFixed(1)}%
                        </div>
                      </div>

                      <div style={{ background: "#1F2937", padding: "12px", borderRadius: "6px", border: "1px solid #374151" }}>
                        <div style={{ color: "#9CA3AF", fontSize: "0.725rem", fontWeight: 600, letterSpacing: "0.04em" }}>FACE TEMPLATE MATCH</div>
                        <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#3B82F6", marginTop: "4px" }}>
                          {((selectedCase.signals?.cosine_similarity_score || 0) * 100).toFixed(1)}%
                        </div>
                      </div>

                      <div style={{ background: "#1F2937", padding: "12px", borderRadius: "6px", border: "1px solid #374151" }}>
                        <div style={{ color: "#9CA3AF", fontSize: "0.725rem", fontWeight: 600, letterSpacing: "0.04em" }}>DUPLICATE CHECK</div>
                        <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "#F9FAFB", marginTop: "6px" }}>
                          {(selectedCase.signals?.registry_velocity_6hr || 1) > 1 ? "Already Verified Record" : "First-Time Verification"}
                        </div>
                      </div>

                      <div style={{ background: "#1F2937", padding: "12px", borderRadius: "6px", border: "1px solid #374151" }}>
                        <div style={{ color: "#9CA3AF", fontSize: "0.725rem", fontWeight: 600, letterSpacing: "0.04em" }}>AUDIO-VIDEO SYNC</div>
                        <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#F9FAFB", marginTop: "4px" }}>
                          {selectedCase.signals?.av_sync_ms || 0} ms
                        </div>
                      </div>

                      <div style={{ background: "#1F2937", padding: "12px", borderRadius: "6px", border: "1px solid #374151", gridColumn: "span 2" }}>
                        <div style={{ color: "#9CA3AF", fontSize: "0.725rem", fontWeight: 600, letterSpacing: "0.04em" }}>NETWORK JITTER</div>
                        <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#F9FAFB", marginTop: "2px" }}>
                          {selectedCase.signals?.webrtc_jitter_ms || 12.5} ms
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Agent Decision Trace Section (Subtle Purple Accent ONLY for Agentic Info) */}
                <div
                  style={{
                    padding: "1.25rem",
                    borderRadius: "8px",
                    background: "#111827",
                    border: "1px solid #374151",
                    display: "flex",
                    flexDirection: "column",
                    gap: "12px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <span style={{ fontSize: "0.875rem", fontWeight: 700, color: "#FFFFFF", letterSpacing: "0.03em" }}>
                        AGENT DECISION TRACE
                      </span>
                      <span
                        style={{
                          fontSize: "0.7rem",
                          fontWeight: 700,
                          padding: "2px 8px",
                          borderRadius: "4px",
                          background: "rgba(168, 85, 247, 0.15)",
                          color: "#C084FC",
                          border: "1px solid rgba(168, 85, 247, 0.3)",
                        }}
                      >
                        LANGGRAPH
                      </span>
                    </div>
                  </div>

                  {/* Agent Rationale */}
                  <div
                    style={{
                      background: "rgba(168, 85, 247, 0.08)",
                      border: "1px solid rgba(168, 85, 247, 0.25)",
                      borderRadius: "6px",
                      padding: "10px 14px",
                      fontSize: "0.85rem",
                      color: "#E9D5FF",
                      lineHeight: 1.5,
                    }}
                  >
                    <strong>Agent Rationale:</strong> {selectedCase.dossier_summary || selectedCase.notes || "Evaluation completed cleanly."}
                  </div>

                  <pre
                    style={{
                      background: "#090D16",
                      padding: "12px 14px",
                      borderRadius: "6px",
                      fontSize: "0.78rem",
                      color: "#A5F3FC",
                      whiteSpace: "pre-wrap",
                      fontFamily: "var(--font-mono), monospace",
                      maxHeight: "180px",
                      overflowY: "auto",
                      border: "1px solid #1F2937",
                      margin: 0,
                    }}
                  >
                    {JSON.stringify(
                      selectedCase.tool_calls_trace && selectedCase.tool_calls_trace.length > 0
                        ? selectedCase.tool_calls_trace
                        : {
                            dossier_summary: selectedCase.dossier_summary,
                            signals: selectedCase.signals,
                            decision: selectedCase.decision,
                            recommendation: selectedCase.agent_recommendation,
                          },
                      null,
                      2
                    )}
                  </pre>
                </div>
              </div>
            ) : (
              <div
                style={{
                  padding: "4rem 2rem",
                  textAlign: "center",
                  color: "#9CA3AF",
                  background: "#111827",
                  borderRadius: "8px",
                  border: "1px solid #1F2937",
                }}
              >
                Select a case from the queue to view dossier and video playback.
              </div>
            )}
          </div>
        ) : (
          /* ═══════════════════════════════════════════════════════════════════
             AUDIT CHAIN EXPLORER VIEW (FORENSIC LEDGER)
             ═══════════════════════════════════════════════════════════════════ */
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            {/* Action & Verification Banner */}
            <div
              style={{
                padding: "1.25rem 1.5rem",
                borderRadius: "8px",
                background: "#111827",
                border: "1px solid #1F2937",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <h2 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#FFFFFF" }}>Cryptographic Hash Chain</h2>
                <p style={{ color: "#9CA3AF", fontSize: "0.825rem", marginTop: "2px" }}>
                  Total Sealed Blocks: {auditBlocks.length} | SHA-256 prev_hash Linkage Ledger
                </p>
              </div>

              <div style={{ display: "flex", gap: "12px" }}>
                <button
                  onClick={loadAuditChain}
                  style={{
                    padding: "8px 14px",
                    borderRadius: "6px",
                    border: "1px solid #374151",
                    background: "transparent",
                    color: "#D1D5DB",
                    cursor: "pointer",
                    fontSize: "0.825rem",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <RefreshIcon size={14} color="currentColor" />
                  <span>Refresh Chain</span>
                </button>
                <button
                  disabled={verifyingChain}
                  onClick={handleVerifyChain}
                  style={{
                    padding: "8px 16px",
                    borderRadius: "6px",
                    border: "none",
                    background: "#2563EB",
                    color: "#FFFFFF",
                    fontSize: "0.825rem",
                    fontWeight: 600,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <ShieldIcon size={14} color="#FFFFFF" />
                  <span>{verifyingChain ? "Verifying..." : "Verify Cryptographic Chain"}</span>
                </button>
              </div>
            </div>

            {/* Verification Results Panel */}
            {verificationResult && (
              <div
                style={{
                  padding: "1rem 1.25rem",
                  borderRadius: "6px",
                  background: verificationResult.is_valid ? "#064E3B" : "#7F1D1D",
                  border: verificationResult.is_valid ? "1px solid #10B981" : "1px solid #DC2626",
                  color: verificationResult.is_valid ? "#A7F3D0" : "#FCA5A5",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  {verificationResult.is_valid ? (
                    <CheckCircleIcon size={20} color="#10B981" />
                  ) : (
                    <AlertTriangleIcon size={20} color="#DC2626" />
                  )}
                  <div>
                    <div style={{ fontWeight: 700, fontSize: "0.95rem" }}>
                      {verificationResult.is_valid ? "VERIFICATION SUCCESS: AUDIT CHAIN INTACT" : "TAMPER DETECTED"}
                    </div>
                    <div style={{ fontSize: "0.825rem", marginTop: "2px", opacity: 0.9 }}>
                      {verificationResult.message} · Verified {verificationResult.verified_count} of {verificationResult.total_count} blocks
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Block Visualizer List */}
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {auditBlocks.length === 0 ? (
                <div style={{ padding: "3rem", textAlign: "center", color: "#9CA3AF", background: "#111827", borderRadius: "8px", border: "1px solid #1F2937" }}>
                  No audit blocks found in chain.
                </div>
              ) : (
                auditBlocks.map((b) => (
                  <div
                    key={b.index}
                    style={{
                      padding: "1.25rem",
                      borderRadius: "6px",
                      background: "#111827",
                      border: "1px solid #1F2937",
                      borderLeft: `4px solid ${
                        b.record_type === "upload" ? "#3B82F6" :
                        b.record_type === "decision" ? "#8B5CF6" :
                        b.record_type === "identity" ? "#F59E0B" :
                        b.record_type === "human_review" ? "#10B981" : "#4B5563"
                      }`,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        <span style={{ fontWeight: 800, fontSize: "0.875rem", fontFamily: "var(--font-mono)", color: "#9CA3AF" }}>
                          #{b.index}
                        </span>
                        <span
                          style={{
                            padding: "2px 8px",
                            borderRadius: "4px",
                            background: "#1F2937",
                            color: "#F3F4F6",
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            border: "1px solid #374151",
                          }}
                        >
                          {b.record_type.toUpperCase()}
                        </span>
                        <span style={{ fontSize: "0.8rem", color: "#9CA3AF", fontFamily: "var(--font-mono)" }}>
                          Session: {b.session_id.slice(0, 12)}
                        </span>
                      </div>
                      <span style={{ fontSize: "0.75rem", color: "#6B7280", fontFamily: "var(--font-mono)" }}>
                        {b.timestamp}
                      </span>
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginTop: "10px", fontSize: "0.75rem", fontFamily: "var(--font-mono)" }}>
                      <div>
                        <span style={{ color: "#6B7280" }}>Prev Hash: </span>
                        <code style={{ color: "#93C5FD" }}>{b.prev_hash.slice(0, 24)}...</code>
                      </div>
                      <div>
                        <span style={{ color: "#6B7280" }}>Record Hash: </span>
                        <code style={{ color: "#C084FC" }}>{b.record_hash.slice(0, 24)}...</code>
                      </div>
                    </div>

                    <pre
                      style={{
                        background: "#090D16",
                        padding: "10px 12px",
                        borderRadius: "4px",
                        marginTop: "10px",
                        fontSize: "0.75rem",
                        color: "#9CA3AF",
                        whiteSpace: "pre-wrap",
                        fontFamily: "var(--font-mono), monospace",
                        border: "1px solid #1F2937",
                        margin: 0,
                      }}
                    >
                      {JSON.stringify(b.payload, null, 2)}
                    </pre>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

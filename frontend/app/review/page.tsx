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

export default function ReviewPage() {
  // Authentication state (persisted strictly in browser sessionStorage)
  const [token, setToken] = useState<string>("");
  const [reviewerName, setReviewerName] = useState<string>("Auditor Priya");
  const [isAuthReady, setIsAuthReady] = useState<boolean>(false);
  const [loginInputToken, setLoginInputToken] = useState<string>("");
  const [loginInputName, setLoginInputName] = useState<string>("Auditor Priya");
  const [authError, setAuthError] = useState<string | null>(null);

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
      // sessionStorage unavailable (e.g. strict sandbox)
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
    const cleanToken = loginInputToken.trim();
    const cleanName = loginInputName.trim() || "Auditor Priya";
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
  };

  // Load Queue
  const loadQueue = useCallback(async () => {
    if (!token) return;
    try {
      setLoadingCases(true);
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
      <main style={{ minHeight: "80vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div className="spinner" />
      </main>
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // REVIEWER AUTHENTICATION GATE (UNAUTHENTICATED VIEW)
  // ═══════════════════════════════════════════════════════════════════════════
  if (!token) {
    return (
      <main
        style={{
          position: "relative",
          zIndex: 1,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "2rem",
        }}
      >
        <div
          className="glass"
          style={{
            maxWidth: "520px",
            width: "100%",
            padding: "2.5rem",
            display: "flex",
            flexDirection: "column",
            gap: "1.5rem",
            border: "1px solid rgba(168, 85, 247, 0.3)",
            boxShadow: "0 0 40px rgba(168, 85, 247, 0.15)",
          }}
        >
          <div style={{ textAlign: "center" }}>
            <div
              style={{
                display: "inline-block",
                padding: "6px 14px",
                borderRadius: "20px",
                background: "rgba(168, 85, 247, 0.15)",
                border: "1px solid var(--accent)",
                fontSize: "0.75rem",
                fontWeight: 700,
                color: "var(--accent-2)",
                marginBottom: "1rem",
              }}
            >
              🛡️ STAGE 4 ADJUDICATION GATEWAY
            </div>
            <h1
              style={{
                fontSize: "1.8rem",
                fontWeight: 800,
                background: "linear-gradient(135deg, #f1f5f9 0%, #a855f7 50%, #06b6d4 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              Reviewer Authentication
            </h1>
            <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: "8px" }}>
              Access to the escalation queue and raw biometric streams requires verified reviewer credentials.
            </p>
          </div>

          {authError && (
            <div
              style={{
                padding: "10px 14px",
                borderRadius: "8px",
                background: "rgba(239, 68, 68, 0.15)",
                border: "1px solid var(--fake)",
                color: "#fca5a5",
                fontSize: "0.85rem",
              }}
            >
              ⚠️ {authError}
            </div>
          )}

          <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div>
              <label style={{ fontSize: "0.8rem", color: "var(--text-muted)", display: "block", marginBottom: "6px" }}>
                Reviewer Access Token
              </label>
              <input
                type="password"
                required
                autoFocus
                placeholder="Enter REVIEWER_TOKEN"
                value={loginInputToken}
                onChange={(e) => setLoginInputToken(e.target.value)}
                style={{
                  width: "100%",
                  padding: "12px 14px",
                  borderRadius: "8px",
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid var(--border)",
                  color: "white",
                  fontSize: "0.9rem",
                  outline: "none",
                }}
              />
            </div>

            <div>
              <label style={{ fontSize: "0.8rem", color: "var(--text-muted)", display: "block", marginBottom: "6px" }}>
                Reviewer Officer Name / Call-sign
              </label>
              <input
                type="text"
                placeholder="e.g. Auditor Priya"
                value={loginInputName}
                onChange={(e) => setLoginInputName(e.target.value)}
                style={{
                  width: "100%",
                  padding: "12px 14px",
                  borderRadius: "8px",
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid var(--border)",
                  color: "white",
                  fontSize: "0.9rem",
                  outline: "none",
                }}
              />
            </div>

            <button
              type="submit"
              className="btn-primary"
              style={{
                marginTop: "0.5rem",
                padding: "12px",
                borderRadius: "10px",
                fontWeight: 700,
                fontSize: "0.95rem",
                cursor: "pointer",
              }}
            >
              ⚡ Authenticate &amp; Open Queue
            </button>
          </form>

          <div
            style={{
              padding: "10px 12px",
              borderRadius: "8px",
              background: "rgba(0,0,0,0.3)",
              border: "1px solid rgba(255,255,255,0.05)",
              fontSize: "0.75rem",
              color: "var(--text-muted)",
              lineHeight: 1.4,
            }}
          >
            🔒 <strong style={{ color: "white" }}>Zero-Leak Architecture:</strong> Your credential is never bundled
            into client javascript or passed in video stream URLs. It is stored exclusively in this browser tab&apos;s{" "}
            <code>sessionStorage</code> and transmitted via headers.
          </div>
        </div>
      </main>
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // AUTHENTICATED REVIEW DASHBOARD
  // ═══════════════════════════════════════════════════════════════════════════
  return (
    <main
      style={{
        position: "relative",
        zIndex: 1,
        minHeight: "100vh",
        padding: "2rem",
        maxWidth: "1300px",
        margin: "0 auto",
        display: "flex",
        flexDirection: "column",
        gap: "1.5rem",
      }}
    >
      {/* Header & Session Bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <h1
            style={{
              fontSize: "2.2rem",
              fontWeight: 800,
              background: "linear-gradient(135deg, #f1f5f9 0%, #a855f7 50%, #06b6d4 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            Human Review &amp; Audit Chain
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", marginTop: "4px" }}>
            Stage 4 Human Escalation Queue · Cryptographic SHA-256 Hash Chain · Tamper Evidence
          </p>
        </div>

        {/* View Switcher Tabs & Reviewer Badge */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
          <div style={{ display: "flex", gap: "8px", background: "rgba(255,255,255,0.05)", padding: "4px", borderRadius: "10px", border: "1px solid var(--border)" }}>
            <button
              onClick={() => setActiveTab("queue")}
              style={{
                padding: "8px 16px",
                borderRadius: "8px",
                border: "none",
                background: activeTab === "queue" ? "var(--accent)" : "transparent",
                color: "white",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.2s ease",
              }}
            >
              Review Queue ({cases.length})
            </button>
            <button
              onClick={() => setActiveTab("audit")}
              style={{
                padding: "8px 16px",
                borderRadius: "8px",
                border: "none",
                background: activeTab === "audit" ? "var(--accent)" : "transparent",
                color: "white",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.2s ease",
              }}
            >
              Audit Chain Explorer
            </button>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              background: "rgba(255,255,255,0.03)",
              padding: "4px 10px",
              borderRadius: "8px",
              border: "1px solid var(--border)",
            }}
          >
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>👤 {reviewerName}</span>
            <button
              onClick={handleLogout}
              title="Disconnect Session"
              style={{
                background: "transparent",
                border: "1px solid rgba(239, 68, 68, 0.4)",
                color: "#fca5a5",
                borderRadius: "6px",
                padding: "3px 8px",
                fontSize: "0.75rem",
                cursor: "pointer",
              }}
            >
              Disconnect
            </button>
          </div>
        </div>
      </div>

      {authError && (
        <div
          style={{
            padding: "12px 16px",
            borderRadius: "10px",
            background: "rgba(239, 68, 68, 0.2)",
            border: "1px solid var(--fake)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: "0.85rem",
          }}
        >
          <span>⚠️ {authError}</span>
          <button
            onClick={handleLogout}
            style={{
              background: "var(--fake)",
              color: "white",
              border: "none",
              borderRadius: "6px",
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

      {activeTab === "queue" ? (
        /* ═══════════════════════════════════════════════════════════════════
           QUEUE & DOSSIER VIEW
           ═══════════════════════════════════════════════════════════════════ */
        <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", gap: "1.5rem" }}>
          {/* Left Column: Queue List & Filters */}
          <div className="glass" style={{ padding: "1.25rem", display: "flex", flexDirection: "column", gap: "1rem", height: "fit-content" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ fontSize: "1.1rem", fontWeight: 700 }}>Escalated Cases</h2>
              <button
                onClick={loadQueue}
                style={{ background: "transparent", border: "none", color: "var(--accent-2)", cursor: "pointer", fontSize: "0.8rem" }}
              >
                ↻ Refresh
              </button>
            </div>

            {/* Status Filter Tabs */}
            <div style={{ display: "flex", gap: "4px", background: "rgba(0,0,0,0.2)", padding: "4px", borderRadius: "8px" }}>
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
                    padding: "6px 4px",
                    borderRadius: "6px",
                    border: "none",
                    background: statusFilter === val ? "rgba(255,255,255,0.12)" : "transparent",
                    color: statusFilter === val ? "white" : "var(--text-muted)",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Case List */}
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxHeight: "600px", overflowY: "auto" }}>
              {loadingCases && cases.length === 0 ? (
                <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)" }}>
                  <div className="spinner" style={{ margin: "0 auto 8px" }} />
                  Loading queue...
                </div>
              ) : cases.length === 0 ? (
                <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)", fontSize: "0.85rem" }}>
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
                        padding: "12px",
                        borderRadius: "10px",
                        background: isSelected ? "rgba(168, 85, 247, 0.15)" : "rgba(255,255,255,0.03)",
                        border: isSelected ? "1px solid var(--accent)" : "1px solid var(--border)",
                        cursor: "pointer",
                        transition: "all 0.15s ease",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontWeight: 600, fontSize: "0.9rem" }}>{c.legal_name}</span>
                        <span
                          className={`badge ${isApproved ? "badge-real" : isPending ? "badge-uncertain" : "badge-fake"}`}
                          style={{ fontSize: "0.65rem", padding: "2px 8px" }}
                        >
                          {isPending ? "PENDING" : isApproved ? "APPROVED" : "REJECTED"}
                        </span>
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px" }}>
                        KIN: {c.kin_token.slice(0, 14)}...
                      </div>
                      <div style={{ display: "flex", gap: "8px", fontSize: "0.75rem", marginTop: "6px" }}>
                        <span>DF: {((c.signals?.deepfake_score || 0) * 100).toFixed(0)}%</span>
                        <span>•</span>
                        <span>Face: {((c.signals?.cosine_similarity_score || 0) * 100).toFixed(0)}%</span>
                        <span>•</span>
                        <span>Vel: {c.signals?.registry_velocity_6hr || 1}</span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Right Column: Case Dossier & Video Review */}
          {selectedCase ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              {/* Top Banner with Applicant Overview */}
              <div className="glass" style={{ padding: "1.25rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
                  <div>
                    <h2 style={{ fontSize: "1.4rem", fontWeight: 700 }}>{selectedCase.legal_name}</h2>
                    <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: "2px" }}>
                      Session ID: <code>{selectedCase.session_id}</code> | Case ID: <code>{selectedCase.case_id}</code>
                    </p>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Autonomous Recommendation:</div>
                    <span
                      className={`badge ${selectedCase.agent_recommendation === "APPROVE" ? "badge-real" : "badge-uncertain"}`}
                      style={{ marginTop: "4px" }}
                    >
                      {selectedCase.agent_recommendation}
                    </span>
                  </div>
                </div>

                {decisionFeedback && (
                  <div
                    style={{
                      marginTop: "1rem",
                      padding: "10px 14px",
                      borderRadius: "8px",
                      background: decisionFeedback.includes("Error") ? "rgba(239, 68, 68, 0.2)" : "rgba(16, 185, 129, 0.2)",
                      border: decisionFeedback.includes("Error") ? "1px solid var(--fake)" : "1px solid var(--real)",
                      fontSize: "0.85rem",
                    }}
                  >
                    {decisionFeedback}
                  </div>
                )}
              </div>

              {/* Video Stream + Telemetry Grid */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.25rem" }}>
                {/* Video Player Box */}
                <div className="glass" style={{ padding: "1.25rem", display: "flex", flexDirection: "column", gap: "10px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <h3 style={{ fontSize: "0.95rem", fontWeight: 600 }}>Archived Live Clip</h3>
                    <span style={{ fontSize: "0.75rem", color: "var(--real)" }}>● Short-Lived HMAC Signed Stream</span>
                  </div>
                  <div
                    style={{
                      width: "100%",
                      aspectRatio: "16/10",
                      background: "#000",
                      borderRadius: "10px",
                      overflow: "hidden",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      border: "1px solid var(--border)",
                    }}
                  >
                    {loadingClip ? (
                      <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", textAlign: "center" }}>
                        <div className="spinner" style={{ margin: "0 auto 8px" }} />
                        Signing and loading stream...
                      </div>
                    ) : clipError ? (
                      <div style={{ color: "#fca5a5", fontSize: "0.8rem", padding: "1rem", textAlign: "center" }}>
                        ⚠️ {clipError}
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
                      <div style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>No video stream available</div>
                    )}
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.7rem", color: "var(--text-muted)" }}>
                    <span>SHA-256: {clipAccess?.sha256 ? `${clipAccess.sha256.slice(0, 16)}...` : "Verified"}</span>
                    <span>Expiry: {clipAccess?.expires_in || 600}s ticket</span>
                  </div>
                </div>

                {/* Telemetry & Signals Box */}
                <div className="glass" style={{ padding: "1.25rem", display: "flex", flexDirection: "column", gap: "12px" }}>
                  <h3 style={{ fontSize: "0.95rem", fontWeight: 600 }}>Physiological &amp; Identity Telemetry</h3>

                  {/* Deepfake Bar */}
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", marginBottom: "4px" }}>
                      <span>Deepfake Anomaly Probability</span>
                      <span style={{ fontWeight: 700, color: (selectedCase.signals?.deepfake_score || 0) >= 0.4 ? "var(--fake)" : "var(--real)" }}>
                        {((selectedCase.signals?.deepfake_score || 0) * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="confidence-bar">
                      <div
                        className="confidence-bar-fill"
                        style={{
                          width: `${(selectedCase.signals?.deepfake_score || 0) * 100}%`,
                          background: (selectedCase.signals?.deepfake_score || 0) >= 0.4 ? "var(--fake)" : "var(--real)",
                        }}
                      />
                    </div>
                  </div>

                  {/* Metric Grid */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginTop: "4px" }}>
                    <div style={{ background: "rgba(255,255,255,0.03)", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--border)" }}>
                      <div style={{ color: "var(--text-muted)", fontSize: "0.7rem" }}>Face Cosine Match</div>
                      <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--accent-2)" }}>
                        {((selectedCase.signals?.cosine_similarity_score || 0) * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div style={{ background: "rgba(255,255,255,0.03)", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--border)" }}>
                      <div style={{ color: "var(--text-muted)", fontSize: "0.7rem" }}>6-Hour Velocity</div>
                      <div style={{ fontSize: "1.1rem", fontWeight: 700, color: (selectedCase.signals?.registry_velocity_6hr || 0) >= 3 ? "var(--uncertain)" : "var(--real)" }}>
                        {selectedCase.signals?.registry_velocity_6hr || 1} attempts
                      </div>
                    </div>
                    <div style={{ background: "rgba(255,255,255,0.03)", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--border)" }}>
                      <div style={{ color: "var(--text-muted)", fontSize: "0.7rem" }}>Audio-Video Sync</div>
                      <div style={{ fontSize: "1.1rem", fontWeight: 700 }}>
                        {selectedCase.signals?.av_sync_ms || 0} ms
                      </div>
                    </div>
                    <div style={{ background: "rgba(255,255,255,0.03)", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--border)" }}>
                      <div style={{ color: "var(--text-muted)", fontSize: "0.7rem" }}>WebRTC Network Jitter</div>
                      <div style={{ fontSize: "1.1rem", fontWeight: 700 }}>
                        {selectedCase.signals?.webrtc_jitter_ms || 0} ms
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Stage 3 Autonomous Agent Tool Execution Trace */}
              <div className="glass" style={{ padding: "1.25rem" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: "8px" }}>
                  Stage 3 Agent Investigation Trace (Cryptographically Sealed)
                </h3>
                <pre
                  style={{
                    background: "rgba(0,0,0,0.4)",
                    padding: "12px",
                    borderRadius: "8px",
                    fontSize: "0.8rem",
                    color: "#a5f3fc",
                    whiteSpace: "pre-wrap",
                    fontFamily: "monospace",
                    maxHeight: "180px",
                    overflowY: "auto",
                    border: "1px solid var(--border)",
                  }}
                >
                  {selectedCase.dossier_summary || JSON.stringify(selectedCase.tool_calls_trace, null, 2)}
                </pre>
              </div>

              {/* Reviewer Action Panel */}
              <div className="glass" style={{ padding: "1.25rem", display: "flex", flexDirection: "column", gap: "12px" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: 600 }}>Human Adjudication</h3>
                <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: "12px" }}>
                  <input
                    type="text"
                    placeholder="Reviewer Name / ID"
                    value={reviewerName}
                    onChange={(e) => setReviewerName(e.target.value)}
                    style={{
                      padding: "8px 12px",
                      borderRadius: "8px",
                      background: "rgba(255,255,255,0.05)",
                      border: "1px solid var(--border)",
                      color: "white",
                      fontSize: "0.85rem",
                    }}
                  />
                  <input
                    type="text"
                    placeholder="Reviewer investigative notes or rationale..."
                    value={reviewNotes}
                    onChange={(e) => setReviewNotes(e.target.value)}
                    style={{
                      padding: "8px 12px",
                      borderRadius: "8px",
                      background: "rgba(255,255,255,0.05)",
                      border: "1px solid var(--border)",
                      color: "white",
                      fontSize: "0.85rem",
                    }}
                  />
                </div>

                <div style={{ display: "flex", gap: "12px", marginTop: "4px" }}>
                  <button
                    disabled={submittingDecision}
                    onClick={() => handleDecision("approve")}
                    style={{
                      flex: 1,
                      padding: "12px",
                      borderRadius: "10px",
                      border: "none",
                      background: "linear-gradient(135deg, #10b981, #059669)",
                      color: "white",
                      fontWeight: 700,
                      cursor: "pointer",
                      boxShadow: "0 0 15px rgba(16, 185, 129, 0.4)",
                      transition: "all 0.2s ease",
                    }}
                  >
                    ✓ APPROVE ONBOARDING
                  </button>
                  <button
                    disabled={submittingDecision}
                    onClick={() => handleDecision("reject")}
                    style={{
                      flex: 1,
                      padding: "12px",
                      borderRadius: "10px",
                      border: "none",
                      background: "linear-gradient(135deg, #ef4444, #dc2626)",
                      color: "white",
                      fontWeight: 700,
                      cursor: "pointer",
                      boxShadow: "0 0 15px rgba(239, 68, 68, 0.4)",
                      transition: "all 0.2s ease",
                    }}
                  >
                    ✕ REJECT ONBOARDING
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="glass" style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
              Select a case from the queue to view dossier and video playback.
            </div>
          )}
        </div>
      ) : (
        /* ═══════════════════════════════════════════════════════════════════
           AUDIT CHAIN EXPLORER VIEW
           ═══════════════════════════════════════════════════════════════════ */
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {/* Action & Verification Banner */}
          <div className="glass" style={{ padding: "1.5rem", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
            <div>
              <h2 style={{ fontSize: "1.2rem", fontWeight: 700 }}>Cryptographic Hash Chain</h2>
              <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: "2px" }}>
                Total Sealed Blocks: {auditBlocks.length} | SHA-256 prev_hash Linkage
              </p>
            </div>

            <div style={{ display: "flex", gap: "12px" }}>
              <button
                onClick={loadAuditChain}
                style={{
                  padding: "8px 16px",
                  borderRadius: "8px",
                  border: "1px solid var(--border)",
                  background: "rgba(255,255,255,0.05)",
                  color: "white",
                  cursor: "pointer",
                }}
              >
                ↻ Refresh Chain
              </button>
              <button
                disabled={verifyingChain}
                onClick={handleVerifyChain}
                className="btn-primary"
                style={{ padding: "8px 20px" }}
              >
                {verifyingChain ? "Verifying..." : "⚡ Verify Cryptographic Chain"}
              </button>
            </div>
          </div>

          {/* Verification Results Panel */}
          {verificationResult && (
            <div
              style={{
                padding: "1rem 1.5rem",
                borderRadius: "12px",
                background: verificationResult.is_valid ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)",
                border: verificationResult.is_valid ? "1px solid var(--real)" : "1px solid var(--fake)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ fontSize: "1.4rem" }}>{verificationResult.is_valid ? "🛡️" : "⚠️"}</span>
                <div>
                  <div style={{ fontWeight: 700, fontSize: "1rem", color: verificationResult.is_valid ? "var(--real)" : "var(--fake)" }}>
                    {verificationResult.is_valid ? "VERIFICATION SUCCESS" : "TAMPER DETECTED"}
                  </div>
                  <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                    {verificationResult.message} · Verified {verificationResult.verified_count} of {verificationResult.total_count} blocks
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Block Visualizer List */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {auditBlocks.length === 0 ? (
              <div className="glass" style={{ padding: "3rem", textAlign: "center", color: "var(--text-muted)" }}>
                No audit blocks found in chain.
              </div>
            ) : (
              auditBlocks.map((b) => (
                <div
                  key={b.index}
                  className="glass"
                  style={{
                    padding: "1.25rem",
                    borderLeft: `4px solid ${
                      b.record_type === "upload" ? "var(--accent-2)" :
                      b.record_type === "decision" ? "var(--accent)" :
                      b.record_type === "identity" ? "#f59e0b" :
                      b.record_type === "investigation" ? "#ec4899" :
                      b.record_type === "human_review" ? "var(--real)" : "var(--border)"
                    }`,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <span style={{ fontWeight: 800, fontSize: "1rem", color: "var(--text-muted)" }}>
                        #{b.index}
                      </span>
                      <span
                        className="badge"
                        style={{
                          background: "rgba(255,255,255,0.08)",
                          color: "white",
                          fontSize: "0.75rem",
                        }}
                      >
                        {b.record_type.toUpperCase()}
                      </span>
                      <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                        Session: {b.session_id.slice(0, 8)}...
                      </span>
                    </div>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      {b.timestamp}
                    </span>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginTop: "10px", fontSize: "0.75rem" }}>
                    <div>
                      <span style={{ color: "var(--text-muted)" }}>Prev Hash: </span>
                      <code style={{ color: "#a5f3fc" }}>{b.prev_hash.slice(0, 24)}...</code>
                    </div>
                    <div>
                      <span style={{ color: "var(--text-muted)" }}>Record Hash: </span>
                      <code style={{ color: "#c084fc" }}>{b.record_hash.slice(0, 24)}...</code>
                    </div>
                  </div>

                  <pre
                    style={{
                      background: "rgba(0,0,0,0.3)",
                      padding: "8px 12px",
                      borderRadius: "6px",
                      marginTop: "10px",
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      whiteSpace: "pre-wrap",
                      fontFamily: "monospace",
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
    </main>
  );
}

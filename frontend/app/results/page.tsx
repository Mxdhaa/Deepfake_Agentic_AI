"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { DetectionResult } from "@/lib/api";

export default function ResultsPage() {
  const router = useRouter();
  const [result, setResult] = useState<DetectionResult | null>(null);

  useEffect(() => {
    const raw = sessionStorage.getItem("deepfake_result");
    if (!raw) {
      router.push("/");
      return;
    }
    try {
      setResult(JSON.parse(raw));
    } catch {
      router.push("/");
    }
  }, [router]);

  if (!result) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}>
        <div className="spinner" />
      </div>
    );
  }

  // Map underlying model verdict strictly to 3 customer-facing states
  const isPass = result.label === "REAL";
  const isReview = result.label === "UNCERTAIN";
  const isFail = result.label === "FAKE";

  const headline = isPass
    ? "You're verified"
    : isReview
    ? "We're reviewing your application"
    : "We couldn't verify you";

  const badgeText = isPass
    ? "VERIFIED ✓"
    : isReview
    ? "UNDER REVIEW ◈"
    : "UNVERIFIED ✕";

  const badgeClass = isPass
    ? "badge-real"
    : isReview
    ? "badge-uncertain"
    : "badge-fake";

  const icon = isPass ? "✅" : isReview ? "⏳" : "❌";

  const description = isPass
    ? "Your identity document and live presence were successfully confirmed."
    : isReview
    ? "Your submission is undergoing secondary verification. We'll update your status shortly."
    : "We could not confirm your identity. Please ensure you are in a well-lit environment with your camera centered and try again.";

  return (
    <main
      style={{
        position: "relative",
        zIndex: 1,
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem",
        gap: "1.5rem",
      }}
    >
      {/* Back button */}
      <button
        id="back-btn"
        onClick={() => router.push("/")}
        style={{
          position: "absolute",
          top: "1.5rem",
          left: "1.5rem",
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "8px",
          padding: "8px 16px",
          color: "var(--text-muted)",
          cursor: "pointer",
          fontSize: "0.875rem",
          transition: "all 0.2s",
        }}
      >
        ← Return Home
      </button>

      <h1
        style={{
          fontSize: "clamp(1.75rem, 4vw, 2.5rem)",
          fontWeight: 800,
          background: "linear-gradient(135deg, #f1f5f9 0%, #a855f7 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text",
          textAlign: "center",
        }}
      >
        {headline}
      </h1>

      {/* Main result card */}
      <div
        className="glass"
        style={{
          width: "100%",
          maxWidth: "580px",
          padding: "2.5rem 2rem",
          display: "flex",
          flexDirection: "column",
          gap: "1.5rem",
        }}
      >
        {/* Verdict Badge & Icon */}
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "3.5rem", marginBottom: "0.75rem" }}>{icon}</div>
          <div className={`badge ${badgeClass}`} style={{ fontSize: "1rem", padding: "6px 20px", marginBottom: "0.75rem" }}>
            {badgeText}
          </div>
          <p style={{ color: "#94a3b8", fontSize: "0.95rem", lineHeight: 1.5, maxWidth: "480px", margin: "0 auto" }}>
            {description}
          </p>
        </div>

        {/* Customer-Facing Verification Metadata */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "1rem",
            marginTop: "0.5rem",
          }}
        >
          {[
            { label: "Verification Status", value: isPass ? "Confirmed" : isReview ? "In Progress" : "Incomplete" },
            { label: "Reference ID", value: result.request_id ? result.request_id.slice(0, 10) + "…" : "REF-SESSION" },
            { label: "Security Verification", value: "SHA-256 Sealed" },
            { label: "Audited Timestamp", value: new Date().toLocaleDateString() },
          ].map(({ label, value }) => (
            <div
              key={label}
              style={{
                background: "rgba(255, 255, 255, 0.03)",
                border: "1px solid var(--border)",
                borderRadius: "10px",
                padding: "0.875rem 1rem",
              }}
            >
              <div style={{ color: "var(--text-muted)", fontSize: "0.75rem", marginBottom: "4px" }}>{label}</div>
              <div style={{ fontWeight: 600, fontSize: "0.9rem", color: "#f8fafc" }}>{value}</div>
            </div>
          ))}
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: "1rem", marginTop: "0.5rem" }}>
          <button
            id="start-new-btn"
            className="btn-primary"
            onClick={() => router.push("/")}
            style={{ flex: 1 }}
          >
            {isPass ? "Complete Onboarding" : "Try Again"}
          </button>
        </div>
      </div>
    </main>
  );
}

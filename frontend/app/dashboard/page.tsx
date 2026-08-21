"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getHealth } from "@/lib/api";
import type { HealthResult } from "@/lib/api";

const MOCK_HISTORY = [
  { id: "a1b2c3d4", filename: "portrait.jpg",   label: "REAL", confidence: 0.12, time: "2 min ago" },
  { id: "e5f6g7h8", filename: "interview.mp4",  label: "FAKE", confidence: 0.93, time: "15 min ago" },
  { id: "i9j0k1l2", filename: "selfie.png",     label: "UNCERTAIN", confidence: 0.51, time: "1 hr ago" },
  { id: "m3n4o5p6", filename: "headshot.webp",  label: "REAL", confidence: 0.08, time: "3 hr ago" },
  { id: "q7r8s9t0", filename: "clip.mp4",       label: "FAKE", confidence: 0.87, time: "Yesterday" },
];

export default function DashboardPage() {
  const router = useRouter();
  const [health, setHealth] = useState<HealthResult | null>(null);
  const [healthError, setHealthError] = useState(false);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealthError(true));
  }, []);

  const stats = {
    total: MOCK_HISTORY.length,
    fake:  MOCK_HISTORY.filter((h) => h.label === "FAKE").length,
    real:  MOCK_HISTORY.filter((h) => h.label === "REAL").length,
  };

  return (
    <main
      style={{
        position: "relative",
        zIndex: 1,
        minHeight: "100vh",
        padding: "2rem",
        maxWidth: "900px",
        margin: "0 auto",
        display: "flex",
        flexDirection: "column",
        gap: "2rem",
      }}
    >
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <h1
            style={{
              fontSize: "2rem",
              fontWeight: 800,
              background: "linear-gradient(135deg, #f1f5f9 0%, #a855f7 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            Dashboard
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
            Detection history &amp; system status
          </p>
        </div>
        <button
          id="new-analysis-btn"
          className="btn-primary"
          onClick={() => router.push("/")}
        >
          + New Analysis
        </button>
      </div>

      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "1rem" }}>
        {[
          { label: "Total Analyzed", value: stats.total, color: "var(--accent)" },
          { label: "Deepfakes Found", value: stats.fake, color: "var(--fake)" },
          { label: "Authentic Media", value: stats.real, color: "var(--real)" },
          { label: "Avg Confidence",  value: "78%",      color: "var(--accent-2)" },
        ].map(({ label, value, color }) => (
          <div
            key={label}
            className="glass"
            style={{ padding: "1.25rem", textAlign: "center" }}
          >
            <div style={{ fontSize: "2rem", fontWeight: 800, color }}>{value}</div>
            <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginTop: "4px" }}>{label}</div>
          </div>
        ))}
      </div>

      {/* Backend status */}
      <div className="glass" style={{ padding: "1.25rem", display: "flex", alignItems: "center", gap: "12px" }}>
        {healthError ? (
          <>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--fake)" }} />
            <span style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
              Backend offline — start with <code style={{ color: "var(--accent)" }}>uvicorn main:app --reload</code>
            </span>
          </>
        ) : health ? (
          <>
            <div className="pulse-dot" />
            <span style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
              Backend v{health.version} · Model {health.model_loaded ? "✅ loaded" : "⚠️ stub mode"} · Uptime {health.uptime_seconds}s
            </span>
          </>
        ) : (
          <>
            <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
            <span style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>Checking backend…</span>
          </>
        )}
      </div>

      {/* History table */}
      <div className="glass" style={{ padding: "1.5rem" }}>
        <h2 style={{ fontWeight: 700, marginBottom: "1rem", fontSize: "1rem" }}>Recent Analyses</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {MOCK_HISTORY.map((item) => {
            const labelClass =
              item.label === "REAL" ? "badge-real" :
              item.label === "FAKE" ? "badge-fake" :
              "badge-uncertain";
            const conf = (item.confidence * 100).toFixed(1);
            return (
              <div
                key={item.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "1rem",
                  padding: "0.875rem 1rem",
                  background: "rgba(255,255,255,0.03)",
                  border: "1px solid var(--border)",
                  borderRadius: "10px",
                  flexWrap: "wrap",
                }}
              >
                <code style={{ color: "var(--text-muted)", fontSize: "0.75rem", minWidth: "6ch" }}>{item.id}</code>
                <span style={{ flex: 1, fontWeight: 500, fontSize: "0.875rem" }}>{item.filename}</span>
                <span className={`badge ${labelClass}`}>{item.label}</span>
                <span style={{ color: "var(--text-muted)", fontSize: "0.8rem", minWidth: "50px", textAlign: "right" }}>{conf}%</span>
                <span style={{ color: "var(--text-muted)", fontSize: "0.75rem", minWidth: "80px", textAlign: "right" }}>{item.time}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer */}
      <p style={{ color: "var(--text-muted)", fontSize: "0.75rem", textAlign: "center" }}>
        Deepfake Agentic AI · Phase 0 — History is demo data; persistence coming in Phase 2.
      </p>
    </main>
  );
}

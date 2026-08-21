"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { DetectionResult } from "@/lib/api";

function ConfidenceBar({ value, label }: { value: number; label: string }) {
  const color =
    label === "REAL" ? "var(--real)" :
    label === "FAKE" ? "var(--fake)" :
    "var(--uncertain)";

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
        <span style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>Deepfake Probability</span>
        <span style={{ fontWeight: 700, color }}>{(value * 100).toFixed(1)}%</span>
      </div>
      <div className="confidence-bar">
        <div
          className="confidence-bar-fill"
          style={{
            width: `${value * 100}%`,
            background: `linear-gradient(90deg, ${color}88, ${color})`,
          }}
        />
      </div>
    </div>
  );
}

export default function ResultsPage() {
  const router = useRouter();
  const [result, setResult] = useState<DetectionResult | null>(null);

  useEffect(() => {
    const raw = sessionStorage.getItem("deepfake_result");
    if (!raw) {
      router.push("/");
      return;
    }
    setResult(JSON.parse(raw));
  }, [router]);

  if (!result) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}>
        <div className="spinner" />
      </div>
    );
  }

  const labelClass =
    result.label === "REAL" ? "badge-real" :
    result.label === "FAKE" ? "badge-fake" :
    "badge-uncertain";

  const labelIcon =
    result.label === "REAL" ? "✅" :
    result.label === "FAKE" ? "🚨" :
    "⚠️";

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
        ← Back
      </button>

      <h1
        style={{
          fontSize: "clamp(1.5rem, 4vw, 2.5rem)",
          fontWeight: 800,
          background: "linear-gradient(135deg, #f1f5f9 0%, #a855f7 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text",
          textAlign: "center",
        }}
      >
        Analysis Complete
      </h1>

      {/* Main result card */}
      <div className="glass" style={{ width: "100%", maxWidth: "600px", padding: "2rem", display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        {/* Verdict */}
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "3.5rem", marginBottom: "0.75rem" }}>{labelIcon}</div>
          <div className={`badge ${labelClass}`} style={{ fontSize: "1rem", padding: "6px 20px", marginBottom: "0.5rem" }}>
            {result.label}
          </div>
          <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", marginTop: "0.5rem" }}>
            {result.filename}
          </p>
        </div>

        {/* Confidence bar */}
        <ConfidenceBar value={result.confidence} label={result.label} />

        {/* Metadata grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "1rem",
          }}
        >
          {[
            { label: "Processing Time", value: `${result.processing_time_ms.toFixed(1)} ms` },
            { label: "Request ID",      value: result.request_id.slice(0, 8) + "…" },
            { label: "File Hash",       value: result.file_hash.slice(0, 12) + "…" },
            { label: "Is Deepfake",     value: result.is_deepfake ? "Yes" : "No" },
          ].map(({ label, value }) => (
            <div
              key={label}
              style={{
                background: "rgba(255,255,255,0.03)",
                border: "1px solid var(--border)",
                borderRadius: "10px",
                padding: "0.875rem 1rem",
              }}
            >
              <div style={{ color: "var(--text-muted)", fontSize: "0.75rem", marginBottom: "4px" }}>{label}</div>
              <div style={{ fontWeight: 600, fontSize: "0.9rem", fontFamily: "monospace" }}>{value}</div>
            </div>
          ))}
        </div>

        {/* Artifacts */}
        {result.artifacts.length > 0 && (
          <div>
            <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginBottom: "8px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Detected Artifacts
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
              {result.artifacts.map((art) => (
                <span
                  key={art}
                  style={{
                    background: "rgba(239,68,68,0.1)",
                    border: "1px solid rgba(239,68,68,0.25)",
                    color: "#ef4444",
                    borderRadius: "6px",
                    padding: "4px 10px",
                    fontSize: "0.75rem",
                    fontWeight: 500,
                  }}
                >
                  {art.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Agent summary */}
        {result.agent_summary && (
          <div
            style={{
              background: "rgba(168,85,247,0.08)",
              border: "1px solid rgba(168,85,247,0.2)",
              borderRadius: "10px",
              padding: "1rem",
            }}
          >
            <p style={{ color: "#a855f7", fontSize: "0.75rem", fontWeight: 600, marginBottom: "6px", textTransform: "uppercase", letterSpacing: "0.06em" }}>
              🤖 Agent Summary
            </p>
            <p style={{ color: "var(--text-primary)", fontSize: "0.875rem", lineHeight: 1.6 }}>
              {result.agent_summary}
            </p>
          </div>
        )}

        {/* Actions */}
        <div style={{ display: "flex", gap: "1rem" }}>
          <button
            id="analyze-another-btn"
            className="btn-primary"
            onClick={() => router.push("/")}
            style={{ flex: 1 }}
          >
            Analyze Another
          </button>
          <button
            id="copy-result-btn"
            onClick={() => navigator.clipboard.writeText(JSON.stringify(result, null, 2))}
            style={{
              flex: 1,
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: "10px",
              color: "var(--text-primary)",
              cursor: "pointer",
              fontWeight: 600,
              fontSize: "1rem",
              transition: "all 0.2s",
            }}
          >
            📋 Copy JSON
          </button>
        </div>
      </div>
    </main>
  );
}

"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { detectDeepfake, ApiError } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback((f: File) => {
    if (f.size > 50 * 1024 * 1024) {
      setError("File too large. Maximum size is 50 MB.");
      return;
    }
    setFile(f);
    setError(null);
    const url = URL.createObjectURL(f);
    setPreview(url);
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const f = e.dataTransfer.files[0];
      if (f) handleFile(f);
    },
    [handleFile],
  );

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleFile(f);
  };

  const handleAnalyze = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const result = await detectDeepfake(file);
      // Store result in sessionStorage and navigate to results page
      sessionStorage.setItem("deepfake_result", JSON.stringify(result));
      router.push("/results");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`API Error ${err.status}: ${err.message}`);
      } else {
        setError("Failed to connect to backend. Is it running at localhost:8000?");
      }
    } finally {
      setLoading(false);
    }
  };

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
        gap: "2rem",
      }}
    >
      {/* Header */}
      <div style={{ textAlign: "center", maxWidth: "640px" }}>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            background: "rgba(168,85,247,0.15)",
            border: "1px solid rgba(168,85,247,0.3)",
            borderRadius: "999px",
            padding: "6px 16px",
            fontSize: "0.8rem",
            fontWeight: 600,
            color: "#a855f7",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            marginBottom: "1.5rem",
          }}
        >
          <span>🤖</span>
          <span>LangGraph Agentic AI</span>
        </div>

        <h1
          style={{
            fontSize: "clamp(2rem, 5vw, 3.5rem)",
            fontWeight: 800,
            lineHeight: 1.1,
            marginBottom: "1rem",
            background: "linear-gradient(135deg, #f1f5f9 0%, #a855f7 60%, #06b6d4 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
          }}
        >
          Deepfake Detection
          <br />
          Powered by AI Agents
        </h1>

        <p style={{ color: "var(--text-muted)", fontSize: "1.1rem", lineHeight: 1.6 }}>
          Upload an image or video and our multi-step LangGraph agent pipeline will
          analyze it for deepfake manipulation with full explainability.
        </p>
      </div>

      {/* Upload Card */}
      <div
        className="glass"
        style={{ width: "100%", maxWidth: "560px", padding: "2rem" }}
      >
        {/* Drop Zone */}
        <div
          id="dropzone"
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => fileInputRef.current?.click()}
          style={{
            border: `2px dashed ${dragging ? "var(--accent)" : "var(--border)"}`,
            borderRadius: "12px",
            padding: "2.5rem 1.5rem",
            textAlign: "center",
            cursor: "pointer",
            transition: "all 0.2s ease",
            background: dragging ? "rgba(168,85,247,0.08)" : "transparent",
            marginBottom: "1.5rem",
          }}
        >
          {preview ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "12px" }}>
              {file?.type.startsWith("video/") ? (
                <video
                  src={preview}
                  style={{ maxHeight: "180px", borderRadius: "8px", maxWidth: "100%" }}
                  controls
                />
              ) : (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={preview}
                  alt="Preview"
                  style={{ maxHeight: "180px", borderRadius: "8px", maxWidth: "100%", objectFit: "cover" }}
                />
              )}
              <span style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                📎 {file?.name} ({((file?.size ?? 0) / 1024 / 1024).toFixed(2)} MB)
              </span>
              <span style={{ color: "var(--accent)", fontSize: "0.8rem" }}>Click to change file</span>
            </div>
          ) : (
            <>
              <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>🔍</div>
              <p style={{ color: "var(--text-primary)", fontWeight: 600, marginBottom: "0.5rem" }}>
                Drop your file here
              </p>
              <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                Supports JPG, PNG, WebP, MP4 — max 50 MB
              </p>
            </>
          )}
        </div>

        <input
          ref={fileInputRef}
          id="file-input"
          type="file"
          accept="image/jpeg,image/png,image/webp,video/mp4,video/avi,video/quicktime"
          onChange={onInputChange}
          style={{ display: "none" }}
        />

        {error && (
          <div
            style={{
              background: "rgba(239,68,68,0.1)",
              border: "1px solid rgba(239,68,68,0.3)",
              borderRadius: "8px",
              padding: "0.75rem 1rem",
              color: "#ef4444",
              fontSize: "0.875rem",
              marginBottom: "1rem",
            }}
          >
            ⚠️ {error}
          </div>
        )}

        <button
          id="analyze-btn"
          className="btn-primary"
          onClick={handleAnalyze}
          disabled={!file || loading}
          style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: "10px" }}
        >
          {loading ? (
            <>
              <div className="spinner" />
              <span>Analyzing with AI Agent…</span>
            </>
          ) : (
            <>
              <span>⚡</span>
              <span>Analyze for Deepfakes</span>
            </>
          )}
        </button>
      </div>

      {/* Pipeline Steps */}
      <div
        style={{
          display: "flex",
          gap: "1rem",
          flexWrap: "wrap",
          justifyContent: "center",
          maxWidth: "640px",
        }}
      >
        {[
          { icon: "🖼️", step: "Preprocess", desc: "Decode & normalize" },
          { icon: "🧠", step: "Detect",     desc: "EfficientNet-B4" },
          { icon: "🔬", step: "Analyze",    desc: "Artifact extraction" },
          { icon: "📊", step: "Report",     desc: "Structured result" },
        ].map(({ icon, step, desc }, i) => (
          <div
            key={step}
            className="glass"
            style={{
              padding: "0.875rem 1.25rem",
              display: "flex",
              alignItems: "center",
              gap: "10px",
              fontSize: "0.875rem",
            }}
          >
            <span style={{ fontSize: "1.25rem" }}>{icon}</span>
            <div>
              <div style={{ fontWeight: 600 }}>{i + 1}. {step}</div>
              <div style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>{desc}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <p style={{ color: "var(--text-muted)", fontSize: "0.75rem", textAlign: "center" }}>
        Deepfake Agentic AI · Phase 0 · MIT License
      </p>
    </main>
  );
}

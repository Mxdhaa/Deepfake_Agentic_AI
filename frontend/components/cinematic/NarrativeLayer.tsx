"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import Link from "next/link";
import {
  FileText,
  Fingerprint,
  Activity,
  ShieldCheck,
  CheckCircle2,
  Lock,
  ArrowRight,
  UserCheck,
} from "lucide-react";

interface NarrativeLayerProps {
  scrollProgress: number; // 0.0 -> 1.0
  currentAct: number;
}

export default function NarrativeLayer({ scrollProgress, currentAct }: NarrativeLayerProps) {
  // Act 01: Character Scramble state for "IDENTITY"
  const [scrambleText, setScrambleText] = useState("IDENTITY");

  useEffect(() => {
    if (currentAct === 1) {
      const frames = ["I D 3 N T 1 T Y", "1 D E N T I T Y", "I D E N T 1 T Y", "IDENTITY"];
      let idx = 0;
      const interval = setInterval(() => {
        if (idx < frames.length) {
          setScrambleText(frames[idx]);
          idx++;
        } else {
          clearInterval(interval);
        }
      }, 100);
      return () => clearInterval(interval);
    } else {
      setScrambleText("IDENTITY");
    }
  }, [currentAct]);

  return (
    <div
      style={{
        position: "relative",
        zIndex: 10,
        pointerEvents: "none",
      }}
    >
      {/* ══════════════════════════════════════════════════════════════════
          ACT 00 — ARRIVAL (0.00 -> 0.10)
      ══════════════════════════════════════════════════════════════════ */}
      <section
        style={{
          height: "100vh",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "flex-start",
          padding: "0 6vw",
          maxWidth: "1400px",
          margin: "0 auto",
        }}
      >
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: currentAct === 0 ? 1 : 0, y: currentAct === 0 ? 0 : -20 }}
          transition={{ duration: 0.5 }}
          style={{ maxWidth: "680px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1.5rem" }}>
            IDENTITY / 00 — THE SIGNAL
          </div>

          <h1
            className="font-serif"
            style={{
              fontSize: "clamp(2.4rem, 5vw, 4rem)",
              fontWeight: 500,
              lineHeight: 1.15,
              color: "#FFFFFF",
              letterSpacing: "-0.02em",
              marginBottom: "1.25rem",
            }}
          >
            Before trust, there is uncertainty.
          </h1>

          <p
            style={{
              fontSize: "1.05rem",
              color: "var(--text-muted)",
              lineHeight: 1.6,
              maxWidth: "520px",
              marginBottom: "2.5rem",
            }}
          >
            In a synthetic world, every digital connection begins as an anonymous signal. Scroll to reconstruct presence.
          </p>

          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              fontFamily: "var(--font-mono)",
              fontSize: "0.75rem",
              color: "var(--text-dim)",
              letterSpacing: "0.08em",
            }}
          >
            <span>SCROLL TO BEGIN RECONSTRUCTION</span>
            <span className="animate-bounce">↓</span>
          </div>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          ACT 01 — RECONSTRUCTION (0.10 -> 0.22)
      ══════════════════════════════════════════════════════════════════ */}
      <section
        style={{
          height: "100vh",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "flex-start",
          padding: "0 6vw",
          maxWidth: "1400px",
          margin: "0 auto",
        }}
      >
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: currentAct === 1 ? 1 : 0, y: currentAct === 1 ? 0 : -20 }}
          transition={{ duration: 0.5 }}
          style={{ maxWidth: "720px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1.5rem" }}>
            01 — RECONSTRUCTION
          </div>

          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(2.4rem, 5vw, 4rem)",
              fontWeight: 500,
              lineHeight: 1.15,
              color: "#FFFFFF",
              letterSpacing: "-0.02em",
              marginBottom: "1.25rem",
            }}
          >
            <span style={{ fontFamily: "var(--font-mono)", color: "#3B82F6" }}>{scrambleText}</span> begins with information.
          </h2>

          <p style={{ fontSize: "1.05rem", color: "var(--text-muted)", lineHeight: 1.6, maxWidth: "520px", marginBottom: "1.5rem" }}>
            Thousands of isolated point vectors converge into the geometric contours of a physical identity.
          </p>

          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.725rem",
              color: "var(--text-dim)",
              letterSpacing: "0.05em",
            }}
          >
            SIGNAL FIELD COHERENCE: <span style={{ color: "#3B82F6" }}>84% RECONSTRUCTING</span>
          </div>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          ACT 02 — IDENTITY DATA (0.22 -> 0.34)
      ══════════════════════════════════════════════════════════════════ */}
      <section
        style={{
          height: "100vh",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "7rem 6vw 4rem",
          maxWidth: "1400px",
          margin: "0 auto",
        }}
      >
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: currentAct === 2 ? 1 : 0, y: currentAct === 2 ? 0 : -20 }}
          transition={{ duration: 0.5 }}
          style={{ textAlign: "center", maxWidth: "700px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1rem" }}>
            02 — MULTI-SIGNAL BINDING
          </div>

          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(2rem, 4vw, 3.25rem)",
              fontWeight: 500,
              color: "#FFFFFF",
              marginBottom: "0.75rem",
            }}
          >
            A person becomes a profile.
          </h2>

          <p style={{ fontSize: "0.95rem", color: "var(--text-muted)" }}>
            Identity is assembled from multiple signals — not a single image.
          </p>
        </motion.div>

        {/* 4 Forensic Data Nodes */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: currentAct === 2 ? 1 : 0 }}
          transition={{ duration: 0.5 }}
          style={{
            width: "100%",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "1.25rem",
            pointerEvents: "auto",
          }}
        >
          {[
            { label: "LEGAL CLAIM", val: "Verified Identity Token", icon: <UserCheck size={15} /> },
            { label: "BIOMETRIC EMBEDDING", val: "Facial Template", icon: <Fingerprint size={15} /> },
            { label: "NETWORK VELOCITY", val: "Registry Signal", icon: <Activity size={15} /> },
            { label: "CREDENTIAL TYPE", val: "Sovereign Passport / CKYC", icon: <FileText size={15} /> },
          ].map((item) => (
            <div
              key={item.label}
              style={{
                background: "rgba(10, 10, 10, 0.85)",
                border: "1px solid var(--border-color)",
                borderRadius: "4px",
                padding: "1rem 1.25rem",
                backdropFilter: "blur(8px)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#3B82F6", marginBottom: "4px" }}>
                {item.icon}
                <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.68rem", letterSpacing: "0.08em" }}>
                  {item.label}
                </span>
              </div>
              <div style={{ fontSize: "0.875rem", fontWeight: 500, color: "#FFFFFF" }}>{item.val}</div>
            </div>
          ))}
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          ACT 03 — DOCUMENT & WIRE HASHING (0.34 -> 0.47)
      ══════════════════════════════════════════════════════════════════ */}
      <section
        style={{
          height: "100vh",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "flex-start",
          padding: "0 6vw",
          maxWidth: "1400px",
          margin: "0 auto",
        }}
      >
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: currentAct === 3 ? 1 : 0, y: currentAct === 3 ? 0 : -20 }}
          transition={{ duration: 0.5 }}
          style={{ maxWidth: "600px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1.5rem" }}>
            03 — DOCUMENT EXTRACTION & WIRE HASHING
          </div>

          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(2.2rem, 4.5vw, 3.5rem)",
              fontWeight: 500,
              color: "#FFFFFF",
              letterSpacing: "-0.02em",
              marginBottom: "1.25rem",
            }}
          >
            Evidence has a physical form.
          </h2>

          <p style={{ fontSize: "1rem", color: "var(--text-muted)", lineHeight: 1.6, marginBottom: "2rem" }}>
            The uploaded credential is decomposed into optical regions and its raw wire bytes are sealed with SHA-256 before downstream scoring.
          </p>

          {/* Truncated Hash & Chain Readout */}
          <div
            style={{
              background: "rgba(10, 10, 10, 0.9)",
              border: "1px solid var(--border-color)",
              borderRadius: "4px",
              padding: "1rem 1.25rem",
              fontFamily: "var(--font-mono)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#3B82F6", fontSize: "0.75rem", marginBottom: "6px" }}>
              <Lock size={14} /> WIRE BYTES SHA-256: <span style={{ color: "#FFFFFF" }}>7c9f...a82d</span> SEALED
            </div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-dim)", display: "flex", gap: "6px" }}>
              <span>AUDIT CHAIN:</span>
              <span style={{ color: "var(--text-muted)" }}>[01] → [02] → [03] → [04] → [05] → [06]</span>
            </div>
          </div>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          ACT 04 — THE CRUCIAL DISTINCTION (0.47 -> 0.58)
      ══════════════════════════════════════════════════════════════════ */}
      <section
        style={{
          height: "100vh",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          textAlign: "center",
          padding: "0 6vw",
          maxWidth: "1400px",
          margin: "0 auto",
        }}
      >
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: currentAct === 4 ? 1 : 0, y: currentAct === 4 ? 0 : -20 }}
          transition={{ duration: 0.5 }}
          style={{ maxWidth: "800px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1.5rem" }}>
            04 — SPATIAL TRANSITION
          </div>

          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(2.4rem, 5.5vw, 4.25rem)",
              fontWeight: 500,
              lineHeight: 1.15,
              letterSpacing: "-0.02em",
              marginBottom: "1.5rem",
            }}
          >
            <span style={{ color: "#FFFFFF", display: "block" }}>A document tells us who you are.</span>
            <span style={{ color: "#3B82F6", display: "block" }}>Liveness tells us you're here.</span>
          </h2>

          <p style={{ fontSize: "1.05rem", color: "var(--text-muted)", lineHeight: 1.6, maxWidth: "560px", margin: "0 auto" }}>
            Static documents can be copied or replayed. Live physiological response is harder to fake convincingly.
          </p>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          ACT 05 — LIVENESS (0.58 -> 0.74)
      ══════════════════════════════════════════════════════════════════ */}
      <section
        style={{
          height: "100vh",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "7rem 6vw 4rem",
          maxWidth: "1400px",
          margin: "0 auto",
        }}
      >
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: currentAct === 5 ? 1 : 0, y: currentAct === 5 ? 0 : -20 }}
          transition={{ duration: 0.5 }}
          style={{ textAlign: "center", maxWidth: "700px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "0.75rem" }}>
            05 — LIVENESS SIGNAL ANALYSIS
          </div>

          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(2rem, 4vw, 3.25rem)",
              fontWeight: 500,
              color: "#FFFFFF",
              marginBottom: "0.5rem",
            }}
          >
            Prove you're present.
          </h2>

          <p style={{ fontSize: "0.95rem", color: "var(--text-muted)" }}>
            A short camera challenge provides live signals that can be evaluated alongside the identity document.
          </p>
        </motion.div>

        {/* Technical Readouts */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: currentAct === 5 ? 1 : 0 }}
          transition={{ duration: 0.5 }}
          style={{
            width: "100%",
            maxWidth: "900px",
            background: "rgba(10, 10, 10, 0.9)",
            border: "1px solid var(--border-color)",
            borderRadius: "4px",
            padding: "1.25rem 1.5rem",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: "1.25rem",
            fontFamily: "var(--font-mono)",
            pointerEvents: "auto",
          }}
        >
          {[
            { label: "LIVENESS CAPTURE", val: "COMPLETE ████████", col: "#10B981" },
            { label: "MOTION SIGNAL", val: "DETECTED ✓", col: "#3B82F6" },
            { label: "BLINK DYNAMICS", val: "14.2 BPM", col: "#FFFFFF" },
            { label: "AUDIO/VIDEO SYNC", val: "12 ms LAG", col: "#FFFFFF" },
          ].map((metric) => (
            <div key={metric.label} style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <span style={{ fontSize: "0.68rem", color: "var(--text-dim)", letterSpacing: "0.08em" }}>
                {metric.label}
              </span>
              <span style={{ fontSize: "0.875rem", fontWeight: 600, color: metric.col }}>
                {metric.val}
              </span>
            </div>
          ))}
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          ACT 06 — CONVERGENCE (0.74 -> 0.88)
      ══════════════════════════════════════════════════════════════════ */}
      <section
        style={{
          height: "100vh",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          textAlign: "center",
          padding: "0 6vw",
          maxWidth: "1400px",
          margin: "0 auto",
        }}
      >
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: currentAct === 6 ? 1 : 0, y: currentAct === 6 ? 0 : -20 }}
          transition={{ duration: 0.5 }}
          style={{ maxWidth: "700px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1.5rem" }}>
            06 — CONVERGENCE
          </div>

          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(2.2rem, 5vw, 3.75rem)",
              fontWeight: 500,
              color: "#FFFFFF",
              letterSpacing: "-0.02em",
              marginBottom: "1.25rem",
            }}
          >
            All signals converge into one decision.
          </h2>

          <p style={{ fontSize: "1.05rem", color: "var(--text-muted)", lineHeight: 1.6, maxWidth: "540px", margin: "0 auto" }}>
            Document, biometric match, and liveness signal fuse into one cryptographically sealed decision.
          </p>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          ACT 07 — VERIFY (0.88 -> 1.00)
      ══════════════════════════════════════════════════════════════════ */}
      <section
        id="security"
        style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          textAlign: "center",
          padding: "6rem 6vw 4rem",
          maxWidth: "1400px",
          margin: "0 auto",
        }}
      >
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: currentAct === 7 ? 1 : 0, y: currentAct === 7 ? 0 : 20 }}
          transition={{ duration: 0.5 }}
          style={{ maxWidth: "750px", pointerEvents: "auto" }}
        >
          {/* Restrained Geometric Verification Mark */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "5px 14px",
              borderRadius: "4px",
              background: "rgba(59, 130, 246, 0.08)",
              border: "1px solid rgba(59, 130, 246, 0.25)",
              fontFamily: "var(--font-mono)",
              fontSize: "0.75rem",
              color: "#3B82F6",
              marginBottom: "1.5rem",
            }}
          >
            <CheckCircle2 size={15} /> VERIFICATION COMPLETE
          </div>

          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(2.6rem, 6vw, 4.5rem)",
              fontWeight: 500,
              color: "#FFFFFF",
              letterSpacing: "-0.03em",
              lineHeight: 1.1,
              marginBottom: "1.25rem",
            }}
          >
            Verify your identity.
          </h2>

          <p style={{ fontSize: "1.15rem", color: "var(--text-muted)", maxWidth: "580px", margin: "0 auto 2.5rem", lineHeight: 1.6 }}>
            A secure, multi-stage verification process using your details, identity document, and a live camera check.
          </p>

          {/* Primary Route Button */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "1rem" }}>
            <Link
              href="/onboarding"
              className="btn-primary-blue"
              style={{
                fontSize: "1rem",
                padding: "0.9rem 2.5rem",
              }}
            >
              <span>Get Started</span>
              <ArrowRight size={18} />
            </Link>

            <span style={{ fontSize: "0.78rem", fontFamily: "var(--font-mono)", color: "var(--text-dim)" }}>
              Cryptographic audit chain · Secure verification · A few minutes
            </span>
          </div>
        </motion.div>
      </section>
    </div>
  );
}

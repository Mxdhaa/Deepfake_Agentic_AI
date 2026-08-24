"use client";

import { useState, useEffect } from "react";
import { motion } from "motion/react";
import Link from "next/link";
import { Lock, ArrowRight, CheckCircle2, ShieldCheck, Activity } from "lucide-react";

interface NarrativeLayerProps {
  scrollProgress: number; // 0.0 -> 1.0
  currentAct: number;
}

export default function NarrativeLayer({ scrollProgress, currentAct }: NarrativeLayerProps) {
  // Mechanical Decrypted Text simulation for "IDENTITY"
  const [decryptedText, setDecryptedText] = useState("IDENTITY");

  useEffect(() => {
    if (currentAct === 1) {
      const glyphs = ["I7E#T1T", "IDENT1T", "IÐENTITY", "1DENT1TY", "IDENTITY"];
      let idx = 0;
      const interval = setInterval(() => {
        if (idx < glyphs.length) {
          setDecryptedText(glyphs[idx]);
          idx++;
        } else {
          clearInterval(interval);
        }
      }, 120);
      return () => clearInterval(interval);
    } else {
      setDecryptedText("IDENTITY");
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
          OPENING DOME GALLERY OVERVIEW (0.00 -> 0.08)
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
          initial={{ opacity: 0 }}
          animate={{ opacity: currentAct === 0 ? 1 : 0 }}
          transition={{ duration: 0.5 }}
          style={{ maxWidth: "680px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1.25rem" }}>
            IDENTITY FIELD
          </div>
          <h1
            className="font-serif"
            style={{
              fontSize: "clamp(2rem, 5vw, 3.5rem)",
              fontWeight: 500,
              color: "#FFFFFF",
              letterSpacing: "-0.02em",
              lineHeight: 1.15,
              marginBottom: "1rem",
            }}
          >
            Selecting identity signal...
          </h1>
          <p style={{ fontSize: "0.95rem", color: "var(--text-muted)" }}>
            Scroll to isolate and reconstruct individual presence from the anonymous field.
          </p>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          SCENE 00 — THE SIGNAL (0.08 -> 0.18)
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
          style={{ maxWidth: "680px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1.5rem" }}>
            IDENTITY / 00 — THE SIGNAL
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
            Before trust, there is uncertainty.
          </h2>

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
            <span>SCROLL TO RECONSTRUCT PRESENCE</span>
            <span className="animate-bounce">↓</span>
          </div>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          SCENE 01 — RECONSTRUCTION (0.18 -> 0.32)
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
          animate={{ opacity: currentAct === 2 ? 1 : 0, y: currentAct === 2 ? 0 : -20 }}
          transition={{ duration: 0.5 }}
          style={{ maxWidth: "720px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1.5rem" }}>
            01 — PROGRESSIVE RECONSTRUCTION
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
            <span style={{ fontFamily: "var(--font-mono)", color: "#3B82F6" }}>{decryptedText}</span> begins with information.
          </h2>

          <p style={{ fontSize: "1.05rem", color: "var(--text-muted)", lineHeight: 1.6, maxWidth: "520px", marginBottom: "1.5rem" }}>
            Thousands of isolated point vectors converge across 7 topological stages into the geometric contours of a physical identity.
          </p>

          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.725rem",
              color: "var(--text-dim)",
              letterSpacing: "0.05em",
            }}
          >
            TOPOLOGY STATUS: <span style={{ color: "#3B82F6" }}>RECONSTRUCTING VOLUMETRIC PRESENCE</span>
          </div>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          SCENE 02 — MOVING INTO FACIAL PLANE (0.32 -> 0.44)
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
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: currentAct === 3 ? 1 : 0, scale: currentAct === 3 ? 1 : 0.95 }}
          transition={{ duration: 0.5 }}
          style={{ maxWidth: "700px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1.25rem" }}>
            02 — SPATIAL CONVERGENCE
          </div>

          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(2.2rem, 4.5vw, 3.5rem)",
              fontWeight: 500,
              color: "#FFFFFF",
              letterSpacing: "-0.02em",
              marginBottom: "1rem",
            }}
          >
            Entering the identity layer.
          </h2>

          <p style={{ fontSize: "1rem", color: "var(--text-muted)", lineHeight: 1.6, maxWidth: "500px", margin: "0 auto" }}>
            Moving through the reconstructed facial plane into the underlying cryptographic evidence.
          </p>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          SCENE 03 — DOCUMENT EVIDENCE (0.44 -> 0.58)
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
          animate={{ opacity: currentAct === 4 ? 1 : 0, y: currentAct === 4 ? 0 : -20 }}
          transition={{ duration: 0.5 }}
          style={{ maxWidth: "620px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1.5rem" }}>
            03 — EVIDENCE EXTRACTION & HASHING
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

          <div
            style={{
              background: "#0a0a0a",
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
          SCENE 04 — LIVENESS EMERGENCE (0.58 -> 0.72)
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
          style={{ textAlign: "center", maxWidth: "780px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1rem" }}>
            04 — PHYSIOLOGICAL LIVENESS
          </div>

          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(2.2rem, 5vw, 3.8rem)",
              fontWeight: 500,
              lineHeight: 1.15,
              letterSpacing: "-0.02em",
              marginBottom: "1rem",
            }}
          >
            <span style={{ color: "#FFFFFF", display: "block" }}>A document tells us who you are.</span>
            <span style={{ color: "#3B82F6", display: "block" }}>Liveness tells us you&apos;re here.</span>
          </h2>

          <p style={{ fontSize: "1rem", color: "var(--text-muted)", maxWidth: "560px", margin: "0 auto" }}>
            Static documents can be copied or replayed. Live physiological response is harder to fake convincingly.
          </p>
        </motion.div>

        {/* Sparse Restrained Telemetry */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: currentAct === 5 ? 1 : 0 }}
          transition={{ duration: 0.5 }}
          style={{
            background: "#0a0a0a",
            border: "1px solid var(--border-color)",
            borderRadius: "4px",
            padding: "1rem 1.5rem",
            display: "flex",
            flexWrap: "wrap",
            gap: "2rem",
            fontFamily: "var(--font-mono)",
            fontSize: "0.75rem",
            pointerEvents: "auto",
          }}
        >
          <div>
            <span style={{ color: "var(--text-dim)", display: "block" }}>LIVENESS SIGNAL</span>
            <span style={{ color: "#FFFFFF", fontWeight: 600 }}>87.4%</span>
          </div>
          <div>
            <span style={{ color: "var(--text-dim)", display: "block" }}>PRESENCE</span>
            <span style={{ color: "#10B981", fontWeight: 600 }}>CONFIRMED ✓</span>
          </div>
          <div>
            <span style={{ color: "var(--text-dim)", display: "block" }}>MOTION VECTOR</span>
            <span style={{ color: "#3B82F6", fontWeight: 600 }}>STABLE</span>
          </div>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          SCENE 05 — FINAL VERIFICATION STABILITY (0.72 -> 0.84)
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
          style={{ maxWidth: "680px", pointerEvents: "auto" }}
        >
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "4px 12px",
              borderRadius: "4px",
              background: "rgba(16, 185, 129, 0.08)",
              border: "1px solid rgba(16, 185, 129, 0.25)",
              fontFamily: "var(--font-mono)",
              fontSize: "0.75rem",
              color: "#10B981",
              marginBottom: "1.25rem",
            }}
          >
            <CheckCircle2 size={14} /> VERIFIED
          </div>

          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(2.4rem, 5.5vw, 4rem)",
              fontWeight: 500,
              color: "#FFFFFF",
              letterSpacing: "-0.02em",
              marginBottom: "0.75rem",
            }}
          >
            Identity verified.
          </h2>

          <p style={{ fontSize: "1.05rem", color: "var(--text-muted)", marginBottom: "2rem" }}>
            Presence confirmed. Multi-stage signals fused and sealed into the cryptographic chain.
          </p>

          <div
            style={{
              display: "inline-grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "1.5rem",
              background: "#0a0a0a",
              border: "1px solid var(--border-color)",
              borderRadius: "4px",
              padding: "1rem 1.5rem",
              fontFamily: "var(--font-mono)",
              fontSize: "0.75rem",
              textAlign: "left",
            }}
          >
            <div>
              <span style={{ color: "var(--text-dim)", display: "block" }}>Session ID</span>
              <span style={{ color: "#FFFFFF" }}>SES-1787475223...</span>
            </div>
            <div>
              <span style={{ color: "var(--text-dim)", display: "block" }}>Audit Status</span>
              <span style={{ color: "#10B981" }}>SHA-256 SEALED</span>
            </div>
          </div>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          SCENE 07 — FINAL CTA (0.94 -> 1.00)
      ══════════════════════════════════════════════════════════════════ */}
      <section
        id="security"
        style={{
          minHeight: "80vh",
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
          <div className="tech-pill" style={{ marginBottom: "1.5rem" }}>
            START VERIFICATION
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

          <p style={{ fontSize: "1.1rem", color: "var(--text-muted)", maxWidth: "560px", margin: "0 auto 2.5rem", lineHeight: 1.6 }}>
            Four stages. One continuous chain of evidence.
          </p>

          {/* Real Customer Action */}
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
              Cryptographic audit chain · Multi-stage verification · A few minutes
            </span>
          </div>
        </motion.div>
      </section>
    </div>
  );
}

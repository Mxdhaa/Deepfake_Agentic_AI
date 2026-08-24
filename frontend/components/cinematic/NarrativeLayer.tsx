"use client";

import { useState, useEffect } from "react";
import { motion } from "motion/react";
import Link from "next/link";
import { Lock, ArrowRight, CheckCircle2 } from "lucide-react";
import DecryptedText from "@/components/ui/DecryptedText";

interface NarrativeLayerProps {
  scrollProgress: number; // 0.0 -> 1.0
  currentAct: number;
}

export default function NarrativeLayer({ scrollProgress, currentAct }: NarrativeLayerProps) {
  // Continuous live microsecond clock tick for active scientific instrument feel
  const [clockTick, setClockTick] = useState("00:00.00");

  useEffect(() => {
    const interval = setInterval(() => {
      const now = new Date();
      const ms = Math.floor(now.getMilliseconds() / 10).toString().padStart(2, "0");
      const sec = now.getSeconds().toString().padStart(2, "0");
      const min = now.getMinutes().toString().padStart(2, "0");
      setClockTick(`${min}:${sec}.${ms}`);
    }, 50);
    return () => clearInterval(interval);
  }, []);

  // Dynamic Liveness Telemetry derived from scroll progress during Act 5 (0.58 – 0.72)
  const isLivenessAct = currentAct === 5;
  const liveProgress = Math.max(0, Math.min(1, (scrollProgress - 0.58) / 0.14));

  let livenessStatusText = "ANALYZING";
  let presenceText = "DETECTING";
  let motionText = "SAMPLING";
  let scanDepth = "034 mm";

  if (liveProgress < 0.25) {
    livenessStatusText = "ANALYZING";
    presenceText = "DETECTING";
    motionText = "SAMPLING";
    scanDepth = "041 mm";
  } else if (liveProgress < 0.6) {
    livenessStatusText = "42.8%";
    presenceText = "DETECTED";
    motionText = "TRACKING";
    scanDepth = "063 mm";
  } else if (liveProgress < 0.88) {
    livenessStatusText = "76.3%";
    presenceText = "DETECTED";
    motionText = "STABLE";
    scanDepth = "087 mm";
  } else {
    livenessStatusText = "98.7%";
    presenceText = "CONFIRMED ✓";
    motionText = "STABLE";
    scanDepth = "112 mm";
  }

  return (
    <div
      style={{
        position: "relative",
        zIndex: 10,
        pointerEvents: "none",
      }}
    >
      {/* ══════════════════════════════════════════════════════════════════
          ACT 00 — ANONYMOUS DOME GALLERY (0.00 -> 0.08)
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
          transition={{ duration: 0.4 }}
          style={{ maxWidth: "780px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1.25rem" }}>
            <span style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "#2F80FF", boxShadow: "0 0 8px #2F80FF" }} />
            <span><strong style={{ color: "#2F80FF" }}>IDENTITY</strong> FIELD</span>
            <span style={{ opacity: 0.5, fontSize: "0.68rem" }}>· {clockTick}</span>
          </div>

          <h1
            className="font-serif"
            style={{
              fontSize: "clamp(2.4rem, 5.5vw, 4.2rem)",
              fontWeight: 500,
              color: "#FFFFFF",
              letterSpacing: "-0.02em",
              lineHeight: 1.15,
              marginBottom: "1rem",
            }}
          >
            <DecryptedText text="Selecting identity signal..." isActive={currentAct === 0} speed={40} />
          </h1>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          ACT 01 — THE SIGNAL (0.08 -> 0.18)
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
          transition={{ duration: 0.4 }}
          style={{ maxWidth: "720px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1.5rem" }}>
            <span style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "#2F80FF", boxShadow: "0 0 8px #2F80FF" }} />
            <span><strong style={{ color: "#2F80FF" }}>IDENTITY</strong> / 00</span>
            <span style={{ opacity: 0.5, fontSize: "0.68rem" }}>· {clockTick}</span>
          </div>

          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(2.4rem, 5.5vw, 4.2rem)",
              fontWeight: 500,
              lineHeight: 1.15,
              color: "#FFFFFF",
              letterSpacing: "-0.02em",
              marginBottom: "1.25rem",
            }}
          >
            <DecryptedText text="Before trust, there is uncertainty." isActive={currentAct === 1} speed={35} />
          </h2>

          <p className="text-body-readable" style={{ maxWidth: "540px" }}>
            In a synthetic world, every digital connection begins as an anonymous signal.
          </p>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          ACT 02 — RECONSTRUCTION & DECRYPTION (0.18 -> 0.32)
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
          transition={{ duration: 0.4 }}
          style={{ maxWidth: "780px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1.5rem" }}>
            <span style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "#2F80FF", boxShadow: "0 0 8px #2F80FF" }} />
            <span>01 — RECONSTRUCTION</span>
            <span style={{ opacity: 0.5, fontSize: "0.68rem" }}>· {clockTick}</span>
          </div>

          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(2.5rem, 5.5vw, 4.2rem)",
              fontWeight: 500,
              lineHeight: 1.15,
              color: "#FFFFFF",
              letterSpacing: "-0.02em",
              marginBottom: "1.25rem",
            }}
          >
            <span style={{ color: "#2F80FF", fontWeight: 700 }}>
              <DecryptedText text="IDENTITY" isActive={currentAct === 2} speed={30} />
            </span>{" "}
            <DecryptedText text="begins with information." isActive={currentAct === 2} speed={35} />
          </h2>

          <p className="text-body-readable" style={{ maxWidth: "540px" }}>
            Thousands of isolated point vectors converge across topological stages into the geometric contours of a physical presence.
          </p>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          ACT 03 — SPATIAL CONVERGENCE (FLY INTO FACE) (0.32 -> 0.44)
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
          transition={{ duration: 0.4 }}
          style={{ maxWidth: "740px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1.25rem" }}>
            <span style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "#2F80FF", boxShadow: "0 0 8px #2F80FF" }} />
            <span>02 — SPATIAL CONVERGENCE</span>
            <span style={{ opacity: 0.5, fontSize: "0.68rem" }}>· {clockTick}</span>
          </div>

          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(2.4rem, 5vw, 3.8rem)",
              fontWeight: 500,
              color: "#FFFFFF",
              letterSpacing: "-0.02em",
              marginBottom: "1rem",
            }}
          >
            <DecryptedText text="Entering the identity layer." isActive={currentAct === 3} speed={35} />
          </h2>

          <p className="text-body-readable" style={{ maxWidth: "520px", margin: "0 auto" }}>
            Moving through the reconstructed facial plane into the underlying cryptographic evidence.
          </p>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          ACT 04 — DOCUMENT EVIDENCE (0.44 -> 0.58)
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
          transition={{ duration: 0.4 }}
          style={{ maxWidth: "660px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1.5rem" }}>
            <span style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "#2F80FF", boxShadow: "0 0 8px #2F80FF" }} />
            <span>03 — EVIDENCE EXTRACTION & WIRE HASHING</span>
            <span style={{ opacity: 0.5, fontSize: "0.68rem" }}>· {clockTick}</span>
          </div>

          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(2.4rem, 5vw, 3.8rem)",
              fontWeight: 500,
              color: "#FFFFFF",
              letterSpacing: "-0.02em",
              marginBottom: "1.25rem",
            }}
          >
            <DecryptedText text="Evidence has a physical form." isActive={currentAct === 4} speed={35} />
          </h2>

          <p className="text-body-readable" style={{ marginBottom: "2rem" }}>
            The uploaded credential is decomposed into optical regions and its raw wire bytes are sealed with SHA-256 before downstream scoring.
          </p>

          <div
            style={{
              background: "rgba(10, 17, 40, 0.8)",
              border: "1px solid var(--border-color)",
              borderRadius: "4px",
              padding: "1.25rem 1.5rem",
              fontFamily: "var(--font-mono)",
              boxShadow: "0 0 25px rgba(0,0,0,0.6)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#2F80FF", fontSize: "0.8rem", marginBottom: "8px" }}>
              <Lock size={14} /> WIRE BYTES SHA-256: <span style={{ color: "#FFFFFF", fontWeight: 600 }}>7c9f...a82d</span> SEALED
            </div>
            <div style={{ fontSize: "0.75rem", color: "#94a3b8", display: "flex", gap: "6px" }}>
              <span>AUDIT CHAIN:</span>
              <span style={{ color: "#c7ced8" }}>[01] → [02] → [03] → [04] → [05] → [06]</span>
            </div>
          </div>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          ACT 05 — LIVENESS SCANNING & DYNAMIC READOUTS (0.58 -> 0.72)
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
          animate={{ opacity: isLivenessAct ? 1 : 0, y: isLivenessAct ? 0 : -20 }}
          transition={{ duration: 0.4 }}
          style={{ textAlign: "center", maxWidth: "800px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1rem" }}>
            <span style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "#2F80FF", boxShadow: "0 0 8px #2F80FF" }} />
            <span>04 — PHYSIOLOGICAL LIVENESS</span>
            <span style={{ opacity: 0.5, fontSize: "0.68rem" }}>· {clockTick}</span>
          </div>

          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(2.4rem, 5.5vw, 4rem)",
              fontWeight: 500,
              lineHeight: 1.15,
              letterSpacing: "-0.02em",
              marginBottom: "1rem",
            }}
          >
            <span style={{ color: "#FFFFFF", display: "block" }}>
              <DecryptedText text="A document tells us who you are." isActive={isLivenessAct} speed={35} />
            </span>
            <span
              style={{
                color: "#2F80FF",
                fontWeight: 700,
                display: "block",
                textShadow: "0 0 25px rgba(47, 128, 255, 0.4)",
              }}
            >
              <DecryptedText text="Liveness tells us you're here." isActive={isLivenessAct} speed={35} />
            </span>
          </h2>

          <p className="text-body-readable" style={{ maxWidth: "580px", margin: "0 auto" }}>
            Static documents can be copied or replayed. Live physiological response is harder to fake convincingly.
          </p>
        </motion.div>

        {/* Dynamic Liveness Telemetry Panel */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: isLivenessAct ? 1 : 0 }}
          transition={{ duration: 0.4 }}
          style={{
            background: "rgba(10, 17, 40, 0.85)",
            border: "1px solid var(--border-color)",
            borderRadius: "4px",
            padding: "1.25rem 2rem",
            display: "flex",
            flexWrap: "wrap",
            gap: "2.5rem",
            fontFamily: "var(--font-mono)",
            fontSize: "0.78rem",
            boxShadow: "0 0 30px rgba(0,0,0,0.7)",
            pointerEvents: "auto",
          }}
        >
          <div>
            <span style={{ color: "#94a3b8", display: "block", fontSize: "0.7rem", marginBottom: "3px" }}>LIVENESS SIGNAL</span>
            <span style={{ color: "#FFFFFF", fontWeight: 600 }}>{livenessStatusText}</span>
          </div>
          <div>
            <span style={{ color: "#94a3b8", display: "block", fontSize: "0.7rem", marginBottom: "3px" }}>PRESENCE</span>
            <span style={{ color: liveProgress > 0.85 ? "#10B981" : "#2F80FF", fontWeight: 600 }}>{presenceText}</span>
          </div>
          <div>
            <span style={{ color: "#94a3b8", display: "block", fontSize: "0.7rem", marginBottom: "3px" }}>MOTION VECTOR</span>
            <span style={{ color: "#c7ced8", fontWeight: 600 }}>{motionText}</span>
          </div>
          <div>
            <span style={{ color: "#94a3b8", display: "block", fontSize: "0.7rem", marginBottom: "3px" }}>SCAN DEPTH</span>
            <span style={{ color: "#2F80FF", fontWeight: 600 }}>{scanDepth}</span>
          </div>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          ACT 06 — FINAL VERIFICATION STABILITY (0.72 -> 0.84)
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
          transition={{ duration: 0.4 }}
          style={{ maxWidth: "700px", pointerEvents: "auto" }}
        >
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "5px 14px",
              borderRadius: "4px",
              background: "rgba(16, 185, 129, 0.1)",
              border: "1px solid rgba(16, 185, 129, 0.3)",
              fontFamily: "var(--font-mono)",
              fontSize: "0.78rem",
              fontWeight: 600,
              color: "#10B981",
              marginBottom: "1.25rem",
              boxShadow: "0 0 20px rgba(16, 185, 129, 0.15)",
            }}
          >
            <CheckCircle2 size={15} /> VERIFIED
          </div>

          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(2.6rem, 6vw, 4.2rem)",
              fontWeight: 500,
              color: "#FFFFFF",
              letterSpacing: "-0.02em",
              marginBottom: "0.75rem",
            }}
          >
            <span style={{ color: "#2F80FF", fontWeight: 700 }}>
              <DecryptedText text="IDENTITY" isActive={currentAct === 6} speed={30} />
            </span>{" "}
            <DecryptedText text="verified." isActive={currentAct === 6} speed={35} />
          </h2>

          <p className="text-body-readable" style={{ maxWidth: "560px", margin: "0 auto 2rem" }}>
            Presence confirmed. Multi-stage signals fused and sealed into the cryptographic chain.
          </p>

          <div
            style={{
              display: "inline-grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "2rem",
              background: "rgba(10, 17, 40, 0.8)",
              border: "1px solid var(--border-color)",
              borderRadius: "4px",
              padding: "1.25rem 2rem",
              fontFamily: "var(--font-mono)",
              fontSize: "0.8rem",
              textAlign: "left",
            }}
          >
            <div>
              <span style={{ color: "#94a3b8", display: "block", fontSize: "0.7rem", marginBottom: "4px" }}>Session ID</span>
              <span style={{ color: "#FFFFFF", fontWeight: 600 }}>SES-1787475223...</span>
            </div>
            <div>
              <span style={{ color: "#94a3b8", display: "block", fontSize: "0.7rem", marginBottom: "4px" }}>Audit Status</span>
              <span style={{ color: "#10B981", fontWeight: 600 }}>SHA-256 SEALED</span>
            </div>
          </div>
        </motion.div>
      </section>

      {/* ══════════════════════════════════════════════════════════════════
          ACT 07 — FINAL CTA (0.94 -> 1.00)
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
          transition={{ duration: 0.4 }}
          style={{ maxWidth: "780px", pointerEvents: "auto" }}
        >
          <div className="tech-pill" style={{ marginBottom: "1.5rem" }}>
            <span style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "#2F80FF", boxShadow: "0 0 8px #2F80FF" }} />
            <span>START VERIFICATION</span>
            <span style={{ opacity: 0.5, fontSize: "0.68rem" }}>· {clockTick}</span>
          </div>

          <h2
            className="font-serif"
            style={{
              fontSize: "clamp(2.8rem, 6vw, 4.6rem)",
              fontWeight: 500,
              color: "#FFFFFF",
              letterSpacing: "-0.03em",
              lineHeight: 1.1,
              marginBottom: "1.25rem",
            }}
          >
            Verify your <span style={{ color: "#2F80FF", fontWeight: 700 }}><DecryptedText text="identity" isActive={currentAct === 7} speed={30} /></span>.
          </h2>

          <p className="text-body-readable" style={{ maxWidth: "560px", margin: "0 auto 2.5rem" }}>
            Four stages. One continuous chain of evidence.
          </p>

          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "1rem" }}>
            <Link
              href="/onboarding"
              className="btn-primary-blue"
              style={{
                fontSize: "1rem",
                padding: "0.95rem 2.75rem",
              }}
            >
              <span>Get Started</span>
              <ArrowRight size={18} />
            </Link>

            <span style={{ fontSize: "0.8rem", fontFamily: "var(--font-mono)", color: "#94a3b8" }}>
              Cryptographic audit chain · Multi-stage verification · A few minutes
            </span>
          </div>
        </motion.div>
      </section>
    </div>
  );
}

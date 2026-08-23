"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useScroll, useTransform, useSpring, AnimatePresence } from "motion/react";
import {
  ShieldCheck,
  Cpu,
  Fingerprint,
  FileCheck2,
  ScanFace,
  Lock,
  ArrowRight,
  Activity,
  CheckCircle2,
  Sparkles,
  Zap,
  Eye,
  Layers,
  Database,
  Radio,
  FileText,
  UserCheck,
} from "lucide-react";

// ─── Particle & Mesh Simulator ────────────────────────────────────────────────

interface Particle {
  x: number;
  y: number;
  z: number;
  targetX: number;
  targetY: number;
  targetZ: number;
  baseX: number;
  baseY: number;
  baseZ: number;
  color: string;
  size: number;
  alpha: number;
}

export default function IdentityReconstructionLanding() {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Scroll Progress across the whole 8-stage journey
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  });

  // Smooth physical spring for scroll movement
  const smoothProgress = useSpring(scrollYProgress, {
    stiffness: 70,
    damping: 20,
    restDelta: 0.001,
  });

  // Active Scene Index calculation
  const [currentScene, setCurrentScene] = useState<number>(0);
  const [interactiveModalOpen, setInteractiveModalOpen] = useState(false);
  const [kycStatus, setKycStatus] = useState<"idle" | "evaluating" | "approved" | "borderline" | "rejected">("idle");
  const [demoName, setDemoName] = useState("Jane Doe");
  const [demoScore, setDemoScore] = useState("0.08");

  useEffect(() => {
    return smoothProgress.on("change", (v) => {
      const sceneIdx = Math.min(7, Math.floor(v * 8));
      setCurrentScene(sceneIdx);
    });
  }, [smoothProgress]);

  // ── Canvas 3D Particle & Biometric Mesh Animation Engine ────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", handleResize);

    // Initialize 1,200 Particles
    const PARTICLE_COUNT = 1100;
    const particles: Particle[] = [];

    // Pre-calculate Head / Silhouette Contour Points
    const silhouettePoints: { x: number; y: number; z: number }[] = [];
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      // 3D Head ellipsoid + shoulders
      const u = Math.random();
      const v = Math.random();
      const theta = u * 2.0 * Math.PI;
      const phi = Math.acos(2.0 * v - 1.0);

      // Distribute: 60% head, 25% shoulders, 15% neck/torso
      let px = 0;
      let py = 0;
      let pz = 0;

      if (i < PARTICLE_COUNT * 0.6) {
        // Head ellipsoid
        const r = 120 + Math.sin(theta * 3) * 8;
        px = r * Math.sin(phi) * Math.cos(theta) * 0.85;
        py = r * Math.cos(phi) * 1.15 - 50;
        pz = r * Math.sin(phi) * Math.sin(theta) * 0.85;
      } else if (i < PARTICLE_COUNT * 0.85) {
        // Shoulders / Torso
        const sX = (Math.random() - 0.5) * 380;
        const sY = 110 + Math.random() * 140;
        const sZ = (Math.random() - 0.5) * 120;
        px = sX;
        py = sY;
        pz = sZ;
      } else {
        // Neck & Facial Landmarks
        const nTheta = Math.random() * Math.PI * 2;
        px = Math.cos(nTheta) * 55;
        py = 50 + Math.random() * 60;
        pz = Math.sin(nTheta) * 55;
      }

      silhouettePoints.push({ x: px, y: py, z: pz });
    }

    // Create Initial Particle Pool
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const sp = silhouettePoints[i];
      const randomScatter = 700;
      particles.push({
        x: (Math.random() - 0.5) * width,
        y: (Math.random() - 0.5) * height,
        z: (Math.random() - 0.5) * 600,
        targetX: sp.x,
        targetY: sp.y,
        targetZ: sp.z,
        baseX: (Math.random() - 0.5) * randomScatter,
        baseY: (Math.random() - 0.5) * randomScatter,
        baseZ: (Math.random() - 0.5) * randomScatter,
        color: i % 3 === 0 ? "#a855f7" : i % 3 === 1 ? "#06b6d4" : "#ffffff",
        size: Math.random() * 2.2 + 0.8,
        alpha: Math.random() * 0.7 + 0.3,
      });
    }

    let time = 0;

    const render = () => {
      time += 0.015;
      ctx.clearRect(0, 0, width, height);

      const p = smoothProgress.get(); // 0.0 -> 1.0
      const centerX = width / 2;
      const centerY = height / 2;

      // ── Rotation Angle based on Scene Stage ──────────────────────────────
      // Scene 05 (Liveness) executes a yaw head turn
      let yaw = time * 0.3;
      let pitch = Math.sin(time * 0.5) * 0.1;

      if (p >= 0.55 && p < 0.75) {
        // Dynamic Liveness Head Turn: Front -> Left -> Right -> Center
        const liveT = (p - 0.55) / 0.2;
        yaw = Math.sin(liveT * Math.PI * 2) * 0.55;
        pitch = Math.cos(liveT * Math.PI * 2) * 0.2;
      } else if (p >= 0.75) {
        // Convergence: rotate faster then collapse
        yaw = time * 0.8;
      }

      const cosY = Math.cos(yaw);
      const sinY = Math.sin(yaw);
      const cosP = Math.cos(pitch);
      const sinP = Math.sin(pitch);

      // ── Determine Morph Targets based on scroll progress ─────────────────
      // p in [0.0, 0.12]  -> Scene 00: Ambient Scattered Brownian motion
      // p in [0.12, 0.26] -> Scene 01: Convergence into Head Silhouette
      // p in [0.26, 0.38] -> Scene 02: Details (Orbiting nodes)
      // p in [0.38, 0.52] -> Scene 03: 3D Holographic ID Card Formation
      // p in [0.52, 0.65] -> Scene 04: Biometric Wireframe Reconstruction
      // p in [0.65, 0.78] -> Scene 05: Active Liveness Biometric Scan
      // p in [0.78, 0.88] -> Scene 06: Convergence to Central Luminous Point
      // p in [0.88, 1.0]  -> Scene 07: CTA Action & Settled Clean Node

      particles.forEach((pt, i) => {
        let tx = 0;
        let ty = 0;
        let tz = 0;

        if (p < 0.15) {
          // Scene 00: Distant Ambient Scatter
          const scatterFactor = 1.0 - p / 0.15;
          tx = pt.baseX * (1.5 + scatterFactor) + Math.sin(time + i) * 30;
          ty = pt.baseY * (1.5 + scatterFactor) + Math.cos(time + i) * 30;
          tz = pt.baseZ * (1.5 + scatterFactor) + 200;
        } else if (p < 0.38) {
          // Scene 01 & 02: Converged Silhouette
          const sp = silhouettePoints[i];
          tx = sp.x + Math.sin(time * 0.5 + i * 0.1) * 2;
          ty = sp.y + Math.cos(time * 0.5 + i * 0.1) * 2;
          tz = sp.z;
        } else if (p < 0.52) {
          // Scene 03: 3D ID Document Grid Plane
          // Arrange in a 3D rectangular plane
          const row = Math.floor(i / 35);
          const col = i % 35;
          tx = (col - 17.5) * 12;
          ty = (row - 15) * 8;
          tz = Math.sin(col * 0.2 + time) * 15;
        } else if (p < 0.78) {
          // Scene 04 & 05: Dense Biometric Facial Depth Cloud
          const sp = silhouettePoints[i];
          const depthMultiplier = 1.2 + Math.sin(p * Math.PI) * 0.3;
          tx = sp.x * depthMultiplier;
          ty = sp.y * depthMultiplier;
          tz = sp.z * depthMultiplier;
        } else if (p < 0.88) {
          // Scene 06: Convergence into Central Node
          const collapse = (p - 0.78) / 0.1;
          const radius = (1.0 - collapse) * 200;
          tx = Math.sin(i + time * 2) * radius;
          ty = Math.cos(i + time * 2) * radius;
          tz = Math.sin(i * 2 + time * 2) * radius;
        } else {
          // Scene 07: Settle into subtle glowing ambient core behind CTA
          const radius = 60 + Math.sin(time + i * 0.05) * 10;
          tx = Math.sin(i + time * 0.4) * radius;
          ty = Math.cos(i + time * 0.4) * radius - 150;
          tz = Math.sin(i * 0.5 + time * 0.4) * radius;
        }

        // Interpolate Particle toward Target
        pt.x += (tx - pt.x) * 0.08;
        pt.y += (ty - pt.y) * 0.08;
        pt.z += (tz - pt.z) * 0.08;

        // 3D Projection Matrix
        const rotX = pt.x * cosY - pt.z * sinY;
        const rotZ = pt.x * sinY + pt.z * cosY;
        const rotY = pt.y * cosP - rotZ * sinP;
        const finalZ = pt.y * sinP + rotZ * cosP;

        const fov = 450;
        const scale = fov / (fov + finalZ + 300);
        const projX = centerX + rotX * scale;
        const projY = centerY + rotY * scale;

        if (scale > 0) {
          ctx.beginPath();
          ctx.arc(projX, projY, Math.max(0.5, pt.size * scale), 0, Math.PI * 2);
          ctx.fillStyle = pt.color;
          ctx.globalAlpha = Math.min(1.0, Math.max(0.15, pt.alpha * scale));
          ctx.fill();
        }
      });

      // ── Draw Connecting Laser Rays (Scene 02: Details & Scene 05: Liveness) ──
      if (p >= 0.22 && p < 0.38) {
        // Draw Circuit Nodes to Silhouette Center
        ctx.strokeStyle = "rgba(6, 182, 212, 0.25)";
        ctx.lineWidth = 1;
        const nodeTargets = [
          { x: centerX - 260, y: centerY - 140 },
          { x: centerX + 260, y: centerY - 140 },
          { x: centerX - 280, y: centerY + 100 },
          { x: centerX + 280, y: centerY + 100 },
        ];
        nodeTargets.forEach((nt) => {
          ctx.beginPath();
          ctx.moveTo(centerX, centerY - 20);
          ctx.lineTo(nt.x, nt.y);
          ctx.stroke();
        });
      }

      // ── Draw Liveness Scan Laser Line (Scene 05) ───────────────────────────
      if (p >= 0.62 && p < 0.78) {
        const scanY = centerY - 160 + Math.sin(time * 3) * 180;
        ctx.beginPath();
        ctx.moveTo(centerX - 180, scanY);
        ctx.lineTo(centerX + 180, scanY);
        ctx.strokeStyle = "rgba(16, 185, 129, 0.75)";
        ctx.lineWidth = 2;
        ctx.shadowColor = "#10b981";
        ctx.shadowBlur = 15;
        ctx.stroke();
        ctx.shadowBlur = 0;
      }

      ctx.globalAlpha = 1.0;
      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", handleResize);
    };
  }, [smoothProgress]);

  // ── Quick Interactive Test Modal Execution ─────────────────────────────────
  const handleRunQuickTest = async () => {
    setKycStatus("evaluating");
    await new Promise((r) => setTimeout(r, 1200));

    const s = parseFloat(demoScore);
    if (s >= 0.75) {
      setKycStatus("rejected");
    } else if (s >= 0.40) {
      setKycStatus("borderline");
    } else {
      setKycStatus("approved");
    }
  };

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        background: "#050811",
        color: "#ffffff",
        minHeight: "750vh", // Continuous scroll track for all 8 chapters
      }}
    >
      {/* ── Fixed Canvas 3D Particle & Biometric Backdrop ─────────────────── */}
      <canvas
        ref={canvasRef}
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          width: "100vw",
          height: "100vh",
          zIndex: 1,
          pointerEvents: "none",
        }}
      />

      {/* ── Fixed Scroll Progress Indicator & Scene Timeline ─────────────── */}
      <div
        style={{
          position: "fixed",
          right: "2rem",
          top: "50%",
          transform: "translateY(-50%)",
          zIndex: 40,
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}
      >
        {[
          "00 Arrival",
          "01 Information",
          "02 Details",
          "03 Document",
          "04 Biometrics",
          "05 Liveness",
          "06 Convergence",
          "07 Verify",
        ].map((name, idx) => (
          <div
            key={name}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              justifyContent: "flex-end",
              cursor: "pointer",
            }}
            onClick={() => {
              window.scrollTo({
                top: (idx / 7) * (document.body.scrollHeight - window.innerHeight),
                behavior: "smooth",
              });
            }}
          >
            <span
              style={{
                fontSize: "0.65rem",
                letterSpacing: "0.08em",
                fontWeight: currentScene === idx ? 700 : 400,
                color: currentScene === idx ? "#a855f7" : "rgba(255,255,255,0.25)",
                transition: "color 0.2s ease",
              }}
            >
              {name}
            </span>
            <div
              style={{
                width: currentScene === idx ? "18px" : "6px",
                height: "6px",
                borderRadius: "3px",
                backgroundColor: currentScene === idx ? "#a855f7" : "rgba(255,255,255,0.2)",
                boxShadow: currentScene === idx ? "0 0 10px #a855f7" : "none",
                transition: "all 0.3s ease",
              }}
            />
          </div>
        ))}
      </div>

      {/* ── Narrative Content Layer (Scroll-Choreographed Chapters) ──────── */}
      <div style={{ position: "relative", zIndex: 10 }}>

        {/* ══════════════════════════════════════════════════════════════════
            00 — ARRIVAL
        ══════════════════════════════════════════════════════════════════ */}
        <section
          style={{
            height: "100vh",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            textAlign: "center",
            padding: "0 2rem",
          }}
        >
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 1.2, ease: "easeOut" }}
            style={{ maxWidth: "700px" }}
          >
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "4px 14px",
                borderRadius: "999px",
                background: "rgba(168, 85, 247, 0.08)",
                border: "1px solid rgba(168, 85, 247, 0.25)",
                fontSize: "0.75rem",
                fontWeight: 700,
                letterSpacing: "0.15em",
                color: "#c084fc",
                marginBottom: "1.5rem",
                textTransform: "uppercase",
              }}
            >
              <Radio size={13} className="animate-pulse" />
              IDENTITY / 00 · THE SIGNAL
            </div>

            <h1
              style={{
                fontSize: "clamp(2rem, 5vw, 3.75rem)",
                fontWeight: 800,
                letterSpacing: "-0.03em",
                lineHeight: 1.15,
                background: "linear-gradient(135deg, #ffffff 0%, #cbd5e1 50%, #94a3b8 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                marginBottom: "1.25rem",
              }}
            >
              Before trust, there is uncertainty.
            </h1>

            <p style={{ fontSize: "1.1rem", color: "#64748b", maxWidth: "520px", margin: "0 auto 2.5rem" }}>
              In a synthetic world, every digital connection begins as an anonymous waveform. Scroll to reconstruct presence.
            </p>

            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                fontSize: "0.8rem",
                color: "#94a3b8",
                borderBottom: "1px dashed rgba(255,255,255,0.2)",
                paddingBottom: "4px",
              }}
            >
              <span>Scroll to begin reconstruction</span>
              <span className="animate-bounce">↓</span>
            </div>
          </motion.div>
        </section>

        {/* ══════════════════════════════════════════════════════════════════
            01 — "WHO ARE YOU?" (Information Begins)
        ══════════════════════════════════════════════════════════════════ */}
        <section
          style={{
            height: "100vh",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            textAlign: "center",
            padding: "0 2rem",
          }}
        >
          <div style={{ maxWidth: "800px" }}>
            <div
              style={{
                fontSize: "0.8rem",
                fontWeight: 700,
                letterSpacing: "0.2em",
                color: "#06b6d4",
                marginBottom: "1rem",
                textTransform: "uppercase",
              }}
            >
              01 · INGESTION & COALESCENCE
            </div>

            <h2
              style={{
                fontSize: "clamp(2.2rem, 5.5vw, 4.25rem)",
                fontWeight: 800,
                letterSpacing: "-0.03em",
                lineHeight: 1.1,
                background: "linear-gradient(135deg, #f8fafc 0%, #06b6d4 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                marginBottom: "1.5rem",
              }}
            >
              Identity begins with information.
            </h2>

            <p style={{ fontSize: "1.15rem", color: "#94a3b8", maxWidth: "560px", margin: "0 auto" }}>
              Thousands of isolated telemetry signals converge into the geometric contours of a unique human presence.
            </p>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════════════════════
            02 — "DETAILS" (The Orbiting Identity Graph)
        ══════════════════════════════════════════════════════════════════ */}
        <section
          style={{
            height: "100vh",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "5rem 2rem",
            position: "relative",
          }}
        >
          <div style={{ textAlign: "center", maxWidth: "700px" }}>
            <div
              style={{
                fontSize: "0.8rem",
                fontWeight: 700,
                letterSpacing: "0.2em",
                color: "#a855f7",
                marginBottom: "0.75rem",
                textTransform: "uppercase",
              }}
            >
              02 · TOPOLOGICAL BINDING
            </div>
            <h2
              style={{
                fontSize: "clamp(1.8rem, 4vw, 3rem)",
                fontWeight: 800,
                background: "linear-gradient(135deg, #ffffff 0%, #c084fc 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              A person becomes a profile.
            </h2>
          </div>

          {/* 4 Orbiting Hologram Badges */}
          <div
            style={{
              width: "100%",
              maxWidth: "1000px",
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "1.5rem",
              zIndex: 20,
            }}
          >
            {[
              { label: "LEGAL CLAIM", value: "Verified Identity Token", icon: <UserCheck size={16} /> },
              { label: "BIOMETRIC EMBEDDING", value: "Facial Template", icon: <Fingerprint size={16} /> },
              { label: "NETWORK VELOCITY", value: "Single Device · 0 Fails", icon: <Activity size={16} /> },
              { label: "CREDENTIAL TYPE", value: "Sovereign Passport / CKYC", icon: <FileText size={16} /> },
            ].map((chip) => (
              <div
                key={chip.label}
                style={{
                  background: "rgba(15, 23, 42, 0.8)",
                  border: "1px solid rgba(168, 85, 247, 0.3)",
                  borderRadius: "12px",
                  padding: "1rem 1.25rem",
                  backdropFilter: "blur(12px)",
                  boxShadow: "0 0 20px rgba(168, 85, 247, 0.15)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#a855f7", marginBottom: "4px" }}>
                  {chip.icon}
                  <span style={{ fontSize: "0.7rem", fontWeight: 700, letterSpacing: "0.05em" }}>{chip.label}</span>
                </div>
                <div style={{ fontSize: "0.9rem", fontWeight: 600, color: "#f1f5f9" }}>{chip.value}</div>
              </div>
            ))}
          </div>

          <div style={{ fontSize: "0.85rem", color: "#64748b" }}>
            Real-time graph links bind biometric claims directly to sovereign device records.
          </div>
        </section>

        {/* ══════════════════════════════════════════════════════════════════
            03 — THE ID DOCUMENT (3D Holographic Verification)
        ══════════════════════════════════════════════════════════════════ */}
        <section
          style={{
            height: "100vh",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            textAlign: "center",
            padding: "0 2rem",
          }}
        >
          <div
            style={{
              maxWidth: "680px",
              background: "rgba(10, 15, 30, 0.85)",
              border: "1px solid rgba(6, 182, 212, 0.35)",
              borderRadius: "20px",
              padding: "2.5rem 3rem",
              backdropFilter: "blur(16px)",
              boxShadow: "0 0 40px rgba(6, 182, 212, 0.2)",
            }}
          >
            <div
              style={{
                fontSize: "0.75rem",
                fontWeight: 700,
                letterSpacing: "0.2em",
                color: "#06b6d4",
                marginBottom: "0.75rem",
                textTransform: "uppercase",
              }}
            >
              03 · DOCUMENT EXTRACTION & WIRE HASHING
            </div>

            <h2
              style={{
                fontSize: "clamp(1.8rem, 4vw, 2.75rem)",
                fontWeight: 800,
                color: "#ffffff",
                marginBottom: "1rem",
              }}
            >
              Optical integrity meets cryptographic sealing.
            </h2>

            <p style={{ fontSize: "1rem", color: "#94a3b8", marginBottom: "1.75rem" }}>
              The government-issued credential is decomposed into optical security zones, machine-readable barcodes, and raw wire-byte SHA-256 digests.
            </p>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "1.5rem",
                flexWrap: "wrap",
              }}
            >
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "6px 14px",
                  borderRadius: "8px",
                  background: "rgba(16, 185, 129, 0.1)",
                  border: "1px solid rgba(16, 185, 129, 0.3)",
                  color: "#10b981",
                  fontSize: "0.8rem",
                  fontWeight: 700,
                }}
              >
                <CheckCircle2 size={15} /> MRZ CHECKSUM: VALID
              </div>
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "6px 14px",
                  borderRadius: "8px",
                  background: "rgba(6, 182, 212, 0.1)",
                  border: "1px solid rgba(6, 182, 212, 0.3)",
                  color: "#06b6d4",
                  fontSize: "0.8rem",
                  fontWeight: 700,
                }}
              >
                <Lock size={15} /> SHA-256 HASH CHAIN SEALED
              </div>
            </div>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════════════════════
            04 — "IS IT REALLY YOU?" (The Emotional Climax)
        ══════════════════════════════════════════════════════════════════ */}
        <section
          style={{
            height: "100vh",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            textAlign: "center",
            padding: "0 2rem",
          }}
        >
          <div style={{ maxWidth: "800px" }}>
            <div
              style={{
                fontSize: "0.8rem",
                fontWeight: 700,
                letterSpacing: "0.2em",
                color: "#c084fc",
                marginBottom: "1rem",
                textTransform: "uppercase",
              }}
            >
              04 · THE CRUCIAL DISTINCTION
            </div>

            <h2
              style={{
                fontSize: "clamp(2.2rem, 5.5vw, 4.5rem)",
                fontWeight: 800,
                letterSpacing: "-0.03em",
                lineHeight: 1.1,
                marginBottom: "1.5rem",
              }}
            >
              <span style={{ color: "#ffffff" }}>A document tells us who you are.</span>
              <br />
              <span
                style={{
                  background: "linear-gradient(135deg, #a855f7 0%, #06b6d4 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                Liveness tells us you're here.
              </span>
            </h2>

            <p style={{ fontSize: "1.2rem", color: "#94a3b8", maxWidth: "600px", margin: "0 auto" }}>
              Static documents can be stolen or synthesized. True physiological presence cannot be forged.
            </p>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════════════════════
            05 — ACTIVE LIVENESS (Autonomous Micro-Challenge)
        ══════════════════════════════════════════════════════════════════ */}
        <section
          style={{
            height: "100vh",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "5rem 2rem",
          }}
        >
          <div style={{ textAlign: "center", maxWidth: "700px" }}>
            <div
              style={{
                fontSize: "0.8rem",
                fontWeight: 700,
                letterSpacing: "0.2em",
                color: "#10b981",
                marginBottom: "0.5rem",
                textTransform: "uppercase",
              }}
            >
              05 · AUTONOMOUS PHYSIOLOGICAL PROFILING
            </div>
            <h2 style={{ fontSize: "clamp(1.8rem, 4vw, 3rem)", fontWeight: 800, color: "#ffffff" }}>
              Sub-second physiological verification.
            </h2>
          </div>

          {/* Live Biometric Status Card */}
          <div
            style={{
              width: "100%",
              maxWidth: "850px",
              background: "rgba(10, 20, 30, 0.85)",
              border: "1px solid rgba(16, 185, 129, 0.35)",
              borderRadius: "16px",
              padding: "1.5rem 2rem",
              backdropFilter: "blur(14px)",
              boxShadow: "0 0 30px rgba(16, 185, 129, 0.15)",
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "1.25rem",
            }}
          >
            {[
              { title: "01 · HEAD POSE & YAW", status: "VERIFIED ✓", desc: "Dynamic yaw trajectory nominal", col: "#10b981" },
              { title: "02 · BLINK DYNAMICS", status: "14.8 BPM ✓", desc: "Natural ocular rhythm detected", col: "#10b981" },
              { title: "03 · AUDIO-VIDEO SYNC", status: "0.0 ms LAG ✓", desc: "Zero neural lip-sync drift", col: "#10b981" },
              { title: "04 · REFLECTANCE", status: "ORGANIC SKIN ✓", desc: "No 2D screen re-projection", col: "#06b6d4" },
            ].map((metric) => (
              <div key={metric.title} style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <span style={{ fontSize: "0.68rem", fontWeight: 700, color: "#64748b", letterSpacing: "0.05em" }}>
                  {metric.title}
                </span>
                <span style={{ fontSize: "1.05rem", fontWeight: 800, color: metric.col }}>
                  {metric.status}
                </span>
                <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>{metric.desc}</span>
              </div>
            ))}
          </div>

          <div style={{ fontSize: "0.85rem", color: "#64748b" }}>
            ISO/IEC 30107-3 Presentation Attack Detection running locally and autonomously.
          </div>
        </section>

        {/* ══════════════════════════════════════════════════════════════════
            06 — EVERYTHING CONVERGES
        ══════════════════════════════════════════════════════════════════ */}
        <section
          style={{
            height: "100vh",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            textAlign: "center",
            padding: "0 2rem",
          }}
        >
          <div style={{ maxWidth: "700px" }}>
            <div
              style={{
                fontSize: "0.8rem",
                fontWeight: 700,
                letterSpacing: "0.2em",
                color: "#a855f7",
                marginBottom: "1rem",
                textTransform: "uppercase",
              }}
            >
              06 · COMPLETE SYNTHESIS
            </div>

            <h2
              style={{
                fontSize: "clamp(2rem, 5vw, 3.75rem)",
                fontWeight: 800,
                color: "#ffffff",
                marginBottom: "1.25rem",
              }}
            >
              All signals collapse into certainty.
            </h2>

            <p style={{ fontSize: "1.1rem", color: "#94a3b8", maxWidth: "540px", margin: "0 auto" }}>
              The data points, holographic document, facial geometry, and liveness signals fuse into an immutable, cryptographic truth.
            </p>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════════════════════
            07 — THE ACTUAL HERO & CTA
        ══════════════════════════════════════════════════════════════════ */}
        <section
          id="verification-hero"
          style={{
            minHeight: "100vh",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            textAlign: "center",
            padding: "6rem 2rem 4rem",
          }}
        >
          <div style={{ maxWidth: "800px" }}>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "6px 16px",
                borderRadius: "999px",
                background: "rgba(168, 85, 247, 0.1)",
                border: "1px solid rgba(168, 85, 247, 0.3)",
                fontSize: "0.8rem",
                fontWeight: 700,
                color: "#c084fc",
                marginBottom: "1.5rem",
              }}
            >
              <Sparkles size={16} /> READY FOR INSTANT VERIFICATION
            </div>

            <h2
              style={{
                fontSize: "clamp(2.5rem, 6vw, 4.75rem)",
                fontWeight: 900,
                letterSpacing: "-0.03em",
                lineHeight: 1.05,
                background: "linear-gradient(135deg, #ffffff 0%, #f1f5f9 50%, #cbd5e1 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                marginBottom: "1.5rem",
              }}
            >
              Verify your identity.
            </h2>

            <p style={{ fontSize: "1.2rem", color: "#94a3b8", maxWidth: "620px", margin: "0 auto 2.5rem" }}>
              A secure, multi-stage verification process using your details, identity document, and autonomous liveness check.
            </p>

            {/* Primary Action Button */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "1rem" }}>
              <button
                onClick={() => setInteractiveModalOpen(true)}
                style={{
                  background: "linear-gradient(135deg, #9333ea 0%, #4f46e5 100%)",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "14px",
                  padding: "1.1rem 3rem",
                  fontSize: "1.15rem",
                  fontWeight: 700,
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "12px",
                  boxShadow: "0 0 35px rgba(147, 51, 234, 0.45)",
                  transition: "all 0.2s ease",
                }}
                onMouseOver={(e) => {
                  e.currentTarget.style.transform = "translateY(-3px) scale(1.02)";
                  e.currentTarget.style.boxShadow = "0 0 45px rgba(147, 51, 234, 0.65)";
                }}
                onMouseOut={(e) => {
                  e.currentTarget.style.transform = "translateY(0) scale(1)";
                  e.currentTarget.style.boxShadow = "0 0 35px rgba(147, 51, 234, 0.45)";
                }}
              >
                <span>Get Started</span>
                <ArrowRight size={20} />
              </button>

              <span style={{ fontSize: "0.825rem", color: "#64748b" }}>
                🔒 Secure verification · Cryptographic Audit Chain · Approximately 2–3 minutes
              </span>
            </div>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════════════════════
            08 — HOW IT WORKS (The 4 Calm Steps)
        ══════════════════════════════════════════════════════════════════ */}
        <section
          style={{
            padding: "6rem 2rem",
            maxWidth: "1250px",
            margin: "0 auto",
          }}
        >
          <div style={{ textAlign: "center", marginBottom: "4rem" }}>
            <h3 style={{ fontSize: "2rem", fontWeight: 800, color: "#ffffff", marginBottom: "0.75rem" }}>
              How it works
            </h3>
            <p style={{ color: "#64748b", fontSize: "1rem" }}>
              Four deterministic stages orchestrating biometric precision with zero secret leakage.
            </p>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
              gap: "2rem",
            }}
          >
            {[
              {
                step: "01",
                title: "Details",
                desc: "Provide your basic demographic information and sovereign credentials.",
                icon: <FileText size={22} color="#a855f7" />,
              },
              {
                step: "02",
                title: "Identity Document",
                desc: "Upload a government-issued photo ID. Wire bytes are hashed before analysis.",
                icon: <FileCheck2 size={22} color="#06b6d4" />,
              },
              {
                step: "03",
                title: "Liveness Check",
                desc: "Complete a 5-second camera challenge measuring micro-blinks and optical flow.",
                icon: <ScanFace size={22} color="#10b981" />,
              },
              {
                step: "04",
                title: "Instant Verification",
                desc: "Receive fast-pass approval or autonomous agent resolution in < 50ms.",
                icon: <ShieldCheck size={22} color="#f59e0b" />,
              },
            ].map((s) => (
              <div
                key={s.step}
                style={{
                  background: "rgba(15, 23, 42, 0.6)",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                  borderRadius: "16px",
                  padding: "2rem 1.75rem",
                  transition: "all 0.2s ease",
                }}
                onMouseOver={(e) => {
                  e.currentTarget.style.borderColor = "rgba(168, 85, 247, 0.4)";
                  e.currentTarget.style.background = "rgba(15, 23, 42, 0.9)";
                  e.currentTarget.style.transform = "translateY(-4px)";
                }}
                onMouseOut={(e) => {
                  e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.08)";
                  e.currentTarget.style.background = "rgba(15, 23, 42, 0.6)";
                  e.currentTarget.style.transform = "translateY(0)";
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
                  <div
                    style={{
                      width: "44px",
                      height: "44px",
                      borderRadius: "10px",
                      background: "rgba(255, 255, 255, 0.04)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    {s.icon}
                  </div>
                  <span style={{ fontSize: "1.5rem", fontWeight: 900, color: "rgba(255, 255, 255, 0.15)" }}>
                    {s.step}
                  </span>
                </div>
                <h4 style={{ fontSize: "1.2rem", fontWeight: 700, color: "#f8fafc", marginBottom: "0.5rem" }}>
                  {s.title}
                </h4>
                <p style={{ fontSize: "0.9rem", color: "#94a3b8", lineHeight: 1.5 }}>
                  {s.desc}
                </p>
              </div>
            ))}
          </div>
        </section>

      </div>

      {/* ── Interactive KYC Onboarding Launch Modal ───────────────────────── */}
      <AnimatePresence>
        {interactiveModalOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              width: "100vw",
              height: "100vh",
              zIndex: 100,
              background: "rgba(5, 8, 17, 0.85)",
              backdropFilter: "blur(20px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "1.5rem",
            }}
          >
            <motion.div
              initial={{ scale: 0.95, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 20 }}
              style={{
                background: "#0f172a",
                border: "1px solid rgba(168, 85, 247, 0.3)",
                borderRadius: "20px",
                maxWidth: "540px",
                width: "100%",
                padding: "2.5rem",
                boxShadow: "0 0 50px rgba(0, 0, 0, 0.8)",
                position: "relative",
              }}
            >
              <button
                onClick={() => setInteractiveModalOpen(false)}
                style={{
                  position: "absolute",
                  top: "1.25rem",
                  right: "1.25rem",
                  background: "transparent",
                  border: "none",
                  color: "#64748b",
                  fontSize: "1.2rem",
                  cursor: "pointer",
                }}
              >
                ✕
              </button>

              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "1rem" }}>
                <div
                  style={{
                    width: "36px",
                    height: "36px",
                    borderRadius: "10px",
                    background: "rgba(168, 85, 247, 0.15)",
                    color: "#c084fc",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <ScanFace size={20} />
                </div>
                <div>
                  <h3 style={{ fontSize: "1.25rem", fontWeight: 800, color: "#ffffff" }}>
                    Identity Verification
                  </h3>
                  <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                    Document Verification & Live Presence Check
                  </span>
                </div>
              </div>

              {kycStatus === "idle" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                  <div>
                    <label style={{ fontSize: "0.8rem", color: "#94a3b8", display: "block", marginBottom: "6px" }}>
                      Applicant Legal Name
                    </label>
                    <input
                      type="text"
                      value={demoName}
                      onChange={(e) => setDemoName(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "0.75rem 1rem",
                        background: "rgba(255, 255, 255, 0.05)",
                        border: "1px solid rgba(255, 255, 255, 0.1)",
                        borderRadius: "8px",
                        color: "#ffffff",
                        fontSize: "0.95rem",
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ fontSize: "0.8rem", color: "#94a3b8", display: "block", marginBottom: "6px" }}>
                      Verification Flow Mode
                    </label>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "8px" }}>
                      {[
                        { label: "Standard Flow", score: "0.08" },
                        { label: "Secondary Review", score: "0.55" },
                        { label: "Unverified Check", score: "0.88" },
                      ].map((opt) => (
                        <button
                          key={opt.label}
                          type="button"
                          onClick={() => setDemoScore(opt.score)}
                          style={{
                            padding: "8px 6px",
                            borderRadius: "8px",
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            cursor: "pointer",
                            background: demoScore === opt.score ? "rgba(168, 85, 247, 0.25)" : "rgba(255, 255, 255, 0.04)",
                            border: demoScore === opt.score ? "1px solid #a855f7" : "1px solid rgba(255, 255, 255, 0.1)",
                            color: demoScore === opt.score ? "#c084fc" : "#94a3b8",
                            transition: "all 0.15s ease",
                          }}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <button
                    onClick={handleRunQuickTest}
                    style={{
                      background: "linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%)",
                      color: "#ffffff",
                      border: "none",
                      padding: "0.9rem",
                      borderRadius: "10px",
                      fontWeight: 700,
                      cursor: "pointer",
                      marginTop: "0.5rem",
                      boxShadow: "0 0 20px rgba(124, 58, 237, 0.3)",
                    }}
                  >
                    Begin Identity Verification →
                  </button>
                </div>
              )}

              {kycStatus === "evaluating" && (
                <div style={{ textAlign: "center", padding: "2rem 0" }}>
                  <div
                    style={{
                      width: "40px",
                      height: "40px",
                      border: "3px solid rgba(168, 85, 247, 0.2)",
                      borderTopColor: "#a855f7",
                      borderRadius: "50%",
                      animation: "spin 0.8s linear infinite",
                      margin: "0 auto 1.25rem",
                    }}
                  />
                  <div style={{ fontSize: "1rem", fontWeight: 700, color: "#ffffff" }}>
                    Verifying Identity & Live Presence...
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "#64748b", marginTop: "4px" }}>
                    Checking document validity and physiological liveness signals
                  </div>
                </div>
              )}

              {kycStatus !== "idle" && kycStatus !== "evaluating" && (
                <div style={{ textAlign: "center", padding: "1.5rem 0" }}>
                  <div
                    style={{
                      display: "inline-flex",
                      padding: "8px 18px",
                      borderRadius: "999px",
                      fontSize: "0.9rem",
                      fontWeight: 800,
                      marginBottom: "1rem",
                      background:
                        kycStatus === "approved"
                          ? "rgba(16, 185, 129, 0.15)"
                          : kycStatus === "borderline"
                          ? "rgba(245, 158, 11, 0.15)"
                          : "rgba(239, 68, 68, 0.15)",
                      color:
                        kycStatus === "approved"
                          ? "#10b981"
                          : kycStatus === "borderline"
                          ? "#f59e0b"
                          : "#ef4444",
                      border: `1px solid ${
                        kycStatus === "approved"
                          ? "rgba(16, 185, 129, 0.3)"
                          : kycStatus === "borderline"
                          ? "rgba(245, 158, 11, 0.3)"
                          : "rgba(239, 68, 68, 0.3)"
                      }`,
                    }}
                  >
                    {kycStatus === "approved" && "YOU'RE VERIFIED ✓"}
                    {kycStatus === "borderline" && "WE'RE REVIEWING YOUR APPLICATION ◈"}
                    {kycStatus === "rejected" && "WE COULDN'T VERIFY YOU ✕"}
                  </div>

                  <p style={{ fontSize: "0.9rem", color: "#94a3b8", marginBottom: "1.5rem" }}>
                    {kycStatus === "approved" && "Your identity document and live presence were successfully confirmed."}
                    {kycStatus === "borderline" && "Your submission is undergoing brief secondary verification. We'll update your status shortly."}
                    {kycStatus === "rejected" && "We could not confirm your identity. Please ensure you are in a well-lit environment and try again."}
                  </p>

                  <button
                    onClick={() => setKycStatus("idle")}
                    style={{
                      background: "rgba(255, 255, 255, 0.08)",
                      border: "1px solid rgba(255, 255, 255, 0.15)",
                      color: "#ffffff",
                      padding: "0.6rem 1.5rem",
                      borderRadius: "8px",
                      cursor: "pointer",
                      fontSize: "0.85rem",
                      fontWeight: 600,
                    }}
                  >
                    Start New Verification
                  </button>
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

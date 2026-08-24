"use client";

import { useState, useRef, useEffect } from "react";
import { motion } from "motion/react";
import { FileText, FileCheck2, ScanFace, ShieldCheck } from "lucide-react";

export default function HowItWorks() {
  const [activeStep, setActiveStep] = useState(0);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const mouseRef = useRef({ x: -1000, y: -1000 });

  const steps = [
    {
      num: "01",
      title: "DETAILS",
      desc: "Provide your basic demographic information and claim identifier.",
      icon: <FileText size={20} color="#3B82F6" />,
    },
    {
      num: "02",
      title: "IDENTITY",
      desc: "Upload your photo ID. The file is hashed with SHA-256 before processing.",
      icon: <FileCheck2 size={20} color="#FFFFFF" />,
    },
    {
      num: "03",
      title: "LIVENESS",
      desc: "Complete a short camera challenge to evaluate motion and physiological signals.",
      icon: <ScanFace size={20} color="#3B82F6" />,
    },
    {
      num: "04",
      title: "VERIFICATION",
      desc: "Receive your multi-stage verification result sealed into the audit chain.",
      icon: <ShieldCheck size={20} color="#FFFFFF" />,
    },
  ];

  // ── Subtle Interactive Cursor Grid Canvas ──────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || window.innerWidth);
    let height = (canvas.height = canvas.parentElement?.clientHeight || 600);

    const handleResize = () => {
      if (!canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = canvas.parentElement.clientHeight;
    };
    window.addEventListener("resize", handleResize);

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseRef.current.x = e.clientX - rect.left;
      mouseRef.current.y = e.clientY - rect.top;
    };
    window.addEventListener("mousemove", handleMouseMove, { passive: true });

    const spacing = 40;
    const renderGrid = () => {
      animId = requestAnimationFrame(renderGrid);
      ctx.clearRect(0, 0, width, height);

      ctx.strokeStyle = "rgba(39, 39, 42, 0.4)";
      ctx.lineWidth = 1;

      // Draw Grid with local cursor disturbance
      for (let x = 0; x < width; x += spacing) {
        ctx.beginPath();
        for (let y = 0; y < height; y += 10) {
          const dx = x - mouseRef.current.x;
          const dy = y - mouseRef.current.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          const maxDist = 120;
          let offsetX = 0;
          if (dist < maxDist) {
            const force = (1 - dist / maxDist) * 12;
            offsetX = (dx / dist) * force;
          }
          if (y === 0) ctx.moveTo(x + offsetX, y);
          else ctx.lineTo(x + offsetX, y);
        }
        ctx.stroke();
      }
    };
    renderGrid();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("mousemove", handleMouseMove);
    };
  }, []);

  return (
    <section
      id="how-it-works"
      style={{
        background: "#0a0a0a",
        borderTop: "1px solid var(--border-color)",
        padding: "6rem 6vw",
        position: "relative",
        zIndex: 20,
        overflow: "hidden",
      }}
    >
      {/* Background Interactive Cursor Grid */}
      <canvas
        ref={canvasRef}
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          pointerEvents: "none",
          zIndex: 1,
        }}
      />

      <div style={{ maxWidth: "1400px", margin: "0 auto", position: "relative", zIndex: 10 }}>
        {/* Header */}
        <div style={{ marginBottom: "3.5rem" }}>
          <div className="tech-pill" style={{ marginBottom: "1rem" }}>
            SYSTEM ARCHITECTURE
          </div>
          <h3
            className="font-serif"
            style={{
              fontSize: "clamp(2rem, 4vw, 3rem)",
              fontWeight: 500,
              color: "#FFFFFF",
              letterSpacing: "-0.02em",
            }}
          >
            How it works
          </h3>
        </div>

        {/* 3D Physical Card Swap Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: "1.5rem",
          }}
        >
          {steps.map((s, idx) => {
            const isHovered = activeStep === idx;
            return (
              <motion.div
                key={s.num}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.08, duration: 0.4 }}
                onMouseEnter={() => setActiveStep(idx)}
                style={{
                  background: "#000000",
                  border: isHovered ? "1px solid #3B82F6" : "1px solid var(--border-color)",
                  borderRadius: "4px",
                  padding: "2rem 1.75rem",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  minHeight: "230px",
                  cursor: "pointer",
                  transition: "all 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
                  transform: isHovered ? "translateY(-4px)" : "none",
                  boxShadow: isHovered ? "0 10px 30px rgba(0, 0, 0, 0.8)" : "none",
                }}
              >
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
                    <div
                      style={{
                        width: "36px",
                        height: "36px",
                        borderRadius: "4px",
                        background: "rgba(255, 255, 255, 0.03)",
                        border: "1px solid rgba(255, 255, 255, 0.08)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      {s.icon}
                    </div>
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.85rem",
                        color: isHovered ? "#3B82F6" : "var(--text-dim)",
                        letterSpacing: "0.08em",
                        transition: "color 0.2s",
                      }}
                    >
                      {s.num}
                    </span>
                  </div>

                  <h4
                    style={{
                      fontFamily: "var(--font-sans)",
                      fontSize: "0.95rem",
                      fontWeight: 600,
                      color: "#FFFFFF",
                      letterSpacing: "0.05em",
                      marginBottom: "0.5rem",
                      textTransform: "uppercase",
                    }}
                  >
                    {s.title}
                  </h4>
                </div>

                <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", lineHeight: 1.5 }}>
                  {s.desc}
                </p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

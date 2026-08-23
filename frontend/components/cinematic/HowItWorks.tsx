"use client";

import { motion } from "motion/react";
import { FileText, FileCheck2, ScanFace, ShieldCheck } from "lucide-react";

export default function HowItWorks() {
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

  return (
    <section
      id="how-it-works"
      style={{
        background: "#0a0a0a",
        borderTop: "1px solid var(--border-color)",
        padding: "7rem 6vw",
        position: "relative",
        zIndex: 20,
      }}
    >
      <div style={{ maxWidth: "1400px", margin: "0 auto" }}>
        {/* Section Header */}
        <div style={{ marginBottom: "4rem" }}>
          <div className="tech-pill" style={{ marginBottom: "1rem" }}>
            ARCHITECTURE & PROCESS
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

        {/* 4 Clean Horizontal Step Cards */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: "1.5rem",
          }}
        >
          {steps.map((s, idx) => (
            <motion.div
              key={s.num}
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: idx * 0.1, duration: 0.4 }}
              style={{
                background: "#000000",
                border: "1px solid var(--border-color)",
                borderRadius: "4px",
                padding: "2rem 1.75rem",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                minHeight: "220px",
                transition: "border-color 0.2s ease",
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.borderColor = "#52525b";
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.borderColor = "var(--border-color)";
              }}
            >
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
                  <div
                    style={{
                      width: "36px",
                      height: "36px",
                      borderRadius: "4px",
                      background: "rgba(255, 255, 255, 0.04)",
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
                      color: "var(--text-dim)",
                      letterSpacing: "0.08em",
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
          ))}
        </div>
      </div>
    </section>
  );
}

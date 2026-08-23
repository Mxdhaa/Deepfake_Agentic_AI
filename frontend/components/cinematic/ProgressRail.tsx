"use client";

import { motion, AnimatePresence } from "motion/react";

interface ProgressRailProps {
  currentAct: number; // 0 to 7
  scrollProgress: number;
}

const ACTS = [
  { id: 0, num: "00", name: "THE SIGNAL" },
  { id: 1, num: "01", name: "RECONSTRUCTION" },
  { id: 2, num: "02", name: "IDENTITY DATA" },
  { id: 3, num: "03", name: "DOCUMENT" },
  { id: 4, num: "04", name: "DISTINCTION" },
  { id: 5, num: "05", name: "LIVENESS" },
  { id: 6, num: "06", name: "CONVERGENCE" },
  { id: 7, num: "07", name: "VERIFY" },
];

export default function ProgressRail({ currentAct, scrollProgress }: ProgressRailProps) {
  return (
    <div
      style={{
        position: "fixed",
        right: "2.5rem",
        top: "50%",
        transform: "translateY(-50%)",
        zIndex: 40,
        display: "flex",
        flexDirection: "column",
        gap: "14px",
        fontFamily: "var(--font-mono)",
      }}
    >
      {ACTS.map((act) => {
        const isActive = currentAct === act.id;
        return (
          <div
            key={act.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              justifyContent: "flex-end",
              cursor: "pointer",
              userSelect: "none",
            }}
            onClick={() => {
              const target = (act.id / 7.5) * (document.body.scrollHeight - window.innerHeight);
              window.scrollTo({ top: target, behavior: "smooth" });
            }}
          >
            {/* Active Label Tooltip */}
            <AnimatePresence>
              {isActive && (
                <motion.span
                  initial={{ opacity: 0, x: 6 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 6 }}
                  transition={{ duration: 0.18 }}
                  style={{
                    fontSize: "0.68rem",
                    letterSpacing: "0.1em",
                    fontWeight: 600,
                    color: "#3B82F6",
                    textTransform: "uppercase",
                  }}
                >
                  {act.num} / {act.name}
                </motion.span>
              )}
            </AnimatePresence>

            {/* Indicator Hash Mark */}
            <div
              style={{
                width: isActive ? "16px" : "4px",
                height: "2px",
                backgroundColor: isActive ? "#3B82F6" : "rgba(255, 255, 255, 0.2)",
                transition: "all 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
              }}
            />
          </div>
        );
      })}
    </div>
  );
}

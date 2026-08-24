"use client";

import { useEffect, useRef, useState } from "react";
import { useScroll, useSpring, useVelocity } from "motion/react";
import CinematicCanvas from "@/components/cinematic/CinematicCanvas";
import NarrativeLayer from "@/components/cinematic/NarrativeLayer";
import ProgressRail from "@/components/cinematic/ProgressRail";
import HowItWorks from "@/components/cinematic/HowItWorks";

export default function ChainProofLandingPage() {
  const containerRef = useRef<HTMLDivElement>(null);

  // Normalized Scroll Progress across the unified timeline
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  });

  // Physical Spring Filter
  const smoothProgress = useSpring(scrollYProgress, {
    stiffness: 75,
    damping: 22,
    restDelta: 0.0005,
  });

  // Scroll Velocity
  const scrollVelocity = useVelocity(smoothProgress);

  const [progressVal, setProgressVal] = useState(0);
  const [velocityVal, setVelocityVal] = useState(0);
  const [currentAct, setCurrentAct] = useState(0);

  useEffect(() => {
    const unsubProgress = smoothProgress.on("change", (latest) => {
      setProgressVal(latest);

      // Continuous Act boundaries:
      // 0.00 -> 0.08: Act 0 (Dome Gallery Overview)
      // 0.08 -> 0.18: Act 1 (The Signal)
      // 0.18 -> 0.32: Act 2 (Reconstruction & Decryption)
      // 0.32 -> 0.44: Act 3 (Spatial Entry / Into Face)
      // 0.44 -> 0.58: Act 4 (Document Evidence)
      // 0.58 -> 0.72: Act 5 (Liveness Emergence)
      // 0.72 -> 0.84: Act 6 (Verification Stability)
      // 0.84 -> 1.00: Act 7 (Final CTA)
      let act = 0;
      if (latest < 0.08) act = 0;
      else if (latest < 0.18) act = 1;
      else if (latest < 0.32) act = 2;
      else if (latest < 0.44) act = 3;
      else if (latest < 0.58) act = 4;
      else if (latest < 0.72) act = 5;
      else if (latest < 0.84) act = 6;
      else act = 7;

      setCurrentAct(act);
    });

    const unsubVelocity = scrollVelocity.on("change", (latest) => {
      setVelocityVal(latest);
    });

    return () => {
      unsubProgress();
      unsubVelocity();
    };
  }, [smoothProgress, scrollVelocity]);

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        backgroundColor: "#000000",
        minHeight: "750vh", // Continuous pinned choreography
      }}
    >
      {/* 1. Persistent WebGL Three.js Canvas */}
      <CinematicCanvas scrollProgress={progressVal} velocity={velocityVal} />

      {/* 2. Subtle Right-Side Progress Rail */}
      <ProgressRail currentAct={currentAct} scrollProgress={progressVal} />

      {/* 3. Synchronized Editorial Narrative Layer */}
      <NarrativeLayer scrollProgress={progressVal} currentAct={currentAct} />

      {/* 4. Dynamic How It Works Section with Interactive Cursor Grid */}
      <HowItWorks />
    </div>
  );
}

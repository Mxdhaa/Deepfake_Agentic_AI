"use client";

import { useEffect, useRef, useState } from "react";
import { useScroll, useSpring, useVelocity } from "motion/react";
import CinematicCanvas from "@/components/cinematic/CinematicCanvas";
import NarrativeLayer from "@/components/cinematic/NarrativeLayer";
import ProgressRail from "@/components/cinematic/ProgressRail";
import HowItWorks from "@/components/cinematic/HowItWorks";

export default function ChainProofLandingPage() {
  const containerRef = useRef<HTMLDivElement>(null);

  // Normalized Scroll Progress (0.00 -> 1.00)
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  });

  // Physical Spring Filter
  const smoothProgress = useSpring(scrollYProgress, {
    stiffness: 80,
    damping: 24,
    restDelta: 0.0005,
  });

  // Scroll Velocity Filter
  const scrollVelocity = useVelocity(smoothProgress);

  const [progressVal, setProgressVal] = useState(0);
  const [velocityVal, setVelocityVal] = useState(0);
  const [currentAct, setCurrentAct] = useState(0);

  useEffect(() => {
    const unsubProgress = smoothProgress.on("change", (latest) => {
      setProgressVal(latest);

      // Act boundaries derived from specification:
      // 0.00 -> 0.10: Act 00 (Arrival)
      // 0.10 -> 0.22: Act 01 (Reconstruction)
      // 0.22 -> 0.34: Act 02 (Identity Data)
      // 0.34 -> 0.47: Act 03 (Document)
      // 0.47 -> 0.58: Act 04 (Distinction)
      // 0.58 -> 0.74: Act 05 (Liveness)
      // 0.74 -> 0.88: Act 06 (Convergence)
      // 0.88 -> 1.00: Act 07 (Verify)
      let act = 0;
      if (latest < 0.10) act = 0;
      else if (latest < 0.22) act = 1;
      else if (latest < 0.34) act = 2;
      else if (latest < 0.47) act = 3;
      else if (latest < 0.58) act = 4;
      else if (latest < 0.74) act = 5;
      else if (latest < 0.88) act = 6;
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
        minHeight: "700vh", // Dense, purposeful 7–8 viewports total
      }}
    >
      {/* 1. Persistent Three.js WebGL Engine */}
      <CinematicCanvas scrollProgress={progressVal} velocity={velocityVal} />

      {/* 2. Subtle Right-Side Progress Rail */}
      <ProgressRail currentAct={currentAct} scrollProgress={progressVal} />

      {/* 3. Synchronized Editorial Narrative Layer */}
      <NarrativeLayer scrollProgress={progressVal} currentAct={currentAct} />

      {/* 4. Calm Post-Cinematic Process Section */}
      <HowItWorks />
    </div>
  );
}

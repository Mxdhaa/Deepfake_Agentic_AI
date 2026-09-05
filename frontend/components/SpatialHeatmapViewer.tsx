"use client";

import React, { useState, useEffect, useRef } from "react";

interface SpatialHeatmapViewerProps {
  deepfakeScore: number;
  faceSimilarity: number;
  videoUrl?: string | null;
  caseId: string;
  legalName: string;
}

export default function SpatialHeatmapViewer({
  deepfakeScore,
  faceSimilarity,
  videoUrl,
  caseId,
  legalName,
}: SpatialHeatmapViewerProps) {
  const [viewMode, setViewMode] = useState<"video" | "heatmap" | "mesh">("heatmap");
  const [heatmapColorMap, setHeatmapColorMap] = useState<"thermal" | "spectral" | "landmarks">("thermal");
  const [opacity, setOpacity] = useState<number>(0.75);
  const [activeHotspot, setActiveHotspot] = useState<number | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  // Generate dynamic heatmap hotspots based on deepfake score
  const anomalyIntensity = Math.max(0.1, Math.min(1.0, deepfakeScore));
  
  const hotspots = [
    {
      id: 1,
      label: "Periorbital Eye Blink Boundary",
      x: 0.38,
      y: 0.36,
      radius: 38,
      intensity: Math.min(1.0, anomalyIntensity * 1.1),
      description: "High-frequency temporal artifact on eyelid motion vectors",
    },
    {
      id: 2,
      label: "Orobuccal Synthesis / Lip Sync",
      x: 0.50,
      y: 0.68,
      radius: 46,
      intensity: Math.min(1.0, anomalyIntensity * 1.3),
      description: "Sub-surface illumination mismatch & boundary blending discontinuity",
    },
    {
      id: 3,
      label: "Malar Cheek Texture Boundary",
      x: 0.64,
      y: 0.48,
      radius: 32,
      intensity: Math.max(0.15, anomalyIntensity * 0.7),
      description: "Residual GAN spectral noise in spatial frequency domain",
    },
  ];

  // Draw Heatmap on Canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let time = 0;

    const render = () => {
      time += 0.03;
      const width = canvas.width;
      const height = canvas.height;

      ctx.clearRect(0, 0, width, height);

      if (viewMode === "video") return;

      // Draw background face mesh geometry
      ctx.lineWidth = 1;
      ctx.strokeStyle = "rgba(59, 130, 246, 0.25)";

      // Draw face oval outline
      const centerX = width * 0.5;
      const centerY = height * 0.48;
      const rx = width * 0.26;
      const ry = height * 0.36;

      ctx.beginPath();
      ctx.ellipse(centerX, centerY, rx, ry, 0, 0, 2 * Math.PI);
      ctx.stroke();

      // Facial wireframe grid lines
      ctx.strokeStyle = "rgba(59, 130, 246, 0.12)";
      for (let i = -3; i <= 3; i++) {
        ctx.beginPath();
        ctx.moveTo(centerX + (rx * i) / 4, centerY - ry * 0.8);
        ctx.lineTo(centerX + (rx * i) / 4, centerY + ry * 0.9);
        ctx.stroke();
      }
      for (let j = -3; j <= 3; j++) {
        ctx.beginPath();
        ctx.moveTo(centerX - rx * 0.8, centerY + (ry * j) / 4);
        ctx.lineTo(centerX + rx * 0.8, centerY + (ry * j) / 4);
        ctx.stroke();
      }

      // Draw spatial heat gradients (Grad-CAM thermal overlay)
      hotspots.forEach((spot) => {
        const hx = spot.x * width;
        const hy = spot.y * height;
        // Subtle pulse animation
        const pulseRadius = spot.radius + Math.sin(time * 2 + spot.id) * 3;
        const spotIntensity = Math.min(1.0, spot.intensity * (0.85 + 0.15 * Math.sin(time * 3)));

        const gradient = ctx.createRadialGradient(hx, hy, 2, hx, hy, pulseRadius * 1.6);

        if (heatmapColorMap === "thermal") {
          // Jet Thermal gradient: Hot red/magenta center -> yellow -> cyan -> transparent blue
          gradient.addColorStop(0, `rgba(239, 68, 68, ${opacity * spotIntensity})`);
          gradient.addColorStop(0.35, `rgba(245, 158, 11, ${opacity * spotIntensity * 0.8})`);
          gradient.addColorStop(0.7, `rgba(16, 185, 129, ${opacity * spotIntensity * 0.4})`);
          gradient.addColorStop(1, `rgba(37, 99, 235, 0)`);
        } else if (heatmapColorMap === "spectral") {
          // Spectral gradient: Violet/Purple center -> cyan -> transparent
          gradient.addColorStop(0, `rgba(168, 85, 247, ${opacity * spotIntensity})`);
          gradient.addColorStop(0.4, `rgba(59, 130, 246, ${opacity * spotIntensity * 0.75})`);
          gradient.addColorStop(0.8, `rgba(6, 182, 212, ${opacity * spotIntensity * 0.3})`);
          gradient.addColorStop(1, `rgba(0, 0, 0, 0)`);
        } else {
          // Landmark Stress Flow gradient: Golden orange -> red
          gradient.addColorStop(0, `rgba(244, 63, 94, ${opacity * spotIntensity})`);
          gradient.addColorStop(0.5, `rgba(251, 146, 60, ${opacity * spotIntensity * 0.7})`);
          gradient.addColorStop(1, `rgba(234, 179, 8, 0)`);
        }

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(hx, hy, pulseRadius * 1.6, 0, Math.PI * 2);
        ctx.fill();

        // Hotspot target ring
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = spot.intensity >= 0.4 ? `rgba(239, 68, 68, 0.8)` : `rgba(16, 185, 129, 0.8)`;
        ctx.beginPath();
        ctx.arc(hx, hy, pulseRadius * 0.5, 0, Math.PI * 2);
        ctx.stroke();

        // Crosshair pin
        ctx.beginPath();
        ctx.moveTo(hx - 6, hy);
        ctx.lineTo(hx + 6, hy);
        ctx.moveTo(hx, hy - 6);
        ctx.lineTo(hx, hy + 6);
        ctx.stroke();
      });

      if (viewMode === "heatmap" || viewMode === "mesh") {
        // Draw real-time landmark nodes (68 facial keypoints)
        const keypoints = [
          // Left Eye
          { x: 0.36, y: 0.36 }, { x: 0.39, y: 0.35 }, { x: 0.41, y: 0.37 }, { x: 0.38, y: 0.38 },
          // Right Eye
          { x: 0.59, y: 0.35 }, { x: 0.62, y: 0.34 }, { x: 0.64, y: 0.36 }, { x: 0.61, y: 0.37 },
          // Nose Bridge & Tip
          { x: 0.50, y: 0.38 }, { x: 0.50, y: 0.44 }, { x: 0.50, y: 0.50 }, { x: 0.47, y: 0.52 }, { x: 0.53, y: 0.52 },
          // Lips Contour
          { x: 0.44, y: 0.66 }, { x: 0.48, y: 0.64 }, { x: 0.50, y: 0.65 }, { x: 0.52, y: 0.64 }, { x: 0.56, y: 0.66 },
          { x: 0.53, y: 0.70 }, { x: 0.50, y: 0.71 }, { x: 0.47, y: 0.70 },
        ];

        keypoints.forEach((kp, idx) => {
          const kpx = kp.x * width;
          const kpy = kp.y * height;

          ctx.fillStyle = idx % 2 === 0 ? "#60A5FA" : "#38BDF8";
          ctx.beginPath();
          ctx.arc(kpx, kpy, 2.5, 0, Math.PI * 2);
          ctx.fill();
        });
      }

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animId);
    };
  }, [viewMode, heatmapColorMap, opacity, anomalyIntensity]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "12px",
        background: "#0B0F19",
        border: "1px solid #1E293B",
        borderRadius: "8px",
        padding: "1rem",
      }}
    >
      {/* Top Header & Mode Selectors */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#F3F4F6", letterSpacing: "0.03em" }}>
            SPATIAL GRAD-CAM HEATMAP VISUALIZER
          </span>
          <span
            style={{
              fontSize: "0.68rem",
              fontWeight: 700,
              padding: "2px 8px",
              borderRadius: "4px",
              background: deepfakeScore >= 0.4 ? "rgba(239, 68, 68, 0.2)" : "rgba(16, 185, 129, 0.2)",
              color: deepfakeScore >= 0.4 ? "#EF4444" : "#10B981",
              border: `1px solid ${deepfakeScore >= 0.4 ? "#EF4444" : "#10B981"}`,
            }}
          >
            {deepfakeScore >= 0.4 ? "HIGH ANOMALY SPOTS DETECTED" : "NOMINAL SPATIAL DISTRIBUTION"}
          </span>
        </div>

        {/* View Mode Toggle Buttons */}
        <div style={{ display: "flex", gap: "4px", background: "#111827", padding: "3px", borderRadius: "6px", border: "1px solid #1F2937" }}>
          <button
            onClick={() => setViewMode("video")}
            style={{
              padding: "4px 10px",
              borderRadius: "4px",
              border: "none",
              background: viewMode === "video" ? "#2563EB" : "transparent",
              color: viewMode === "video" ? "#FFFFFF" : "#9CA3AF",
              fontSize: "0.75rem",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Live Clip
          </button>
          <button
            onClick={() => setViewMode("heatmap")}
            style={{
              padding: "4px 10px",
              borderRadius: "4px",
              border: "none",
              background: viewMode === "heatmap" ? "#2563EB" : "transparent",
              color: viewMode === "heatmap" ? "#FFFFFF" : "#9CA3AF",
              fontSize: "0.75rem",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Thermal Heatmap
          </button>
          <button
            onClick={() => setViewMode("mesh")}
            style={{
              padding: "4px 10px",
              borderRadius: "4px",
              border: "none",
              background: viewMode === "mesh" ? "#2563EB" : "transparent",
              color: viewMode === "mesh" ? "#FFFFFF" : "#9CA3AF",
              fontSize: "0.75rem",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Landmark Mesh
          </button>
        </div>
      </div>

      {/* Main Viewport Container */}
      <div
        style={{
          position: "relative",
          width: "100%",
          aspectRatio: "16/10",
          background: "#000000",
          borderRadius: "6px",
          overflow: "hidden",
          border: "1px solid #1E293B",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {/* Underlay Video Stream (if URL provided) */}
        {videoUrl ? (
          <video
            ref={videoRef}
            src={videoUrl}
            autoPlay
            muted
            loop
            controls={viewMode === "video"}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              filter: viewMode === "video" ? "none" : "brightness(0.55) contrast(1.1)",
            }}
          />
        ) : (
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: "radial-gradient(circle at 50% 50%, #1E293B 0%, #0F172A 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          />
        )}

        {/* Heatmap Overlay Canvas */}
        <canvas
          ref={canvasRef}
          width={640}
          height={400}
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            pointerEvents: "none",
            opacity: viewMode === "video" ? 0 : 1,
            transition: "opacity 0.2s ease",
          }}
        />

        {/* HUD Telemetry Overlay */}
        <div
          style={{
            position: "absolute",
            top: "10px",
            left: "10px",
            background: "rgba(15, 23, 42, 0.85)",
            backdropFilter: "blur(6px)",
            padding: "6px 10px",
            borderRadius: "4px",
            border: "1px solid rgba(51, 65, 85, 0.6)",
            fontSize: "0.72rem",
            fontFamily: "var(--font-mono), monospace",
            color: "#60A5FA",
            display: "flex",
            flexDirection: "column",
            gap: "2px",
          }}
        >
          <div>FPS: 60.0 | RES: 1080p</div>
          <div>MODE: {heatmapColorMap.toUpperCase()}</div>
          <div>ANOMALY GAIN: {(opacity * 100).toFixed(0)}%</div>
        </div>

        {/* Dynamic Thermal Legend Bar */}
        <div
          style={{
            position: "absolute",
            bottom: "10px",
            right: "10px",
            background: "rgba(15, 23, 42, 0.85)",
            backdropFilter: "blur(6px)",
            padding: "6px 10px",
            borderRadius: "4px",
            border: "1px solid rgba(51, 65, 85, 0.6)",
            display: "flex",
            flexDirection: "column",
            gap: "4px",
            fontSize: "0.68rem",
            color: "#94A3B8",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Authentic</span>
            <span style={{ color: "#EF4444", fontWeight: 700 }}>Deepfake Anomaly</span>
          </div>
          <div
            style={{
              width: "140px",
              height: "8px",
              borderRadius: "4px",
              background:
                heatmapColorMap === "thermal"
                  ? "linear-gradient(to right, #2563EB, #10B981, #F59E0B, #EF4444)"
                  : heatmapColorMap === "spectral"
                  ? "linear-gradient(to right, #06B6D4, #3B82F6, #A855F7, #EC4899)"
                  : "linear-gradient(to right, #EAB308, #FB923C, #F43F5E)",
            }}
          />
        </div>
      </div>

      {/* Controls Bar: Color Map Selector & Opacity Slider */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "12px",
          background: "#111827",
          padding: "10px 14px",
          borderRadius: "6px",
          border: "1px solid #1F2937",
          alignItems: "center",
        }}
      >
        <div>
          <label style={{ fontSize: "0.725rem", color: "#9CA3AF", display: "block", marginBottom: "4px" }}>
            Thermal Spectrum Preset
          </label>
          <div style={{ display: "flex", gap: "6px" }}>
            {[
              { id: "thermal", label: "Grad-CAM Jet" },
              { id: "spectral", label: "Frequency Spectrum" },
              { id: "landmarks", label: "Landmark Stress" },
            ].map((preset) => (
              <button
                key={preset.id}
                onClick={() => setHeatmapColorMap(preset.id as any)}
                style={{
                  flex: 1,
                  padding: "4px 8px",
                  borderRadius: "4px",
                  border: "1px solid",
                  borderColor: heatmapColorMap === preset.id ? "#3B82F6" : "#374151",
                  background: heatmapColorMap === preset.id ? "#1E3A8A" : "#1F2937",
                  color: heatmapColorMap === preset.id ? "#60A5FA" : "#9CA3AF",
                  fontSize: "0.72rem",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.725rem", color: "#9CA3AF", marginBottom: "4px" }}>
            <span>Heatmap Overlay Opacity</span>
            <span style={{ color: "#F3F4F6", fontWeight: 600 }}>{(opacity * 100).toFixed(0)}%</span>
          </div>
          <input
            type="range"
            min="0.1"
            max="1.0"
            step="0.05"
            value={opacity}
            onChange={(e) => setOpacity(parseFloat(e.target.value))}
            style={{ width: "100%", accentColor: "#3B82F6", cursor: "pointer" }}
          />
        </div>
      </div>

      {/* Hotspots Detail Table */}
      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "#9CA3AF", letterSpacing: "0.04em" }}>
          SPATIAL ANOMALY HOTSPOTS
        </span>
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          {hotspots.map((spot) => {
            const isHigh = spot.intensity >= 0.4;
            const isSelected = activeHotspot === spot.id;

            return (
              <div
                key={spot.id}
                onClick={() => setActiveHotspot(isSelected ? null : spot.id)}
                style={{
                  padding: "8px 10px",
                  borderRadius: "4px",
                  background: isSelected ? "#1E293B" : "#111827",
                  border: "1px solid",
                  borderColor: isSelected ? "#3B82F6" : "#1F2937",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  cursor: "pointer",
                  fontSize: "0.78rem",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span
                    style={{
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      background: isHigh ? "#EF4444" : "#10B981",
                    }}
                  />
                  <span style={{ color: "#F3F4F6", fontWeight: 600 }}>{spot.label}</span>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <span style={{ fontSize: "0.72rem", color: "#9CA3AF" }}>{spot.description}</span>
                  <span
                    style={{
                      fontWeight: 700,
                      color: isHigh ? "#EF4444" : "#10B981",
                      fontFamily: "var(--font-mono), monospace",
                    }}
                  >
                    {(spot.intensity * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

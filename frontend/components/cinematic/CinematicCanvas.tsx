"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

interface CinematicCanvasProps {
  scrollProgress: number; // 0.0 -> 1.0
  velocity: number;
}

// Generate circular soft-glow particle texture to avoid harsh square pixels
function createPointTexture(): THREE.Texture {
  const canvas = document.createElement("canvas");
  canvas.width = 64;
  canvas.height = 64;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    const gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    gradient.addColorStop(0.0, "rgba(255, 255, 255, 1.0)");
    gradient.addColorStop(0.25, "rgba(96, 165, 250, 0.85)");
    gradient.addColorStop(0.6, "rgba(47, 128, 255, 0.3)");
    gradient.addColorStop(1.0, "rgba(0, 0, 0, 0.0)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 64, 64);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

export default function CinematicCanvas({ scrollProgress, velocity }: CinematicCanvasProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const progressRef = useRef(scrollProgress);
  const velocityRef = useRef(velocity);
  const mouseRef = useRef({ x: 0, y: 0, targetX: 0, targetY: 0 });

  useEffect(() => {
    progressRef.current = scrollProgress;
    velocityRef.current = velocity;
  }, [scrollProgress, velocity]);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const isMobile = window.innerWidth < 768;
    const PARTICLE_COUNT = isMobile ? 2800 : 5200;
    const DOME_CARD_COUNT = isMobile ? 6 : 10;

    // ── 1. Scene, Camera, Renderer ───────────────────────────────────────────
    const scene = new THREE.Scene();
    // Deep optical laboratory background with navy atmosphere
    scene.background = new THREE.Color(0x030712);
    scene.fog = new THREE.FogExp2(0x030712, 0.032);

    let width = window.innerWidth;
    let height = window.innerHeight;

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 0, 22);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: false,
      powerPreference: "high-performance",
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, isMobile ? 1.5 : 2));
    container.appendChild(renderer.domElement);

    const pointTexture = createPointTexture();

    // ── 2. Dome Gallery Spatial Identity Frames (0.00 – 0.08) ────────────────
    const domeGroup = new THREE.Group();
    const domeCards: THREE.Group[] = [];
    const domeRadius = 11.0;

    for (let i = 0; i < DOME_CARD_COUNT; i++) {
      const angle = (i / DOME_CARD_COUNT) * Math.PI * 2;
      const cardGroup = new THREE.Group();

      // Outer frame
      const frameGeo = new THREE.EdgesGeometry(new THREE.PlaneGeometry(2.0, 2.8));
      const isSelected = i === 0;
      const frameMat = new THREE.LineBasicMaterial({
        color: isSelected ? 0x2f80ff : 0x334155,
        transparent: true,
        opacity: isSelected ? 0.95 : 0.4,
      });
      const frame = new THREE.LineSegments(frameGeo, frameMat);
      cardGroup.add(frame);

      // Translucent inner backing
      const backGeo = new THREE.PlaneGeometry(1.98, 2.78);
      const backMat = new THREE.MeshBasicMaterial({
        color: isSelected ? 0x081738 : 0x070d1e,
        transparent: true,
        opacity: isSelected ? 0.65 : 0.3,
        side: THREE.DoubleSide,
      });
      const back = new THREE.Mesh(backGeo, backMat);
      back.position.z = -0.01;
      cardGroup.add(back);

      cardGroup.position.set(
        Math.sin(angle) * domeRadius,
        (Math.sin(i * 1.5) * 0.8),
        Math.cos(angle) * domeRadius - 3.5
      );
      cardGroup.lookAt(0, cardGroup.position.y, -3.5);
      domeGroup.add(cardGroup);
      domeCards.push(cardGroup);
    }
    scene.add(domeGroup);

    // ── 3. High-Fidelity 5,200 Particle BufferGeometry ───────────────────────
    const geometry = new THREE.BufferGeometry();

    const currentPositions = new Float32Array(PARTICLE_COUNT * 3);
    const targetDome = new Float32Array(PARTICLE_COUNT * 3);
    const targetSignal = new Float32Array(PARTICLE_COUNT * 3);
    const targetSilhouette = new Float32Array(PARTICLE_COUNT * 3);
    const targetDocument = new Float32Array(PARTICLE_COUNT * 3);
    const targetLiveness = new Float32Array(PARTICLE_COUNT * 3);

    const colors = new Float32Array(PARTICLE_COUNT * 3);
    const baseColors = new Float32Array(PARTICLE_COUNT * 3);
    const sizes = new Float32Array(PARTICLE_COUNT);

    const colorWhite = new THREE.Color(0xffffff);
    const colorBlue = new THREE.Color(0x2f80ff);
    const colorDim = new THREE.Color(0x64748b);
    const colorScanActive = new THREE.Color(0x93c5fd);

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const i3 = i * 3;

      // Dome Gallery arrangement
      const dAngle = (i / PARTICLE_COUNT) * Math.PI * 2 * 4;
      const dRad = 9.0 + (i % 6) * 0.6;
      targetDome[i3] = Math.sin(dAngle) * dRad;
      targetDome[i3 + 1] = ((i % 120) / 120 - 0.5) * 9;
      targetDome[i3 + 2] = Math.cos(dAngle) * dRad - 5;

      // 00: Volumetric Signal Field
      const rSig = 8.0 + Math.random() * 15;
      const thetaSig = Math.random() * Math.PI * 2;
      const phiSig = Math.acos(Math.random() * 2 - 1);
      targetSignal[i3] = rSig * Math.sin(phiSig) * Math.cos(thetaSig);
      targetSignal[i3 + 1] = rSig * Math.sin(phiSig) * Math.sin(thetaSig);
      targetSignal[i3 + 2] = rSig * Math.cos(phiSig) - 4;

      currentPositions[i3] = targetDome[i3];
      currentPositions[i3 + 1] = targetDome[i3 + 1];
      currentPositions[i3 + 2] = targetDome[i3 + 2];

      // 01: Distinct Anatomical Human Silhouette (Head, Facial Plane, Torso)
      if (i < PARTICLE_COUNT * 0.45) {
        // Facial Plane & Eyes / Nose / Jawline Structure
        const u = Math.random();
        const v = Math.random();
        const t = u * Math.PI * 2;
        const p = Math.acos(2 * v - 1);
        const rHead = 2.4 + (Math.sin(t * 4) * 0.08);

        // Define facial forward contour
        const isFaceFront = Math.sin(t) > 0;
        const forwardBias = isFaceFront ? 1.15 : 0.85;

        targetSilhouette[i3] = rHead * Math.sin(p) * Math.cos(t) * 0.82;
        targetSilhouette[i3 + 1] = rHead * Math.cos(p) * 1.15 + 0.6;
        targetSilhouette[i3 + 2] = rHead * Math.sin(p) * Math.sin(t) * forwardBias;
      } else if (i < PARTICLE_COUNT * 0.75) {
        // Shoulders & Chest
        const sx = (Math.random() - 0.5) * 8.0;
        const sy = -2.2 - Math.random() * 3.5;
        const sz = (Math.random() - 0.5) * 2.2;
        targetSilhouette[i3] = sx;
        targetSilhouette[i3 + 1] = sy;
        targetSilhouette[i3 + 2] = sz;
      } else {
        // Peripheral Biometric Aura / Contour Points
        const aRad = 3.5 + Math.random() * 2.0;
        const aAng = Math.random() * Math.PI * 2;
        targetSilhouette[i3] = Math.cos(aAng) * aRad * 0.85;
        targetSilhouette[i3 + 1] = Math.sin(aAng) * aRad + 0.5;
        targetSilhouette[i3 + 2] = (Math.random() - 0.5) * 2.0;
      }

      // 03: Organic Decomposed Credential Field (No boxy rectangular edges)
      const uDoc = Math.random() * Math.PI * 2;
      const vDoc = (Math.random() - 0.5) * 6.0;
      const wave = Math.sin(vDoc * 1.5) * 0.4;
      targetDocument[i3] = (Math.random() - 0.5) * 7.0 + wave;
      targetDocument[i3 + 1] = vDoc;
      targetDocument[i3 + 2] = Math.sin(uDoc) * 1.8;

      // 04: Liveness Dense Biometric Field
      targetLiveness[i3] = targetSilhouette[i3] * 1.1;
      targetLiveness[i3 + 1] = targetSilhouette[i3 + 1] * 1.1;
      targetLiveness[i3 + 2] = targetSilhouette[i3 + 2] * 1.1;

      // Colors & Sizes: Electric blue accents with bright cool white points
      const isBlue = i % 6 === 0;
      const c = isBlue ? colorBlue : (i % 2 === 0 ? colorWhite : colorDim);
      colors[i3] = c.r;
      colors[i3 + 1] = c.g;
      colors[i3 + 2] = c.b;

      baseColors[i3] = c.r;
      baseColors[i3 + 1] = c.g;
      baseColors[i3 + 2] = c.b;

      // Point size modulation for spatial depth
      sizes[i] = (i % 4 === 0 ? 0.09 : 0.055);
    }

    geometry.setAttribute("position", new THREE.BufferAttribute(currentPositions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    geometry.setAttribute("size", new THREE.BufferAttribute(sizes, 1));

    const particleMaterial = new THREE.PointsMaterial({
      size: isMobile ? 0.08 : 0.065,
      map: pointTexture,
      vertexColors: true,
      transparent: true,
      opacity: 0.92,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const particleSystem = new THREE.Points(geometry, particleMaterial);
    scene.add(particleSystem);

    // ── 4. 3D Physical Scanning Band (5–12% Viewport Height) ──────────────────
    const scanBandGroup = new THREE.Group();

    // Leading laser line
    const scanLineGeo = new THREE.BufferGeometry();
    scanLineGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array([-5.5, 0, 0, 5.5, 0, 0]), 3));
    const scanLineMat = new THREE.LineBasicMaterial({
      color: 0x60a5fa,
      transparent: true,
      opacity: 0.0,
      linewidth: 2,
    });
    const scanLine = new THREE.Line(scanLineGeo, scanLineMat);
    scanBandGroup.add(scanLine);

    // Translucent scanning volume plane
    const scanVolumeGeo = new THREE.PlaneGeometry(10.0, 1.2);
    const scanVolumeMat = new THREE.MeshBasicMaterial({
      color: 0x1d4ed8,
      transparent: true,
      opacity: 0.0,
      side: THREE.DoubleSide,
    });
    const scanVolume = new THREE.Mesh(scanVolumeGeo, scanVolumeMat);
    scanVolume.position.y = -0.6;
    scanBandGroup.add(scanVolume);

    scene.add(scanBandGroup);

    // ── 5. Mouse Tracking ──────────────────────────────────────────────────────
    const handleMouseMove = (e: MouseEvent) => {
      mouseRef.current.targetX = (e.clientX / window.innerWidth) * 2 - 1;
      mouseRef.current.targetY = -(e.clientY / window.innerHeight) * 2 + 1;
    };
    window.addEventListener("mousemove", handleMouseMove, { passive: true });

    // ── 6. Master Render & Animation Loop ──────────────────────────────────────
    let animId: number;
    const clock = new THREE.Clock();

    const renderLoop = () => {
      animId = requestAnimationFrame(renderLoop);
      const time = clock.getElapsedTime();
      const p = progressRef.current;

      mouseRef.current.x += (mouseRef.current.targetX - mouseRef.current.x) * 0.06;
      mouseRef.current.y += (mouseRef.current.targetY - mouseRef.current.y) * 0.06;

      const posAttr = geometry.attributes.position as THREE.BufferAttribute;
      const colorAttr = geometry.attributes.color as THREE.BufferAttribute;
      const posArr = posAttr.array as Float32Array;
      const colorArr = colorAttr.array as Float32Array;

      // ── B. Continuous Camera Choreography with Ambient Float ───────────────
      const ambientCamX = Math.sin(time * 0.4) * 0.22;
      const ambientCamY = Math.cos(time * 0.32) * 0.15;

      if (p < 0.08) {
        domeGroup.visible = true;
        domeGroup.rotation.y = time * 0.18 + p * 14;
        const selP = Math.min(1.0, p / 0.06);
        domeCards[0].scale.set(1.0 + selP * 1.3, 1.0 + selP * 1.3, 1.0);
        camera.position.set(ambientCamX, ambientCamY, 22);
      } else {
        domeGroup.visible = false;
        
        if (p < 0.18) {
          // Scene 00: The Signal (Z = 22 -> 17)
          const sP = (p - 0.08) / 0.10;
          camera.position.set(mouseRef.current.x * 0.5 + ambientCamX, mouseRef.current.y * 0.5 + ambientCamY, 22 - sP * 5);
        } else if (p < 0.32) {
          // Scene 01: Reconstruction (Z = 17 -> 11)
          const rP = (p - 0.18) / 0.14;
          camera.position.set(mouseRef.current.x * 0.3 + ambientCamX * 0.7, mouseRef.current.y * 0.3 + ambientCamY * 0.7, 17 - rP * 6);
        } else if (p < 0.44) {
          // Scene 02: FLY INTO THE FACE (Z = 11 -> -8 through facial plane)
          const fP = (p - 0.32) / 0.12;
          camera.position.set(ambientCamX * 0.3 * (1 - fP), 0.6 * (1 - fP) + ambientCamY * 0.3 * (1 - fP), 11 - fP * 19);
        } else if (p < 0.58) {
          // Scene 03: Evidence Decomposition
          const eP = (p - 0.44) / 0.14;
          camera.position.set(Math.sin(eP * Math.PI) * 0.4 + ambientCamX * 0.5, ambientCamY * 0.5, 9.0);
        } else if (p < 0.72) {
          // Scene 04: Liveness Physical Scanning (Z = 9.5)
          camera.position.set(ambientCamX * 0.4, ambientCamY * 0.4, 9.5);
        } else if (p < 0.84) {
          // Scene 05: Verification Stability
          const vP = (p - 0.72) / 0.12;
          camera.position.set(ambientCamX * 0.5, ambientCamY * 0.5, 9.5 + vP * 5.0);
        } else {
          camera.position.set(ambientCamX * 0.3, ambientCamY * 0.3, 16.5);
        }
      }

      // ── C. Physical Liveness Scanning Band Sweep & Particle Reaction ─────────
      let currentScanY = -999;
      if (p >= 0.58 && p < 0.72) {
        const liveP = (p - 0.58) / 0.14;
        // Continuous organic head movement
        const yaw = Math.sin(liveP * Math.PI * 2 + time * 0.5) * 0.42;
        particleSystem.rotation.y = THREE.MathUtils.lerp(particleSystem.rotation.y, yaw, 0.12);

        // Scan sweeps from head (+3.2) down to shoulders (-2.8)
        currentScanY = 3.2 - liveP * 6.0;
        scanBandGroup.position.set(0, currentScanY, 0.8);
        scanLineMat.opacity = 0.95;
        scanVolumeMat.opacity = 0.25;
      } else {
        // Gentle continuous idle rotation
        const idleRotY = Math.sin(time * 0.25) * 0.08;
        particleSystem.rotation.y = THREE.MathUtils.lerp(particleSystem.rotation.y, idleRotY, 0.08);
        scanLineMat.opacity = 0.0;
        scanVolumeMat.opacity = 0.0;
      }

      // ── D. Particle Position & Continuous Ambient Micro-Drift ────────────────
      const ease = 0.085;
      for (let i = 0; i < PARTICLE_COUNT; i++) {
        const i3 = i * 3;
        let tx = 0;
        let ty = 0;
        let tz = 0;

        if (p < 0.08) {
          tx = targetDome[i3];
          ty = targetDome[i3 + 1];
          tz = targetDome[i3 + 2];
        } else if (p < 0.18) {
          // Subtle cursor field attraction
          const dx = targetSignal[i3] - mouseRef.current.x * 4;
          const dy = targetSignal[i3 + 1] - mouseRef.current.y * 4;
          const dist = Math.hypot(dx, dy);
          const push = Math.max(0, 1.2 - dist * 0.35);
          tx = targetSignal[i3] + push * mouseRef.current.x;
          ty = targetSignal[i3 + 1] + push * mouseRef.current.y;
          tz = targetSignal[i3 + 2];
        } else if (p < 0.32) {
          // Reconstruction to clear human silhouette
          const blend = Math.min(1.0, (p - 0.18) / 0.12);
          tx = THREE.MathUtils.lerp(targetSignal[i3], targetSilhouette[i3], blend);
          ty = THREE.MathUtils.lerp(targetSignal[i3 + 1], targetSilhouette[i3 + 1], blend);
          tz = THREE.MathUtils.lerp(targetSignal[i3 + 2], targetSilhouette[i3 + 2], blend);
        } else if (p < 0.44) {
          // Fly into face - particles expand naturally around camera path
          const enterP = (p - 0.32) / 0.12;
          const expansion = 1.0 + enterP * 2.0;
          tx = targetSilhouette[i3] * expansion;
          ty = targetSilhouette[i3 + 1] * expansion;
          tz = targetSilhouette[i3 + 2];
        } else if (p < 0.58) {
          // Organic Document Evidence
          const blend = Math.min(1.0, (p - 0.44) / 0.08);
          tx = THREE.MathUtils.lerp(targetSilhouette[i3], targetDocument[i3], blend);
          ty = THREE.MathUtils.lerp(targetSilhouette[i3 + 1], targetDocument[i3 + 1], blend);
          tz = THREE.MathUtils.lerp(targetSilhouette[i3 + 2], targetDocument[i3 + 2], blend);
        } else if (p < 0.72) {
          // Liveness silhouette emergence
          const blend = Math.min(1.0, (p - 0.58) / 0.08);
          tx = THREE.MathUtils.lerp(targetDocument[i3], targetLiveness[i3], blend);
          ty = THREE.MathUtils.lerp(targetDocument[i3 + 1], targetLiveness[i3 + 1], blend);
          tz = THREE.MathUtils.lerp(targetDocument[i3 + 2], targetLiveness[i3 + 2], blend);
        } else if (p < 0.84) {
          tx = targetLiveness[i3];
          ty = targetLiveness[i3 + 1];
          tz = targetLiveness[i3 + 2];
        } else {
          tx = targetSignal[i3] * 1.3;
          ty = targetSignal[i3 + 1] * 1.3;
          tz = targetSignal[i3 + 2] * 1.3;
        }

        // CONTINUOUS AMBIENT MICRO-MOTION (Alive in every single frame!)
        const breathX = Math.sin(time * 1.1 + i * 0.35) * 0.045;
        const breathY = Math.cos(time * 0.95 + i * 0.28) * 0.045;
        const breathZ = Math.sin(time * 0.8 + i * 0.42) * 0.035;

        tx += breathX;
        ty += breathY;
        tz += breathZ;

        posArr[i3] += (tx - posArr[i3]) * ease;
        posArr[i3 + 1] += (ty - posArr[i3 + 1]) * ease;
        posArr[i3 + 2] += (tz - posArr[i3 + 2]) * ease;

        // Dynamic Physical Particle Reaction when Scan Passes + subtle continuous shimmer
        const shimmer = (Math.sin(time * 2.0 + i) * 0.08);
        if (currentScanY !== -999) {
          const distToScan = Math.abs(posArr[i3 + 1] - currentScanY);
          if (distToScan < 0.85) {
            // Inside scan band: Bright electric blue-white glow
            const intensity = 1.0 - distToScan / 0.85;
            colorArr[i3] = THREE.MathUtils.lerp(baseColors[i3], colorScanActive.r, intensity);
            colorArr[i3 + 1] = THREE.MathUtils.lerp(baseColors[i3 + 1], colorScanActive.g, intensity);
            colorArr[i3 + 2] = THREE.MathUtils.lerp(baseColors[i3 + 2], colorScanActive.b, intensity);
          } else {
            colorArr[i3] += (baseColors[i3] + shimmer - colorArr[i3]) * 0.1;
            colorArr[i3 + 1] += (baseColors[i3 + 1] + shimmer - colorArr[i3 + 1]) * 0.1;
            colorArr[i3 + 2] += (baseColors[i3 + 2] + shimmer - colorArr[i3 + 2]) * 0.1;
          }
        } else {
          colorArr[i3 + 1] += (baseColors[i3 + 1] - colorArr[i3 + 1]) * 0.1;
          colorArr[i3 + 2] += (baseColors[i3 + 2] - colorArr[i3 + 2]) * 0.1;
        }
      }

      posAttr.needsUpdate = true;
      colorAttr.needsUpdate = true;

      renderer.render(scene, camera);
    };

    renderLoop();

    const handleResize = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };

    window.addEventListener("resize", handleResize);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("resize", handleResize);
      renderer.dispose();
      geometry.dispose();
      particleMaterial.dispose();
      pointTexture.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <div
      ref={mountRef}
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
  );
}

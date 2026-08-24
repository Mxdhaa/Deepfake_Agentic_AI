"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

interface CinematicCanvasProps {
  scrollProgress: number; // 0.0 -> 1.0
  velocity: number;
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

    // Check device / performance capability
    const isMobile = window.innerWidth < 768;
    const PARTICLE_COUNT = isMobile ? 2200 : 4600;
    const DOME_CARD_COUNT = isMobile ? 6 : 12;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000000);

    let width = window.innerWidth;
    let height = window.innerHeight;

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 0, 20);

    const renderer = new THREE.WebGLRenderer({
      antialias: !isMobile,
      alpha: false,
      powerPreference: "high-performance",
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, isMobile ? 1.5 : 2));
    container.appendChild(renderer.domElement);

    // ── 1. Dome Gallery Cylindrical Group (Opening 0.00 – 0.08) ───────────────
    const domeGroup = new THREE.Group();
    const domeCards: THREE.LineSegments[] = [];
    const domeRadius = 9.5;

    for (let i = 0; i < DOME_CARD_COUNT; i++) {
      const angle = (i / DOME_CARD_COUNT) * Math.PI * 2;
      const cardGeo = new THREE.EdgesGeometry(new THREE.PlaneGeometry(1.6, 2.2));
      const isSelected = i === 0;
      const cardMat = new THREE.LineBasicMaterial({
        color: isSelected ? 0x3b82f6 : 0x27272a,
        transparent: true,
        opacity: isSelected ? 0.9 : 0.35,
      });
      const card = new THREE.LineSegments(cardGeo, cardMat);
      card.position.set(
        Math.sin(angle) * domeRadius,
        (Math.random() - 0.5) * 1.5,
        Math.cos(angle) * domeRadius - 2
      );
      card.lookAt(0, card.position.y, -2);
      domeGroup.add(card);
      domeCards.push(card);
    }
    scene.add(domeGroup);

    // ── 2. Unified 4,600 Particle BufferGeometry ──────────────────────────────
    const geometry = new THREE.BufferGeometry();

    const currentPositions = new Float32Array(PARTICLE_COUNT * 3);
    const targetDome = new Float32Array(PARTICLE_COUNT * 3);
    const targetSignal = new Float32Array(PARTICLE_COUNT * 3);
    const targetSilhouette = new Float32Array(PARTICLE_COUNT * 3);
    const targetDocument = new Float32Array(PARTICLE_COUNT * 3);
    const targetPortal = new Float32Array(PARTICLE_COUNT * 3);
    const targetLiveness = new Float32Array(PARTICLE_COUNT * 3);

    const colors = new Float32Array(PARTICLE_COUNT * 3);
    const colorWhite = new THREE.Color(0xf5f5f5);
    const colorBlue = new THREE.Color(0x3b82f6);
    const colorDim = new THREE.Color(0x52525b);

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const i3 = i * 3;

      // Dome Gallery Points
      const dAngle = (i / PARTICLE_COUNT) * Math.PI * 2 * 3;
      const dRad = 8 + (i % 5) * 0.8;
      targetDome[i3] = Math.sin(dAngle) * dRad;
      targetDome[i3 + 1] = ((i % 100) / 100 - 0.5) * 8;
      targetDome[i3 + 2] = Math.cos(dAngle) * dRad - 4;

      // State 00: Volumetric Signal Field
      const rSig = 9 + Math.random() * 16;
      const thetaSig = Math.random() * Math.PI * 2;
      const phiSig = Math.acos(Math.random() * 2 - 1);
      targetSignal[i3] = rSig * Math.sin(phiSig) * Math.cos(thetaSig);
      targetSignal[i3 + 1] = rSig * Math.sin(phiSig) * Math.sin(thetaSig);
      targetSignal[i3 + 2] = rSig * Math.cos(phiSig) - 6;

      currentPositions[i3] = targetDome[i3];
      currentPositions[i3 + 1] = targetDome[i3 + 1];
      currentPositions[i3 + 2] = targetDome[i3 + 2];

      // State 01: Human Silhouette & Facial Plane
      if (i < PARTICLE_COUNT * 0.7) {
        // Head volume & facial topology
        const u = Math.random();
        const v = Math.random();
        const theta = u * 2 * Math.PI;
        const phi = Math.acos(2 * v - 1);
        const rHead = 2.6 + Math.sin(theta * 3) * 0.12;
        targetSilhouette[i3] = rHead * Math.sin(phi) * Math.cos(theta) * 0.88;
        targetSilhouette[i3 + 1] = rHead * Math.cos(phi) * 1.18 + 0.5;
        targetSilhouette[i3 + 2] = rHead * Math.sin(phi) * Math.sin(theta) * 0.88;
      } else {
        // Shoulders / Torso
        targetSilhouette[i3] = (Math.random() - 0.5) * 9.0;
        targetSilhouette[i3 + 1] = -2.6 - Math.random() * 3.8;
        targetSilhouette[i3 + 2] = (Math.random() - 0.5) * 3.0;
      }

      // State 03: Document Evidence Decomposition Cloud (Volumetric sheet)
      const sheetX = (Math.random() - 0.5) * 7.5;
      const sheetY = (Math.random() - 0.5) * 5.5;
      const sheetZ = (Math.random() - 0.5) * 1.5;
      targetDocument[i3] = sheetX;
      targetDocument[i3 + 1] = sheetY;
      targetDocument[i3 + 2] = sheetZ;

      // State 04: Vertical Data Portal Columns
      const colIdx = i % 4;
      targetPortal[i3] = (colIdx - 1.5) * 2.8 + (Math.random() - 0.5) * 0.6;
      targetPortal[i3 + 1] = (Math.random() - 0.5) * 12.0;
      targetPortal[i3 + 2] = (Math.random() - 0.5) * 1.2;

      // State 05: Liveness Volumetric Scan Mesh
      targetLiveness[i3] = targetSilhouette[i3] * 1.12 + (Math.random() - 0.5) * 0.15;
      targetLiveness[i3 + 1] = targetSilhouette[i3 + 1] * 1.12;
      targetLiveness[i3 + 2] = targetSilhouette[i3 + 2] * 1.12;

      // Palette: 88% white/dim, 12% electric blue
      const isElectricBlue = i % 7 === 0;
      const c = isElectricBlue ? colorBlue : (i % 3 === 0 ? colorDim : colorWhite);
      colors[i3] = c.r;
      colors[i3 + 1] = c.g;
      colors[i3 + 2] = c.b;
    }

    geometry.setAttribute("position", new THREE.BufferAttribute(currentPositions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));

    const particleMaterial = new THREE.PointsMaterial({
      size: isMobile ? 0.065 : 0.052,
      vertexColors: true,
      transparent: true,
      opacity: 0.88,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const particleSystem = new THREE.Points(geometry, particleMaterial);
    scene.add(particleSystem);

    // ── 3. Horizontal & Vertical Blue Scanning Lasers ──────────────────────────
    const scanGeo = new THREE.BufferGeometry();
    const scanPos = new Float32Array([-5, 0, 0, 5, 0, 0]);
    scanGeo.setAttribute("position", new THREE.BufferAttribute(scanPos, 3));
    const scanMat = new THREE.LineBasicMaterial({
      color: 0x3b82f6,
      transparent: true,
      opacity: 0.0,
    });
    const laserBeam = new THREE.Line(scanGeo, scanMat);
    scene.add(laserBeam);

    // ── 4. Mouse Tracking for Subtle Spatial Disturbance ───────────────────────
    const handleMouseMove = (e: MouseEvent) => {
      mouseRef.current.targetX = (e.clientX / window.innerWidth) * 2 - 1;
      mouseRef.current.targetY = -(e.clientY / window.innerHeight) * 2 + 1;
    };
    window.addEventListener("mousemove", handleMouseMove, { passive: true });

    // ── 5. Main Render Loop ────────────────────────────────────────────────────
    let animId: number;
    const clock = new THREE.Clock();

    const renderFrame = () => {
      animId = requestAnimationFrame(renderFrame);
      const time = clock.getElapsedTime();
      const p = progressRef.current;
      const v = velocityRef.current;

      // Smooth mouse interpolation
      mouseRef.current.x += (mouseRef.current.targetX - mouseRef.current.x) * 0.05;
      mouseRef.current.y += (mouseRef.current.targetY - mouseRef.current.y) * 0.05;

      const posAttr = geometry.attributes.position as THREE.BufferAttribute;
      const posArray = posAttr.array as Float32Array;

      // ── A. Dome Gallery Animation (0.00 – 0.08) ─────────────────────────────
      if (p < 0.08) {
        domeGroup.visible = true;
        domeGroup.rotation.y = time * 0.2 + p * 12;
        const selectedRatio = Math.min(1.0, p / 0.06);
        domeCards[0].scale.set(1.0 + selectedRatio * 1.2, 1.0 + selectedRatio * 1.2, 1.0);
        (domeCards[0].material as THREE.LineBasicMaterial).opacity = 0.9 + selectedRatio * 0.1;
      } else {
        domeGroup.visible = false;
      }

      // ── B. Camera Choreography (Flying INTO Face & Exiting) ──────────────────
      // 0.00 - 0.08: Dome Gallery Overview
      // 0.08 - 0.18: Scene 00 The Signal (Z = 20 -> 16)
      // 0.18 - 0.32: Scene 01 Reconstruction (Z = 16 -> 12)
      // 0.32 - 0.44: Scene 02 Fly Straight INTO Face (Z = 12 -> 0.5 -> -6 through facial void)
      // 0.44 - 0.58: Scene 03 Document Evidence Cloud (Z = 8.5)
      // 0.58 - 0.72: Scene 04 Liveness Portal & Emerging Silhouette (Z = 9.0)
      // 0.72 - 0.84: Scene 05 Verification Stability (Z = 14.0)
      // 0.84 - 1.00: How It Works & CTA (Z = 18.0)

      if (p < 0.08) {
        camera.position.set(0, 0, 20);
      } else if (p < 0.18) {
        const sigP = (p - 0.08) / 0.10;
        camera.position.set(
          mouseRef.current.x * 0.6,
          mouseRef.current.y * 0.6,
          20 - sigP * 4
        );
      } else if (p < 0.32) {
        const recP = (p - 0.18) / 0.14;
        camera.position.set(
          mouseRef.current.x * 0.4,
          mouseRef.current.y * 0.4,
          16 - recP * 4
        );
      } else if (p < 0.44) {
        // Fly straight through the facial plane!
        const faceP = (p - 0.32) / 0.12;
        camera.position.set(0, 0.5 * (1 - faceP), 12 - faceP * 18); // Z moves from 12 -> -6
      } else if (p < 0.58) {
        // Document Evidence Plane
        const docP = (p - 0.44) / 0.14;
        camera.position.set(Math.sin(docP * Math.PI) * 0.5, 0, 8.5);
      } else if (p < 0.72) {
        // Liveness Emergence from Portal
        camera.position.set(0, 0, 9.2);
      } else if (p < 0.84) {
        // Verified Stabilized Shot
        const verP = (p - 0.72) / 0.12;
        camera.position.set(0, 0, 9.2 + verP * 4.8);
      } else {
        camera.position.set(0, 0, 16);
      }

      // ── C. PointCloud Rotation & Scanning Beam ──────────────────────────────
      if (p >= 0.18 && p < 0.32) {
        particleSystem.rotation.y = time * 0.12 + mouseRef.current.x * 0.25;
        particleSystem.rotation.x = mouseRef.current.y * 0.15;
      } else if (p >= 0.32 && p < 0.44) {
        particleSystem.rotation.set(0, 0, 0); // Aligned for flying through
      } else if (p >= 0.58 && p < 0.72) {
        // Liveness Head Movement
        const liveP = (p - 0.58) / 0.14;
        const yaw = Math.sin(liveP * Math.PI * 2) * 0.45;
        particleSystem.rotation.y = THREE.MathUtils.lerp(particleSystem.rotation.y, yaw, 0.1);
        particleSystem.rotation.x = 0;

        // Laser Scan Beam sweeping top to bottom
        scanMat.opacity = 0.75;
        laserBeam.position.y = 2.4 - liveP * 4.8;
        laserBeam.position.z = 1.0;
      } else {
        particleSystem.rotation.y = THREE.MathUtils.lerp(particleSystem.rotation.y, 0, 0.08);
        particleSystem.rotation.x = THREE.MathUtils.lerp(particleSystem.rotation.x, 0, 0.08);
        scanMat.opacity = 0.0;
      }

      // ── D. Continuous Particle Position Interpolation ────────────────────────
      const ease = 0.08;
      for (let i = 0; i < PARTICLE_COUNT; i++) {
        const i3 = i * 3;
        let tx = 0;
        let ty = 0;
        let tz = 0;

        if (p < 0.08) {
          // Dome Gallery points
          tx = targetDome[i3];
          ty = targetDome[i3 + 1];
          tz = targetDome[i3 + 2];
        } else if (p < 0.18) {
          // Scene 00: Volumetric Signal Field + subtle cursor displacement
          const dist = Math.hypot(
            targetSignal[i3] - mouseRef.current.x * 4,
            targetSignal[i3 + 1] - mouseRef.current.y * 4
          );
          const push = Math.max(0, 1.5 - dist * 0.4);
          tx = targetSignal[i3] + push * mouseRef.current.x;
          ty = targetSignal[i3 + 1] + push * mouseRef.current.y;
          tz = targetSignal[i3 + 2];
        } else if (p < 0.32) {
          // Scene 01: Progressive 7-stage Human Reconstruction
          const blend = Math.min(1.0, (p - 0.18) / 0.12);
          tx = THREE.MathUtils.lerp(targetSignal[i3], targetSilhouette[i3], blend);
          ty = THREE.MathUtils.lerp(targetSignal[i3 + 1], targetSilhouette[i3 + 1], blend);
          tz = THREE.MathUtils.lerp(targetSignal[i3 + 2], targetSilhouette[i3 + 2], blend);
        } else if (p < 0.44) {
          // Scene 02: Silhouette expands as camera enters through face
          const enterP = (p - 0.32) / 0.12;
          const expansion = 1.0 + enterP * 1.5;
          tx = targetSilhouette[i3] * expansion;
          ty = targetSilhouette[i3 + 1] * expansion;
          tz = targetSilhouette[i3 + 2];
        } else if (p < 0.58) {
          // Scene 03: Document Evidence Decomposition
          const blend = Math.min(1.0, (p - 0.44) / 0.08);
          tx = THREE.MathUtils.lerp(targetSilhouette[i3], targetDocument[i3], blend);
          ty = THREE.MathUtils.lerp(targetSilhouette[i3 + 1], targetDocument[i3 + 1], blend);
          tz = THREE.MathUtils.lerp(targetSilhouette[i3 + 2], targetDocument[i3 + 2], blend);
        } else if (p < 0.72) {
          // Scene 04: Liveness Portal -> Emerging Silhouette
          const blend = Math.min(1.0, (p - 0.58) / 0.08);
          tx = THREE.MathUtils.lerp(targetPortal[i3], targetLiveness[i3], blend);
          ty = THREE.MathUtils.lerp(targetPortal[i3 + 1], targetLiveness[i3 + 1], blend);
          tz = THREE.MathUtils.lerp(targetPortal[i3 + 2], targetLiveness[i3 + 2], blend);
        } else if (p < 0.84) {
          // Scene 05: Verification Stability
          tx = targetLiveness[i3];
          ty = targetLiveness[i3 + 1];
          tz = targetLiveness[i3 + 2];
        } else {
          // Scene 06 & 07: Settled background
          tx = targetSignal[i3] * 1.2;
          ty = targetSignal[i3 + 1] * 1.2;
          tz = targetSignal[i3 + 2] * 1.2;
        }

        posArray[i3] += (tx - posArray[i3]) * ease;
        posArray[i3 + 1] += (ty - posArray[i3 + 1]) * ease;
        posArray[i3 + 2] += (tz - posArray[i3 + 2]) * ease;
      }

      posAttr.needsUpdate = true;

      // Opacity fade on final sections
      if (p >= 0.84) {
        particleMaterial.opacity = Math.max(0.12, 0.88 - (p - 0.84) * 4);
      } else {
        particleMaterial.opacity = 0.88;
      }

      renderer.render(scene, camera);
    };

    renderFrame();

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

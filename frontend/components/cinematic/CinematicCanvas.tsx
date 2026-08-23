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

  useEffect(() => {
    progressRef.current = scrollProgress;
    velocityRef.current = velocity;
  }, [scrollProgress, velocity]);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    // Check prefers-reduced-motion
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Scene, Camera, Renderer
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000000);

    let width = window.innerWidth;
    let height = window.innerHeight;

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 0, 18);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // ── Particle System (3,600 Points) ─────────────────────────────────────────
    const PARTICLE_COUNT = 3600;
    const geometry = new THREE.BufferGeometry();

    const currentPositions = new Float32Array(PARTICLE_COUNT * 3);
    const targetPositions00 = new Float32Array(PARTICLE_COUNT * 3); // State 00: Dispersed
    const targetPositions01 = new Float32Array(PARTICLE_COUNT * 3); // State 01/02: Head Silhouette
    const targetPositions03 = new Float32Array(PARTICLE_COUNT * 3); // State 03: Document Slab
    const targetPositions05 = new Float32Array(PARTICLE_COUNT * 3); // State 05: Dense Biometrics
    const colors = new Float32Array(PARTICLE_COUNT * 3);
    const opacities = new Float32Array(PARTICLE_COUNT);

    const colorWhite = new THREE.Color(0xffffff);
    const colorBlue = new THREE.Color(0x3b82f6);
    const colorDim = new THREE.Color(0x52525b);

    // 1. Generate Targets
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const i3 = i * 3;

      // State 00: Dispersed Volume
      const r0 = 8 + Math.random() * 14;
      const theta0 = Math.random() * Math.PI * 2;
      const phi0 = Math.acos(Math.random() * 2 - 1);
      targetPositions00[i3] = r0 * Math.sin(phi0) * Math.cos(theta0);
      targetPositions00[i3 + 1] = r0 * Math.sin(phi0) * Math.sin(theta0);
      targetPositions00[i3 + 2] = r0 * Math.cos(phi0) - 5;

      // Initial positions start at State 00
      currentPositions[i3] = targetPositions00[i3];
      currentPositions[i3 + 1] = targetPositions00[i3 + 1];
      currentPositions[i3 + 2] = targetPositions00[i3 + 2];

      // State 01 / 02: Head Silhouette + Shoulders
      if (i < PARTICLE_COUNT * 0.65) {
        // Head ellipsoid
        const u = Math.random();
        const v = Math.random();
        const t = u * 2 * Math.PI;
        const p = Math.acos(2 * v - 1);
        const rHead = 2.4 + (Math.sin(t * 3) * 0.1);
        targetPositions01[i3] = rHead * Math.sin(p) * Math.cos(t) * 0.85;
        targetPositions01[i3 + 1] = rHead * Math.cos(p) * 1.15 + 0.4;
        targetPositions01[i3 + 2] = rHead * Math.sin(p) * Math.sin(t) * 0.85;
      } else {
        // Shoulders / Torso
        const sx = (Math.random() - 0.5) * 8.5;
        const sy = -2.5 - Math.random() * 3.5;
        const sz = (Math.random() - 0.5) * 2.5;
        targetPositions01[i3] = sx;
        targetPositions01[i3 + 1] = sy;
        targetPositions01[i3 + 2] = sz;
      }

      // State 03: 3D Identity Document Rectangular Slab
      const gridW = 60;
      const gridH = 60;
      const gx = (i % gridW) - gridW / 2;
      const gy = Math.floor(i / gridW) - gridH / 2;
      targetPositions03[i3] = (gx / gridW) * 7.5;
      targetPositions03[i3 + 1] = (gy / gridH) * 5.0;
      targetPositions03[i3 + 2] = (Math.random() - 0.5) * 0.2;

      // State 05: Volumetric Biometric Mesh
      targetPositions05[i3] = targetPositions01[i3] * 1.15 + (Math.random() - 0.5) * 0.15;
      targetPositions05[i3 + 1] = targetPositions01[i3 + 1] * 1.15;
      targetPositions05[i3 + 2] = targetPositions01[i3 + 2] * 1.15;

      // Colors: Overwhelmingly white/dim with restrained 12% electric blue points
      const isBlue = i % 8 === 0;
      const c = isBlue ? colorBlue : (i % 3 === 0 ? colorDim : colorWhite);
      colors[i3] = c.r;
      colors[i3 + 1] = c.g;
      colors[i3 + 2] = c.b;

      opacities[i] = Math.random() * 0.7 + 0.3;
    }

    geometry.setAttribute("position", new THREE.BufferAttribute(currentPositions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));

    // Particle Material
    const material = new THREE.PointsMaterial({
      size: 0.055,
      vertexColors: true,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const pointCloud = new THREE.Points(geometry, material);
    scene.add(pointCloud);

    // ── 3D Laser Scanning Beam (Act 03 Document & Act 05 Liveness) ─────────────
    const scanLineGeo = new THREE.BufferGeometry();
    const scanLinePos = new Float32Array([ -5, 0, 0,  5, 0, 0 ]);
    scanLineGeo.setAttribute("position", new THREE.BufferAttribute(scanLinePos, 3));
    const scanLineMat = new THREE.LineBasicMaterial({
      color: 0x3b82f6,
      transparent: true,
      opacity: 0.0,
      linewidth: 2,
    });
    const scanLine = new THREE.Line(scanLineGeo, scanLineMat);
    scene.add(scanLine);

    // ── Central Convergence Point (Act 06 / 07) ───────────────────────────────
    const singlePointGeo = new THREE.SphereGeometry(0.06, 16, 16);
    const singlePointMat = new THREE.MeshBasicMaterial({
      color: 0x3b82f6,
      transparent: true,
      opacity: 0.0,
    });
    const convergenceCore = new THREE.Mesh(singlePointGeo, singlePointMat);
    scene.add(convergenceCore);

    // ── Render & Physics Loop ──────────────────────────────────────────────────
    let animId: number;
    let clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const delta = clock.getDelta();
      const time = clock.getElapsedTime();

      const p = prefersReducedMotion ? 0.5 : progressRef.current;
      const v = velocityRef.current;

      const posAttr = geometry.attributes.position as THREE.BufferAttribute;
      const posArray = posAttr.array as Float32Array;

      // ── Spatial Camera & Particle Choreography Across 8 Master Acts ──────────
      // Act 00 (0.00 -> 0.10): Wide shot, slow push
      // Act 01 (0.10 -> 0.22): Medium shot, silhouette emerges
      // Act 02 (0.22 -> 0.34): Orbiting data connections
      // Act 03 (0.34 -> 0.47): Macro push into document plane
      // Act 04 (0.47 -> 0.58): Document layer fracture & push through
      // Act 05 (0.58 -> 0.74): Close portrait, yaw turn
      // Act 06 (0.74 -> 0.88): Convergence to singular point
      // Act 07 (0.88 -> 1.00): Scene dissolves into final product interface

      // Camera Positioning
      if (p < 0.10) {
        camera.position.z = 22 - p * 40;
        camera.position.x = 0;
        camera.position.y = 0;
      } else if (p < 0.34) {
        camera.position.z = 18 - (p - 0.10) * 15;
        camera.position.x = Math.sin(time * 0.2) * 0.3;
        camera.position.y = 0;
      } else if (p < 0.47) {
        // Document: Macro Close-up
        const docP = (p - 0.34) / 0.13;
        camera.position.z = 14 - docP * 4;
        camera.position.x = Math.sin(docP * Math.PI) * 0.8;
      } else if (p < 0.58) {
        // Fracture & push through
        const fracP = (p - 0.47) / 0.11;
        camera.position.z = 10 - fracP * 3;
      } else if (p < 0.74) {
        // Liveness Close Portrait
        camera.position.z = 8.5;
        camera.position.x = 0;
      } else if (p < 0.88) {
        // Convergence Wide
        const convP = (p - 0.74) / 0.14;
        camera.position.z = 8.5 + convP * 8;
      } else {
        // Verify Scene fades out
        camera.position.z = 16.5;
      }

      // PointCloud Rotation (Yaw / Pitch)
      if (p < 0.34) {
        pointCloud.rotation.y = time * 0.15 + v * 0.002;
        pointCloud.rotation.x = Math.sin(time * 0.2) * 0.05;
        pointCloud.rotation.z = 0;
      } else if (p < 0.47) {
        // Document 3D Isometric Tilt
        const docTilt = (p - 0.34) / 0.13;
        pointCloud.rotation.y = THREE.MathUtils.lerp(pointCloud.rotation.y, 0.45 - docTilt * 0.2, 0.1);
        pointCloud.rotation.x = THREE.MathUtils.lerp(pointCloud.rotation.x, -0.3 + docTilt * 0.15, 0.1);
      } else if (p < 0.58) {
        pointCloud.rotation.y = THREE.MathUtils.lerp(pointCloud.rotation.y, 0, 0.1);
        pointCloud.rotation.x = THREE.MathUtils.lerp(pointCloud.rotation.x, 0, 0.1);
      } else if (p < 0.74) {
        // Dynamic Head Turn (Front -> Left -> Right -> Front)
        const liveP = (p - 0.58) / 0.16;
        const liveYaw = Math.sin(liveP * Math.PI * 2) * 0.55;
        const livePitch = Math.cos(liveP * Math.PI * 2) * 0.15;
        pointCloud.rotation.y = THREE.MathUtils.lerp(pointCloud.rotation.y, liveYaw, 0.12);
        pointCloud.rotation.x = THREE.MathUtils.lerp(pointCloud.rotation.x, livePitch, 0.12);
      } else if (p < 0.88) {
        pointCloud.rotation.y += 0.03;
      } else {
        pointCloud.rotation.y = 0;
      }

      // Laser Scan Line behavior
      if (p >= 0.34 && p < 0.47) {
        scanLineMat.opacity = 0.8;
        const docScanP = (p - 0.34) / 0.13;
        scanLine.position.y = 2.5 - (docScanP * 5.0);
        scanLine.position.z = 0.2;
        scanLine.rotation.copy(pointCloud.rotation);
      } else if (p >= 0.58 && p < 0.74) {
        scanLineMat.opacity = 0.65;
        scanLine.position.y = Math.sin(time * 3) * 2.2 + 0.4;
        scanLine.position.z = 1.0;
        scanLine.rotation.set(0, 0, 0);
      } else {
        scanLineMat.opacity = 0.0;
      }

      // Convergence Core behavior (Act 06 & 07)
      if (p >= 0.74 && p < 0.90) {
        const convP = (p - 0.74) / 0.16;
        singlePointMat.opacity = Math.min(1.0, convP * 2.5);
        const scale = 0.5 + Math.sin(time * 6) * 0.15;
        convergenceCore.scale.set(scale, scale, scale);
      } else {
        singlePointMat.opacity = 0.0;
      }

      // Particle Position Interpolation
      const ease = 0.075;
      for (let i = 0; i < PARTICLE_COUNT; i++) {
        const i3 = i * 3;
        let tx = 0;
        let ty = 0;
        let tz = 0;

        if (p < 0.10) {
          // Act 00: Dispersed
          tx = targetPositions00[i3];
          ty = targetPositions00[i3 + 1];
          tz = targetPositions00[i3 + 2];
        } else if (p < 0.34) {
          // Act 01 & 02: Head Silhouette
          const blend = Math.min(1.0, (p - 0.10) / 0.12);
          tx = THREE.MathUtils.lerp(targetPositions00[i3], targetPositions01[i3], blend);
          ty = THREE.MathUtils.lerp(targetPositions00[i3 + 1], targetPositions01[i3 + 1], blend);
          tz = THREE.MathUtils.lerp(targetPositions00[i3 + 2], targetPositions01[i3 + 2], blend);
        } else if (p < 0.47) {
          // Act 03: Document
          const blend = Math.min(1.0, (p - 0.34) / 0.08);
          tx = THREE.MathUtils.lerp(targetPositions01[i3], targetPositions03[i3], blend);
          ty = THREE.MathUtils.lerp(targetPositions01[i3 + 1], targetPositions03[i3 + 1], blend);
          tz = THREE.MathUtils.lerp(targetPositions01[i3 + 2], targetPositions03[i3 + 2], blend);
        } else if (p < 0.58) {
          // Act 04: Layer Fracture
          const frac = (p - 0.47) / 0.11;
          const layerOffset = (i % 4) * 0.6 * frac;
          tx = targetPositions03[i3] * (1.0 + frac * 0.4);
          ty = targetPositions03[i3 + 1] * (1.0 + frac * 0.4);
          tz = targetPositions03[i3 + 2] + layerOffset;
        } else if (p < 0.74) {
          // Act 05: Biometric Mesh
          const blend = Math.min(1.0, (p - 0.58) / 0.08);
          tx = THREE.MathUtils.lerp(targetPositions03[i3], targetPositions05[i3], blend);
          ty = THREE.MathUtils.lerp(targetPositions03[i3 + 1], targetPositions05[i3 + 1], blend);
          tz = THREE.MathUtils.lerp(targetPositions03[i3 + 2], targetPositions05[i3 + 2], blend);
        } else if (p < 0.88) {
          // Act 06: Convergence into Center Point
          const conv = (p - 0.74) / 0.14;
          const radius = (1.0 - conv) * 3.5;
          tx = Math.sin(i * 0.3 + time * 2) * radius;
          ty = Math.cos(i * 0.3 + time * 2) * radius;
          tz = Math.sin(i * 0.5 + time * 2) * radius;
        } else {
          // Act 07: Vanish / Disperse gently in background
          tx = targetPositions00[i3] * 1.5;
          ty = targetPositions00[i3 + 1] * 1.5;
          tz = targetPositions00[i3 + 2] * 1.5;
        }

        posArray[i3] += (tx - posArray[i3]) * ease;
        posArray[i3 + 1] += (ty - posArray[i3 + 1]) * ease;
        posArray[i3 + 2] += (tz - posArray[i3 + 2]) * ease;
      }

      posAttr.needsUpdate = true;

      // Global particle opacity fadeout on final CTA act
      if (p >= 0.88) {
        material.opacity = Math.max(0.08, 1.0 - (p - 0.88) / 0.12);
      } else {
        material.opacity = 0.85;
      }

      renderer.render(scene, camera);
    };

    animate();

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
      window.removeEventListener("resize", handleResize);
      renderer.dispose();
      geometry.dispose();
      material.dispose();
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

'use client';

import { useEffect, useRef } from 'react';
import * as THREE from 'three';

export default function DNAHelix({ className }: { className?: string }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const W = container.clientWidth;
    const H = container.clientHeight;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    container.appendChild(renderer.domElement);

    const scene  = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(52, W / H, 0.1, 100);
    camera.position.set(0, 0, 10);

    const matCyan = new THREE.MeshStandardMaterial({
      color:             new THREE.Color('#00F5D4'),
      emissive:          new THREE.Color('#00F5D4'),
      emissiveIntensity: 0.25,
      roughness:         0.3,
      metalness:         0.6,
      transparent:       true,
      opacity:           0.30,
    });
    const matPurple = new THREE.MeshStandardMaterial({
      color:             new THREE.Color('#8B5CF6'),
      emissive:          new THREE.Color('#8B5CF6'),
      emissiveIntensity: 0.25,
      roughness:         0.3,
      metalness:         0.6,
      transparent:       true,
      opacity:           0.30,
    });
    const matAmber = new THREE.MeshStandardMaterial({
      color:             new THREE.Color('#F59E0B'),
      emissive:          new THREE.Color('#F59E0B'),
      emissiveIntensity: 0.15,
      roughness:         0.5,
      metalness:         0.3,
      transparent:       true,
      opacity:           0.40,
    });

    const group = new THREE.Group();
    const TURNS    = 2.5;
    const HEIGHT   = 7.5;
    const RADIUS   = 1.2;
    const SEGMENTS = 140;
    const N_PAIRS  = 20;

    const pts1: THREE.Vector3[] = [];
    const pts2: THREE.Vector3[] = [];
    for (let i = 0; i <= SEGMENTS; i++) {
      const frac  = i / SEGMENTS;
      const theta = frac * TURNS * Math.PI * 2;
      const y     = frac * HEIGHT - HEIGHT / 2;
      pts1.push(new THREE.Vector3(Math.cos(theta) * RADIUS, y, Math.sin(theta) * RADIUS));
      pts2.push(new THREE.Vector3(Math.cos(theta + Math.PI) * RADIUS, y, Math.sin(theta + Math.PI) * RADIUS));
    }

    const curve1 = new THREE.CatmullRomCurve3(pts1);
    const curve2 = new THREE.CatmullRomCurve3(pts2);
    group.add(new THREE.Mesh(new THREE.TubeGeometry(curve1, SEGMENTS, 0.052, 12, false), matCyan));
    group.add(new THREE.Mesh(new THREE.TubeGeometry(curve2, SEGMENTS, 0.052, 12, false), matPurple));

    const sphereGeo = new THREE.SphereGeometry(0.10, 20, 20);
    const yAxis     = new THREE.Vector3(0, 1, 0);

    for (let i = 0; i < N_PAIRS; i++) {
      const idx = Math.round((i / N_PAIRS) * SEGMENTS);
      const p1  = pts1[idx].clone();
      const p2  = pts2[idx].clone();
      const dir = new THREE.Vector3().subVectors(p2, p1);
      const len = dir.length();
      const mid = new THREE.Vector3().addVectors(p1, p2).multiplyScalar(0.5);

      const cylGeo = new THREE.CylinderGeometry(0.026, 0.026, len, 8);
      const conn   = new THREE.Mesh(cylGeo, matAmber);
      conn.position.copy(mid);
      conn.quaternion.setFromUnitVectors(yAxis, dir.normalize());
      group.add(conn);

      const s1 = new THREE.Mesh(sphereGeo, matCyan.clone());
      s1.position.copy(p1);
      const s2 = new THREE.Mesh(sphereGeo, matPurple.clone());
      s2.position.copy(p2);
      group.add(s1, s2);
    }

    scene.add(group);

    const P_COUNT = 320;
    const pPositions = new Float32Array(P_COUNT * 3);
    const pColors    = new Float32Array(P_COUNT * 3);
    const cCyan   = new THREE.Color('#00F5D4');
    const cPurple = new THREE.Color('#8B5CF6');

    for (let i = 0; i < P_COUNT; i++) {
      pPositions[i * 3]     = (Math.random() - 0.5) * 24;
      pPositions[i * 3 + 1] = (Math.random() - 0.5) * 18;
      pPositions[i * 3 + 2] = (Math.random() - 0.5) * 12 - 4;
      const c = Math.random() > 0.55 ? cCyan : cPurple;
      pColors[i * 3]     = c.r;
      pColors[i * 3 + 1] = c.g;
      pColors[i * 3 + 2] = c.b;
    }

    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute('position', new THREE.BufferAttribute(pPositions, 3));
    pGeo.setAttribute('color', new THREE.BufferAttribute(pColors, 3));
    const pMat = new THREE.PointsMaterial({
      size: 0.04,
      vertexColors: true,
      transparent: true,
      opacity: 0.20,
      sizeAttenuation: true,
    });
    const particles = new THREE.Points(pGeo, pMat);
    scene.add(particles);

    scene.add(new THREE.AmbientLight(0xffffff, 0.2));

    const l1 = new THREE.PointLight('#00F5D4', 1.2, 25);
    l1.position.set(4, 4, 5);
    scene.add(l1);

    const l2 = new THREE.PointLight('#8B5CF6', 1.2, 25);
    l2.position.set(-4, -4, 5);
    scene.add(l2);

    const l3 = new THREE.PointLight('#F59E0B', 0.6, 18);
    l3.position.set(0, 0, 7);
    scene.add(l3);

    let targetMX = 0;
    let targetMY = 0;
    let currentMX = 0;
    let currentMY = 0;

    const onMouseMove = (e: MouseEvent) => {
      targetMX = (e.clientX / window.innerWidth - 0.5) * 2;
      targetMY = (e.clientY / window.innerHeight - 0.5) * 2;
    };
    window.addEventListener('mousemove', onMouseMove);

    const clock = new THREE.Clock();
    let rafId: number;

    const animate = () => {
      rafId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      currentMX += (targetMX - currentMX) * 0.04;
      currentMY += (targetMY - currentMY) * 0.04;

      group.rotation.y = elapsed * 0.22 + currentMX * 0.35;
      group.rotation.x = currentMY * 0.08;
      group.position.y = Math.sin(elapsed * 0.38) * 0.14;

      const pos = pGeo.attributes.position.array as Float32Array;
      for (let i = 0; i < P_COUNT; i++) {
        pos[i * 3 + 1] += 0.006;
        if (pos[i * 3 + 1] > 9) pos[i * 3 + 1] = -9;
      }
      pGeo.attributes.position.needsUpdate = true;
      particles.rotation.y = elapsed * 0.03;

      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      const nw = container.clientWidth;
      const nh = container.clientHeight;
      camera.aspect = nw / nh;
      camera.updateProjectionMatrix();
      renderer.setSize(nw, nh);
    };
    window.addEventListener('resize', onResize);

    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('resize', onResize);
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  return <div ref={containerRef} className={className ?? 'w-full h-full'} />;
}

'use client';

import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { useTheme } from '@/contexts/theme';

/**
 * Binary DNA helix — the two backbone strands are threaded with 0/1 glyphs
 * (billboard sprites from a canvas texture) that tick like a living data
 * stream. Slow rotation, a gentle bob, pointer parallax and ambient particle
 * dust keep it alive without shouting. Reduced motion renders a static frame
 * (apple-design §14). Colors follow the bioluminescent green + violet
 * instrument in globals.css.
 */
export default function DNAHelix({ className }: { className?: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const isLight = theme === 'light';

    const digitA   = isLight ? '#15803D' : '#4ADE80';
    const digitB   = isLight ? '#5B21B6' : '#A78BFA';
    const strandA  = isLight ? '#15803D' : '#22C55E';
    const strandB  = isLight ? '#5B21B6' : '#7C6CF2';
    const rung     = isLight ? '#059669' : '#2FBF6E';
    const particle = isLight ? '#15803D' : '#4ADE80';
    const additive = !isLight;

    const W = container.clientWidth || 1;
    const H = container.clientHeight || 1;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, W / H, 0.1, 100);
    camera.position.set(0, 0, 9);

    const group = new THREE.Group();
    scene.add(group);

    const TURNS = 2.2;
    const HEIGHT = 7.4;
    const RADIUS = 1.35;
    const N_RUNG = 15;
    const N_DIGITS = 44;

    const helix = (offset: number) => {
      const pts: THREE.Vector3[] = [];
      const steps = 160;
      for (let i = 0; i <= steps; i++) {
        const frac = i / steps;
        const theta = frac * TURNS * Math.PI * 2 + offset;
        const y = frac * HEIGHT - HEIGHT / 2;
        pts.push(new THREE.Vector3(Math.cos(theta) * RADIUS, y, Math.sin(theta) * RADIUS));
      }
      return new THREE.CatmullRomCurve3(pts);
    };

    const curveA = helix(0);
    const curveB = helix(Math.PI);

    const tubeMat = new THREE.MeshBasicMaterial({
      color: strandA,
      transparent: true,
      opacity: isLight ? 0.28 : 0.16,
      depthWrite: false,
    });
    group.add(new THREE.Mesh(new THREE.TubeGeometry(curveA, 120, 0.032, 4, false), tubeMat));

    const tubeMatB = new THREE.MeshBasicMaterial({
      color: strandB,
      transparent: true,
      opacity: isLight ? 0.22 : 0.12,
      depthWrite: false,
    });
    group.add(new THREE.Mesh(new THREE.TubeGeometry(curveB, 120, 0.032, 4, false), tubeMatB));

    const rungMat = new THREE.MeshBasicMaterial({
      color: rung,
      transparent: true,
      opacity: isLight ? 0.22 : 0.11,
      depthWrite: false,
    });
    const rungGeom = new THREE.CylinderGeometry(0.014, 0.014, 1, 4);
    rungGeom.translate(0, 0.5, 0);
    for (let i = 0; i < N_RUNG; i++) {
      const t = i / (N_RUNG - 1);
      const p1 = curveA.getPointAt(t);
      const p2 = curveB.getPointAt(t);
      const dir = p2.clone().sub(p1);
      const mesh = new THREE.Mesh(rungGeom, rungMat);
      mesh.position.copy(p1);
      mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
      mesh.scale.set(1, dir.length(), 1);
      group.add(mesh);
    }

    const makeGlyph = (char: string, color: string) => {
      const size = 96;
      const cv = document.createElement('canvas');
      cv.width = size;
      cv.height = size;
      const ctx = cv.getContext('2d');
      if (ctx) {
        ctx.clearRect(0, 0, size, size);
        ctx.font = `600 ${Math.round(size * 0.72)}px "Geist Mono", ui-monospace, SFMono-Regular, Menlo, monospace`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = color;
        ctx.fillText(char, size / 2, size / 2 + size * 0.04);
      }
      return new THREE.CanvasTexture(cv);
    };

    const mkSpriteMat = (tex: THREE.Texture, opacity: number) =>
      new THREE.SpriteMaterial({
        map: tex,
        transparent: true,
        depthWrite: false,
        opacity,
        blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
      });

    const texA0 = makeGlyph('0', digitA);
    const texA1 = makeGlyph('1', digitA);
    const texB0 = makeGlyph('0', digitB);
    const texB1 = makeGlyph('1', digitB);
    const matsA = [mkSpriteMat(texA0, isLight ? 0.95 : 0.9), mkSpriteMat(texA1, isLight ? 0.95 : 0.9)];
    const matsB = [mkSpriteMat(texB0, isLight ? 0.9 : 0.72), mkSpriteMat(texB1, isLight ? 0.9 : 0.72)];

    type Glyph = {
      sprite: THREE.Sprite;
      mats: THREE.SpriteMaterial[];
      base: number;
      curve: THREE.CatmullRomCurve3;
      rate: number;
      index: number;
    };
    const glyphs: Glyph[] = [];

    const spawnGlyphs = (curve: THREE.CatmullRomCurve3, mats: THREE.SpriteMaterial[], rateBase: number) => {
      for (let i = 0; i < N_DIGITS; i++) {
        const sprite = new THREE.Sprite(mats[i % 2]);
        sprite.scale.setScalar(0.36);
        group.add(sprite);
        glyphs.push({
          sprite,
          mats,
          base: i / N_DIGITS,
          curve,
          rate: rateBase + (i % 7) * 0.06,
          index: i,
        });
      }
    };
    spawnGlyphs(curveA, matsA, 1.4);
    spawnGlyphs(curveB, matsB, 0.9);

    const particleCount = 150;
    const particlePos = new Float32Array(particleCount * 3);
    const particleSpeed: number[] = [];
    for (let i = 0; i < particleCount; i++) {
      particlePos[i * 3] = (Math.random() - 0.5) * 14;
      particlePos[i * 3 + 1] = (Math.random() - 0.5) * 10;
      particlePos[i * 3 + 2] = (Math.random() - 0.5) * 8;
      particleSpeed.push(0.05 + Math.random() * 0.2);
    }
    const particleGeom = new THREE.BufferGeometry();
    particleGeom.setAttribute('position', new THREE.BufferAttribute(particlePos, 3));
    const particleMat = new THREE.PointsMaterial({
      color: particle,
      size: 0.045,
      transparent: true,
      opacity: isLight ? 0.28 : 0.2,
      depthWrite: false,
      sizeAttenuation: true,
      blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
    });
    const particles = new THREE.Points(particleGeom, particleMat);
    group.add(particles);

    let targetRotX = 0;
    let targetRotY = 0;
    const onPointerMove = (e: PointerEvent) => {
      const nx = (e.clientX / window.innerWidth) * 2 - 1;
      const ny = (e.clientY / window.innerHeight) * 2 - 1;
      targetRotY = nx * 0.24;
      targetRotX = ny * 0.14;
    };
    window.addEventListener('pointermove', onPointerMove);

    let lastW = W;
    let lastH = H;
    const resize = () => {
      const w = container.clientWidth || 1;
      const h = container.clientHeight || 1;
      if (w === lastW && h === lastH) return;
      lastW = w;
      lastH = h;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.render(scene, camera);
    };
    const ro = new ResizeObserver(resize);
    ro.observe(container);

    const placeGlyph = (g: Glyph, t: number, bit: number) => {
      g.sprite.position.copy(g.curve.getPointAt(t));
      g.sprite.material = g.mats[bit % 2];
    };

    let raf = 0;
    let elapsed = 0;
    const clock = new THREE.Clock();

    const render = () => {
      renderer.render(scene, camera);
      if (!reducedMotion) raf = requestAnimationFrame(tick);
    };

    const tick = () => {
      const dt = Math.min(clock.getDelta(), 0.05);
      elapsed += dt;

      group.rotation.y = elapsed * 0.22 + targetRotY * 0.35;
      group.rotation.x = THREE.MathUtils.lerp(group.rotation.x, targetRotX, dt * 2.5);
      group.position.y = Math.sin(elapsed * 0.5) * 0.12;

      for (const g of glyphs) {
        const flow = (elapsed * g.rate * 0.035) % 1;
        const bit = (g.index + Math.floor(elapsed * g.rate)) % 2;
        placeGlyph(g, (g.base + flow) % 1, bit);
      }

      const posArr = particleGeom.attributes.position.array as Float32Array;
      for (let i = 0; i < particleCount; i++) {
        posArr[i * 3 + 1] += particleSpeed[i] * dt;
        if (posArr[i * 3 + 1] > 5.2) posArr[i * 3 + 1] = -5.2;
      }
      (particleGeom.attributes.position as THREE.BufferAttribute).needsUpdate = true;

      render();
    };

    if (reducedMotion) {
      for (const g of glyphs) placeGlyph(g, g.base, g.index % 2);
      group.rotation.y = 0.5;
      render();
    } else {
      raf = requestAnimationFrame(tick);
    }

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('pointermove', onPointerMove);
      ro.disconnect();
      renderer.dispose();
      particleGeom.dispose();
      particleMat.dispose();
      tubeMat.dispose();
      tubeMatB.dispose();
      rungMat.dispose();
      rungGeom.dispose();
      [texA0, texA1, texB0, texB1].forEach((t) => t.dispose());
      if (renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [theme]);

  return (
    <div ref={containerRef} className={className} aria-hidden aria-label="Animated double helix made of binary digits" />
  );
}

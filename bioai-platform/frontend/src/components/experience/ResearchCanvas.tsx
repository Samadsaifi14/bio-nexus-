'use client';

import { useEffect, useRef } from 'react';
import type { MutableRefObject } from 'react';

export type SceneControl = { setProgress: (progress: number) => void };

export default function ResearchCanvas({ controller, progressRef }: {
  controller: MutableRefObject<SceneControl | null>; progressRef: MutableRefObject<number>;
}) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    let stopped = false;
    let dispose: (() => void) | undefined;
    const media = window.matchMedia('(min-width: 768px) and (prefers-reduced-motion: no-preference)');
    let generation = 0;
    const start = async () => {
      const current = ++generation;
      dispose?.(); dispose = undefined; controller.current = null;
      if (!media.matches || stopped) return;
      const [THREE, factory] = await Promise.all([import('three'), import('@/lib/experience/scene')]);
      if (stopped || current !== generation) return;
      let renderer;
      try { renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'low-power' }); }
      catch { return; } // The static poster remains visible without WebGL.
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
      renderer.setClearColor(0x000000, 0);
      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(36, 1, .1, 50);
      camera.position.set(0, 0, 10.8);
      const { root, chapters } = factory.createResearchScene();
      scene.add(root, new THREE.HemisphereLight(0xffffff, 0x75938b, 2.6));
      const key = new THREE.DirectionalLight(0xffffff, 3.5); key.position.set(-3, 5, 6); scene.add(key);
      const rim = new THREE.DirectionalLight(0xe7fff5, 2); rim.position.set(4, -1, -3); scene.add(rim);
      let progress = progressRef.current;
      let visible = true;
      let raf = 0;
      const render = () => {
        raf = 0;
        if (!visible || document.hidden || stopped) return;
        const chapter = progress * 2;
        chapters.forEach((group, index) => {
          const weight = Math.max(0, 1 - Math.abs(chapter - index));
          group.visible = weight > .001;
          group.scale.setScalar(Math.max(.001, weight));
          group.rotation.y = progress * Math.PI * 1.6 + index * .3;
        });
        root.rotation.x = Math.sin(progress * Math.PI) * .15;
        renderer.render(scene, camera);
      };
      const requestRender = () => { if (!raf) raf = requestAnimationFrame(render); };
      controller.current = { setProgress(value) { progress = Math.max(0, Math.min(1, value)); requestRender(); } };
      const resize = () => {
        const w = element.clientWidth, h = element.clientHeight;
        if (!w || !h) return;
        renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix(); requestRender();
      };
      element.appendChild(renderer.domElement);
      renderer.domElement.setAttribute('aria-hidden', 'true');
      const observer = new ResizeObserver(resize); observer.observe(element);
      const visibility = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; if (visible) requestRender(); });
      visibility.observe(element);
      const lost = (event: Event) => { event.preventDefault(); element.dataset.ready = 'false'; };
      const restored = () => { element.dataset.ready = 'true'; requestRender(); };
      renderer.domElement.addEventListener('webglcontextlost', lost);
      renderer.domElement.addEventListener('webglcontextrestored', restored);
      document.addEventListener('visibilitychange', requestRender);
      resize(); element.dataset.ready = 'true';
      dispose = () => {
        cancelAnimationFrame(raf); observer.disconnect(); visibility.disconnect();
        document.removeEventListener('visibilitychange', requestRender);
        renderer.domElement.removeEventListener('webglcontextlost', lost);
        renderer.domElement.removeEventListener('webglcontextrestored', restored);
        factory.disposeResearchScene(root); renderer.dispose(); renderer.domElement.remove();
        element.dataset.ready = 'false';
      };
    };
    const run = () => { void start().catch(() => { /* Retain the poster if an optional chunk fails. */ }); };
    run(); media.addEventListener('change', run);
    return () => { stopped = true; generation++; media.removeEventListener('change', run); dispose?.(); controller.current = null; };
  }, [controller, progressRef]);
  return <div ref={host} className="bn-research-canvas" aria-hidden="true" />;
}

'use client';

import { useEffect, useRef } from 'react';
import type { MutableRefObject } from 'react';
import type { SceneControl } from './ResearchCanvas';

/** Activate with a published scene containing Input, Analysis and Evidence groups. */
export default function SplineCanvas({ url, controller, progressRef }: { url: string; controller: MutableRefObject<SceneControl | null>; progressRef: MutableRefObject<number> }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const media = window.matchMedia('(min-width: 768px) and (prefers-reduced-motion: no-preference)');
    let generation = 0;
    let disposed = false;
    let cleanup: (() => void) | undefined;
    const run = async () => {
      const current = ++generation;
      cleanup?.(); controller.current = null; element.dataset.ready = 'false';
      if (!media.matches || disposed) return;
      const { Application } = await import('@splinetool/runtime');
      if (disposed || current !== generation) return;
      const app = new Application(element, { renderMode: 'manual' });
      cleanup = () => app.dispose();
      try {
        await app.load(url);
        if (disposed || current !== generation) { app.dispose(); return; }
        const groups = ['Input', 'Analysis', 'Evidence'].map(name => app.findObjectByName(name));
        if (groups.some(group => !group)) throw new Error('Missing BioNexus scene groups');
        controller.current = { setProgress(progress) {
          const p = Math.max(0, Math.min(1, progress));
          groups.forEach((group, i) => {
            if (!group) return;
            group.position.x = 0;
            const weight = Math.max(.001, 1 - Math.abs(p * 2 - i));
            group.visible = weight > .001;
            group.scale.x = group.scale.y = group.scale.z = weight;
            group.rotation.y = p * Math.PI * 1.6 + i * .3;
          });
          if (!document.hidden) app.requestRender();
        } };
        controller.current.setProgress(progressRef.current); element.dataset.ready = 'true';
      } catch { app.dispose(); } // Visible static asset remains available.
    };
    const start = () => { void run().catch(() => {}); };
    start(); media.addEventListener('change', start);
    return () => { disposed = true; generation++; media.removeEventListener('change', start); cleanup?.(); controller.current = null; };
  }, [url, controller, progressRef]);
  return <canvas ref={canvas} className="bn-spline-canvas" aria-hidden="true" />;
}

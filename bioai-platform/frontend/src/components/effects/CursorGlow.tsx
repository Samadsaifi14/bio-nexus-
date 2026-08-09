'use client';

import { useEffect, useState } from 'react';
import { motion, useReducedMotion, useSpring } from 'framer-motion';

/**
 * A soft radial glow that trails the cursor with spring physics.
 * Rendered only on fine pointers and never for users who prefer reduced motion.
 * Purely decorative — pointer-events-none and aria-hidden.
 */
export function CursorGlow() {
  const reduceMotion = useReducedMotion();
  const [enabled, setEnabled] = useState(false);
  const [visible, setVisible] = useState(false);
  const x = useSpring(0, { stiffness: 60, damping: 20, mass: 0.6 });
  const y = useSpring(0, { stiffness: 60, damping: 20, mass: 0.6 });

  useEffect(() => {
    if (reduceMotion) return;
    const fine = window.matchMedia('(pointer: fine)').matches;
    if (!fine) return;
    setEnabled(true);

    const SIZE = 480;
    const HALF = SIZE / 2;
    const move = (e: MouseEvent) => {
      x.set(e.clientX - HALF);
      y.set(e.clientY - HALF);
      setVisible(true);
    };
    const leave = () => setVisible(false);
    window.addEventListener('mousemove', move);
    document.documentElement.addEventListener('mouseleave', leave);
    return () => {
      window.removeEventListener('mousemove', move);
      document.documentElement.removeEventListener('mouseleave', leave);
    };
  }, [reduceMotion, x, y]);

  if (!enabled) return null;

  return (
    <motion.div
      aria-hidden
      className="pointer-events-none fixed left-0 top-0 z-[60] h-[480px] w-[480px] rounded-full"
      style={{
        x,
        y,
        background: 'var(--cursor-glow)',
        opacity: visible ? 1 : 0,
        transition: 'opacity 400ms ease-out',
      }}
    />
  );
}

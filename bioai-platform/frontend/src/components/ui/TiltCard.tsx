'use client';

import { useRef, useState } from 'react';
import { useReducedMotion } from 'framer-motion';

interface TiltCardProps {
  children: React.ReactNode;
  className?: string;
  maxTilt?: number;
}

/**
 * Cursor-tracking 3D tilt card with a spotlight that follows the pointer.
 * Disabled for users who prefer reduced motion.
 */
export function TiltCard({ children, className = '', maxTilt = 6 }: TiltCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const reduceMotion = useReducedMotion();
  const [style, setStyle] = useState<{ transform?: string; spotlight?: string }>({});

  function handleMove(e: React.MouseEvent<HTMLDivElement>) {
    if (reduceMotion || !ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width;
    const py = (e.clientY - rect.top) / rect.height;
    const rotateY = (px - 0.5) * 2 * maxTilt;
    const rotateX = -(py - 0.5) * 2 * maxTilt;
    setStyle({
      transform: `perspective(900px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg)`,
      spotlight: `radial-gradient(420px circle at ${px * 100}% ${py * 100}%, rgba(45,212,191,0.10), transparent 65%)`,
    });
  }

  function handleLeave() {
    if (reduceMotion) return;
    setStyle({});
  }

  return (
    <div
      ref={ref}
      onMouseMove={handleMove}
      onMouseLeave={handleLeave}
      className={`relative ${className}`}
      style={{ transform: style.transform, transition: 'transform 150ms ease-out' }}
    >
      <div
        className="pointer-events-none absolute inset-0 rounded-2xl"
        style={{ background: style.spotlight, opacity: style.spotlight ? 1 : 0, transition: 'opacity 150ms ease-out' }}
      />
      {children}
    </div>
  );
}

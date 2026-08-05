'use client';

import { useRef } from 'react';
import type { ReactNode } from 'react';
import { motion, useReducedMotion, useScroll, useTransform } from 'framer-motion';

/**
 * Subtle scroll-driven parallax wrapper. `speed` is a positive fraction that
 * controls how far the child drifts relative to scroll (0.1–0.2 feels calm).
 * Disabled for users who prefer reduced motion.
 */
export function Parallax({
  children,
  speed = 0.15,
  className = '',
}: {
  children: ReactNode;
  speed?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const reduceMotion = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'end start'] });
  const y = useTransform(scrollYProgress, [0, 1], [speed * 90, -speed * 90]);

  return (
    <motion.div ref={ref} style={reduceMotion ? undefined : { y }} className={className}>
      {children}
    </motion.div>
  );
}

import type { Variants } from 'framer-motion';

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 24 },
  show:   { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.25, 1, 0.5, 1] as const } },
};

export const stagger: Variants = {
  show: { transition: { staggerChildren: 0.06 } },
};

export const cardHover = { y: -2, transition: { duration: 0.15 } };

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show:   { opacity: 1, transition: { duration: 0.25 } },
};

// ─── Entrance reveal ─────────────────────────────────────────────────────────

export const reveal: Variants = {
  hidden: { opacity: 0, y: 32, filter: 'blur(6px)' },
  show: {
    opacity: 1,
    y: 0,
    filter: 'blur(0px)',
    transition: { duration: 0.5, ease: [0.25, 1, 0.5, 1] as const },
  },
};

export const zoomIn: Variants = {
  hidden: { opacity: 0, scale: 0.96 },
  show:   { opacity: 1, scale: 1, transition: { duration: 0.4, ease: [0.25, 1, 0.5, 1] as const } },
};

export const slideInLeft: Variants = {
  hidden: { opacity: 0, x: -28 },
  show:   { opacity: 1, x: 0, transition: { duration: 0.4, ease: [0.25, 1, 0.5, 1] as const } },
};

export const slideInRight: Variants = {
  hidden: { opacity: 0, x: 28 },
  show:   { opacity: 1, x: 0, transition: { duration: 0.4, ease: [0.25, 1, 0.5, 1] as const } },
};

// ─── Hover / microinteraction presets ────────────────────────────────────────

export const hoverLift = {
  y: -4,
  transition: { duration: 0.2, ease: 'easeOut' as const },
};

export const hoverGlow = {
  y: -3,
  boxShadow: '0 10px 32px rgba(45, 212, 191, 0.14)',
  transition: { duration: 0.2, ease: 'easeOut' as const },
};

export const tapScale = { scale: 0.98 };

export const press = {
  scale: 0.97,
  transition: { duration: 0.1, ease: 'easeOut' as const },
};

export const microPop: Variants = {
  rest: { scale: 1 },
  hover: { scale: 1.03, transition: { type: 'spring', stiffness: 400, damping: 22 } },
  tap: { scale: 0.96 },
};

export const staggerFast: Variants = {
  show: { transition: { staggerChildren: 0.045 } },
};

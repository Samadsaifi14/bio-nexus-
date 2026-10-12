'use client';

import { motion } from 'framer-motion';
import { Dna } from '@phosphor-icons/react';

/**
 * Branded smooth loader — a spinning DNA ring plus a cascade of dots.
 * Use `compact` for inline states (buttons, small cards) and the default
 * size for full-section loading states.
 */
export function SmoothLoader({
  label = 'Loading…',
  compact = false,
}: {
  label?: string;
  compact?: boolean;
}) {
  return (
    <div
      role="status"
      aria-label={label}
      className={`flex flex-col items-center justify-center ${compact ? 'gap-2' : 'gap-4 py-12'}`}
    >
      <div className={`relative ${compact ? 'w-9 h-9' : 'w-14 h-14'}`}>
        <span className="absolute inset-0 rounded-full border border-accent-cyan/15" />
        <motion.span
          className="absolute inset-0 rounded-full border-t-2 border-r-2 border-accent-cyan/70"
          animate={{ rotate: 360 }}
          transition={{ duration: 1.1, repeat: Infinity, ease: 'linear' }}
        />
        <motion.span
          className="absolute inset-[18%] rounded-full border-b-2 border-accent-purple/60"
          animate={{ rotate: -360 }}
          transition={{ duration: 1.6, repeat: Infinity, ease: 'linear' }}
        />
        <Dna
          className={`absolute inset-0 m-auto text-accent-cyan ${compact ? 'w-3.5 h-3.5' : 'w-5 h-5'}`}
          weight="duotone"
        />
      </div>

      <div className="flex items-center gap-1.5">
        {[0, 1, 2].map(i => (
          <motion.span
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-accent-cyan"
            animate={{ opacity: [0.2, 1, 0.2], scale: [0.8, 1.15, 0.8] }}
            transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.16 }}
          />
        ))}
      </div>

      {label && <p className={`text-text-secondary ${compact ? 'text-xs' : 'text-sm'}`}>{label}</p>}
    </div>
  );
}

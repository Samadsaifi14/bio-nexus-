'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { X, User } from 'lucide-react';
import { fadeUp } from '@/lib/animations';
import { useAuth } from '@/contexts/auth';

export function GuestBanner() {
  const { isGuest, upgradeToAccount } = useAuth();
  const [dismissed, setDismissed] = useState(false);

  if (!isGuest || dismissed) return null;

  return (
    <motion.div variants={fadeUp} className="mb-6 glass-card p-4 flex items-start justify-between gap-4 border border-accent-amber/20">
      <div className="flex items-start gap-3">
        <User className="w-5 h-5 text-accent-amber shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-medium text-text-primary">You're browsing as a guest</p>
          <p className="text-sm text-text-secondary mt-1">
            Your results are saved for 24 hours.{' '}
            <button
              onClick={upgradeToAccount}
              className="font-medium text-accent-cyan hover:text-accent-cyan/80 underline underline-offset-2"
            >
              Sign in with Google
            </button>{' '}
            to keep them forever.
          </p>
        </div>
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="p-1 hover:bg-surface-2 rounded transition shrink-0"
        aria-label="Dismiss"
      >
        <X className="w-4 h-4 text-text-muted" />
      </button>
    </motion.div>
  );
}

'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { X, User } from 'lucide-react';
import { fadeUp } from '@/lib/animations';
import { useAuth } from '@/contexts/auth';

export function GuestBanner() {
  const { isGuest, signIn } = useAuth();
  const [dismissed, setDismissed] = useState(false);

  if (!isGuest || dismissed) return null;

  return (
    <motion.div variants={fadeUp} className="mb-6 bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start justify-between gap-4">
      <div className="flex items-start gap-3">
        <User className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-medium text-amber-900">You're browsing as a guest</p>
          <p className="text-sm text-amber-700 mt-1">
            Your results are saved for 24 hours.{' '}
            <button
              onClick={signIn}
              className="font-medium text-teal-700 hover:text-teal-800 underline underline-offset-2"
            >
              Sign in with Google
            </button>{' '}
            to keep them forever and get unlimited access.
          </p>
        </div>
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="p-1 hover:bg-amber-100 rounded transition shrink-0"
        aria-label="Dismiss"
      >
        <X className="w-4 h-4 text-amber-500" />
      </button>
    </motion.div>
  );
}

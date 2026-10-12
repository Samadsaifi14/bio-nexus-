'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CircleNotch as LoaderCircle } from '@phosphor-icons/react';
import { getSupabase } from '@/lib/supabase';
import { motion } from 'framer-motion';
import { fadeUp } from '@/lib/animations';

export default function AuthCallback() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');

    if (!code) {
      router.replace('/auth');
      return;
    }

    getSupabase().auth.exchangeCodeForSession(code).then(({ error }: { error?: { message: string } | null }) => {
      if (error) {
        setError(error.message);
        return;
      }
      router.replace('/analyze');
    }).catch((e: Error) => {
      setError(e.message || 'Unknown error');
    });
  }, [router]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-void">
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="bg-surface-0 rounded-2xl border border-error/20 p-8 max-w-sm text-center">
          <h2 className="text-lg font-semibold text-error mb-2">Sign in failed</h2>
          <p className="text-sm text-error">{error}</p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-void">
      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="text-center">
        <LoaderCircle className="w-8 h-8 text-accent-cyan animate-spin mx-auto mb-4" />
        <p className="text-sm text-text-muted">Completing sign in...</p>
      </motion.div>
    </div>
  );
}

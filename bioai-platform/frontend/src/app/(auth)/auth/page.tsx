'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowRight, CircleNotch, MagnifyingGlass, Flask, ChartScatter } from '@phosphor-icons/react';
import { motion, useReducedMotion } from 'framer-motion';
import { useAuth } from '@/contexts/auth';

export default function AuthPage() {
  const { user, loading, signIn, isGuest } = useAuth();
  const router = useRouter();
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    if (!loading && (user || isGuest)) router.replace('/analyze');
  }, [user, isGuest, loading, router]);

  if (loading) return <div className="min-h-[100dvh] flex items-center justify-center bg-void" role="status"><CircleNotch className="w-8 h-8 text-accent-cyan animate-spin" aria-hidden="true" /><span className="sr-only">Loading sign in</span></div>;

  return <main className="bn-auth-page">
    <section className="bn-auth-story" aria-labelledby="auth-story-title">
      <Link href="/" className="bn-wordmark"><span className="bn-mark" aria-hidden="true">B<span className="bn-mark-dot" /></span><span>BioNexus</span></Link>
      <motion.div initial={reduceMotion ? false : { opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .65 }} className="bn-auth-story-content"><p className="bn-kicker">A space for the work behind the finding</p><h1 id="auth-story-title">The next question starts here.</h1><p>Bring sequence, structure and simulation into a workspace where the method and the evidence stay together.</p></motion.div>
      <div className="bn-auth-story-steps"><div><MagnifyingGlass size={20} aria-hidden="true" /><span>Choose a method</span></div><div><Flask size={20} aria-hidden="true" /><span>Inspect the run</span></div><div><ChartScatter size={20} aria-hidden="true" /><span>Read the evidence</span></div></div>
    </section>
    <section className="bn-auth-action" aria-labelledby="auth-title"><motion.div initial={reduceMotion ? false : { opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: .6, delay: .1 }} className="bn-auth-action-inner"><p className="bn-kicker">Enter the workspace</p><h2 id="auth-title">Welcome to BioNexus.</h2><p className="bn-auth-intro">Sign in to keep your work together, or explore as a guest.</p>
      <button type="button" onClick={signIn} className="bn-button bn-button-primary bn-auth-button">Sign in with Google <ArrowRight size={18} aria-hidden="true" /></button>
      <div className="bn-auth-divider"><span>or</span></div>
      <button type="button" onClick={() => router.replace('/analyze')} className="bn-button bn-auth-button bn-auth-guest">Continue as guest <ArrowRight size={18} aria-hidden="true" /></button>
      <p className="bn-auth-fineprint">Guest results are saved for 24 hours. Sign in to keep a longer history.</p>
    </motion.div></section>
  </main>;
}

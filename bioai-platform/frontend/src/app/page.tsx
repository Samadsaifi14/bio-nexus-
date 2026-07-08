'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useRef } from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import { ArrowRight, Database, Zap, Brain, ChevronDown } from 'lucide-react';

const DNAHelix = dynamic(
  () => import('@/components/three/DNAHelix'),
  { ssr: false, loading: () => <div className="w-full h-full bg-void" /> }
);

const DATABASES = ['NCBI', 'UniProt', 'PDB', 'KEGG', 'Ensembl', 'STRING', 'EMBL', 'Pfam'];

const PIPELINE = [
  { step: '01', label: 'Sequence Input',       sub: 'FASTA / accession ID'   },
  { step: '02', label: 'BLAST Search',         sub: 'EBI BLAST + NCBI'       },
  { step: '03', label: 'UniProt Lookup',       sub: 'Annotation & function'  },
  { step: '04', label: 'Structure Prediction', sub: 'AlphaFold 3D viewer'    },
  { step: '05', label: 'AI Interpretation',    sub: 'Plain-language insight' },
];

const FEATURES = [
  {
    icon:  Database,
    color: '#00F5D4',
    title: 'Unified Access',
    body:  'NCBI, UniProt, PDB, KEGG, Ensembl — one plain-English query retrieves across every major database simultaneously.',
  },
  {
    icon:  Zap,
    color: '#8B5CF6',
    title: 'Pipeline Automation',
    body:  'BLAST → UniProt → AlphaFold runs sequentially, hands-free. Real-time progress via SSE, results assembled automatically.',
  },
  {
    icon:  Brain,
    color: '#F59E0B',
    title: 'AI Interpretation',
    body:  'Every result is narrated in plain language. Clinical relevance, evolutionary context, functional insights — streamed live.',
  },
];

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  show:   { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.25, 1, 0.5, 1] as const } },
};

const stagger = {
  show: { transition: { staggerChildren: 0.1 } },
};

export default function LandingPage() {
  const heroRef = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({
    target:  heroRef,
    offset:  ['start start', 'end start'],
  });

  const helixY       = useTransform(scrollYProgress, [0, 1], ['0%', '28%']);
  const helixOpacity = useTransform(scrollYProgress, [0, 0.55], [1, 0]);
  const textY        = useTransform(scrollYProgress, [0, 1], ['0%', '18%']);
  const textOpacity  = useTransform(scrollYProgress, [0, 0.4], [1, 0]);

  return (
    <main className="relative bg-void text-text-primary overflow-x-hidden">
      <nav
        className="fixed top-0 inset-x-0 z-50 flex items-center justify-between px-8 py-5"
        style={{ backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)' }}
      >
        <span className="font-display text-sm font-semibold tracking-widest uppercase">
          Bio <span className="text-gradient">Nexus</span>
        </span>

        <div className="flex items-center gap-6">
          <Link href="#features" className="hidden sm:block text-xs text-text-muted hover:text-text-primary transition-colors tracking-wide">
            Features
          </Link>
          <Link href="#pipeline" className="hidden sm:block text-xs text-text-muted hover:text-text-primary transition-colors tracking-wide">
            Pipeline
          </Link>
          <Link
            href="/auth"
            className="text-xs px-4 py-2 rounded-full border border-glass-border text-text-secondary hover:border-accent-cyan/40 hover:text-accent-cyan transition-all"
          >
            Sign in
          </Link>
          <Link href="/dashboard" className="btn-primary text-xs py-2 px-4">
            Get started
          </Link>
        </div>
      </nav>

      <section
        ref={heroRef}
        className="relative h-screen flex items-center justify-center overflow-hidden"
      >
        <motion.div
          style={{ y: helixY, opacity: helixOpacity }}
          className="absolute inset-0 z-0"
        >
          <DNAHelix className="w-full h-full" />
        </motion.div>

        <div className="absolute inset-0 z-[1] bg-grid pointer-events-none opacity-40" />
        <div className="absolute inset-0 z-[2] bg-vignette pointer-events-none" />

        <div
          className="absolute z-[1] w-[40vw] h-[40vw] rounded-full pointer-events-none"
          style={{
            top: '20%', left: '10%',
            background: 'radial-gradient(circle, rgba(0,245,212,0.07) 0%, transparent 70%)',
            filter: 'blur(40px)',
          }}
        />
        <div
          className="absolute z-[1] w-[35vw] h-[35vw] rounded-full pointer-events-none"
          style={{
            bottom: '15%', right: '8%',
            background: 'radial-gradient(circle, rgba(139,92,246,0.07) 0%, transparent 70%)',
            filter: 'blur(40px)',
          }}
        />

        <motion.div
          style={{ y: textY, opacity: textOpacity }}
          className="relative z-10 text-center max-w-4xl px-6"
        >
          <motion.p
            variants={fadeUp}
            initial={{ y: 24 }}
            animate="show"
            transition={{ delay: 0.2 }}
            className="text-[10px] tracking-[0.35em] uppercase text-accent-cyan mb-7 font-mono"
          >
            Bioinformatics · Automated · AI-powered
          </motion.p>

          <motion.h1
            variants={fadeUp}
            initial={{ y: 24 }}
            animate="show"
            transition={{ delay: 0.4 }}
            className="font-display font-bold leading-[0.92] tracking-tight mb-8"
            style={{ fontSize: 'clamp(3.2rem, 8.5vw, 7.5rem)' }}
          >
            One query.{' '}
            <br className="hidden sm:block" />
            <span className="text-gradient">Every database.</span>
          </motion.h1>

          <motion.p
            variants={fadeUp}
            initial={{ y: 24 }}
            animate="show"
            transition={{ delay: 0.6 }}
            className="text-text-secondary text-lg max-w-[520px] mx-auto mb-10 leading-relaxed"
          >
            BioNexus unifies NCBI, UniProt, PDB, and KEGG into a single plain-language
            interface — with AI-interpreted visual results, instantly.
          </motion.p>

          <motion.div
            variants={fadeUp}
            initial={{ y: 24 }}
            animate="show"
            transition={{ delay: 0.75 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-4"
          >
            <Link href="/dashboard" className="btn-primary">
              Start analyzing
              <ArrowRight size={15} />
            </Link>
            <Link href="#pipeline" className="btn-ghost">
              See the pipeline
            </Link>
          </motion.div>
        </motion.div>

        <motion.div
          className="absolute bottom-9 left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-2 opacity-50"
          animate={{ y: [0, 7, 0] }}
          transition={{ repeat: Infinity, duration: 2, ease: 'easeInOut' }}
        >
          <ChevronDown size={14} className="text-text-muted" />
        </motion.div>
      </section>

      <section className="relative py-14 border-y border-glass-border overflow-hidden">
        <div className="absolute inset-0 bg-surface-0/60" />
        <div className="relative z-10">
          <p className="text-center text-[10px] tracking-[0.35em] uppercase text-text-muted font-mono mb-8">
            Unified access to
          </p>
          <motion.div
            variants={stagger}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true }}
            className="flex flex-wrap items-center justify-center gap-x-10 gap-y-3 px-6"
          >
            {DATABASES.map((db) => (
              <motion.span
                key={db}
                variants={fadeUp}
                className="text-sm font-mono text-text-muted hover:text-accent-cyan transition-colors cursor-default select-none"
              >
                {db}
              </motion.span>
            ))}
          </motion.div>
        </div>
      </section>

      <section id="pipeline" className="py-28 px-6 max-w-5xl mx-auto">
        <motion.div
          variants={fadeUp}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          className="text-center mb-20"
        >
          <p className="text-[10px] tracking-[0.35em] uppercase text-accent-cyan font-mono mb-4">
            How it works
          </p>
          <h2 className="font-display text-4xl font-bold tracking-tight">
            From sequence to insight
          </h2>
          <p className="text-text-secondary mt-4 max-w-md mx-auto text-sm leading-relaxed">
            Five automated stages, zero manual database switching.
          </p>
        </motion.div>

        <div className="relative">
          <div className="absolute top-10 left-0 right-0 h-px hidden md:block">
            <div className="h-full bg-gradient-to-r from-transparent via-glass-border to-transparent mx-12" />
          </div>

          <motion.div
            variants={stagger}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: '-60px' }}
            className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-5"
          >
            {PIPELINE.map(({ step, label, sub }) => (
              <motion.div
                key={step}
                variants={fadeUp}
                whileHover={{ y: -4, transition: { duration: 0.2 } }}
                className="glass-card p-5 text-center relative cursor-default"
              >
                <div className="w-8 h-8 rounded-full bg-accent-cyan/10 border border-accent-cyan/25 flex items-center justify-center mx-auto mb-4">
                  <span className="text-accent-cyan text-[10px] font-mono font-semibold">{step}</span>
                </div>

                <p className="font-display text-[13px] font-semibold mb-1 text-text-primary">
                  {label}
                </p>
                <p className="text-[11px] text-text-muted font-mono">{sub}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      <section id="features" className="py-28 px-6 max-w-5xl mx-auto">
        <motion.div
          variants={fadeUp}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          className="text-center mb-20"
        >
          <p className="text-[10px] tracking-[0.35em] uppercase text-accent-purple font-mono mb-4">
            Features
          </p>
          <h2 className="font-display text-4xl font-bold tracking-tight">
            Everything you need
          </h2>
        </motion.div>

        <motion.div
          variants={stagger}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: '-60px' }}
          className="grid grid-cols-1 md:grid-cols-3 gap-6"
        >
          {FEATURES.map((f) => {
            const Icon = f.icon;
            return (
              <motion.div
                key={f.title}
                variants={fadeUp}
                whileHover={{ y: -6, transition: { duration: 0.25 } }}
                className="glass-card p-7 cursor-default"
              >
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center mb-6"
                  style={{
                    background: `${f.color}12`,
                    border:     `1px solid ${f.color}28`,
                  }}
                >
                  <Icon size={18} style={{ color: f.color }} strokeWidth={1.8} />
                </div>

                <h3 className="font-display text-base font-semibold mb-2 text-text-primary">
                  {f.title}
                </h3>
                <p className="text-sm text-text-secondary leading-relaxed">
                  {f.body}
                </p>

                <div
                  className="mt-6 h-px rounded-full"
                  style={{
                    background: `linear-gradient(90deg, ${f.color}40 0%, transparent 100%)`,
                  }}
                />
              </motion.div>
            );
          })}
        </motion.div>
      </section>

      <section className="py-32 px-6 relative overflow-hidden">
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: 'radial-gradient(ellipse 60% 60% at 50% 50%, rgba(0,245,212,0.05) 0%, transparent 70%)',
          }}
        />

        <motion.div
          variants={fadeUp}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          className="relative z-10 text-center max-w-xl mx-auto"
        >
          <p className="text-[10px] tracking-[0.35em] uppercase text-accent-amber font-mono mb-6">
            Get started
          </p>
          <h2 className="font-display text-4xl font-bold tracking-tight mb-5">
            Ready to decode your sequences?
          </h2>
          <p className="text-text-secondary mb-10 leading-relaxed">
            Free to start. No API keys required to run your first analysis.
          </p>
          <Link href="/dashboard" className="btn-primary text-base px-8 py-4">
            Open Bio Nexus
            <ArrowRight size={17} />
          </Link>
        </motion.div>
      </section>

      <footer className="border-t border-glass-border py-8 px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
        <span className="font-mono text-xs text-text-muted">
          Bio Nexus · Built at Jamia Millia Islamia
        </span>
        <div className="flex items-center gap-6">
          <Link href="/auth" className="text-xs text-text-muted hover:text-text-primary transition-colors">
            Sign in
          </Link>
          <span className="text-xs text-text-muted">&copy; 2026</span>
        </div>
      </footer>
    </main>
  );
}

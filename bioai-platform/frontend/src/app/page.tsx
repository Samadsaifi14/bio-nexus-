'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useRef } from 'react';
import { motion, useReducedMotion, useScroll, useTransform } from 'framer-motion';
import { ArrowRight, Database, FlowArrow, Brain, CaretDown as ChevronDown } from '@phosphor-icons/react';
import { TiltCard } from '@/components/ui/TiltCard';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import { JsonLd } from '@/components/seo/JsonLd';
import { ORG_ID, SOFTWARE_ID, SITE_NAME, SITE_URL, WEBPAGE_ID, WEBSITE_ID } from '@/lib/seo';

const DNAHelix = dynamic(
  () => import('@/components/three/DNAHelix'),
  { ssr: false, loading: () => <div className="w-full h-full bg-void" /> }
);

const DATABASES = ['NCBI', 'UniProt', 'PDB', 'AlphaFold', 'EMBL', 'InterPro', 'KEGG', 'STRING'];

const DB_GROUPS = [
  { label: 'Portals',    names: 'NCBI · EMBL-EBI' },
  { label: 'Annotation', names: 'UniProt · InterPro' },
  { label: 'Structure',  names: 'RCSB PDB · AlphaFold' },
  { label: 'Systems',    names: 'KEGG · STRING' },
];

const CONFIDENCE_BANDS = [
  { label: 'Very high', dot: 'bg-confidence-very-high' },
  { label: 'High',      dot: 'bg-confidence-high' },
  { label: 'Moderate',  dot: 'bg-confidence-moderate' },
  { label: 'Low',       dot: 'bg-confidence-low' },
];

const REVEAL = { initial: { opacity: 0, y: 28 }, whileInView: { opacity: 1, y: 0 }, viewport: { once: true, margin: '-80px' } };

const PIPELINE = [
  { tag: 'input',    label: 'Sequence Input',       sub: 'FASTA / accession ID'  },
  { tag: 'blast',    label: 'BLAST Search',         sub: 'EBI BLAST + NCBI'      },
  { tag: 'uniprot',  label: 'UniProt Lookup',       sub: 'Annotation & function' },
  { tag: 'fold',     label: 'Structure Prediction', sub: 'AlphaFold 3D viewer'   },
  { tag: 'ai',       label: 'AI Interpretation',    sub: 'Plain-language insight' },
];

const FEATURES = [
  {
    icon:  Database,
    title: 'Unified Access',
    body:  'NCBI, UniProt, PDB, KEGG, STRING and more — one plain-English query retrieves across every major database simultaneously.',
    span:  'md:col-span-2',
  },
  {
    icon:  FlowArrow,
    title: 'Pipeline Automation',
    body:  'BLAST → UniProt → AlphaFold runs sequentially, hands-free. Real-time progress via SSE, results assembled automatically.',
    span:  'md:col-span-1',
  },
  {
    icon:  Brain,
    title: 'AI Interpretation',
    body:  'Every result is narrated in plain language. Clinical relevance, evolutionary context, functional insights — streamed live.',
    span:  'md:col-span-3',
  },
];

export default function LandingPage() {
  const heroRef = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({
    target:  heroRef,
    offset:  ['start start', 'end start'],
  });

  const reduceMotion = useReducedMotion();

  // Parallax slides the hero as you scroll — flattened to a cross-fade under
  // reduced motion (apple-design §14).
  const contentY      = useTransform(scrollYProgress, [0, 1], reduceMotion ? ['0%', '0%'] : ['0%', '12%']);
  const contentOpacity = useTransform(scrollYProgress, [0, 0.6], [1, 0.2]);

  return (
    <main className="relative bg-void text-text-primary overflow-x-hidden">
      <nav className="fixed top-4 inset-x-0 z-50 flex justify-center px-4 pointer-events-none">
        <div className="liquid-glass pointer-events-auto flex w-full max-w-5xl items-center justify-between px-6 py-3.5">
          <span className="font-display text-sm font-semibold tracking-tight uppercase">
            Bio&nbsp;<span className="text-accent-cyan">Nexus</span>
          </span>

          <div className="flex items-center gap-4 lg:gap-6">
            <Link href="#features" className="hidden sm:block text-xs text-text-muted hover:text-text-primary transition-colors tracking-wide">
              Features
            </Link>
            <Link href="#pipeline" className="hidden sm:block text-xs text-text-muted hover:text-text-primary transition-colors tracking-wide">
              Pipeline
            </Link>
            <ThemeToggle />
            <Link
              href="/auth"
              className="hidden sm:inline-flex text-xs px-3 lg:px-4 min-h-[44px] items-center rounded-full border border-glass-border text-text-secondary hover:border-accent-cyan/40 hover:text-accent-cyan transition-all"
            >
              Sign in
            </Link>
            <Link href="/dashboard" className="btn-primary text-xs px-3 lg:px-4 min-h-[44px] flex items-center">
              Start analyzing
            </Link>
          </div>
        </div>
      </nav>

      <section
        ref={heroRef}
        className="relative min-h-[100dvh] flex items-center overflow-hidden"
      >
        <div className="absolute inset-0 z-0 pointer-events-none">
          <div
            className="absolute inset-0"
            style={{
              background:
                'radial-gradient(ellipse 55% 55% at 78% 45%, rgba(96,165,250,0.10) 0%, transparent 70%), radial-gradient(ellipse 45% 45% at 12% 70%, rgba(74,222,128,0.08) 0%, transparent 70%), radial-gradient(ellipse 42% 42% at 55% 15%, rgba(251,191,36,0.06) 0%, transparent 70%)',
            }}
          />
          <div className="absolute inset-0 bg-gradient-to-r from-void via-void/55 to-transparent" />
          <div className="absolute inset-0 bg-gradient-to-b from-void/70 via-transparent to-void/70" />
        </div>

        <motion.div
          style={{ y: contentY, opacity: contentOpacity }}
          className="relative z-10 w-full max-w-6xl mx-auto px-6 py-24"
        >
          <div className="grid lg:grid-cols-[1.05fr_0.95fr] gap-14 lg:gap-16 items-center">
            <div className="max-w-3xl">
              <motion.h1
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ type: 'spring', bounce: 0, duration: 0.7 }}
                className="font-display font-bold leading-[0.98] tracking-tight"
                style={{ fontSize: 'clamp(2.75rem, 5.5vw, 5.5rem)' }}
              >
                Stop tab-switching
                <br />
                <span className="text-accent-cyan">between eight databases.</span>
              </motion.h1>

              <motion.p
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ type: 'spring', bounce: 0, duration: 0.7, delay: 0.08 }}
                className="text-text-secondary text-lg max-w-[460px] mt-8 leading-relaxed"
              >
                Paste a sequence. Bio Nexus runs BLAST, annotation, structure and
                AI interpretation — assembled on one page, in one query.
              </motion.p>

              <motion.div
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ type: 'spring', bounce: 0, duration: 0.7, delay: 0.16 }}
                className="flex flex-col sm:flex-row items-start gap-4 mt-10"
              >
                <Link href="/dashboard" className="btn-primary">
                  Start analyzing
                  <ArrowRight size={15} />
                </Link>
                <Link href="#pipeline" className="btn-ghost">
                  See the pipeline
                </Link>
              </motion.div>

              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.6, delay: 0.5 }}
                className="flex items-center gap-2.5 mt-10 text-[11px] font-mono text-text-muted"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan animate-pulse" />
                <span>No API keys · results streamed live</span>
              </motion.div>
            </div>

            <motion.div
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ type: 'spring', bounce: 0, duration: 0.9, delay: 0.2 }}
              className="hidden md:block"
            >
              <div
                className="relative rounded-2xl border border-glass-border bg-surface-0/70 overflow-hidden"
                style={{ aspectRatio: '4 / 4.3' }}
              >
                <div className="absolute inset-0">
                  <DNAHelix className="w-full h-full" />
                </div>
                <div
                  className="absolute inset-0 pointer-events-none opacity-40"
                  style={{ background: 'linear-gradient(180deg, transparent 55%, rgba(5,6,9,0.6) 100%)' }}
                />
                <div className="absolute top-3.5 left-4 flex items-center gap-2 font-mono text-[10px] tracking-wider text-text-muted">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan animate-pulse" />
                  DOUBLE HELIX · LIVE
                </div>
                <div className="absolute bottom-3 left-4 right-4 flex items-center justify-between font-mono text-[10px] tracking-wider text-text-muted">
                  <span>5′ — 3′</span>
                  <span>4.2 kb</span>
                </div>
              </div>
            </motion.div>
          </div>
        </motion.div>

        <div className="absolute bottom-9 left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-2 opacity-50">
          <ChevronDown size={14} className="text-text-muted" />
        </div>
      </section>

      <section className="relative py-14 border-y border-glass-border overflow-hidden">
        <div className="absolute inset-0 bg-surface-0/60" />
        <div className="relative z-10 marquee-mask">
          <div className="marquee-track items-center gap-x-10 gap-y-3">
            {[...DATABASES, ...DATABASES].map((db, i) => (
              <span
                key={`${db}-${i}`}
                className="text-sm font-mono text-text-muted hover:text-accent-cyan transition-colors cursor-default select-none"
              >
                {db}
              </span>
            ))}
          </div>
        </div>
      </section>

      <section id="pipeline" className="py-24 px-6 max-w-5xl mx-auto">
        <motion.div {...REVEAL} transition={{ duration: 0.45 }} className="text-center mb-16">
          <h2 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">
            From sequence to insight
          </h2>
          <p className="text-text-secondary mt-3 max-w-md mx-auto text-sm leading-relaxed">
            Five automated stages, zero manual database switching.
          </p>
        </motion.div>

        <div className="relative">
          <div className="hidden md:block absolute top-[13px] left-10 right-10 h-px bg-gradient-to-r from-transparent via-glass-border to-transparent" />
          <div className="hidden md:block absolute top-[13px] left-10 right-10 h-px pipeline-line" />

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-8 md:gap-4">
            {PIPELINE.map(({ tag, label, sub }, i) => (
              <motion.div
                key={tag}
                {...REVEAL}
                transition={{ duration: 0.4, delay: i * 0.08 }}
                className="relative text-center"
              >
                <motion.div
                  className="hidden md:flex w-[26px] h-[26px] rounded-full border border-accent-cyan/40 bg-surface-0 items-center justify-center relative z-10 mx-auto"
                  initial={{ boxShadow: '0 0 0 0 rgba(74,222,128,0)' }}
                  whileInView={{ boxShadow: ['0 0 0 0 rgba(74,222,128,0)', '0 0 14px 2px rgba(74,222,128,0.3)', '0 0 0 0 rgba(74,222,128,0)'] }}
                  viewport={{ once: true, margin: '-80px' }}
                  transition={{ duration: 0.9, delay: i * 0.25, ease: 'easeInOut' }}
                >
                  <span className="w-[6px] h-[6px] rounded-full bg-accent-cyan/70" />
                </motion.div>
                <div className="mt-4 md:mt-5">
                  <p className="text-[10px] font-mono tracking-widest uppercase text-accent-cyan/80">{tag}</p>
                  <p className="text-sm font-medium text-text-primary mt-1">{label}</p>
                  <p className="text-[11px] text-text-muted mt-0.5 font-mono">{sub}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section id="results" className="py-24 px-6 max-w-5xl mx-auto">
        <motion.div {...REVEAL} transition={{ duration: 0.45 }} className="text-center mb-16">
          <h2 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">
            What you get back
          </h2>
          <p className="text-text-secondary mt-3 max-w-md mx-auto text-sm leading-relaxed">
            BLAST hits, annotation, structure and AI insight — cross-referenced on one page, exportable as PDF or JSON.
          </p>
        </motion.div>

        <motion.div {...REVEAL} transition={{ duration: 0.45 }}>
          <div className="data-card p-6 sm:p-8">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-glass-border pb-4">
              <div className="flex items-center gap-2.5">
                <span className="w-2 h-2 rounded-full bg-confidence-very-high" />
                <span className="font-mono text-sm text-text-primary">P01308 · Insulin [Homo sapiens]</span>
              </div>
              <span className="px-2 py-0.5 rounded-full border border-glass-border bg-surface-1 text-[10px] font-mono uppercase tracking-widest text-text-muted">
                sample
              </span>
            </div>

            <div className="grid md:grid-cols-2 gap-8 pt-5">
              <div>
                <p className="text-[10px] font-mono uppercase tracking-widest text-text-muted mb-3">BLAST hits · top 3 of 14</p>
                <ul className="flex flex-col gap-2.5">
                  <li className="flex items-center justify-between gap-4 font-mono text-xs">
                    <span className="text-text-primary">P01308 · INS_HUMAN</span>
                    <span className="text-text-secondary">100% · e 0.0</span>
                  </li>
                  <li className="flex items-center justify-between gap-4 font-mono text-xs">
                    <span className="text-text-primary">insulin [mouse]</span>
                    <span className="text-text-secondary">87% · e 1e-97</span>
                  </li>
                  <li className="flex items-center justify-between gap-4 font-mono text-xs">
                    <span className="text-text-primary">insulin-like INSL3</span>
                    <span className="text-text-secondary">41% · e 3e-14</span>
                  </li>
                </ul>
              </div>

              <div>
                <p className="text-[10px] font-mono uppercase tracking-widest text-text-muted mb-3">AI interpretation</p>
                <p className="font-mono text-[13px] text-text-secondary leading-relaxed">
                  <span className="text-accent-cyan">&gt; </span>Insulin — reviewed UniProt entry with an experimental
                  structure. Function, family and disease annotations cross-referenced from the source databases.
                </p>
              </div>
            </div>

            <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-2 pt-4 border-t border-glass-border">
              {CONFIDENCE_BANDS.map((b) => (
                <span key={b.label} className="flex items-center gap-1.5 text-[10px] font-mono text-text-muted">
                  <span className={`w-1.5 h-1.5 rounded-full ${b.dot}`} />
                  {b.label}
                </span>
              ))}
              <span className="ml-auto text-[11px] font-mono text-text-muted">NCBI · UniProt · PDB · AlphaFold</span>
            </div>
          </div>
        </motion.div>
      </section>

      <section id="features" className="py-24 px-6 max-w-5xl mx-auto">
        <motion.div {...REVEAL} transition={{ duration: 0.45 }} className="mb-16">
          <h2 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">
            All your databases, one query
          </h2>
          <p className="text-text-secondary mt-3 max-w-md mx-auto text-sm leading-relaxed">
            One query retrieves across every major database simultaneously — results cross-referenced on a single page.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {FEATURES.map((f, i) => {
            const Icon = f.icon;
            const wide = f.span === 'md:col-span-2';
            const full = f.span === 'md:col-span-3';
            return (
              <motion.div
                key={f.title}
                {...REVEAL}
                transition={{ duration: 0.4, delay: (i % 3) * 0.08 }}
                className={`${f.span}`}
              >
                <TiltCard
                  className={`glass-card p-8 cursor-default h-full ${full ? 'flex flex-col md:flex-row md:items-center gap-8' : ''}`}
                >
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center bg-accent-cyan/10 border border-accent-cyan/20 shrink-0 ${full ? 'mb-0' : 'mb-6'}`}
                  >
                    <Icon size={18} className="text-accent-cyan" weight="regular" />
                  </div>

                  <div className={wide ? 'grid lg:grid-cols-2 gap-8 items-start' : ''}>
                    <div>
                      <h3 className={`font-display font-semibold mb-2 text-text-primary ${wide ? 'text-xl' : 'text-base'}`}>
                        {f.title}
                      </h3>
                      <p className="text-sm text-text-secondary leading-relaxed max-w-[46ch]">
                        {f.body}
                      </p>
                    </div>

                    {wide && (
                      <div className="flex flex-col gap-2 lg:pt-1">
                        {DB_GROUPS.map((g) => (
                          <div key={g.label} className="flex items-center gap-2">
                            <span className="text-[10px] font-mono uppercase tracking-widest text-text-muted w-20 shrink-0">
                              {g.label}
                            </span>
                            <span className="px-2.5 py-1 rounded-lg border border-glass-border bg-surface-1 text-[11px] font-mono text-text-secondary">
                              {g.names}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    {full && (
                      <div className="min-w-0 md:ml-auto w-full">
                        <p className="font-mono text-[13px] text-text-secondary leading-relaxed">
                          <span className="text-accent-cyan">&gt; </span>docking · <span className="text-text-primary">7 poses</span> scored against target pocket
                          <span className="inline-block w-[2px] h-3 bg-accent-cyan/70 ml-1 animate-blink align-middle" />
                        </p>
                        <p className="mt-3 text-sm text-text-secondary leading-relaxed max-w-[46ch]">
                          Best pose: binding affinity −8.4 kcal/mol, ligand efficiency 0.31 — narrated in plain language alongside the raw AutoDock Vina output.
                        </p>
                        <p className="mt-3 text-[11px] font-mono text-text-muted">
                          engine · AutoDock Vina · CPU-based, no GPU required
                        </p>
                      </div>
                    )}
                  </div>

                  <div className={`mt-6 h-px rounded-full bg-gradient-to-r from-accent-cyan/25 to-transparent ${full ? 'md:hidden' : ''}`} />
                </TiltCard>
              </motion.div>
            );
          })}
        </div>
      </section>

      <section className="py-32 px-6 relative overflow-hidden">
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: 'radial-gradient(ellipse 60% 60% at 50% 50%, rgba(96,165,250,0.06) 0%, transparent 70%), radial-gradient(ellipse 40% 40% at 68% 62%, rgba(52,211,153,0.04) 0%, transparent 70%)',
          }}
        />

        <div className="relative z-10 text-center max-w-xl mx-auto">
          <h2 className="font-display text-3xl sm:text-4xl font-bold tracking-tight mb-5">
            Ready to decode your sequences?
          </h2>
          <p className="text-text-secondary mb-4 leading-relaxed">
            Free to start. No API keys required to run your first analysis.
          </p>
          <p className="text-sm text-text-muted mb-10 font-mono">
            Your sequences stay yours — never shared or used beyond the analysis you ask for.
          </p>
          <Link href="/dashboard" className="btn-primary text-base px-8 py-4">
            Start analyzing
            <ArrowRight size={17} />
          </Link>
        </div>
      </section>

      <footer className="border-t border-glass-border py-8 px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
        <span className="text-xs text-text-muted">
          Bio Nexus · Built at Jamia Millia Islamia
        </span>
        <div className="flex items-center gap-6">
          <Link href="/auth" className="text-xs text-text-muted hover:text-text-primary transition-colors">
            Sign in
          </Link>
          <span className="text-xs text-text-muted">&copy; 2026</span>
        </div>
      </footer>

      <JsonLd
        data={{
          '@context': 'https://schema.org',
          '@type': 'WebPage',
          '@id': WEBPAGE_ID,
          url: `${SITE_URL}/`,
          name: 'Bio Nexus — One interface for every bioinformatics tool',
          isPartOf: { '@id': WEBSITE_ID },
          about: { '@id': SOFTWARE_ID },
          mainEntity: {
            '@type': 'SoftwareApplication',
            '@id': SOFTWARE_ID,
            name: SITE_NAME,
            applicationCategory: 'ScienceApplication',
            applicationSubCategory: 'Bioinformatics',
            operatingSystem: 'Web',
            url: `${SITE_URL}/`,
            description:
              'Runs BLAST, UniProt annotation, AlphaFold structure prediction, molecular docking and AI interpretation from a single sequence input, with results cross-referenced on one page.',
            offers: {
              '@type': 'Offer',
              price: '0',
              priceCurrency: 'USD',
              description: 'Free to start, no API key required',
            },
            featureList: [
              'BLAST search (EBI + NCBI)',
              'UniProt annotation lookup',
              'AlphaFold 3D structure prediction',
              'Molecular docking (AutoDock Vina)',
              'Phylogenetic tree construction (NJ, UPGMA, Maximum Likelihood)',
              'AI-generated plain-language interpretation',
              'PDF/JSON export',
            ],
            creator: { '@id': ORG_ID },
          },
        }}
      />

      <JsonLd
        data={{
          '@context': 'https://schema.org',
          '@type': 'HowTo',
          name: 'How Bio Nexus analyzes a sequence',
          description: 'Five automated stages from raw sequence to AI-interpreted results.',
          step: [
            { '@type': 'HowToStep', position: 1, name: 'Sequence Input', text: 'Paste a FASTA sequence or accession ID.' },
            { '@type': 'HowToStep', position: 2, name: 'BLAST Search', text: 'Runs EBI BLAST and NCBI BLAST against reference databases.' },
            { '@type': 'HowToStep', position: 3, name: 'UniProt Lookup', text: 'Retrieves functional annotation from UniProt.' },
            { '@type': 'HowToStep', position: 4, name: 'Structure Prediction', text: 'AlphaFold structure is fetched and rendered in an interactive 3D viewer.' },
            { '@type': 'HowToStep', position: 5, name: 'AI Interpretation', text: 'Results are synthesized into a plain-language summary.' },
          ],
        }}
      />
    </main>
  );
}

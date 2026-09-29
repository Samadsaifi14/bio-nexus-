"use client";

import { useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowRight, Atom, ChartScatter, Dna, MagnifyingGlass, ArrowUpRight } from "@phosphor-icons/react";
import { JsonLd } from "@/components/seo/JsonLd";
import { ORG_ID, SOFTWARE_ID, SITE_NAME, SITE_URL, WEBPAGE_ID, WEBSITE_ID } from "@/lib/seo";

const methods = [
  {
    number: "01", title: "NGS analysis", field: "Genomics", href: "/analyze/ngs-v2", icon: Dna,
    question: "What does this sequencing run actually support?",
    description: "Explore quality, coverage, contamination, identity and variant evidence in the exploratory preview.",
    input: "FASTQ reads", output: "QC and variant evidence", boundary: "Production planning and external execution are separate steps.",
  },
  {
    number: "02", title: "BLAST search", field: "Sequence biology", href: "/analyze/blast", icon: MagnifyingGlass,
    question: "Where does this sequence find its closest matches?",
    description: "Inspect hits with identity, coverage, scores, alignments and reference information.",
    input: "Protein or nucleotide sequence", output: "Ranked similarity hits", boundary: "Similarity alone does not establish function.",
  },
  {
    number: "03", title: "Molecular docking", field: "Structural biology", href: "/analyze/docking", icon: Atom,
    question: "How might this ligand fit the target?",
    description: "Review poses, affinity estimates and available interaction evidence alongside method details.",
    input: "Prepared target and ligand", output: "Pose and interaction views", boundary: "A docking score is a model estimate, not experimental binding.",
  },
  {
    number: "04", title: "Molecular dynamics", field: "Simulation", href: "/analyze/md-v2", icon: ChartScatter,
    question: "What changes during the simulated trajectory?",
    description: "Follow preparation, equilibration, production and trajectory quality checks for hosted implicit-solvent OpenMM.",
    input: "Prepared molecular system", output: "Trajectory and QC views", boundary: "The hosted workflow uses implicit solvent.",
  },
];

const reveal = { hidden: { opacity: 0, y: 24 }, visible: { opacity: 1, y: 0 } };

export default function LandingPage() {
  const [selected, setSelected] = useState(0);
  const reduceMotion = useReducedMotion();
  const method = methods[selected];
  const Icon = method.icon;
  const inView = reduceMotion ? undefined : { once: true, amount: 0.16 as const };

  return (
    <main className="bn-landing min-h-[100dvh] bg-void text-text-primary">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:bg-accent-cyan focus:px-4 focus:py-3 focus:text-surface-0">Skip to content</a>
      <header className="bn-site-header">
        <nav aria-label="Main navigation" className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4 sm:px-8">
          <Link href="/" className="bn-wordmark" aria-label="BioNexus home"><span className="bn-mark" aria-hidden="true">B<span className="bn-mark-dot" /></span><span>BioNexus</span></Link>
          <div className="flex items-center gap-3 sm:gap-8">
            <Link href="#methods" className="bn-nav-link hidden sm:inline-flex">Methods</Link>
            <Link href="#principles" className="bn-nav-link hidden md:inline-flex">How it works</Link>
            <Link href="/auth" className="bn-nav-link hidden md:inline-flex">Sign in</Link>
            <Link href="/analyze" className="bn-button bn-button-primary text-sm">Enter workspace <ArrowUpRight size={17} aria-hidden="true" /></Link>
          </div>
        </nav>
      </header>

      <div id="main-content">
        <section className="bn-hero mx-auto max-w-7xl px-5 pb-16 pt-14 sm:px-8 sm:pt-20 lg:pb-24 lg:pt-28">
          <div className="bn-hero-copy">
            <motion.p initial={reduceMotion ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .45 }} className="bn-eyebrow"><span className="bn-eyebrow-line" /> A workspace for asking better biological questions</motion.p>
            <motion.h1 initial={reduceMotion ? false : { opacity: 0, y: 28 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .68, delay: .08, ease: [.22, 1, .36, 1] }} className="bn-hero-title">From raw signal to <em>reasoned</em> result.</motion.h1>
            <motion.p initial={reduceMotion ? false : { opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .55, delay: .2 }} className="bn-hero-description">Sequence, structure and simulation in one place. BioNexus keeps the method, the quality checks and the source result close enough to read together.</motion.p>
            <motion.div initial={reduceMotion ? false : { opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5, delay: .32 }} className="mt-9 flex flex-wrap items-center gap-5">
              <Link href="/analyze" className="bn-button bn-button-primary">Explore the methods <ArrowRight size={18} aria-hidden="true" /></Link>
              <Link href="/wizard" className="bn-text-link">Guide me through a workflow <ArrowUpRight size={17} aria-hidden="true" /></Link>
            </motion.div>
            <p className="mt-9 max-w-[54ch] text-xs leading-6 text-text-muted">Run availability depends on the method, input and connected services. Each result reports its own status and limits.</p>
          </div>
          <motion.div initial={reduceMotion ? false : { opacity: 0, x: 28, rotate: 1 }} animate={{ opacity: 1, x: 0, rotate: 0 }} transition={{ duration: .75, delay: .16, ease: [.22, 1, .36, 1] }} className="bn-specimen" aria-label="Illustrative structure of a research workflow; no sample data">
            <div className="bn-specimen-top"><span>THE RESEARCH RECORD</span><span>BN / 001</span></div>
            <div className="bn-specimen-body">
              <div className="bn-specimen-index">Observe <span>→</span> Test <span>→</span> Interpret</div>
              <div className="bn-specimen-figure" aria-hidden="true">
                <span className="bn-figure-ring bn-figure-ring-one" /><span className="bn-figure-ring bn-figure-ring-two" /><span className="bn-figure-ring bn-figure-ring-three" />
                <span className="bn-figure-core">?</span>
                <span className="bn-figure-note bn-figure-note-one">INPUT</span><span className="bn-figure-note bn-figure-note-two">METHOD</span><span className="bn-figure-note bn-figure-note-three">EVIDENCE</span>
              </div>
              <p className="bn-specimen-caption">A finding is only as useful as the path that produced it.</p>
            </div>
            <div className="bn-specimen-bottom"><span>ILLUSTRATIVE WORKFLOW</span><span>NO SAMPLE MEASUREMENTS</span></div>
          </motion.div>
        </section>

        <section id="methods" className="bn-methods-section">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-8 lg:py-28">
            <motion.div variants={reveal} initial={reduceMotion ? false : "hidden"} whileInView="visible" viewport={inView} transition={{ duration: .6 }} className="bn-section-heading">
              <div><p className="bn-kicker">Explore / 01—04</p><h2>Start with the question.</h2></div>
              <p>Choose a method to see the input, the evidence it can show, and the boundary that matters when interpreting it.</p>
            </motion.div>
            <div className="bn-method-explorer">
              <div className="bn-method-list" aria-label="Research methods">
                {methods.map((item, index) => {
                  const ItemIcon = item.icon;
                  return <button key={item.number} type="button" onClick={() => setSelected(index)} aria-pressed={selected === index} className={`bn-method-choice ${selected === index ? "is-selected" : ""}`}>
                    <span className="bn-method-number">{item.number}</span><span className="bn-method-icon"><ItemIcon size={23} aria-hidden="true" /></span><span className="bn-method-name"><strong>{item.title}</strong><small>{item.field}</small></span><ArrowUpRight size={18} className="bn-method-arrow" aria-hidden="true" />
                  </button>;
                })}
              </div>
              <div className="bn-method-detail" aria-live="polite">
                <AnimatePresence mode="wait" initial={false}>
                  <motion.div key={method.number} initial={reduceMotion ? false : { opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -12 }} transition={{ duration: .28, ease: "easeOut" }}>
                    <div className="bn-detail-top"><span>METHOD {method.number} / {method.field.toUpperCase()}</span><Icon size={27} aria-hidden="true" /></div>
                    <h3>{method.question}</h3><p className="bn-detail-description">{method.description}</p>
                    <dl className="bn-detail-facts"><div><dt>Begin with</dt><dd>{method.input}</dd></div><div><dt>Inspect</dt><dd>{method.output}</dd></div></dl>
                    <div className="bn-detail-boundary"><span>READ WITH CARE</span><p>{method.boundary}</p></div>
                    <Link href={method.href} className="bn-button bn-button-primary mt-8">Open {method.title} <ArrowRight size={18} aria-hidden="true" /></Link>
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
            <Link href="/analyze" className="bn-text-link mt-8 inline-flex">Browse every workflow <ArrowUpRight size={17} aria-hidden="true" /></Link>
          </div>
        </section>

        <section id="principles" className="bn-principles-section">
          <div className="mx-auto grid max-w-7xl gap-12 px-5 py-20 sm:px-8 lg:grid-cols-[.85fr_1.15fr] lg:gap-24 lg:py-28">
            <motion.div variants={reveal} initial={reduceMotion ? false : "hidden"} whileInView="visible" viewport={inView} transition={{ duration: .6 }}><p className="bn-kicker">The way we work</p><h2 className="bn-principles-title">Make room for the <em>why</em> behind a result.</h2><p className="mt-6 max-w-[42ch] leading-7 text-text-secondary">An output becomes useful when you can see where it came from and what it cannot tell you.</p></motion.div>
            <div className="bn-principles-list">
              {[
                ["01", "See the measurement", "Tables and figures show values returned by the run. Missing data is never treated as a measured zero."],
                ["02", "Keep the method in view", "Parameters, reference identity, quality checks and run status stay close to the result where available."],
                ["03", "Interpret with limits", "AI explanations are checked against recorded evidence. Grounding is not independent biological validation."],
              ].map(([number, title, copy]) => <motion.div key={number} variants={reveal} initial={reduceMotion ? false : "hidden"} whileInView="visible" viewport={inView} transition={{ duration: .5 }} className="bn-principle"><span>{number}</span><div><h3>{title}</h3><p>{copy}</p></div></motion.div>)}
            </div>
          </div>
        </section>
        <section className="bn-final-cta"><div className="mx-auto flex max-w-7xl flex-col justify-between gap-8 px-5 py-16 sm:px-8 md:flex-row md:items-end"><div><p className="bn-kicker">Your next question</p><h2>Take it into the workspace.</h2><p className="mt-3 text-sm text-text-secondary">Browse methods or start with a guided path.</p></div><Link href="/analyze" className="bn-button bn-button-primary self-start">Open workspace <ArrowUpRight size={18} aria-hidden="true" /></Link></div></section>
      </div>
      <footer className="bn-footer"><div className="mx-auto flex max-w-7xl flex-col justify-between gap-4 px-5 py-8 sm:flex-row sm:px-8"><span>BioNexus · Built at Jamia Millia Islamia</span><div className="flex gap-6"><Link href="/auth">Sign in</Link><span>© 2026 BioNexus</span></div></div></footer>
      <JsonLd data={{ "@context": "https://schema.org", "@type": "WebPage", "@id": WEBPAGE_ID, url: `${SITE_URL}/`, name: "BioNexus — Bioinformatics research workspace", isPartOf: { "@id": WEBSITE_ID }, about: { "@id": SOFTWARE_ID }, mainEntity: { "@type": "SoftwareApplication", "@id": SOFTWARE_ID, name: SITE_NAME, applicationCategory: "ScienceApplication", applicationSubCategory: "Bioinformatics", operatingSystem: "Web", url: `${SITE_URL}/`, description: "Bioinformatics workspace for sequencing, sequence analysis and structural methods with result and provenance views.", featureList: ["NGS exploratory analysis and production planning", "BLAST similarity search", "Molecular docking", "Molecular dynamics", "Scientific result workspace"], creator: { "@id": ORG_ID } } }} />
    </main>
  );
}

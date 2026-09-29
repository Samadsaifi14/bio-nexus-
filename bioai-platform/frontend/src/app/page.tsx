"use client";

import Link from "next/link";
import { ArrowRight, Atom, ChartScatter, Dna, MagnifyingGlass } from "@phosphor-icons/react";
import { JsonLd } from "@/components/seo/JsonLd";
import { ORG_ID, SOFTWARE_ID, SITE_NAME, SITE_URL, WEBPAGE_ID, WEBSITE_ID } from "@/lib/seo";

const methods = [
  { number: "01", title: "NGS analysis", field: "Genomics", href: "/analyze/ngs-v2", icon: Dna,
    description: "Explore sequencing quality, coverage, contamination, identity and variant evidence. Plan production workflows separately from the exploratory preview." },
  { number: "02", title: "BLAST search", field: "Sequence biology", href: "/analyze/blast", icon: MagnifyingGlass,
    description: "Inspect similarity hits with identity, coverage, scores, alignments and reference information." },
  { number: "03", title: "Molecular docking", field: "Structural biology", href: "/analyze/docking", icon: Atom,
    description: "Review poses, affinity estimates and available interaction evidence alongside the method details." },
  { number: "04", title: "Molecular dynamics", field: "Simulation", href: "/analyze/md-v2", icon: ChartScatter,
    description: "Follow preparation, equilibration, production and trajectory quality checks for the hosted implicit-solvent OpenMM workflow." },
];

export default function LandingPage() {
  return (
    <main className="min-h-[100dvh] bg-void text-text-primary">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:bg-accent-cyan focus:px-4 focus:py-3 focus:text-surface-0">Skip to content</a>
      <header className="border-b border-glass-border bg-surface-0">
        <nav aria-label="Main navigation" className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-5 sm:px-8">
          <Link href="/" className="flex items-center gap-3 font-display text-xl text-text-primary">
            <span className="flex h-9 w-9 items-center justify-center rounded-sm bg-accent-cyan text-lg text-surface-0" aria-hidden="true">B</span>BioNexus
          </Link>
          <div className="flex items-center gap-4 sm:gap-7">
            <Link href="#methods" className="hidden min-h-11 items-center text-sm text-text-secondary hover:text-accent-cyan sm:inline-flex">Methods</Link>
            <Link href="#approach" className="hidden min-h-11 items-center text-sm text-text-secondary hover:text-accent-cyan md:inline-flex">Approach</Link>
            <Link href="/auth" className="hidden min-h-11 items-center text-sm text-text-secondary hover:text-accent-cyan md:inline-flex">Sign in</Link>
            <Link href="/analyze" className="inline-flex min-h-11 items-center gap-2 rounded-sm border border-accent-cyan bg-accent-cyan px-4 py-2 text-sm font-semibold text-surface-0 hover:bg-accent-hover">Open workspace <ArrowRight aria-hidden="true" size={16} /></Link>
          </div>
        </nav>
      </header>
      <div id="main-content">
        <section className="mx-auto grid max-w-7xl border-x border-glass-border lg:grid-cols-[minmax(0,1.25fr)_minmax(320px,.75fr)]">
          <div className="flex flex-col justify-between px-5 pb-16 pt-16 sm:px-8 sm:pb-24 sm:pt-24 lg:border-r lg:border-glass-border lg:px-12 lg:pt-28">
            <div>
              <p className="mb-10 font-mono text-xs uppercase tracking-[.18em] text-accent-cyan">Research workspace / 2026</p>
              <h1 className="max-w-[13ch] font-display text-5xl font-normal leading-[1.03] tracking-[-.035em] sm:text-6xl lg:text-[5.4rem]">The evidence is the starting point.</h1>
              <p className="mt-8 max-w-[55ch] text-lg leading-8 text-text-secondary">BioNexus brings sequencing, sequence biology and structural methods into one research workspace. Follow the input, inspect the run, and read the result with its context.</p>
            </div>
            <div className="mt-12 flex flex-wrap items-center gap-5">
              <Link href="/analyze" className="inline-flex min-h-12 items-center gap-3 rounded-sm bg-accent-cyan px-6 py-3 text-sm font-semibold text-surface-0 hover:bg-accent-hover">Explore methods <ArrowRight aria-hidden="true" size={18} /></Link>
              <Link href="/wizard" className="inline-flex min-h-12 items-center gap-2 border-b border-accent-cyan text-sm font-semibold text-accent-cyan hover:text-accent-hover">Start a guided workflow <ArrowRight aria-hidden="true" size={16} /></Link>
            </div>
          </div>
          <aside className="flex flex-col border-t border-glass-border bg-surface-1 px-5 py-10 sm:px-8 lg:border-t-0 lg:px-10 lg:py-16" aria-labelledby="result-anatomy">
            <p className="font-mono text-xs uppercase tracking-[.18em] text-text-muted">Field note 001 / Reading a result</p>
            <h2 id="result-anatomy" className="mt-7 max-w-[15ch] font-display text-3xl leading-tight sm:text-4xl">A result has a history.</h2>
            <p className="mt-5 text-sm leading-7 text-text-secondary">The workspace keeps these layers visible where the method supplies them. This is a workflow outline, without sample measurements.</p>
            <ol className="mt-12 border-t border-glass-border">
              {[
                ["01", "Input", "Start from a sequence, structure or sequencing dataset."],
                ["02", "Method", "Review parameters, run status and quality checks."],
                ["03", "Evidence", "Inspect tables, figures, source data and limits."],
              ].map(([number, title, detail]) => (
                <li key={number} className="grid grid-cols-[2.5rem_1fr] gap-3 border-b border-glass-border py-5">
                  <span className="font-mono text-xs text-accent-cyan">{number}</span>
                  <div><h3 className="font-sans text-sm font-semibold">{title}</h3><p className="mt-1 text-sm leading-6 text-text-secondary">{detail}</p></div>
                </li>
              ))}
            </ol>
            <p className="mt-auto pt-10 text-xs leading-5 text-text-muted">Analysis availability depends on the method, input and connected services. Each run shows its own status.</p>
          </aside>
        </section>
        <section id="methods" className="border-y border-glass-border bg-surface-0">
          <div className="mx-auto max-w-7xl px-5 py-20 sm:px-8 lg:px-12">
            <div className="grid gap-5 md:grid-cols-[1fr_1fr] md:gap-12">
              <div><p className="font-mono text-xs uppercase tracking-[.18em] text-accent-cyan">Method index / 01—04</p><h2 className="mt-5 max-w-[15ch] font-display text-4xl leading-tight sm:text-5xl">Choose the question. See the method.</h2></div>
              <p className="max-w-[54ch] self-end text-base leading-7 text-text-secondary">Each method opens into its own workflow, with the scientific output and available provenance beside it.</p>
            </div>
            <div className="mt-14 border-t border-glass-border">
              {methods.map(({ number, title, field, href, icon: Icon, description }) => (
                <Link key={number} href={href} className="group grid gap-3 border-b border-glass-border px-2 py-7 transition-colors hover:bg-surface-1 sm:grid-cols-[3rem_minmax(0,1fr)_minmax(0,1.2fr)_2rem] sm:items-start sm:gap-6">
                  <span className="font-mono text-xs text-accent-cyan">{number}</span>
                  <div><Icon aria-hidden="true" size={22} className="mb-4 text-accent-cyan" /><h3 className="font-display text-2xl sm:text-3xl">{title}</h3><span className="mt-2 block font-mono text-xs uppercase tracking-wider text-text-muted">{field}</span></div>
                  <p className="max-w-[53ch] text-sm leading-7 text-text-secondary">{description}</p>
                  <ArrowRight aria-hidden="true" size={20} className="text-accent-cyan transition-transform group-hover:translate-x-1" />
                </Link>
              ))}
            </div>
          </div>
        </section>
        <section id="approach" className="mx-auto grid max-w-7xl border-x border-glass-border lg:grid-cols-[1fr_1fr]">
          <div className="px-5 py-20 sm:px-8 lg:border-r lg:border-glass-border lg:px-12"><p className="font-mono text-xs uppercase tracking-[.18em] text-accent-cyan">Approach / Scientific context</p><h2 className="mt-5 max-w-[17ch] font-display text-4xl leading-tight sm:text-5xl">Keep the result connected to the run.</h2></div>
          <div className="border-t border-glass-border px-5 py-12 sm:px-8 lg:border-t-0 lg:px-12 lg:py-20">
            <div className="space-y-8">
              <div><h3 className="font-sans text-base font-semibold">Measurements</h3><p className="mt-2 text-sm leading-7 text-text-secondary">Tables and plots represent values returned by the run. A missing measurement is different from a measured zero.</p></div>
              <div className="border-t border-glass-border pt-8"><h3 className="font-sans text-base font-semibold">Methods and provenance</h3><p className="mt-2 text-sm leading-7 text-text-secondary">Review the engine, parameters, reference identity and run status where those records are available.</p></div>
              <div className="border-t border-glass-border pt-8"><h3 className="font-sans text-base font-semibold">Interpretation with limits</h3><p className="mt-2 text-sm leading-7 text-text-secondary">AI explanations are checked against recorded results. A grounding check does not independently validate a biological conclusion.</p></div>
            </div>
          </div>
        </section>
        <section className="border-t border-glass-border bg-accent-cyan px-5 py-16 text-surface-0 sm:px-8"><div className="mx-auto flex max-w-7xl flex-col justify-between gap-8 md:flex-row md:items-end"><div><p className="font-mono text-xs uppercase tracking-[.18em] text-surface-0/80">Continue / Workspace</p><h2 className="mt-4 max-w-[18ch] font-display text-3xl text-surface-0 sm:text-4xl">Bring your question to the workspace.</h2></div><Link href="/analyze" className="inline-flex min-h-12 items-center gap-3 self-start rounded-sm border border-surface-0 px-5 py-3 text-sm font-semibold text-surface-0 hover:bg-surface-0 hover:text-accent-cyan">Open workspace <ArrowRight aria-hidden="true" size={18} /></Link></div></section>
      </div>
      <footer className="border-t border-glass-border px-5 py-8 text-sm text-text-secondary sm:px-8"><div className="mx-auto flex max-w-7xl flex-col justify-between gap-4 sm:flex-row"><span>BioNexus · Built at Jamia Millia Islamia</span><div className="flex gap-6"><Link href="/auth" className="hover:text-accent-cyan">Sign in</Link><span>© 2026 BioNexus</span></div></div></footer>
      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "WebPage",
          "@id": WEBPAGE_ID,
          url: `${SITE_URL}/`,
          name: "BioNexus — Bioinformatics research workspace",
          isPartOf: { "@id": WEBSITE_ID },
          about: { "@id": SOFTWARE_ID },
          mainEntity: {
            "@type": "SoftwareApplication",
            "@id": SOFTWARE_ID,
            name: SITE_NAME,
            applicationCategory: "ScienceApplication",
            applicationSubCategory: "Bioinformatics",
            operatingSystem: "Web",
            url: `${SITE_URL}/`,
            description:
              "Bioinformatics workspace for sequencing, sequence analysis and structural methods with result and provenance views.",
            featureList: [
              "NGS exploratory analysis and production planning",
              "BLAST similarity search",
              "Molecular docking",
              "Molecular dynamics",
              "Scientific result workspace",
            ],
            creator: { "@id": ORG_ID },
          },
        }}
      />
    </main>
  );
}

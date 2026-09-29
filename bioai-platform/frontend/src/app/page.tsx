"use client";

import Link from "next/link";
import {
  ArrowRight,
  Atom,
  ChartScatter,
  Dna,
  Flask,
  MagnifyingGlass,
  ShieldCheck,
} from "@phosphor-icons/react";
import { JsonLd } from "@/components/seo/JsonLd";
import {
  ORG_ID,
  SOFTWARE_ID,
  SITE_NAME,
  SITE_URL,
  WEBPAGE_ID,
  WEBSITE_ID,
} from "@/lib/seo";

const methods = [
  {
    title: "NGS analysis",
    group: "Genomics",
    href: "/analyze/ngs-v2",
    icon: Dna,
    description:
      "Explore sequencing quality, coverage, contamination, identity and variant evidence. Plan production workflows separately from the exploratory preview.",
  },
  {
    title: "BLAST search",
    group: "Sequence biology",
    href: "/analyze/blast",
    icon: MagnifyingGlass,
    description:
      "Inspect similarity hits with identity, coverage, scores, alignments and reference information.",
  },
  {
    title: "Molecular docking",
    group: "Structural biology",
    href: "/analyze/docking",
    icon: Atom,
    description:
      "Review poses, affinity estimates and available interaction evidence alongside the method details.",
  },
  {
    title: "Molecular dynamics",
    group: "Simulation",
    href: "/analyze/md-v2",
    icon: ChartScatter,
    description:
      "Follow preparation, equilibration, production and trajectory quality checks for the hosted implicit-solvent OpenMM workflow.",
  },
];

const steps = [
  {
    label: "Choose a method",
    detail: "Start from a sequence, structure or sequencing dataset.",
  },
  {
    label: "Inspect the run",
    detail: "See method parameters, status and quality checks.",
  },
  {
    label: "Review the evidence",
    detail: "Read tables and figures with their source data and limits.",
  },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-void text-text-primary">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-accent-cyan focus:px-4 focus:py-3 focus:text-void"
      >
        Skip to content
      </a>
      <header className="border-b border-glass-border bg-surface-0">
        <nav
          aria-label="Main navigation"
          className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-4 sm:px-8"
        >
          <Link
            href="/"
            className="text-lg font-semibold tracking-tight text-text-primary"
          >
            Bio<span className="text-accent-cyan">Nexus</span>
          </Link>
          <div className="flex items-center gap-3 sm:gap-6">
            <Link
              href="#methods"
              className="hidden text-sm text-text-secondary hover:text-text-primary sm:inline"
            >
              Methods
            </Link>
            <Link
              href="#evidence"
              className="hidden text-sm text-text-secondary hover:text-text-primary sm:inline"
            >
              Evidence
            </Link>
            <Link
              href="/auth"
              className="hidden text-sm text-text-secondary hover:text-text-primary md:inline"
            >
              Sign in
            </Link>
            <Link
              href="/analyze"
              className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-accent-cyan px-4 py-2 text-sm font-semibold text-void hover:bg-accent-cyan/85"
            >
              Open workspace <ArrowRight aria-hidden="true" size={16} />
            </Link>
          </div>
        </nav>
      </header>

      <div id="main-content">
        <section className="mx-auto grid max-w-6xl gap-12 px-5 pb-20 pt-20 sm:px-8 md:pb-28 md:pt-28 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
          <div>
            <p className="mb-5 text-sm font-medium text-accent-cyan">
              Bioinformatics research workspace
            </p>
            <h1 className="max-w-[12ch] font-display text-5xl font-semibold leading-[1.05] tracking-tight sm:text-6xl lg:text-7xl">
              Follow the evidence from input to result.
            </h1>
            <p className="mt-7 max-w-[59ch] text-base leading-7 text-text-secondary sm:text-lg">
              Work across sequencing, sequence biology and structural analysis
              in one place. Keep methods, quality checks and source results
              visible as you interpret a finding.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <Link
                href="/analyze"
                className="inline-flex min-h-12 items-center gap-2 rounded-lg bg-accent-cyan px-5 py-3 text-sm font-semibold text-void hover:bg-accent-cyan/85"
              >
                Explore methods <ArrowRight aria-hidden="true" size={17} />
              </Link>
              <Link
                href="/wizard"
                className="inline-flex min-h-12 items-center rounded-lg border border-glass-border px-5 py-3 text-sm font-medium text-text-primary hover:border-accent-cyan/50 hover:bg-surface-1"
              >
                Guided workflow
              </Link>
            </div>
            <p className="mt-6 max-w-[58ch] text-sm leading-6 text-text-muted">
              Analysis availability depends on the method, input and connected
              services. Each run shows its own status and evidence.
            </p>
          </div>
          <div
            className="rounded-2xl border border-glass-border bg-surface-0 p-6 sm:p-8"
            aria-label="How a BioNexus result is organized"
          >
            <div className="flex items-start justify-between gap-4 border-b border-glass-border pb-5">
              <div>
                <p className="text-sm font-semibold text-text-primary">
                  A traceable result
                </p>
                <p className="mt-1 text-sm text-text-muted">
                  Workflow overview · no sample measurements
                </p>
              </div>
              <ShieldCheck
                aria-hidden="true"
                size={24}
                className="shrink-0 text-accent-cyan"
              />
            </div>
            <ol className="mt-5 space-y-5">
              {steps.map((step, index) => (
                <li key={step.label} className="flex gap-4">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-glass-border bg-surface-1 font-mono text-xs text-accent-cyan">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-text-primary">
                      {step.label}
                    </p>
                    <p className="mt-1 text-sm leading-6 text-text-muted">
                      {step.detail}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
            <p className="mt-7 border-t border-glass-border pt-5 text-sm leading-6 text-text-secondary">
              A missing measurement is different from a measured zero. Check the
              run status before interpreting either.
            </p>
          </div>
        </section>

        <section
          id="methods"
          className="border-t border-glass-border bg-surface-0/50 py-20 sm:py-24"
        >
          <div className="mx-auto max-w-6xl px-5 sm:px-8">
            <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
              <div>
                <h2 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">
                  Start with a research question
                </h2>
                <p className="mt-3 max-w-[65ch] text-sm leading-7 text-text-secondary sm:text-base">
                  Choose a method, then inspect the output and its scientific
                  context in the workspace.
                </p>
              </div>
              <Link
                href="/analyze"
                className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-accent-cyan hover:underline"
              >
                View all methods <ArrowRight aria-hidden="true" size={16} />
              </Link>
            </div>
            <div className="mt-10 grid gap-px overflow-hidden rounded-2xl border border-glass-border bg-glass-border md:grid-cols-2">
              {methods.map((method) => {
                const Icon = method.icon;
                return (
                  <Link
                    key={method.title}
                    href={method.href}
                    className="group flex min-h-52 flex-col bg-surface-0 p-6 transition-colors hover:bg-surface-1 sm:p-8"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <Icon
                        aria-hidden="true"
                        size={25}
                        className="text-accent-cyan"
                      />
                      <ArrowRight
                        aria-hidden="true"
                        size={18}
                        className="text-text-muted transition-transform group-hover:translate-x-1 group-hover:text-accent-cyan"
                      />
                    </div>
                    <p className="mt-6 text-xs font-medium text-text-muted">
                      {method.group}
                    </p>
                    <h3 className="mt-2 text-xl font-semibold text-text-primary">
                      {method.title}
                    </h3>
                    <p className="mt-2 max-w-[48ch] text-sm leading-6 text-text-secondary">
                      {method.description}
                    </p>
                  </Link>
                );
              })}
            </div>
          </div>
        </section>

        <section
          id="evidence"
          className="mx-auto grid max-w-6xl gap-10 px-5 py-20 sm:px-8 sm:py-24 lg:grid-cols-[0.8fr_1.2fr] lg:gap-20"
        >
          <div>
            <Flask aria-hidden="true" size={28} className="text-accent-cyan" />
            <h2 className="mt-5 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
              Results with context
            </h2>
            <p className="mt-4 text-base leading-7 text-text-secondary">
              The output matters alongside the method that produced it. Review
              scientific values, quality signals and interpretation in the
              result workspace.
            </p>
          </div>
          <div className="divide-y divide-glass-border border-y border-glass-border">
            <div className="py-5">
              <h3 className="text-base font-semibold">Scientific values</h3>
              <p className="mt-2 text-sm leading-6 text-text-secondary">
                Tables and plots represent the measurements returned by the run.
                Inspect source data when the method supplies it.
              </p>
            </div>
            <div className="py-5">
              <h3 className="text-base font-semibold">
                Methods and provenance
              </h3>
              <p className="mt-2 text-sm leading-6 text-text-secondary">
                Review the engine, parameters, reference identity and run status
                where those records are available.
              </p>
            </div>
            <div className="py-5">
              <h3 className="text-base font-semibold">
                Interpretation with limits
              </h3>
              <p className="mt-2 text-sm leading-6 text-text-secondary">
                AI explanations are checked against recorded results. A
                grounding check does not independently validate a biological
                conclusion.
              </p>
            </div>
          </div>
        </section>
        <section className="border-t border-glass-border bg-surface-0 px-5 py-20 sm:px-8">
          <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-7 md:flex-row md:items-center">
            <div>
              <h2 className="font-display text-3xl font-semibold tracking-tight">
                Bring your question to the workspace.
              </h2>
              <p className="mt-3 text-sm leading-6 text-text-secondary">
                Browse the methods or start with a guided analysis.
              </p>
            </div>
            <Link
              href="/analyze"
              className="inline-flex min-h-12 shrink-0 items-center gap-2 rounded-lg bg-accent-cyan px-5 py-3 text-sm font-semibold text-void hover:bg-accent-cyan/85"
            >
              Open workspace <ArrowRight aria-hidden="true" size={17} />
            </Link>
          </div>
        </section>
      </div>
      <footer className="border-t border-glass-border px-5 py-8 text-sm text-text-muted sm:px-8">
        <div className="mx-auto flex max-w-6xl flex-col justify-between gap-4 sm:flex-row">
          <span>BioNexus · Built at Jamia Millia Islamia</span>
          <div className="flex gap-6">
            <Link href="/auth" className="hover:text-text-primary">
              Sign in
            </Link>
            <span>© 2026 BioNexus</span>
          </div>
        </div>
      </footer>
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

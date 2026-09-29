'use client';

import { FormEvent, useState } from 'react';
import { CircleNotch, MagnifyingGlass, ArrowSquareOut } from '@phosphor-icons/react';
import { PageHeader, BackButton } from '@/components/ui';
import { RnaSeqExpressionWorkspace } from '@/components/results/RnaSeqExpressionWorkspace';
import { RnaSeqProductionSupportCard } from '@/components/results/RnaSeqProductionSupportCard';
import { longApi } from '@/lib/api';

type GeoSeries = { accession: string; title: string; summary: string; sample_count?: number; organism?: string; url: string };

const steps = [
  { title: 'Define the biological question', detail: 'Declare the organism, condition, comparison, biological replicates, experimental units and expected outcome before data selection.', evidence: 'Sample metadata and explicit contrast' },
  { title: 'Find and select RNA-seq data', detail: 'Search GEO for a Series, inspect its sample metadata and SRA links, and choose a study with adequate biological replication. GEO records may contain processed counts; SRA contains raw reads.', evidence: 'GSE accession, sample sheet and source links' },
  { title: 'Acquire FASTQ reads', detail: 'For raw-read analysis, stage SRA runs as paired or single-end FASTQ using SRA Toolkit. Record source accessions and verify checksums and sample identity.', evidence: 'FASTQ files, accessions and SHA-256 checksums' },
  { title: 'Quality control', detail: 'Inspect per-base quality, GC content, adapters, duplication and overrepresented sequences using FastQC and MultiQC before deciding on trimming.', evidence: 'FastQC and MultiQC reports' },
  { title: 'Sequence identity and homology', detail: 'When organism or sample identity needs confirmation, compare representative sequences with an appropriate reference. Identity checks are contextual; they do not replace whole-study read QC.', evidence: 'Search database, version, alignments, coverage and E-values' },
  { title: 'Prepare the reference', detail: 'Select a matching genome FASTA and gene annotation GTF/GFF from the same assembly. Record versions and checksums before building indexes.', evidence: 'Reference build, annotation and index provenance' },
  { title: 'Align or quantify reads', detail: 'Run the pinned nf-core/rnaseq production workflow with a declared aligner and quantifier. Review alignment, assignment and expression outputs when execution completes.', evidence: 'BAM or quantification files and execution trace' },
  { title: 'Generate raw gene counts', detail: 'Export a gene-by-sample raw integer count matrix with matching sample identifiers. Estimated fractional abundances, TPM and FPKM are not raw DESeq2 input.', evidence: 'Count matrix and sample metadata' },
  { title: 'Review sample quality and design', detail: 'Check library sizes, count distributions, replication, batch/confounding, PCA and sample distances before interpreting a contrast.', evidence: 'Design audit, VST PCA and sample-distance heatmap' },
  { title: 'Differential expression', detail: 'Use DESeq2 size factors, dispersion estimates and a negative-binomial model. Report the explicit test-versus-reference contrast, adjusted p-values and log2 fold changes.', evidence: 'All-gene and DEG tables, MA, volcano and expression heatmap' },
];

export default function RnaSeqWorkflow() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<GeoSeries[]>([]);
  const [searched, setSearched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (query.trim().length < 2) return;
    setBusy(true); setError(null); setSearched(false); setResults([]);
    try {
      const response = await longApi.get<{ results: GeoSeries[] }>('/api/ngs/v2/geo/search', { params: { q: query.trim() } });
      setResults(response.data.results);
      setSearched(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'GEO search failed.');
    } finally { setBusy(false); }
  }

  return <div className="scientific-page mx-auto max-w-7xl space-y-6 pb-12">
    <BackButton />
    <PageHeader title="RNA-seq analysis" subtitle="From a biological question and GEO/SRA sources to quality control, raw counts and DESeq2 figures." />

    <section className="data-card p-5">
      <h2 className="text-base font-semibold text-text-primary">Workflow</h2>
      <p className="mt-1 text-xs text-text-muted">Follow the source of each result. Raw FASTQ execution and count-matrix statistics use different inputs; the production runner requires staged files and configured compute.</p>
      <div className="mt-4 flex flex-wrap gap-2 text-xs"><a href="#geo-search" className="rounded border border-glass-border px-3 py-2 text-accent-cyan">Find GEO study</a><a href="#raw-reads" className="rounded border border-glass-border px-3 py-2 text-accent-cyan">Run raw reads</a><a href="#count-matrix" className="rounded border border-glass-border px-3 py-2 text-accent-cyan">Analyze counts</a></div>
      <ol className="mt-4 grid gap-3 md:grid-cols-2">
        {steps.map((step, index) => <li key={step.title} className="rounded-lg border border-glass-border bg-surface-1 p-4">
          <div className="flex gap-3"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-glass-border font-mono text-xs text-accent-cyan">{index + 1}</span><div><h3 className="text-sm font-semibold text-text-primary">{step.title}</h3><p className="mt-1 text-xs leading-5 text-text-secondary">{step.detail}</p><p className="mt-2 text-[11px] text-text-muted">Evidence: {step.evidence}</p></div></div>
        </li>)}
      </ol>
    </section>

    <section id="geo-search" className="data-card p-5">
      <h2 className="text-base font-semibold text-text-primary">Search GEO Series</h2>
      <p className="mt-1 text-xs leading-5 text-text-muted">Search a GSE accession or biological terms. Open the source record to inspect the samples, supplementary files and SRA runs. A GEO Series is not automatically a DESeq2-ready raw count matrix.</p>
      <form onSubmit={search} className="mt-4 flex flex-wrap gap-2"><input aria-label="GEO accession or search terms" value={query} onChange={event => setQuery(event.target.value)} placeholder="GSE accession or RNA-seq topic" className="min-w-0 flex-1 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-sm text-text-primary" /><button disabled={busy || query.trim().length < 2} className="inline-flex items-center gap-2 rounded-lg border border-accent-cyan/30 px-4 py-2 text-xs text-accent-cyan disabled:opacity-40">{busy ? <CircleNotch className="animate-spin" /> : <MagnifyingGlass />} Search</button></form>
      {error && <p role="alert" className="mt-3 text-xs text-error">{error}</p>}
      {searched && !results.length && <p className="mt-3 text-xs text-text-muted">No GEO Series matched this search.</p>}
      <div className="mt-4 space-y-2">{results.map(item => <article key={item.accession} className="rounded-lg border border-glass-border bg-surface-1 p-4"><a href={item.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-sm font-semibold text-accent-cyan">{item.accession} · {item.title} <ArrowSquareOut /></a><p className="mt-1 text-xs text-text-muted">{item.organism || 'Organism unspecified'}{item.sample_count ? ` · ${item.sample_count} samples` : ''}</p><p className="mt-2 text-xs leading-5 text-text-secondary">{item.summary}</p></article>)}</div>
    </section>

    <div id="raw-reads"><RnaSeqProductionSupportCard /></div>
    <div id="count-matrix"><RnaSeqExpressionWorkspace /></div>
  </div>;
}

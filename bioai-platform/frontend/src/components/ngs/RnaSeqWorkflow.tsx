'use client';

import { FormEvent, useState } from 'react';
import { ArrowSquareOut, CircleNotch, DownloadSimple, MagnifyingGlass } from '@phosphor-icons/react';
import { PageHeader, BackButton } from '@/components/ui';
import { RnaSeqExpressionWorkspace } from '@/components/results/RnaSeqExpressionWorkspace';
import { longApi } from '@/lib/api';
import { DurableJobReview } from './RnaSeqRecoveryPanel';
import RnaSeqProductionPanel from './RnaSeqProductionPanel';
import type { RnaSeqExpressionResult } from '@/lib/rnaseqExpressionApi';

type GeoSeries = { accession: string; title: string; summary: string; sample_count?: number; organism?: string; url: string };
type GeoSample = { accession: string; title: string; characteristics: Record<string, string> };
type SeriesDetail = { read_projects?: string[]; organisms?: string[]; experiment_types?: string[]; workflow_issue?: string | null; accession: string; title: string; design: string; samples: GeoSample[]; files: { name: string; url: string; analysis_eligible?: boolean; analysis_issue?: string | null }[] };
type CountColumn = { column: string; gsm: string | null; title: string | null; characteristics: Record<string, string>; library_size: number };
type MatrixPreview = { accession: string; filename: string; source_url: string; source_sha256: string; genes: number; annotation_columns: string[]; columns: CountColumn[]; samples: GeoSample[]; design: string };
type Assignment = { column: string; gsm: string; condition: string; experimental_unit: string };

function message(caught: unknown): string {
  if (caught && typeof caught === 'object' && 'response' in caught) {
    const response = (caught as { response?: { data?: { detail?: unknown } } }).response;
    const detail = response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map(item => typeof item?.msg === 'string' ? item.msg : 'Invalid request').join('; ');
  }
  return caught instanceof Error ? caught.message : 'The request failed. Please try again.';
}

export default function RnaSeqWorkflow() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<GeoSeries[]>([]);
  const [series, setSeries] = useState<SeriesDetail | null>(null);
  const [preview, setPreview] = useState<MatrixPreview | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [reference, setReference] = useState('');
  const [test, setTest] = useState('');
  const [reviewed, setReviewed] = useState(false);
  const [analysis, setAnalysis] = useState<RnaSeqExpressionResult | null>(null);
  const [busy, setBusy] = useState<'search' | 'series' | 'preview' | 'analysis' | 'recovery' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState('');
  const [originEvidence, setOriginEvidence] = useState('');
  const [countMethod, setCountMethod] = useState('');
  const [annotation, setAnnotation] = useState('');
  const [searched, setSearched] = useState(false);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (query.trim().length < 2) return;
    setBusy('search'); setError(null); setSearched(false); setResults([]); setSeries(null); setPreview(null); setAnalysis(null); setJobId('');
    try {
      const response = await longApi.get<{ results: GeoSeries[] }>('/api/ngs/v2/geo/search', { params: { q: query.trim() } });
      setResults(response.data.results); setSearched(true);
    } catch (caught) { setError(message(caught)); }
    finally { setBusy(null); }
  }

  async function inspect(accession: string) {
    setBusy('series'); setError(null); setSeries(null); setPreview(null); setAnalysis(null); setJobId('');
    try {
      const response = await longApi.get<SeriesDetail>(`/api/ngs/v2/geo/series/${encodeURIComponent(accession)}`);
      setSeries(response.data);
    } catch (caught) { setError(message(caught)); }
    finally { setBusy(null); }
  }

  async function inspectMatrix(filename: string) {
    if (!series) return;
    setBusy('preview'); setError(null); setPreview(null); setAnalysis(null); setJobId(''); setReviewed(false);
    try {
      const response = await longApi.post<MatrixPreview>('/api/ngs/v2/geo/preview', { accession: series.accession, filename });
      const next = response.data;
      setPreview(next);
      const groups = next.columns.map(column => column.characteristics.treatment ?? column.characteristics.condition ?? '');
      setAssignments(next.columns.map((column, i) => ({ column: column.column, gsm: column.gsm ?? '', condition: groups[i], experimental_unit: '' })));
      const distinct = [...new Set(groups.filter(Boolean))];
      setReference(distinct.length === 2 ? distinct[0] : '');
      setTest(distinct.length === 2 ? distinct[1] : '');
    } catch (caught) { setError(message(caught)); }
    finally { setBusy(null); }
  }

  async function downloadRecovery() {
    if (!series) return;
    setBusy('recovery'); setError(null);
    try {
      const response = await longApi.get<Blob>(`/api/ngs/v2/geo/series/${encodeURIComponent(series.accession)}/recovery`, { responseType: 'blob' });
      const url = URL.createObjectURL(response.data);
      const anchor = document.createElement('a');
      anchor.href = url; anchor.download = `${series.accession}_expression_recovery.zip`; anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (caught) { setError(message(caught)); }
    finally { setBusy(null); }
  }

  function assign(index: number, patch: Partial<Assignment>) {
    setReviewed(false);
    setAssignments(current => current.map((row, i) => i === index ? { ...row, ...patch } : row));
  }

  const eligibleFiles = series?.files.filter(file => file.analysis_eligible !== false) ?? [];
  const hasNormalizedFiles = series?.files.some(file => /labelled.*(?:FPKM|RPKM|TPM|CPM|NORMALIZED|NORMALISED)/i.test(file.analysis_issue ?? '')) ?? false;

  const mapped = assignments.length > 0 && assignments.every(row => row.gsm && row.condition && row.experimental_unit.trim()) && new Set(assignments.map(row => row.gsm)).size === assignments.length;
  const groupsValid = Boolean(reference && test && reference !== test && assignments.every(row => row.condition === reference || row.condition === test)
    && assignments.filter(row => row.condition === reference).length >= 2 && assignments.filter(row => row.condition === test).length >= 2);
  const assignedCharacteristics = preview ? assignments.map(row => preview.samples.find(sample => sample.accession === row.gsm)?.characteristics ?? {}) : [];
  const technicalKeys = [...new Set(assignedCharacteristics.flatMap(row => Object.keys(row)))]
    .filter(key => /(^|[ _-])(batch|run|lane|plate|operator|site|processing[ _-]?day|extraction[ _-]?batch|kit[ _-]?lot|flow[ _-]?cell)([ _-]|$)/i.test(key));
  const varyingTechnical = technicalKeys.filter(key => new Set(assignedCharacteristics.map(row => row[key] ?? '')).size > 1);

  async function runAnalysis() {
    if (!preview || !mapped || !groupsValid || !reviewed || varyingTechnical.length) return;
    setBusy('analysis'); setError(null); setAnalysis(null); setJobId('');
    try {
      const response = await longApi.post<{ job_id: string }>('/api/ngs/v2/geo/analyze', {
        accession: preview.accession, filename: preview.filename, source_sha256: preview.source_sha256,
        origin: { kind: 'raw_counts', normalization: 'none', evidence: originEvidence, method: countMethod, annotation, reviewed },
        assignments, reference_level: reference, test_level: test, min_count: 10, min_samples: 0, lfc_threshold: 1,
      });
      setJobId(response.data.job_id);
      window.setTimeout(() => document.getElementById('expression-results')?.scrollIntoView({ behavior: 'smooth' }), 100);
    } catch (caught) { setError(message(caught)); }
    finally { setBusy(null); }
  }

  return <div className="scientific-page mx-auto max-w-7xl space-y-6 pb-12">
    <BackButton />
    <PageHeader title="RNA-seq analysis" subtitle="Find published raw gene counts, check the samples and groups, then run DESeq2 and inspect the figures." />
    <div className="rounded-lg border border-glass-border bg-surface-1 p-4 text-xs leading-5 text-text-secondary">This path begins with a published gene count matrix. It does not reprocess SRA FASTQ files or verify extraction, library preparation, strandedness, alignment or read-level QC. GEO sample metadata and the matrix are inspected before the statistical run; each result retains the source link and checksums.</div>

    <section className="data-card p-5">
      <div className="flex items-center gap-3"><span className="font-mono text-accent-cyan">01</span><h2 className="text-base font-semibold text-text-primary">Find a GEO Series</h2></div>
      <form onSubmit={search} className="mt-4 flex flex-wrap gap-2"><input aria-label="GEO accession or search terms" value={query} onChange={event => setQuery(event.target.value)} placeholder="GSE336901 or RNA-seq topic" className="min-w-0 flex-1 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-sm text-text-primary" /><button disabled={!!busy || query.trim().length < 2} className="inline-flex items-center gap-2 rounded-lg border border-accent-cyan/30 px-4 py-2 text-xs text-accent-cyan disabled:opacity-40">{busy === 'search' ? <CircleNotch className="animate-spin" /> : <MagnifyingGlass />} Search</button></form>
      {searched && !results.length && <p className="mt-3 text-xs text-text-muted">No Series matched. Try a GSE accession.</p>}
      <div className="mt-4 space-y-2">{results.map(item => <article key={item.accession} className="rounded-lg border border-glass-border bg-surface-1 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-sm font-semibold text-text-primary">{item.accession} · {item.title}</p><p className="mt-1 text-xs text-text-muted">{item.organism || 'Organism unspecified'}{item.sample_count ? ` · ${item.sample_count} samples` : ''}</p></div><button type="button" disabled={!!busy} onClick={() => inspect(item.accession)} className="rounded border border-accent-cyan/30 px-3 py-2 text-xs text-accent-cyan disabled:opacity-40">{busy === 'series' ? 'Loading…' : 'Inspect files'}</button></div><p className="mt-2 text-xs leading-5 text-text-secondary">{item.summary}</p></article>)}</div>
    </section>

    {series && <section className="data-card p-5">
      <div className="flex items-center gap-3"><span className="font-mono text-accent-cyan">02</span><h2 className="text-base font-semibold text-text-primary">Choose a raw count matrix</h2></div>
      <p className="mt-2 text-xs leading-5 text-text-secondary">{series.design}</p>
      <p className="mt-2 text-xs text-text-muted">{series.organisms?.join(", ") || "Organism not recorded"} · {series.samples.length} GEO samples · {series.files.length} Series and sample supplements · {eligibleFiles.length} candidate count matrices. Only validated raw count matrices can enter DESeq2.</p>
      {!!series.experiment_types?.length && <p className="mt-2 text-xs text-text-muted">Assay: {series.experiment_types.join('; ')}</p>}
      {series.workflow_issue && <p role="status" className="mt-3 rounded border border-warn/25 bg-warn/5 p-3 text-xs leading-5 text-warn">{series.workflow_issue}</p>}
      {!eligibleFiles.length && <div className="mt-3 space-y-2 text-xs leading-5 text-text-secondary">
        <p>{series.workflow_issue ? 'Choose a study with RNA-seq gene counts to continue here.' : 'No supported raw-count candidate is listed. Check the GEO record and sample supplements for a raw gene count matrix.'}</p>
        {!series.workflow_issue && <p>If counts are inside an archive or available from another repository, extract and verify them, then use the manual upload below with sample metadata. If only FASTQ reads are available, alignment or quantification and raw gene counting are required first. Normalized expression and signal tracks cannot substitute for raw counts.</p>}
        <div className="flex flex-wrap gap-3">
          <button type="button" onClick={() => { setQuery('RNA-seq'); document.querySelector<HTMLInputElement>('[aria-label="GEO accession or search terms"]')?.focus(); }} className="text-accent-cyan">Find an RNA-seq study</button>
          {!series.workflow_issue && <button type="button" onClick={() => document.getElementById('expression-results')?.scrollIntoView({ behavior: 'smooth' })} className="text-accent-cyan">Upload verified counts and metadata</button>}
          <a href={`https://www.ncbi.nlm.nih.gov/sra/?term=${series.accession}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-accent-cyan">Inspect SRA reads <ArrowSquareOut /></a>
        </div>
      </div>}
      <div className="mt-3 space-y-2">{series.files.map(file => <div key={file.name} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-glass-border bg-surface-1 p-3"><div><span className="break-all font-mono text-xs text-text-primary">{file.name}</span>{file.analysis_issue && <p className="mt-1 text-xs leading-5 text-warn">{file.analysis_issue}</p>}</div><div className="flex gap-2"><a href={file.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-text-secondary"><DownloadSimple /> Source</a><button type="button" disabled={!!busy || file.analysis_eligible === false} onClick={() => inspectMatrix(file.name)} className="rounded border border-accent-cyan/30 px-3 py-2 text-xs text-accent-cyan disabled:opacity-40">{file.analysis_eligible === false ? 'Not raw counts' : busy === 'preview' ? 'Validating…' : 'Validate counts'}</button></div></div>)}</div>
      {!series.workflow_issue && (hasNormalizedFiles || !eligibleFiles.length) && <div className="mt-4 rounded-lg border border-glass-border p-4 text-xs leading-5 text-text-secondary">
        <h3 className="font-semibold text-text-primary">Recover a usable expression analysis</h3>
        <p className="mt-2">BioNexus checked both Series and sample supplements. {eligibleFiles.length ? 'Validate a raw-count candidate above before choosing an alternative.' : 'No supported candidate is currently listed. The source may contain an archive, raw reads or an author-provided matrix.'} Individual sample files still need a reviewed cohort matrix.</p>
        <ol className="mt-3 list-decimal space-y-2 pl-5">
          <li><strong>Obtain raw counts.</strong> Inspect the source supplements or use the author-request draft in the recovery download. It requests the count matrix, sample mapping, batch information and annotation versions.</li>
          <li><strong>Regenerate from FASTQ.</strong> Use reviewed STAR/HISAT2 alignments with featureCounts, or actual Salmon quantifications with tximport and DESeq2 length corrections. The download includes scripts and metadata templates. These steps run in your own compute/R environment.</li>
          <li><strong>Only FPKM/TPM remains.</strong> The download includes a separate exploratory limma-trend script for reviewed, unlogged continuous expression. It exports its own results and figures. It does not enter the hosted DESeq2 workflow.</li>
        </ol>
        <p className="mt-3 text-warn">Rounding FPKM/TPM or back-calculating approximate counts does not restore the original count model. limma-voom also needs counts. Review normalized-data assumptions before using limma-trend.</p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button type="button" disabled={!!busy} onClick={downloadRecovery} className="inline-flex items-center gap-1 rounded border border-accent-cyan/30 px-3 py-2 text-accent-cyan disabled:opacity-40"><DownloadSimple />{busy === 'recovery' ? 'Preparing recovery package…' : 'Download recovery scripts and templates'}</button>
          {(series.read_projects ?? []).map(project => <a key={project} href={`https://www.ebi.ac.uk/ena/browser/view/${encodeURIComponent(project)}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-accent-cyan">{project} on ENA <ArrowSquareOut /></a>)}
        </div>
      </div>}
      <a href={`https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=${series.accession}`} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs text-accent-cyan">Open GEO source record <ArrowSquareOut /></a>
    </section>}

    {preview && <section className="data-card p-5">
      <div className="flex items-center gap-3"><span className="font-mono text-accent-cyan">03</span><h2 className="text-base font-semibold text-text-primary">Review sample mapping and comparison</h2></div>
      <p className="mt-2 text-xs leading-5 text-text-secondary">{preview.genes.toLocaleString()} genes · {preview.columns.length} count columns · {preview.annotation_columns.length ? `excluded annotation column(s): ${preview.annotation_columns.join(', ')}` : 'no annotation columns excluded'}. Non-negative integer values and unique gene identifiers passed format validation; confirm from the GEO record that these are raw counts.</p>
      <p className="mt-1 break-all font-mono text-[10px] text-text-muted">Source SHA-256: {preview.source_sha256}</p>
      <div className="mt-4 overflow-x-auto rounded-lg border border-glass-border"><table className="w-full text-xs"><thead className="bg-surface-1 text-text-muted"><tr><th className="px-3 py-2 text-left">Count column</th><th className="px-3 py-2 text-left">GEO sample</th><th className="px-3 py-2 text-left">Condition</th><th className="px-3 py-2 text-left">Biological unit</th><th className="px-3 py-2 text-right">Library counts</th></tr></thead><tbody className="divide-y divide-glass-border">{preview.columns.map((column, index) => <tr key={column.column}><td className="max-w-[300px] break-all px-3 py-2 font-mono text-text-secondary">{column.column}</td><td className="px-3 py-2"><select aria-label={`GEO sample for ${column.column}`} value={assignments[index]?.gsm ?? ''} onChange={event => { const sample = preview.samples.find(item => item.accession === event.target.value); assign(index, { gsm: event.target.value, condition: sample?.characteristics.treatment ?? sample?.characteristics.condition ?? assignments[index]?.condition ?? '' }); }} className="scientific-select min-w-[190px]"><option value="">Select sample</option>{preview.samples.map(sample => <option key={sample.accession} value={sample.accession}>{sample.accession} · {sample.title}</option>)}</select><p className="mt-1 max-w-sm text-[10px] leading-4 text-text-muted">{Object.entries(preview.samples.find(item => item.accession === assignments[index]?.gsm)?.characteristics ?? {}).map(([key, value]) => `${key}: ${value}`).join(' · ') || 'No characteristics recorded'}</p></td><td className="px-3 py-2"><input aria-label={`Condition for ${column.column}`} value={assignments[index]?.condition ?? ''} onChange={event => assign(index, { condition: event.target.value })} className="w-32 rounded border border-glass-border bg-surface-1 px-2 py-2 text-xs text-text-primary" /></td><td className="px-3 py-2"><input aria-label={`Biological unit for ${column.column}`} value={assignments[index]?.experimental_unit ?? ''} onChange={event => assign(index, { experimental_unit: event.target.value })} placeholder="Reviewed unit ID" className="scientific-select" /></td><td className="px-3 py-2 text-right font-mono text-text-secondary">{column.library_size.toLocaleString()}</td></tr>)}</tbody></table></div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="text-xs text-text-muted">Reference group<input value={reference} onChange={event => { setReviewed(false); setReference(event.target.value); }} className="mt-1 w-full rounded border border-glass-border bg-surface-1 px-3 py-2 text-text-primary" /></label><label className="text-xs text-text-muted">Test group<input value={test} onChange={event => { setReviewed(false); setTest(event.target.value); }} className="mt-1 w-full rounded border border-glass-border bg-surface-1 px-3 py-2 text-text-primary" /></label></div>
      <p className="mt-3 text-xs text-text-muted">Positive log2 fold change means higher expression in the test group. Verify that each matrix column matches its GEO sample and that the condition is biologically correct.</p>
      <p className="mt-2 text-xs text-text-muted">The automatic model includes condition only. Other GEO characteristics are shown for review but are not adjusted in this comparison.</p>
      {varyingTechnical.length > 0 && <p className="mt-2 rounded border border-warn/25 bg-warn/5 p-3 text-xs leading-5 text-warn">Varying recorded technical variables: {varyingTechnical.join(', ')}. This automatic comparison cannot adjust for them. Use the source matrix and the manual count upload with reviewed sample metadata and explicit covariates.</p>}
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <label className="text-xs">Evidence that the matrix is unnormalized raw counts<input value={originEvidence} onChange={event => { setReviewed(false); setOriginEvidence(event.target.value); }} placeholder="Source URL and methods statement" className="scientific-select mt-1 w-full" /></label>
        <label className="text-xs">Counting method<input value={countMethod} onChange={event => { setReviewed(false); setCountMethod(event.target.value); }} className="scientific-select mt-1 w-full" /></label>
        <label className="text-xs">Reference / annotation release<input value={annotation} onChange={event => { setReviewed(false); setAnnotation(event.target.value); }} className="scientific-select mt-1 w-full" /></label>
      </div>
      <p className="mt-2 text-xs text-text-muted">GSM accessions identify deposited samples, not independent biological units. Count origin is analyst attestation; integer formatting is not independent validation.</p>
      <label className="mt-4 flex items-center gap-2 text-xs text-text-secondary"><input type="checkbox" checked={reviewed} onChange={event => setReviewed(event.target.checked)} /> I reviewed the GEO source, sample identities, biological units, group assignments and recorded batch variables</label>
      {(!mapped || !groupsValid) && <p className="mt-2 text-xs text-warn">Map each column to a different GEO sample and assign at least two samples to each of the two groups.</p>}
      <button type="button" disabled={!mapped || !groupsValid || !reviewed || originEvidence.length < 10 || countMethod.length < 2 || annotation.length < 2 || !!busy || varyingTechnical.length > 0} onClick={runAnalysis} className="mt-4 rounded-lg border border-accent-cyan/30 bg-accent-cyan/10 px-4 py-2.5 text-xs font-semibold text-accent-cyan disabled:opacity-40">{busy === 'analysis' ? 'Submitting QC…' : 'Generate PCA and QC for review'}</button>
    </section>}

    {error && <div role="alert" className="rounded-lg border border-error/25 bg-error/10 p-4 text-sm text-error">{error}</div>}

    {jobId && <DurableJobReview jobId={jobId} onResult={setAnalysis} />}
    <RnaSeqProductionPanel />
    <div id="expression-results"><RnaSeqExpressionWorkspace externalResult={analysis} /></div>
  </div>;
}

'use client';

import { FormEvent, useEffect, useState } from 'react';
import { CircleNotch, ArrowSquareOut } from '@phosphor-icons/react';
import { PageHeader, BackButton } from '@/components/ui';
import { RnaSeqExpressionWorkspace } from '@/components/results/RnaSeqExpressionWorkspace';
import { longApi } from '@/lib/api';
import { parseExpressionResult, type RnaSeqExpressionResult } from '@/lib/rnaseqExpressionApi';
import RnaSeqProductionPanel from './RnaSeqProductionPanel';

type Series = { accession: string; title: string };
type Prepared = {
  status: 'ready' | 'choose_matrix' | 'choose_comparison' | 'no_counts';
  accession?: string; title?: string; filename?: string; message?: string;
  files?: { name: string }[]; comparisons?: { key: string; levels: string[] }[];
  genes?: number; samples?: number; source_sha256?: string; source_record_sha256?: string;
  group_key?: string; reference_level?: string; test_level?: string;
  groups?: { name: string; samples: number }[]; covariates?: string[];
};
type Job = { state: string; error?: string; result?: unknown; progress?: { step: number; status: string }[] };
const DEMO = { accession: 'GSE336901', filename: 'GSE336901_Fig3_FFPE_raw_counts_matrix_GEO.csv.gz' };
const STEPS = ['Inspect counts and library sizes', 'Build sample metadata', 'Construct DESeq2 object and design',
  'Pre-filter low-count genes', 'Normalize counts', 'PCA and sample-distance QC',
  'Fit, shrink and export differential genes', 'Volcano and MA plots', 'Expression heatmap', 'Functional enrichment'];
function errorMessage(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(item => typeof item?.msg === 'string' ? item.msg : 'Invalid request').join('; ');
  return error instanceof Error ? error.message : 'Could not complete the request. Please retry.';
}

export default function RnaSeqWorkflow() {
  const [query, setQuery] = useState(DEMO.accession);
  const [results, setResults] = useState<Series[]>([]);
  const [prepared, setPrepared] = useState<Prepared | null>(null);
  const [selectedAccession, setSelectedAccession] = useState('');
  const [analysis, setAnalysis] = useState<RnaSeqExpressionResult | null>(null);
  const [jobId, setJobId] = useState('');
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [pollError, setPollError] = useState('');
  const [resume, setResume] = useState('');

  useEffect(() => {
    if (!jobId) return;
    let active = true;
    let terminal = false;
    let inFlight = false;
    const refresh = async () => {
      if (terminal || inFlight) return;
      inFlight = true;
      try {
        const response = await longApi.get<Job>(`/api/ngs/v2/rnaseq/recovery/jobs/${encodeURIComponent(jobId)}`);
        if (!active) return;
        const next = response.data;
        if (!next || typeof next.state !== 'string') throw new Error('The analysis service returned an invalid job response.');
        setJob(next); setPollError('');
        if (next.state === 'SUCCEEDED' && next.result) {
          setAnalysis(parseExpressionResult(next.result)); terminal = true;
          window.setTimeout(() => document.getElementById('expression-results')?.scrollIntoView({ behavior: 'smooth' }), 100);
        } else if (['FAILED', 'CANCELLED', 'QC_REVIEW'].includes(next.state)) terminal = true;
      } catch (caught) { if (active) setPollError(errorMessage(caught)); }
      finally { inFlight = false; }
    };
    void refresh(); const timer = window.setInterval(refresh, 2000);
    return () => { active = false; window.clearInterval(timer); };
  }, [jobId]);

  async function run(accession: string, filename?: string, groupKey?: string, liveDemo = false) {
    setBusy(true); setError(''); setPrepared(null); setAnalysis(null); setJobId(''); setJob(null); setPollError('');
    setSelectedAccession(accession);
    try {
      const response = await longApi.post<Prepared>('/api/ngs/v2/geo/prepare', { accession, filename, group_key: groupKey });
      const next = response.data;
      setPrepared(next);
      if (next.status === 'ready') {
        setJob({ state: 'SUBMITTING' });
        const submitted = await longApi.post<{ job_id?: string; result?: unknown }>('/api/ngs/v2/geo/run', {
          accession, filename: next.filename, group_key: next.group_key, require_durable: liveDemo,
          source_sha256: next.source_sha256, source_record_sha256: next.source_record_sha256,
        });
        if (submitted.data.result) {
          setAnalysis(parseExpressionResult(submitted.data.result)); setJob({ state: 'SUCCEEDED' });
          window.setTimeout(() => document.getElementById('expression-results')?.scrollIntoView({ behavior: 'smooth' }), 100);
        } else if (submitted.data.job_id) {
          setJobId(submitted.data.job_id); setJob({ state: 'QUEUED' });
        } else throw new Error('The analysis service did not return a result or job ID.');
      }
    } catch (caught) { setError(errorMessage(caught)); setJob({ state: 'FAILED' }); }
    finally { setBusy(false); }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = query.trim();
    if (/^GSE\d+$/i.test(value)) { setResults([]); await run(value.toUpperCase()); return; }
    setBusy(true); setError(''); setResults([]); setPrepared(null); setAnalysis(null); setJobId(''); setJob(null);
    try {
      const response = await longApi.get<{ results: Series[] }>('/api/ngs/v2/geo/search', { params: { q: value } });
      setResults(response.data.results);
      if (!response.data.results.length) setError('No GEO study matched. Try a GSE accession or another search term.');
    } catch (caught) { setError(errorMessage(caught)); } finally { setBusy(false); }
  }
  const running = busy || Boolean(jobId && !['SUCCEEDED', 'FAILED', 'CANCELLED', 'QC_REVIEW'].includes(job?.state ?? ''));
  return <div className="scientific-page mx-auto max-w-7xl space-y-6 pb-12">
    <BackButton />
    <PageHeader title="RNA-seq analysis" subtitle="Enter a GEO accession. BioNexus retrieves the counts, prepares the samples and runs the ten-step analysis in R." />
    <section className="data-card p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h2 className="text-sm font-semibold">Live RNA-seq example · {DEMO.accession}</h2><p className="text-xs text-text-secondary">Published FFPE raw counts. Fetch the study and submit a fresh R/DESeq2 job; figures are computed from these inputs.</p></div>
        <button type="button" disabled={running} onClick={() => { setQuery(DEMO.accession); setResults([]); void run(DEMO.accession, DEMO.filename, undefined, true); }} className="btn-primary disabled:opacity-40">Run live example</button>
      </div>
      <form onSubmit={submit} className="flex flex-wrap gap-3">
        <input aria-label="GEO accession or search terms" value={query} onChange={event => setQuery(event.target.value)} placeholder="GSE accession or RNA-seq study" className="min-w-0 flex-1 rounded-lg border border-glass-border bg-surface-1 px-3 py-3 text-sm" />
        <button disabled={running || query.trim().length < 2} className="btn-primary inline-flex items-center gap-2 disabled:opacity-40">{running && <CircleNotch className="animate-spin" />} {busy ? 'Preparing study…' : running ? 'Analysis running…' : 'Run analysis'}</button>
      </form>
      <p className="text-xs leading-5 text-text-secondary">Counts and sample information come from GEO. A clear two-group study runs automatically. If the study contains several matrices or comparisons, choose the one you want below.</p>
      {results.map(item => <div key={item.accession} className="flex flex-wrap items-center justify-between gap-3 border-t border-glass-border pt-3"><span className="text-sm">{item.accession} · {item.title}</span><button disabled={running} onClick={() => run(item.accession)} className="btn-primary disabled:opacity-40">Analyze study</button></div>)}
      {prepared?.status === 'choose_matrix' && <fieldset className="space-y-3"><legend className="text-sm font-semibold">Which count matrix would you like to analyze?</legend>{prepared.files?.map(file => <button key={file.name} disabled={running} onClick={() => run(selectedAccession, file.name)} className="block text-left text-sm text-accent-cyan disabled:opacity-40">{file.name}</button>)}</fieldset>}
      {prepared?.status === 'choose_comparison' && <fieldset className="space-y-3"><legend className="text-sm font-semibold">What would you like to compare?</legend>{prepared.comparisons?.map(choice => <button key={choice.key} disabled={running} onClick={() => run(selectedAccession, prepared.filename, choice.key)} className="block text-left text-sm text-accent-cyan disabled:opacity-40">{choice.key}: {choice.levels.join(' versus ')}</button>)}</fieldset>}
      {prepared?.status === 'no_counts' && <p role="status" className="text-sm text-warn">{prepared.message}</p>}
      {prepared?.status === 'ready' && <div className="space-y-2 text-sm">
        <p className="font-semibold">{selectedAccession} · {prepared.title}</p>
        <p>{prepared.genes?.toLocaleString()} genes · {prepared.samples} samples · {prepared.groups?.map(group => `${group.name} (${group.samples})`).join(' versus ')}</p>
        <p className="text-xs text-text-secondary">Reference: {prepared.reference_level}. Positive fold changes indicate higher expression in {prepared.test_level}.{Boolean(prepared.covariates?.length) && ` Adjusting for ${prepared.covariates?.join(', ')}.`}</p>
        <a href={`https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=${selectedAccession}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-accent-cyan">GEO source <ArrowSquareOut /></a>
      </div>}
    </section>
    {(busy || prepared?.status === 'ready' || jobId) && <section className="data-card space-y-4 p-5" aria-live="polite">
      <h2 className="font-semibold">Ten-step analysis</h2>
      <p className="text-xs text-text-muted">Stage updates come from the R worker and refresh every two seconds. No simulated percentages.</p>
      <p className="text-sm text-text-secondary">{job?.state === 'RUNNING' ? 'R is checking the design, normalizing counts and generating the figures. This can take several minutes. Keep this page open until the results appear.' : busy ? 'Retrieving and validating the published counts and sample metadata…' : job?.state === 'QUEUED' ? 'Inputs are retained. Waiting for the R worker…' : job?.state === 'SUCCEEDED' ? 'Analysis complete. Your figures and tables are below.' : job?.state === 'FAILED' ? 'The analysis stopped. See the reason below.' : 'Study prepared.'}</p>
      <ol className="grid gap-3 sm:grid-cols-2">{STEPS.map((label, index) => {
        const event = job?.progress?.filter(item => item.step === index + 1).at(-1);
        const complete = job?.state === 'SUCCEEDED' && index < 9 || prepared?.status === 'ready' && index < 2;
        const status = event ? (event.status === 'running' && ['FAILED', 'CANCELLED'].includes(job?.state ?? '') ? 'Stopped' : event.status === 'running' ? 'Running in R' : event.status === 'unavailable' ? 'Not available for this run' : event.status === 'complete' ? 'Complete' : 'Stopped') : index === 9 && analysis ? analysis.summary.enrichment?.status?.replaceAll('_', ' ').toLowerCase() ?? 'not available' : complete ? 'Complete' : job?.state === 'FAILED' ? 'Stopped' : job?.state === 'RUNNING' ? 'R analysis in progress' : 'Pending';
        return <li key={label} className="flex gap-3 text-sm"><span className="font-mono text-accent-cyan">{String(index + 1).padStart(2, '0')}</span><div>{label}<p className="text-xs text-text-muted">{status}</p></div></li>;
      })}</ol>
      {jobId && <p className="break-all text-xs text-text-muted">Resume ID: {jobId}</p>}
      {job?.error && <p role="alert" className="text-sm text-error">{job.error}</p>}
      {pollError && <p role="alert" className="text-sm text-error">{pollError} Your job is retained; status will retry automatically.</p>}
    </section>}
    {error && <p role="alert" className="data-card p-4 text-sm text-error">{error}</p>}
    {job?.state === 'QC_REVIEW' && <p role="status" className="text-sm text-warn">This is an older job awaiting QC approval. Open advanced recovery below and resume it there.</p>}
    {analysis && <section className="data-card p-5 space-y-2">
      <h2 className="font-semibold">Continue with gene-set and pathway enrichment</h2>
      <p className="text-sm text-text-secondary">Use the differential-expression table, tested-gene background and recorded organism from this run. GO is included when available; continue with preranked GSEA or a supplied pathway gene-set collection without copying gene lists.</p>
      <button type="button" className="btn-primary" onClick={() => { const options = document.getElementById('rnaseq-enrichment-options') as HTMLDetailsElement | null; if (options) { options.open = true; options.scrollIntoView({ behavior: 'smooth' }); } }}>Open enrichment options</button>
    </section>}
    <div id="expression-results"><RnaSeqExpressionWorkspace externalResult={analysis} /></div>
    <details className="data-card p-5"><summary className="cursor-pointer text-sm">Advanced: recover a saved analysis or process raw sequencing reads</summary>
      <form className="mt-4 flex flex-wrap gap-2" onSubmit={event => { event.preventDefault(); setAnalysis(null); setPrepared(null); setJob(null); setJobId(resume.trim()); }}><input aria-label="Saved RNA-seq job ID" value={resume} onChange={event => setResume(event.target.value)} placeholder="Saved job ID" className="scientific-select flex-1" /><button disabled={!resume.trim() || running} className="btn-primary disabled:opacity-40">Resume analysis</button></form>
      <RnaSeqProductionPanel />
    </details>
  </div>;
}

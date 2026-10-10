'use client';

import { useEffect, useState } from 'react';
import { longApi } from '@/lib/api';
import { parseExpressionResult, type RnaSeqExpressionResult, type RnaSeqArtifact } from '@/lib/rnaseqExpressionApi';

type Job = { job_id: string; state: string; phase: string; error?: string; result?: { run_id: string; checkpoint_sha256?: string; artifacts: RnaSeqArtifact[] } };

export function recoveryError(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  return error instanceof Error ? error.message : 'The request failed.';
}

export function DurableJobReview({ jobId, onResult }: { jobId: string; onResult: (result: RnaSeqExpressionResult) => void }) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState('');
  const [reviewed, setReviewed] = useState(false);
  useEffect(() => {
    let active = true; let terminal = false;
    const refresh = async () => {
      if (terminal) return;
      try {
        const response = await longApi.get<Job>(`/api/ngs/v2/rnaseq/recovery/jobs/${encodeURIComponent(jobId)}`);
        if (!active) return;
        const next = response.data;
        if (!next || typeof next.state !== 'string') throw new Error('Invalid job response');
        setJob(next); setError('');
        if (next.state === 'SUCCEEDED' && next.result) { onResult(parseExpressionResult(next.result)); terminal = true; }
        if (next.state === 'FAILED') terminal = true;
      } catch (caught) { if (active) setError(recoveryError(caught)); }
    };
    void refresh(); const timer = window.setInterval(refresh, 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, [jobId, onResult]);
  async function approve() {
    try {
      await longApi.post(`/api/ngs/v2/rnaseq/recovery/jobs/${encodeURIComponent(jobId)}/approve`, {
        reviewed, checkpoint_sha256: job?.result?.checkpoint_sha256,
      });
      setJob(current => current ? { ...current, state: 'QUEUED', phase: 'infer' } : current);
    } catch (caught) { setError(recoveryError(caught)); }
  }
  return <section className="data-card space-y-3 p-5" aria-live="polite">
    <h3 className="font-semibold">Retained analysis · {job?.state ?? 'Loading'}</h3>
    <p className="break-all font-mono text-xs">Job: {jobId}</p>
    <p className="text-xs text-text-muted">Keep this ID to resume after closing the browser. Inputs and the reviewed checkpoint are retained privately on the configured worker volume.</p>
    {job?.error && <p role="alert" className="text-error">{job.error}</p>}
    {error && <p role="alert" className="text-error">{error}</p>}
    {job?.state === 'QC_REVIEW' && <>
      <p className="text-sm">Review the PCA, sample distances and design audit before differential testing. Check sample identity, outliers, biological independence and batch patterns.</p>
      <div className="grid gap-4 md:grid-cols-2">{(job.result?.artifacts ?? []).filter(item => ['pca.svg', 'sample_distance_heatmap.svg'].includes(item.name)).map(item => <figure key={item.name}><img src={item.url} alt={item.name === 'pca.svg' ? 'PCA from the retained VST counts' : 'VST sample distance heatmap'} className="w-full bg-white" /><figcaption className="text-xs">{item.name}</figcaption></figure>)}</div>
      <div className="flex flex-wrap gap-3">{(job.result?.artifacts ?? []).filter(item => item.name.endsWith('.tsv') || item.name === 'design_audit.json').map(item => <a key={item.name} href={item.url} target="_blank" rel="noreferrer" className="text-xs text-accent-cyan">{item.name}</a>)}</div>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={reviewed} onChange={event => setReviewed(event.target.checked)} />I reviewed QC and the experimental design and approve this checkpoint for inference.</label>
      <button type="button" disabled={!reviewed} onClick={approve} className="btn-primary disabled:opacity-40">Run differential testing from reviewed QC</button>
    </>}
  </section>;
}

export default function RnaSeqRecoveryPanel({ onResult }: { onResult: (result: RnaSeqExpressionResult) => void }) {
  const [geoAccession, setGeoAccession] = useState('');
  const [geoFiles, setGeoFiles] = useState<{ name: string; url: string }[]>([]);
  const [geoSelected, setGeoSelected] = useState<string[]>([]);
  const [geoChecksums, setGeoChecksums] = useState<Record<string, string> | null>(null);
  const [kind, setKind] = useState('raw_counts');
  const [data, setData] = useState<File | null>(null);
  const [metadata, setMetadata] = useState<File | null>(null);
  const [tx2gene, setTx2gene] = useState<File | null>(null);
  const [members, setMembers] = useState<{ name: string; count_issue?: string; salmon_candidate: boolean }[]>([]);
  const [matrixMember, setMatrixMember] = useState('');
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [assemble, setAssemble] = useState(false);
  const [reference, setReference] = useState('');
  const [test, setTest] = useState('');
  const [covariates, setCovariates] = useState('');
  const [evidence, setEvidence] = useState('');
  const [method, setMethod] = useState('');
  const [annotation, setAnnotation] = useState('');
  const [reviewed, setReviewed] = useState(false);
  const [jobId, setJobId] = useState('');
  const [resume, setResume] = useState('');
  const [productionId, setProductionId] = useState('');
  const [productionMapping, setProductionMapping] = useState('');
  const [readQc, setReadQc] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [capabilities, setCapabilities] = useState<{ counts?: { available: boolean; missing: string[] }; salmon?: { available: boolean; missing: string[] } } | null>(null);
  useEffect(() => { longApi.get('/api/ngs/v2/rnaseq/recovery/capabilities').then(response => setCapabilities(response.data)).catch(caught => setError(recoveryError(caught))); }, []);
  const inputClass = 'mt-1 w-full rounded border border-glass-border bg-surface-1 px-3 py-2 text-sm';
  async function discoverGeo() {
    setBusy(true); setError(''); setGeoChecksums(null); setMembers([]);
    try {
      const response = await longApi.get(`/api/ngs/v2/geo/series/${encodeURIComponent(geoAccession.trim())}`);
      if (response.data.workflow_issue) throw new Error(response.data.workflow_issue);
      setGeoFiles(response.data.files); setGeoSelected([]);
    } catch (caught) { setError(recoveryError(caught)); } finally { setBusy(false); }
  }
  async function inspectGeo() {
    setBusy(true); setError('');
    try {
      const response = await longApi.post('/api/ngs/v2/rnaseq/recovery/geo/inspect', { accession: geoAccession, filenames: geoSelected });
      setMembers(response.data.members); setGeoChecksums(response.data.source.source_sha256); setMapping({}); setMatrixMember('');
    } catch (caught) { setError(recoveryError(caught)); } finally { setBusy(false); }
  }
  async function inspect() {
    if (!data) return;
    setBusy(true); setError('');
    try { const form = new FormData(); form.append('archive', data); const response = await longApi.post('/api/ngs/v2/rnaseq/recovery/inspect', form); setMembers(response.data.members); }
    catch (caught) { setError(recoveryError(caught)); } finally { setBusy(false); }
  }
  async function submit(production = false) {
    if (!metadata || !reviewed) return;
    setBusy(true); setError('');
    try {
      const form = new FormData();
      form.append('metadata', metadata);
      form.append('origin', JSON.stringify({ kind, normalization: 'none', evidence, method, annotation, reviewed }));
      form.append('parameters', JSON.stringify({ reference_level: reference, test_level: test, min_samples: 0, covariates: covariates.split(',').map(value => value.trim()).filter(Boolean) }));
      if (tx2gene) form.append('tx2gene', tx2gene);
      if (production) {
        form.append('mapping', productionMapping); form.append('read_qc_reviewed', String(readQc));
      } else if (geoChecksums) {
        form.append('source_selection', JSON.stringify({ accession: geoAccession, filenames: geoSelected }));
        form.append('source_sha256', JSON.stringify(geoChecksums));
        form.append('matrix_member', matrixMember);
        form.append('mapping', JSON.stringify(Object.fromEntries(Object.entries(mapping).filter(([, sample]) => sample.trim()))));
      } else {
        if (!data) throw new Error('Select the count matrix or quantification archive.');
        form.append('data', data); form.append('matrix_member', matrixMember);
        form.append('mapping', JSON.stringify(Object.fromEntries(Object.entries(mapping).filter(([, sample]) => sample.trim()))));
      }
      const url = production ? `/api/ngs/v2/rnaseq/recovery/production/${encodeURIComponent(productionId)}/import` : geoChecksums ? '/api/ngs/v2/rnaseq/recovery/geo/submit' : '/api/ngs/v2/rnaseq/recovery/submit';
      const response = await longApi.post(url, form); setJobId(response.data.job_id);
    } catch (caught) { setError(recoveryError(caught)); } finally { setBusy(false); }
  }
  const readiness = kind === 'salmon' ? capabilities?.salmon : capabilities?.counts;
  return <section className="data-card space-y-4 p-5">
    <h2 className="text-lg font-semibold">Recover counts or import quantifications</h2>
    <p className="text-sm text-text-secondary">Retrieve deposited raw counts first. When only normalized expression is available, use raw reads with the production workflow below. FPKM/TPM is never rounded into counts.</p>
    {readiness && !readiness.available && <p role="status" className="text-sm text-warn">Execution unavailable: {readiness.missing.join(', ')}. A persistent worker and private storage must be configured before submission.</p>}
    <details className="space-y-3"><summary className="cursor-pointer text-sm">Retrieve raw counts from GEO supplements or archives</summary>
      <label className="block text-xs">GEO Series accession<input value={geoAccession} onChange={event => { setGeoAccession(event.target.value); setGeoChecksums(null); setGeoFiles([]); setMembers([]); }} placeholder="GSE…" className={inputClass} /></label>
      <button type="button" disabled={busy || !geoAccession} onClick={discoverGeo} className="btn-secondary">Find source supplements</button>
      {geoFiles.map(file => <label key={file.name} className="flex gap-2 text-xs"><input type="checkbox" checked={geoSelected.includes(file.name)} onChange={event => { setGeoChecksums(null); setMembers([]); setGeoSelected(current => event.target.checked ? [...current, file.name] : current.filter(name => name !== file.name)); }} />{file.name}</label>)}
      <button type="button" disabled={busy || !geoSelected.length} onClick={inspectGeo} className="btn-secondary">Retrieve and inspect selected files</button>
      {geoChecksums && <p className="text-xs">Sources retrieved and checksummed. Select the matrix or map each sample file below. Files are fetched again and checked for changes on submission.</p>}
    </details>
    <label className="block text-xs">Input type<select value={kind} onChange={event => { setKind(event.target.value); setMapping({}); }} className={inputClass}><option value="raw_counts">Raw gene counts</option><option value="salmon">Salmon quant.sf + matching transcript annotation</option></select></label>
    <div className="grid gap-4 md:grid-cols-2">
      <label className="text-xs">Count matrix or ZIP/TAR archive (60 MB maximum)<input type="file" onChange={event => { setData(event.target.files?.[0] ?? null); setGeoChecksums(null); setMembers([]); setMapping({}); setMatrixMember(''); }} className={inputClass} /></label>
      <label className="text-xs">Reviewed metadata TSV: sample, condition, experimental_unit; optional covariates<input type="file" accept=".tsv,.txt" onChange={event => setMetadata(event.target.files?.[0] ?? null)} className={inputClass} /></label>
      {kind === 'salmon' && <label className="text-xs">Matching tx2gene TSV (transcript and gene columns)<input type="file" accept=".tsv,.txt" onChange={event => setTx2gene(event.target.files?.[0] ?? null)} className={inputClass} /></label>}
    </div>
    <a className="text-xs text-accent-cyan" download="metadata.tsv" href={'data:text/tab-separated-values;charset=utf-8,' + encodeURIComponent('sample\tcondition\texperimental_unit\ncontrol1\tcontrol\tunit1\ncontrol2\tcontrol\tunit2\ntest1\ttest\tunit3\ntest2\ttest\tunit4\n')}>Download metadata example</a>
    <button type="button" disabled={!data || busy} onClick={inspect} className="btn-secondary">Inspect archive members</button>
    {members.length > 0 && <>
      {kind === 'raw_counts' && <label className="flex gap-2 text-sm"><input type="checkbox" checked={assemble} onChange={event => { setAssemble(event.target.checked); setMapping({}); }} />Assemble individual sample counts with identical gene sets</label>}
      {kind === 'raw_counts' && !assemble ? <label className="block text-xs">Choose the cohort matrix<select value={matrixMember} onChange={event => setMatrixMember(event.target.value)} className={inputClass}><option value="">Select matrix</option>{members.filter(member => !member.count_issue).map(member => <option key={member.name}>{member.name}</option>)}</select></label> : <div className="space-y-2">{members.filter(member => kind === 'salmon' ? member.salmon_candidate : !member.count_issue).map(member => <label key={member.name} className="block text-xs">{member.name}<input value={mapping[member.name] ?? ''} placeholder="Sample ID from metadata; leave unused files blank" onChange={event => setMapping(current => ({ ...current, [member.name]: event.target.value }))} className={inputClass} /></label>)}</div>}
    </>}
    <div className="grid gap-3 md:grid-cols-2">
      <label className="text-xs">Reference group<input value={reference} onChange={event => setReference(event.target.value)} className={inputClass} /></label>
      <label className="text-xs">Test group<input value={test} onChange={event => setTest(event.target.value)} className={inputClass} /></label>
      <label className="text-xs">Covariates (comma separated)<input value={covariates} onChange={event => setCovariates(event.target.value)} className={inputClass} /></label>
      <label className="text-xs">Counting or quantification method<input value={method} onChange={event => setMethod(event.target.value)} className={inputClass} /></label>
      <label className="text-xs">Reference and annotation release<input value={annotation} onChange={event => setAnnotation(event.target.value)} className={inputClass} /></label>
      <label className="text-xs">Source evidence for unnormalized counts / original quantifier outputs<input value={evidence} onChange={event => setEvidence(event.target.value)} placeholder="Source URL and methods statement" className={inputClass} /></label>
    </div>
    <label className="flex gap-2 text-sm"><input type="checkbox" checked={reviewed} onChange={event => setReviewed(event.target.checked)} />I reviewed count origin, common annotation, sample mapping and biological units. This is analyst attestation, not independent validation.</label>
    <button type="button" disabled={busy || !reviewed || (!data && !geoChecksums) || !metadata || !readiness?.available} onClick={() => submit()} className="btn-primary disabled:opacity-40">Generate QC for review</button>
    {kind === 'salmon' && <details className="space-y-3"><summary className="cursor-pointer text-sm">Import outputs from my completed production run</summary>
      <label className="block text-xs">Production run ID<input value={productionId} onChange={event => setProductionId(event.target.value)} className={inputClass} /></label>
      <label className="block text-xs">Selected relative quant.sf paths mapped to metadata samples (JSON)<textarea value={productionMapping} onChange={event => setProductionMapping(event.target.value)} placeholder={'{"star_salmon/sample1/quant.sf":"sample1"}'} className={inputClass} /></label>
      <label className="flex gap-2 text-sm"><input type="checkbox" checked={readQc} onChange={event => setReadQc(event.target.checked)} />I reviewed FastQC, MultiQC, alignment and strandedness evidence from this run.</label>
      <button type="button" disabled={busy || !reviewed || !readQc || !metadata || !tx2gene || !readiness?.available} onClick={() => submit(true)} className="btn-primary disabled:opacity-40">Import quantifications and generate QC</button>
    </details>}
    <div className="flex gap-2"><input value={resume} onChange={event => setResume(event.target.value)} placeholder="Resume a saved analysis job ID" aria-label="Saved analysis job ID" className={inputClass} /><button type="button" onClick={() => setJobId(resume.trim())} disabled={!resume.trim()} className="btn-secondary">Resume</button></div>
    {error && <p role="alert" className="text-error">{error}</p>}
    {jobId && <DurableJobReview jobId={jobId} onResult={onResult} />}
  </section>;
}

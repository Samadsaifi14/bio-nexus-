'use client';

import { useState } from 'react';
import { longApi } from '@/lib/api';
import { recoveryError } from './RnaSeqRecoveryPanel';

type Plan = { ready_to_launch: boolean; command_display: string; blockers: string[]; warnings: string[] };

export default function RnaSeqProductionPanel() {
  const [samplesheet, setSamplesheet] = useState('');
  const [outdir, setOutdir] = useState('');
  const [genome, setGenome] = useState('GRCh38');
  const [profile, setProfile] = useState('awsbatch');
  const [config, setConfig] = useState('');
  const [plan, setPlan] = useState<Plan | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const [runId, setRunId] = useState('');
  const [status, setStatus] = useState('');
  const [artifacts, setArtifacts] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const payload = () => ({ samplesheet_path: samplesheet, outdir, genome, execution_profile: profile, custom_config: config || null, aligner: 'star_salmon' });
  const inputClass = 'mt-1 w-full rounded border border-glass-border bg-surface-1 px-3 py-2 text-sm';
  async function request(submit = false) {
    setBusy(true); setError('');
    try {
      const response = await longApi.post(`/api/ngs/v2/rnaseq/production/${submit ? 'submit' : 'plan'}`, payload());
      if (submit) { setRunId(response.data.run_id); setStatus(response.data.state); }
      else setPlan(response.data);
    } catch (caught) { setError(recoveryError(caught)); } finally { setBusy(false); }
  }
  async function refresh() {
    setBusy(true); setError('');
    try {
      const response = await longApi.get(`/api/ngs/v2/production/runs/${encodeURIComponent(runId)}`); setStatus(response.data.state);
      if (response.data.state === 'SUCCEEDED') {
        const inventory = await longApi.get(`/api/ngs/v2/production/runs/${encodeURIComponent(runId)}/artifacts`);
        setArtifacts((inventory.data.groups?.quantification ?? []).filter((path: string) => path.endsWith('quant.sf')));
      }
    } catch (caught) { setError(recoveryError(caught)); } finally { setBusy(false); }
  }
  function changed(update: () => void) { update(); setPlan(null); setReviewed(false); }
  return <details className="data-card space-y-4 p-5">
    <summary className="cursor-pointer text-lg font-semibold">Regenerate counts from FASTQ with durable compute</summary>
    <p className="mt-3 text-sm">Use this when deposited raw counts are unavailable. The pinned nf-core/rnaseq pipeline runs read QC, alignment and Salmon quantification. Import its original quant.sf outputs above to preserve transcript-length corrections in DESeq2.</p>
    <p className="text-xs text-text-muted">An administrator must provision the selected executor, references, private input paths and persistent result storage. AWS Batch uses your configured queue and S3; jobs incur compute/storage charges. No job is launched by building a plan.</p>
    <p className="text-xs">The sample sheet needs sample, fastq_1, fastq_2 and strandedness columns. Repeated lanes use the same sample name; they are not biological replicates.</p>
    <div className="grid gap-3 md:grid-cols-2">
      <label className="text-xs">Sample sheet path or S3 URI<input value={samplesheet} onChange={event => changed(() => setSamplesheet(event.target.value))} className={inputClass} /></label>
      <label className="text-xs">Private output directory or S3 prefix<input value={outdir} onChange={event => changed(() => setOutdir(event.target.value))} className={inputClass} /></label>
      <label className="text-xs">Reference catalogue key<input value={genome} onChange={event => changed(() => setGenome(event.target.value))} className={inputClass} /></label>
      <label className="text-xs">Executor<select value={profile} onChange={event => changed(() => setProfile(event.target.value))} className={inputClass}><option value="awsbatch">AWS Batch</option><option value="slurm">Slurm</option><option value="docker">Local Docker</option><option value="apptainer">Local Apptainer</option></select></label>
      <label className="text-xs">Administrator-reviewed Nextflow configuration path<input value={config} onChange={event => changed(() => setConfig(event.target.value))} className={inputClass} /></label>
    </div>
    <button type="button" disabled={busy || !samplesheet || !outdir} onClick={() => request()} className="btn-secondary">Build execution plan</button>
    {plan && <><pre className="overflow-x-auto whitespace-pre-wrap rounded bg-surface-1 p-3 text-xs">{plan.command_display}</pre>{[...plan.blockers, ...plan.warnings].map((text, index) => <p key={index} className="text-xs text-warn">{text}</p>)}
      <label className="flex gap-2 text-sm"><input type="checkbox" checked={reviewed} onChange={event => setReviewed(event.target.checked)} />I reviewed sample/read identities, assay, reference, strandedness, compute configuration and costs.</label>
      <button type="button" disabled={busy || !reviewed || !plan.ready_to_launch} onClick={() => request(true)} className="btn-primary disabled:opacity-40">Submit to configured executor</button></>}
    <label className="block text-xs">Production run ID<input value={runId} onChange={event => setRunId(event.target.value)} className={inputClass} /></label>
    <button type="button" disabled={!runId || busy} onClick={refresh} className="btn-secondary">Refresh execution and artifact inventory</button>
    {status && <p className="text-sm">Execution: {status}. Successful execution still requires QC review before differential testing.</p>}
    {artifacts.length > 0 && <div className="text-xs"><p>Observed quantifications (select relative paths in the import form):</p>{artifacts.map(path => <p key={path} className="break-all font-mono">{path}</p>)}</div>}
    {error && <p role="alert" className="text-error">{error}</p>}
  </details>;
}

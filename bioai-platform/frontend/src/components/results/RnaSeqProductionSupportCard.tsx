'use client';

import { useEffect, useMemo, useState } from 'react';
import { CircleNotch, Flask, ShieldCheck, Warning } from '@phosphor-icons/react';
import { FlatInput } from '@/components/ui';
import {
  buildRnaSeqProductionPlan,
  getProductionArtifacts,
  getProductionCapabilities,
  getProductionRun,
  submitRnaSeqProductionRun,
  type ProductionArtifacts,
  type ProductionCapabilities,
  type ProductionPlan,
  type ProductionProfile,
  type ProductionRun,
  type RnaSeqProductionPlanRequest,
} from '@/lib/ngsProductionApi';

export function RnaSeqProductionSupportCard() {
  const [samplesheet, setSamplesheet] = useState('/staged/rnaseq_samplesheet.csv');
  const [outdir, setOutdir] = useState('/results/rnaseq');
  const [genome, setGenome] = useState('GRCh38');
  const [profile, setProfile] = useState<ProductionProfile>('docker');
  const [aligner, setAligner] = useState<RnaSeqProductionPlanRequest['aligner']>('star_salmon');
  const [strandedness, setStrandedness] = useState<RnaSeqProductionPlanRequest['strandedness']>('auto');
  const [customConfig, setCustomConfig] = useState('');
  const [skipTrimming, setSkipTrimming] = useState(false);
  const [saveTrimmed, setSaveTrimmed] = useState(true);
  const [deRequested, setDeRequested] = useState(true);
  const [plan, setPlan] = useState<ProductionPlan | null>(null);
  const [capabilities, setCapabilities] = useState<ProductionCapabilities | null>(null);
  const [run, setRun] = useState<ProductionRun | null>(null);
  const [artifacts, setArtifacts] = useState<ProductionArtifacts | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProductionCapabilities().then(setCapabilities).catch(() => setCapabilities(null));
  }, []);

  useEffect(() => {
    if (!run || !['SUBMITTED', 'PENDING', 'RUNNING'].includes(run.state)) return;
    const timer = window.setInterval(() => {
      getProductionRun(run.run_id).then(setRun).catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [run]);

  useEffect(() => {
    if (run?.state !== 'SUCCEEDED') return;
    getProductionArtifacts(run.run_id).then(setArtifacts).catch(() => setArtifacts(null));
  }, [run?.run_id, run?.state]);

  const executorKey = useMemo<'local' | 'slurm' | 'awsbatch'>(
    () => profile === 'awsbatch' ? 'awsbatch' : profile === 'slurm' ? 'slurm' : 'local',
    [profile],
  );
  const executor = capabilities?.executors[executorKey];

  const payload = (): RnaSeqProductionPlanRequest => ({
    samplesheet_path: samplesheet,
    outdir,
    genome,
    execution_profile: profile,
    aligner,
    pseudo_aligner: aligner === 'hisat2' ? 'salmon' : null,
    strandedness,
    custom_config: customConfig || null,
    skip_trimming: skipTrimming,
    save_trimmed: saveTrimmed,
    differential_expression_requested: deRequested,
    fusion_detection_requested: false,
  });

  const validate = async () => {
    setLoading(true); setError(null); setPlan(null);
    try { setPlan(await buildRnaSeqProductionPlan(payload())); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not validate RNA-seq production plan'); }
    finally { setLoading(false); }
  };

  const submit = async () => {
    setSubmitting(true); setError(null);
    try {
      const submitted = await submitRnaSeqProductionRun(payload());
      setRun(await getProductionRun(submitted.run_id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not submit RNA-seq production run');
    } finally { setSubmitting(false); }
  };

  return <section className="data-card overflow-hidden">
    <header className="border-b border-glass-border p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-text-primary">Production RNA-seq</h2>
            <span className="rounded border border-info/20 bg-info/5 px-2 py-0.5 font-mono text-[9px] text-info">nf-core/rnaseq 3.26.0</span>
            <span className="rounded border border-good/20 bg-good/5 px-2 py-0.5 font-mono text-[9px] text-good">EXECUTION CAPABLE</span>
          </div>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted">A design-aware launch contract for real transcriptomics compute. The workflow produces QC, alignment and abundance evidence; differential-expression claims remain a separate statistical stage using raw counts and recorded contrasts.</p>
        </div>
        <Flask className="h-5 w-5 text-accent-cyan" />
      </div>
    </header>

    <div className="grid gap-px bg-glass-border lg:grid-cols-[1.2fr_0.8fr]">
      <div className="grid gap-4 bg-surface-0 p-5 md:grid-cols-2">
        <div><label className="mb-1.5 block text-xs text-text-muted">Sample sheet</label><FlatInput value={samplesheet} onChange={e => { setSamplesheet(e.target.value); setPlan(null); }} className="w-full font-mono text-xs" /></div>
        <div><label className="mb-1.5 block text-xs text-text-muted">Result directory</label><FlatInput value={outdir} onChange={e => { setOutdir(e.target.value); setPlan(null); }} className="w-full font-mono text-xs" /></div>
        <div><label className="mb-1.5 block text-xs text-text-muted">Reference</label><select className="scientific-select" value={genome} onChange={e => { setGenome(e.target.value); setPlan(null); }}><option value="GRCh38">GRCh38</option><option value="GRCh37">GRCh37</option></select></div>
        <div><label className="mb-1.5 block text-xs text-text-muted">Alignment + quantification</label><select className="scientific-select" value={aligner} onChange={e => { setAligner(e.target.value as typeof aligner); setPlan(null); }}><option value="star_salmon">STAR + Salmon</option><option value="star_rsem">STAR + RSEM</option><option value="hisat2">HISAT2 + Salmon</option><option value="bowtie2_salmon">Bowtie2 + Salmon</option></select></div>
        <div><label className="mb-1.5 block text-xs text-text-muted">Strandedness</label><select className="scientific-select" value={strandedness} onChange={e => { setStrandedness(e.target.value as typeof strandedness); setPlan(null); }}><option value="auto">Auto / infer and verify</option><option value="unstranded">Unstranded</option><option value="forward">Forward</option><option value="reverse">Reverse</option></select></div>
        <div><label className="mb-1.5 block text-xs text-text-muted">Compute</label><select className="scientific-select" value={profile} onChange={e => { setProfile(e.target.value as ProductionProfile); setPlan(null); }}><option value="docker">Docker worker</option><option value="apptainer">Apptainer worker</option><option value="singularity">Singularity worker</option><option value="slurm">SLURM cluster</option><option value="awsbatch">AWS Batch</option></select></div>
        {(profile === 'slurm' || profile === 'awsbatch') && <div className="md:col-span-2"><label className="mb-1.5 block text-xs text-text-muted">Reviewed Nextflow config</label><FlatInput value={customConfig} onChange={e => { setCustomConfig(e.target.value); setPlan(null); }} placeholder="/config/nextflow.config" className="w-full font-mono text-xs" /></div>}
        <label className="flex items-start gap-2 text-xs text-text-secondary"><input type="checkbox" checked={!skipTrimming} onChange={e => { setSkipTrimming(!e.target.checked); setPlan(null); }} className="mt-0.5 accent-cyan-500"/><span><b className="text-text-primary">Adapter/quality preprocessing</b><span className="block text-[11px] text-text-muted">Keep enabled unless the input has already been processed and documented.</span></span></label>
        <label className="flex items-start gap-2 text-xs text-text-secondary"><input type="checkbox" checked={deRequested} onChange={e => { setDeRequested(e.target.checked); setPlan(null); }} className="mt-0.5 accent-cyan-500"/><span><b className="text-text-primary">Prepare for differential expression</b><span className="block text-[11px] text-text-muted">Requires raw-count statistics, PCA/sample-distance QC, contrasts and FDR correction after this base workflow.</span></span></label>
        <button onClick={validate} disabled={loading || !samplesheet.trim() || !outdir.trim()} className="inline-flex items-center justify-center gap-2 rounded-lg border border-accent-cyan/30 bg-accent-cyan/10 px-4 py-2.5 text-xs font-semibold text-accent-cyan disabled:opacity-50 md:col-span-2">{loading && <CircleNotch className="animate-spin"/>}Validate RNA-seq contract</button>
      </div>

      <aside className="space-y-4 bg-surface-1 p-5">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-text-muted">Scientific contract</p>
          <div className="mt-3 space-y-2 text-xs leading-5 text-text-secondary">
            <p><b className="text-text-primary">Counts:</b> raw integer counts remain authoritative for DESeq2/edgeR-style testing.</p>
            <p><b className="text-text-primary">TPM:</b> descriptive abundance and visualization, not the hypothesis-test input.</p>
            <p><b className="text-text-primary">QC before testing:</b> sample PCA/distances and recorded batch/design variables precede DEG claims.</p>
            <p><b className="text-text-primary">Interpretation:</b> transcript abundance is not protein abundance or causation.</p>
          </div>
        </div>
        <div className={`rounded-lg border p-3 text-xs ${executor?.available ? 'border-good/20 bg-good/5' : 'border-warn/20 bg-warn/5'}`}>
          <strong className={executor?.available ? 'text-good' : 'text-warn'}>{executor?.available ? `${executorKey} compute ready` : `${executorKey} compute unavailable`}</strong>
          <p className="mt-1 leading-5 text-text-muted">{executor ? (executor.available ? 'Submission starts a real pinned Nextflow run; there is no exploratory fallback.' : `Missing: ${[...(!executor.enabled ? ['enable flag'] : []), ...executor.missing].join(', ') || 'compute configuration'}.`) : 'Capability status has not been returned by the backend.'}</p>
        </div>
      </aside>
    </div>

    {error && <div className="border-t border-error/20 bg-error/5 px-5 py-3 text-xs text-error">{error}</div>}
    {plan && <div className="space-y-3 border-t border-glass-border p-5">
      <div className={`flex items-start gap-2 rounded-lg border p-3 text-xs ${plan.ready_to_launch ? 'border-good/20 bg-good/5' : 'border-error/20 bg-error/5'}`}>{plan.ready_to_launch ? <ShieldCheck className="mt-0.5 text-good"/> : <Warning className="mt-0.5 text-error"/>}<div><strong className="text-text-primary">{plan.ready_to_launch ? 'Contract ready' : 'Contract blocked'}</strong><p className="mt-1 text-text-muted">{plan.workflow.name} {plan.workflow.revision} · {plan.workflow.aligner ?? aligner}</p></div></div>
      {plan.blockers.length > 0 && <ul className="space-y-1 text-[11px] text-error">{plan.blockers.map(item => <li key={item}>• {item}</li>)}</ul>}
      {plan.warnings.length > 0 && <ul className="space-y-1 text-[11px] text-warn">{plan.warnings.map(item => <li key={item}>• {item}</li>)}</ul>}
      <details className="rounded-lg border border-glass-border bg-surface-1 p-3"><summary className="cursor-pointer text-xs font-medium text-text-primary">Exact reproducible launch contract</summary><pre className="mt-3 overflow-x-auto whitespace-pre-wrap font-mono text-[10px] leading-5 text-text-muted">{plan.command_display}</pre></details>
      <button onClick={submit} disabled={submitting || !plan.ready_to_launch || !executor?.available} className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-good/30 bg-good/10 px-4 py-2.5 text-xs font-semibold text-good disabled:opacity-50">{submitting && <CircleNotch className="animate-spin"/>}{submitting ? 'Submitting RNA-seq run…' : 'Submit production RNA-seq run'}</button>
      {run && <div className="rounded-lg border border-glass-border bg-surface-1 p-3 text-xs"><div className="flex items-center justify-between gap-2"><strong className="text-text-primary">{run.workflow} {run.revision}</strong><span className="font-mono text-accent-cyan">{run.state}</span></div><p className="mt-2 font-mono text-[10px] text-text-muted">Run {run.run_id} · executor job {run.executor_job_id}</p></div>}
      {artifacts && <div className="rounded-lg border border-glass-border bg-surface-1 p-3 text-xs"><div className="flex items-center justify-between gap-2"><strong className="text-text-primary">Observed RNA-seq artifacts</strong><span className={artifacts.required_groups_complete ? 'text-good' : 'text-warn'}>{artifacts.required_groups_complete ? 'COMPLETE' : 'INCOMPLETE'}</span></div><div className="mt-2 grid gap-1 text-[11px] text-text-muted">{Object.entries(artifacts.groups).map(([name, files]) => <div key={name} className="flex justify-between gap-3"><span>{name.replaceAll('_', ' ')}</span><span className="font-mono">{files.length}</span></div>)}</div>{artifacts.missing_groups.length > 0 && <p className="mt-2 text-warn">Missing: {artifacts.missing_groups.join(', ')}</p>}</div>}
    </div>}
  </section>;
}

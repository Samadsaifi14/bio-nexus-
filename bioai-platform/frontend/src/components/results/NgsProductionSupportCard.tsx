'use client';

import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { CircleNotch, ShieldCheck, Warning } from '@phosphor-icons/react';
import {
  buildNgsProductionPlan,
  getNgsProductionArtifacts,
  getNgsProductionCapabilities,
  getNgsProductionRun,
  submitNgsProductionRun,
} from '@/lib/api';
import type {
  NgsProductionArtifacts,
  NgsProductionCapabilities,
  NgsProductionPlan,
  NgsProductionPlanRequest,
  NgsProductionRun,
} from '@/lib/api';
import { FlatInput } from '@/components/ui';

interface NgsProductionSupportCardProps {
  defaultReference?: 'GRCh38' | 'GRCh37';
}

export function NgsProductionSupportCard({ defaultReference = 'GRCh38' }: NgsProductionSupportCardProps) {
  const [assay, setAssay] = useState<'WGS' | 'WES'>('WGS');
  const [genome, setGenome] = useState<'GRCh38' | 'GRCh37'>(defaultReference);
  const [sampleModel, setSampleModel] = useState<'singleton' | 'cohort' | 'duo' | 'trio' | 'family'>('singleton');
  const [inputType, setInputType] = useState<'FASTQ' | 'BAM' | 'CRAM'>('FASTQ');
  const [startStep, setStartStep] = useState<'mapping' | 'markduplicates' | 'variant_calling'>('mapping');
  const [caller, setCaller] = useState<'haplotypecaller' | 'deepvariant'>('haplotypecaller');
  const [profile, setProfile] = useState<'docker' | 'singularity' | 'apptainer' | 'slurm' | 'awsbatch'>('docker');
  const [samplesheet, setSamplesheet] = useState('/staged/samplesheet.csv');
  const [outdir, setOutdir] = useState('/results/sarek');
  const [targetBed, setTargetBed] = useState('');
  const [customConfig, setCustomConfig] = useState('');
  const [clinicalIntent, setClinicalIntent] = useState(false);
  const [plan, setPlan] = useState<NgsProductionPlan | null>(null);
  const [capabilities, setCapabilities] = useState<NgsProductionCapabilities | null>(null);
  const [run, setRun] = useState<NgsProductionRun | null>(null);
  const [artifacts, setArtifacts] = useState<NgsProductionArtifacts | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getNgsProductionCapabilities().then(setCapabilities).catch(() => setCapabilities(null));
  }, []);

  useEffect(() => {
    if (!run || !['SUBMITTED', 'PENDING', 'RUNNING'].includes(run.state)) return;
    const timer = window.setInterval(() => getNgsProductionRun(run.run_id).then(setRun).catch(() => undefined), 5000);
    return () => window.clearInterval(timer);
  }, [run]);

  useEffect(() => {
    if (run?.state !== 'SUCCEEDED') return;
    getNgsProductionArtifacts(run.run_id).then(setArtifacts).catch(() => setArtifacts(null));
  }, [run?.run_id, run?.state]);

  const request = (): NgsProductionPlanRequest => ({
    assay,
    sample_model: sampleModel,
    input_type: inputType,
    start_step: startStep,
    samplesheet_path: samplesheet,
    outdir,
    genome,
    execution_profile: profile,
    caller,
    target_bed: targetBed || undefined,
    custom_config: customConfig || undefined,
    annotate_with_vep: true,
    clinical_intent: clinicalIntent,
  });

  const executorKey = useMemo<'local' | 'slurm' | 'awsbatch'>(
    () => profile === 'awsbatch' ? 'awsbatch' : profile === 'slurm' ? 'slurm' : 'local',
    [profile],
  );
  const executor = capabilities?.executors[executorKey];

  const validatePlan = async () => {
    setLoading(true); setError(null); setPlan(null);
    try { setPlan(await buildNgsProductionPlan(request())); }
    catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.status === 404) setError('The deployed backend does not expose the production NGS planner. Deploy the matching backend revision.');
      else setError(err instanceof Error ? err.message : 'Could not validate the production contract');
    } finally { setLoading(false); }
  };

  const submit = async () => {
    setSubmitting(true); setError(null);
    try {
      const submission = await submitNgsProductionRun(request());
      setRun(await getNgsProductionRun(submission.run_id));
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.status === 401) setError('Sign in before submitting a production run.');
      else if (axios.isAxiosError(err) && err.response?.status === 503) setError(typeof err.response.data?.detail === 'string' ? err.response.data.detail : 'The selected executor is not configured.');
      else setError(err instanceof Error ? err.message : 'Could not submit the production run');
    } finally { setSubmitting(false); }
  };

  const changeInput = (value: typeof inputType) => {
    setInputType(value);
    setStartStep(value === 'FASTQ' ? 'mapping' : 'markduplicates');
    setPlan(null);
  };

  return <section className="data-card overflow-hidden">
    <header className="border-b border-glass-border p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold text-text-primary">Production WGS / WES</h2>
        <span className="rounded border border-info/20 bg-info/5 px-2 py-0.5 font-mono text-[9px] text-info">nf-core/sarek 3.10.0</span>
        <span className="rounded border border-good/20 bg-good/5 px-2 py-0.5 font-mono text-[9px] text-good">EXECUTION CAPABLE</span>
      </div>
      <p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted">Validate a pinned launch contract, then submit a real Nextflow job when local, SLURM or AWS Batch compute is configured. Exploratory preview results are never substituted for a failed or unavailable production executor.</p>
    </header>

    <div className="grid gap-px bg-glass-border lg:grid-cols-[1.25fr_0.75fr]">
      <div className="grid gap-4 bg-surface-0 p-5 md:grid-cols-2">
        <div><label className="mb-1.5 block text-xs text-text-muted">Assay</label><select className="scientific-select" value={assay} onChange={e => { setAssay(e.target.value as typeof assay); setPlan(null); }}><option value="WGS">Human WGS</option><option value="WES">Human WES</option></select></div>
        <div><label className="mb-1.5 block text-xs text-text-muted">Reference build</label><select className="scientific-select" value={genome} onChange={e => { setGenome(e.target.value as typeof genome); setPlan(null); }}><option value="GRCh38">GRCh38</option><option value="GRCh37">GRCh37</option></select></div>
        <div><label className="mb-1.5 block text-xs text-text-muted">Sample model</label><select className="scientific-select" value={sampleModel} onChange={e => { setSampleModel(e.target.value as typeof sampleModel); setPlan(null); }}><option value="singleton">Singleton</option><option value="cohort">Cohort</option><option value="duo">Duo</option><option value="trio">Trio</option><option value="family">Family</option></select></div>
        <div><label className="mb-1.5 block text-xs text-text-muted">Input type</label><select className="scientific-select" value={inputType} onChange={e => changeInput(e.target.value as typeof inputType)}><option value="FASTQ">FASTQ</option><option value="BAM">BAM</option><option value="CRAM">CRAM</option></select></div>
        <div><label className="mb-1.5 block text-xs text-text-muted">Start stage</label><select className="scientific-select" value={startStep} onChange={e => { setStartStep(e.target.value as typeof startStep); setPlan(null); }}><option value="mapping">Mapping</option><option value="markduplicates">Prepared alignment</option><option value="variant_calling">Variant calling</option></select></div>
        <div><label className="mb-1.5 block text-xs text-text-muted">Germline caller</label><select className="scientific-select" value={caller} onChange={e => { setCaller(e.target.value as typeof caller); setPlan(null); }}><option value="haplotypecaller">HaplotypeCaller</option><option value="deepvariant">DeepVariant</option></select></div>
        <div><label className="mb-1.5 block text-xs text-text-muted">Compute</label><select className="scientific-select" value={profile} onChange={e => { setProfile(e.target.value as typeof profile); setPlan(null); }}><option value="docker">Docker worker</option><option value="apptainer">Apptainer worker</option><option value="singularity">Singularity worker</option><option value="slurm">SLURM cluster</option><option value="awsbatch">AWS Batch</option></select></div>
        <div><label className="mb-1.5 block text-xs text-text-muted">Sample sheet</label><FlatInput className="w-full font-mono text-xs" value={samplesheet} onChange={e => { setSamplesheet(e.target.value); setPlan(null); }}/></div>
        <div><label className="mb-1.5 block text-xs text-text-muted">Result directory</label><FlatInput className="w-full font-mono text-xs" value={outdir} onChange={e => { setOutdir(e.target.value); setPlan(null); }}/></div>
        {assay === 'WES' && <div><label className="mb-1.5 block text-xs text-text-muted">Target BED</label><FlatInput className="w-full font-mono text-xs" value={targetBed} placeholder="/references/exome_targets.bed" onChange={e => { setTargetBed(e.target.value); setPlan(null); }}/></div>}
        {(profile === 'slurm' || profile === 'awsbatch') && <div className="md:col-span-2"><label className="mb-1.5 block text-xs text-text-muted">Reviewed Nextflow config</label><FlatInput className="w-full font-mono text-xs" value={customConfig} placeholder="/config/nextflow.config" onChange={e => { setCustomConfig(e.target.value); setPlan(null); }}/></div>}
        <label className="flex items-start gap-2 rounded-lg border border-glass-border bg-surface-1 p-3 md:col-span-2"><input type="checkbox" checked={clinicalIntent} onChange={e => { setClinicalIntent(e.target.checked); setPlan(null); }} className="mt-0.5 accent-cyan-500"/><span className="text-xs"><b className="text-text-primary">Clinical-intent software gate</b><span className="mt-0.5 block text-[11px] leading-4 text-text-muted">Requires external truth benchmarking, sample identity/contamination evidence, assay validation, complete provenance and authorized human release. Passing it is not clinical accreditation.</span></span></label>
        <button onClick={validatePlan} disabled={loading || !samplesheet.trim() || !outdir.trim()} className="inline-flex items-center justify-center gap-2 rounded-lg border border-accent-cyan/30 bg-accent-cyan/10 px-4 py-2.5 text-xs font-semibold text-accent-cyan disabled:opacity-50 md:col-span-2">{loading && <CircleNotch className="animate-spin"/>}Validate production contract</button>
      </div>

      <aside className="space-y-4 bg-surface-1 p-5">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-text-muted">Execution boundary</p>
          <p className="mt-2 text-xs leading-5 text-text-secondary">Plan validation is cheap and synchronous. Execution is durable and external to the request lifecycle. Results become evidence only when observed artifacts are imported; missing artifacts are never synthesized.</p>
        </div>
        <div className={`rounded-lg border p-3 text-xs ${executor?.available ? 'border-good/20 bg-good/5' : 'border-warn/20 bg-warn/5'}`}><strong className={executor?.available ? 'text-good' : 'text-warn'}>{executor?.available ? `${executorKey} compute ready` : `${executorKey} compute unavailable`}</strong><p className="mt-1 leading-5 text-text-muted">{executor ? (executor.available ? 'A real pinned Sarek job can be submitted.' : `Missing: ${[...(!executor.enabled ? ['enable flag'] : []), ...executor.missing].join(', ') || 'compute configuration'}.`) : 'Capability status has not been returned by the backend.'}</p></div>
      </aside>
    </div>

    {error && <div className="border-t border-error/20 bg-error/5 px-5 py-3 text-xs text-error">{error}</div>}
    {plan && <div className="space-y-3 border-t border-glass-border p-5">
      <div className={`flex items-start gap-2 rounded-lg border p-3 text-xs ${plan.ready_to_launch ? 'border-good/20 bg-good/5' : 'border-error/20 bg-error/5'}`}>{plan.ready_to_launch ? <ShieldCheck className="mt-0.5 text-good"/> : <Warning className="mt-0.5 text-error"/>}<div><strong className="text-text-primary">{plan.ready_to_launch ? 'Contract ready' : 'Contract blocked'}</strong><p className="mt-1 text-text-muted">{plan.workflow.name} {plan.workflow.revision} · {plan.workflow.assay}</p></div></div>
      {plan.blockers.length > 0 && <ul className="space-y-1 text-[11px] text-error">{plan.blockers.map(item => <li key={item}>• {item}</li>)}</ul>}
      {plan.warnings.length > 0 && <ul className="space-y-1 text-[11px] text-warn">{plan.warnings.map(item => <li key={item}>• {item}</li>)}</ul>}
      <details className="rounded-lg border border-glass-border bg-surface-1 p-3"><summary className="cursor-pointer text-xs font-medium text-text-primary">Exact reproducible launch contract</summary><pre className="mt-3 overflow-x-auto whitespace-pre-wrap font-mono text-[10px] leading-5 text-text-muted">{plan.command_display}</pre></details>
      <button onClick={submit} disabled={submitting || !plan.ready_to_launch || !executor?.available} className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-good/30 bg-good/10 px-4 py-2.5 text-xs font-semibold text-good disabled:opacity-50">{submitting && <CircleNotch className="animate-spin"/>}{submitting ? 'Submitting production run…' : 'Submit production run'}</button>
      {run && <div className="rounded-lg border border-glass-border bg-surface-1 p-3 text-xs"><div className="flex items-center justify-between gap-2"><strong className="text-text-primary">{run.workflow} {run.revision}</strong><span className="font-mono text-accent-cyan">{run.state}</span></div><p className="mt-2 font-mono text-[10px] text-text-muted">Run {run.run_id} · executor job {run.executor_job_id}</p></div>}
      {artifacts && <div className="rounded-lg border border-glass-border bg-surface-1 p-3 text-xs"><div className="flex items-center justify-between gap-2"><strong className="text-text-primary">Observed production artifacts</strong><span className={artifacts.required_groups_complete ? 'text-good' : 'text-warn'}>{artifacts.required_groups_complete ? 'COMPLETE' : 'INCOMPLETE'}</span></div><div className="mt-2 grid gap-1 text-[11px] text-text-muted">{Object.entries(artifacts.groups).map(([name, files]) => <div key={name} className="flex justify-between gap-3"><span>{name.replaceAll('_', ' ')}</span><span className="font-mono">{files.length}</span></div>)}</div>{artifacts.missing_groups.length > 0 && <p className="mt-2 text-warn">Missing: {artifacts.missing_groups.join(', ')}</p>}</div>}
    </div>}
  </section>;
}

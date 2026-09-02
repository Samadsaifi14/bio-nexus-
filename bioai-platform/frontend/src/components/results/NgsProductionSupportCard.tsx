'use client';

import { useEffect, useState } from 'react';
import axios from 'axios';
import { CircleNotch, ShieldCheck, Warning } from '@phosphor-icons/react';
import { buildNgsProductionPlan, getNgsProductionArtifacts, getNgsProductionCapabilities, getNgsProductionRun, submitNgsProductionRun } from '@/lib/api';
import type { NgsProductionArtifacts, NgsProductionCapabilities, NgsProductionPlan, NgsProductionPlanRequest, NgsProductionRun } from '@/lib/api';
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
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [capabilities, setCapabilities] = useState<NgsProductionCapabilities | null>(null);
  const [run, setRun] = useState<NgsProductionRun | null>(null);
  const [artifacts, setArtifacts] = useState<NgsProductionArtifacts | null>(null);

  useEffect(() => {
    getNgsProductionCapabilities().then(setCapabilities).catch(() => setCapabilities(null));
  }, []);

  useEffect(() => {
    if (!run || !['SUBMITTED', 'PENDING', 'RUNNING'].includes(run.state)) return;
    const timer = window.setInterval(() => {
      getNgsProductionRun(run.run_id).then(setRun).catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [run]);

  useEffect(() => {
    if (run?.state !== 'SUCCEEDED') return;
    getNgsProductionArtifacts(run.run_id).then(setArtifacts).catch(() => setArtifacts(null));
  }, [run?.run_id, run?.state]);

  const request = (): NgsProductionPlanRequest => ({
    assay, sample_model: sampleModel, input_type: inputType, start_step: startStep, samplesheet_path: samplesheet,
    outdir, genome, execution_profile: profile, caller,
    target_bed: targetBed || undefined, custom_config: customConfig || undefined,
    annotate_with_vep: true, clinical_intent: clinicalIntent,
  });

  const buildPlan = async () => {
    setLoading(true); setError(null);
    try {
      setPlan(await buildNgsProductionPlan(request()));
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.status === 404) {
        setError('Production planning is not installed on the deployed BioNexus backend yet. The exploratory preview remains available; deploy the matching backend revision before using this plan validator.');
      } else {
        setError(err instanceof Error ? err.message : 'Could not build the production plan');
      }
    } finally { setLoading(false); }
  };

  const submit = async () => {
    setSubmitting(true); setError(null);
    try {
      const submission = await submitNgsProductionRun(request());
      setRun(await getNgsProductionRun(submission.run_id));
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        setError('Sign in before submitting a production run. Production jobs are private and tied to an authenticated account.');
      } else if (axios.isAxiosError(err) && err.response?.status === 503) {
        const detail = err.response.data?.detail;
        setError(typeof detail === 'string' ? detail : 'The selected production executor is not configured.');
      } else {
        setError(err instanceof Error ? err.message : 'Could not submit the production run');
      }
    } finally { setSubmitting(false); }
  };

  const executorKey: 'local' | 'slurm' | 'awsbatch' = profile === 'awsbatch' ? 'awsbatch' : profile === 'slurm' ? 'slurm' : 'local';
  const executorCapability = capabilities?.executors[executorKey];

  return <section className="data-card overflow-hidden">
    <div className="border-b border-glass-border p-5">
      <div className="flex flex-wrap items-center gap-2"><h2 className="text-sm font-semibold text-text-primary">Production human WGS/WES</h2><span className="rounded border border-info/20 bg-info/5 px-2 py-0.5 font-mono text-[9px] text-info">PINNED WORKFLOW</span><span className="rounded border border-warn/20 bg-warn/5 px-2 py-0.5 font-mono text-[9px] text-warn">CLINICAL GATE FAIL-CLOSED</span></div>
      <p className="mt-1 text-xs leading-5 text-text-muted">This form validates and displays a reproducible nf-core/sarek launch contract. It does not submit a job. A run is not marked executed until its real trace, QC, checksums, alignments and variant files are imported.</p>
    </div>
    <div className="grid gap-4 p-5 md:grid-cols-2">
      <div><label className="mb-1.5 block text-xs text-text-muted">Assay</label><select className="scientific-select" value={assay} onChange={event => { setAssay(event.target.value as 'WGS' | 'WES'); setPlan(null); }}><option value="WGS">Human WGS</option><option value="WES">Human WES</option></select></div>
      <div><label className="mb-1.5 block text-xs text-text-muted">Reference build</label><select className="scientific-select" value={genome} onChange={event => { setGenome(event.target.value as typeof genome); setPlan(null); }}><option value="GRCh38">GRCh38</option><option value="GRCh37">GRCh37</option></select></div>
      <div><label className="mb-1.5 block text-xs text-text-muted">Sample model</label><select className="scientific-select" value={sampleModel} onChange={event => { setSampleModel(event.target.value as typeof sampleModel); setPlan(null); }}><option value="singleton">Singleton</option><option value="cohort">Cohort</option><option value="duo">Duo</option><option value="trio">Trio</option><option value="family">Family</option></select></div>
      <div><label className="mb-1.5 block text-xs text-text-muted">Input</label><select className="scientific-select" value={inputType} onChange={event => { const value = event.target.value as typeof inputType; setInputType(value); setStartStep(value === 'FASTQ' ? 'mapping' : 'markduplicates'); setPlan(null); }}><option value="FASTQ">FASTQ</option><option value="BAM">BAM</option><option value="CRAM">CRAM</option></select></div>
      <div><label className="mb-1.5 block text-xs text-text-muted">Start stage</label><select className="scientific-select" value={startStep} onChange={event => { setStartStep(event.target.value as typeof startStep); setPlan(null); }}><option value="mapping">Mapping</option><option value="markduplicates">Prepared alignment</option><option value="variant_calling">Recalibrated alignment</option></select></div>
      <div><label className="mb-1.5 block text-xs text-text-muted">Germline caller</label><select className="scientific-select" value={caller} onChange={event => { setCaller(event.target.value as typeof caller); setPlan(null); }}><option value="haplotypecaller">HaplotypeCaller</option><option value="deepvariant">DeepVariant</option></select></div>
      <div><label className="mb-1.5 block text-xs text-text-muted">Execution environment</label><select className="scientific-select" value={profile} onChange={event => { setProfile(event.target.value as typeof profile); setPlan(null); }}><option value="docker">Docker worker</option><option value="singularity">Singularity worker</option><option value="apptainer">Apptainer worker</option><option value="slurm">SLURM cluster</option><option value="awsbatch">AWS Batch</option></select></div>
      <div><label className="mb-1.5 block text-xs text-text-muted">Staged sample sheet</label><FlatInput className="w-full font-mono text-xs" value={samplesheet} onChange={event => { setSamplesheet(event.target.value); setPlan(null); }}/></div>
      <div><label className="mb-1.5 block text-xs text-text-muted">Result directory</label><FlatInput className="w-full font-mono text-xs" value={outdir} onChange={event => { setOutdir(event.target.value); setPlan(null); }}/></div>
      {assay === 'WES' && <div><label className="mb-1.5 block text-xs text-text-muted">Target BED (required)</label><FlatInput className="w-full font-mono text-xs" placeholder="/references/exome_targets.bed" value={targetBed} onChange={event => { setTargetBed(event.target.value); setPlan(null); }}/></div>}
      {(profile === 'slurm' || profile === 'awsbatch') && <div><label className="mb-1.5 block text-xs text-text-muted">Reviewed compute configuration (required)</label><FlatInput className="w-full font-mono text-xs" placeholder="/config/nextflow.config" value={customConfig} onChange={event => { setCustomConfig(event.target.value); setPlan(null); }}/></div>}
      <label className="flex items-start gap-2 rounded-lg border border-glass-border bg-surface-1 p-3 md:col-span-2"><input type="checkbox" checked={clinicalIntent} onChange={event => { setClinicalIntent(event.target.checked); setPlan(null); }} className="mt-0.5 accent-cyan-500"/><span><span className="block text-xs font-medium text-text-primary">Clinical-intent safeguards</span><span className="mt-0.5 block text-[11px] leading-4 text-text-muted">Requires assay validation, identity/contamination evidence, external truth benchmarking, complete provenance, authorized review and release signature. It does not certify the assay.</span></span></label>
      <button onClick={buildPlan} disabled={loading || !samplesheet.trim() || !outdir.trim()} className="inline-flex items-center justify-center gap-2 rounded-lg border border-accent-cyan/30 bg-accent-cyan/10 px-4 py-2.5 text-xs font-semibold text-accent-cyan hover:bg-accent-cyan/15 disabled:opacity-50 md:col-span-2">{loading && <CircleNotch className="animate-spin"/>}Validate production plan</button>
    </div>
    {error && <div className="border-t border-error/20 bg-error/5 px-5 py-3 text-xs text-error">{error}</div>}
    {plan && <div className="space-y-3 border-t border-glass-border p-5">
      <div className={`flex items-start gap-2 rounded-lg border p-3 text-xs ${plan.ready_to_launch ? 'border-good/20 bg-good/5 text-good' : 'border-error/20 bg-error/5 text-error'}`}>{plan.ready_to_launch ? <ShieldCheck className="mt-0.5 shrink-0"/> : <Warning className="mt-0.5 shrink-0"/>}<div><strong>{plan.ready_to_launch ? 'Launch contract ready' : 'Launch blocked'}</strong><p className="mt-1 text-text-muted">{plan.workflow.name} {plan.workflow.revision} · {plan.workflow.assay} · {plan.workflow.execution_engine}</p></div></div>
      {plan.blockers.length > 0 && <ul className="space-y-1 text-[11px] text-error">{plan.blockers.map(item => <li key={item}>• {item}</li>)}</ul>}
      <details className="rounded-lg border border-glass-border bg-surface-1 p-3"><summary className="cursor-pointer text-xs font-medium text-text-primary">Reproducible launch details</summary><pre className="mt-3 overflow-x-auto whitespace-pre-wrap font-mono text-[10px] leading-5 text-text-muted">{plan.command_display}</pre><p className="mt-2 text-[11px] text-text-muted">{plan.required_artifacts.length} required artifact groups · {plan.provenance_requirements.length} provenance requirements</p></details>
      <div className={`rounded-lg border p-3 text-xs ${executorCapability?.available ? 'border-good/20 bg-good/5' : 'border-warn/20 bg-warn/5'}`}>
        <strong className={executorCapability?.available ? 'text-good' : 'text-warn'}>{executorCapability?.available ? `${executorKey} executor available` : `${executorKey} executor not configured`}</strong>
        <p className="mt-1 leading-5 text-text-muted">{executorCapability ? (executorCapability.available ? 'Submitting starts the real pinned Sarek workflow. No preview fallback is used.' : `Missing: ${[...(!executorCapability.enabled ? ['server enable flag'] : []), ...executorCapability.missing].join(', ') || 'executor infrastructure'}.`) : 'Executor capability could not be read from the deployed backend.'}</p>
      </div>
      <button onClick={submit} disabled={submitting || !plan.ready_to_launch || !executorCapability?.available} className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-good/30 bg-good/10 px-4 py-2.5 text-xs font-semibold text-good hover:bg-good/15 disabled:opacity-50">{submitting && <CircleNotch className="animate-spin"/>}{submitting ? 'Submitting real Sarek run…' : 'Submit production run'}</button>
      {run && <div className="rounded-lg border border-glass-border bg-surface-1 p-3 text-xs"><div className="flex flex-wrap items-center justify-between gap-2"><strong className="text-text-primary">{run.workflow} {run.revision}</strong><span className="font-mono text-accent-cyan">{run.state}</span></div><dl className="mt-2 grid gap-1 text-[11px] text-text-muted"><div><dt className="inline">Run ID: </dt><dd className="inline font-mono">{run.run_id}</dd></div><div><dt className="inline">Executor job: </dt><dd className="inline font-mono">{run.executor_job_id}</dd></div><div><dt className="inline">Results: </dt><dd className="inline font-mono">{run.outdir}</dd></div></dl>{run.message && <p className="mt-2 text-warn">{run.message}</p>}</div>}
      {artifacts && <div className="rounded-lg border border-glass-border bg-surface-1 p-3 text-xs"><div className="flex flex-wrap items-center justify-between gap-2"><strong className="text-text-primary">Imported Sarek artifacts</strong><span className={artifacts.required_groups_complete ? 'text-good' : 'text-warn'}>{artifacts.required_groups_complete ? 'COMPLETE' : 'INCOMPLETE'}</span></div><p className="mt-1 text-[11px] leading-5 text-text-muted">{artifacts.observed_file_count} files observed at {artifacts.source}. {artifacts.claim}</p><div className="mt-2 grid gap-1 text-[11px] text-text-muted">{Object.entries(artifacts.groups).map(([group, files]) => <div key={group} className="flex justify-between gap-3"><span>{group.replaceAll('_', ' ')}</span><span className="font-mono">{files.length}</span></div>)}</div>{artifacts.missing_groups.length > 0 && <p className="mt-2 text-warn">Missing: {artifacts.missing_groups.join(', ')}</p>}</div>}
      <div className="rounded-lg border border-warn/20 bg-warn/5 p-3 text-[11px] leading-5 text-text-muted"><strong className="text-warn">{plan.clinical_boundary.current_status.replaceAll('_', ' ')}</strong> — {plan.clinical_boundary.reason}</div>
    </div>}
  </section>;
}

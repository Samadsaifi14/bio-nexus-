'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Dna, CircleNotch, TestTube, MapTrifold, Warning, Database, FileText, ArrowCounterClockwise, ShieldWarning, ShieldCheck, CaretRight } from '@phosphor-icons/react';
import { fadeUp } from '@/lib/animations';
import { getNgsPortableBenchmark, runNgs2Analyze } from '@/lib/api';
import type { Ngs2AnalyzeResult, NgsPortableBenchmark } from '@/lib/api';
import { validateScientificStages } from '@/lib/scientificIntegrity';
import { BackButton, CriticalButton, FlatInput, PageHeader } from '@/components/ui';
import ScientificResultsWorkspace, { type ScientificStatus } from '@/components/results/ScientificResultsWorkspace';
import StageEvidenceTable from '@/components/results/StageEvidenceTable';
import { ProvenancePanel } from '@/components/results/ProvenancePanel';
import NgsArtifactPanel from '@/components/results/NgsArtifactPanel';
import NgsEvidenceInterpretation from '@/components/results/NgsEvidenceInterpretation';
import { NgsBenchmarkPanel } from '@/components/results/NgsBenchmarkPanel';
import { NgsPortableBenchmarkCard } from '@/components/results/NgsPortableBenchmarkCard';
import { NgsProductionSupportCard } from '@/components/results/NgsProductionSupportCard';
import GenomeViewer from '@/components/GenomeViewer';

const ASSAY_OPTIONS = [
  { value: '', label: 'Auto-detect assay' },
  { value: 'WGS', label: 'Whole Genome Sequencing (WGS)' },
  { value: 'WES', label: 'Whole Exome Sequencing (WES)' },
  { value: 'RNA-seq', label: 'RNA-seq' },
  { value: 'Amplicon', label: 'Targeted Amplicon' },
];

const DEMOS = [
  { id: 'wgs-clean', title: 'Clean WGS', subtitle: '2×150 bp · high-quality paired reads' },
  { id: 'wgs-mixed-quality', title: 'Mixed-quality WGS', subtitle: 'low-quality tails + duplicates' },
  { id: 'wes-small', title: 'Compact WES', subtitle: 'small paired-end exome-style run' },
] as const;

type DemoMeta = { profile: string; label: string; description: string; synthetic: boolean; read_pairs: number };
type ExtendedResult = Ngs2AnalyzeResult & { demo?: DemoMeta | null; requested: Ngs2AnalyzeResult['requested'] & { demo_profile?: string | null; reads_analyzed?: number } };
type AnalysisMode = 'production' | 'preview';

function readinessStatus(verdict: string, integrityBlocked: boolean, researchReady: boolean): { status: ScientificStatus; label: string } {
  if (integrityBlocked) return { status: 'FAIL', label: 'INTEGRITY REVIEW REQUIRED' };
  if (!researchReady) return { status: 'INFO', label: 'EXPLORATORY PREVIEW' };
  if (verdict === 'ANALYSIS_READY' || verdict === 'PASS') return { status: 'PASS', label: 'ANALYSIS READY' };
  if (verdict === 'ANALYSIS_READY_WITH_WARNINGS' || verdict === 'WARN') return { status: 'WARN', label: 'READY WITH WARNINGS' };
  if (verdict === 'NOT_ANALYSIS_READY' || verdict === 'FAIL') return { status: 'FAIL', label: 'NOT ANALYSIS READY' };
  return { status: 'INFO', label: verdict || 'STATUS NOT REPORTED' };
}

export default function NgsV2Page() {
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode | null>(null);
  const [filePaths, setFilePaths] = useState('');
  const [assay, setAssay] = useState('');
  const [reference, setReference] = useState('grch38');
  const [synthetic, setSynthetic] = useState(true);
  const [loading, setLoading] = useState(false);
  const [runningDemo, setRunningDemo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExtendedResult | null>(null);
  const [portableBenchmark, setPortableBenchmark] = useState<NgsPortableBenchmark | null>(null);

  useEffect(() => {
    getNgsPortableBenchmark().then(setPortableBenchmark).catch(() => setPortableBenchmark(null));
  }, []);

  const resetResult = () => { setResult(null); setError(null); setRunningDemo(null); };
  const changeMode = (mode: AnalysisMode | null) => {
    setAnalysisMode(mode);
    setResult(null);
    setError(null);
    setRunningDemo(null);
  };

  const run = async (demoProfile?: string) => {
    const files = filePaths.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean);
    if (!demoProfile && files.length === 0) return;
    setLoading(true); setRunningDemo(demoProfile ?? null); setError(null); setResult(null);
    try {
      const payload = {
        file_paths: demoProfile ? [] : files,
        reference: reference || undefined,
        assay: demoProfile ? undefined : (assay || undefined),
        metadata: { platform: 'illumina', source: demoProfile ? 'bionexus-demo' : 'user', demonstration_data: Boolean(demoProfile) },
        synthetic_reference: demoProfile ? true : synthetic,
        demo_profile: demoProfile,
      };
      const res = await runNgs2Analyze(payload as Parameters<typeof runNgs2Analyze>[0] & { demo_profile?: string });
      setResult(res as ExtendedResult);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to run analysis');
    } finally { setLoading(false); setRunningDemo(null); }
  };

  const stages = Array.isArray(result?.pipeline?.stages) ? result!.pipeline.stages : [];
  const visualization = result?.visualization ?? { sam: '', vcf: '', locus: null, n_reads: 0, n_mapped: 0, n_variants: 0 };
  const warnings = Array.isArray(result?.pipeline?.warnings) ? [...new Set(result!.pipeline.warnings.filter(Boolean))] : [];
  const verdict = result?.pipeline?.pipeline_status ?? 'INFO';
  const integrityIssues = validateScientificStages(stages);
  const integrityErrors = integrityIssues.filter((issue) => issue.level === 'ERROR');
  const integrityWarnings = integrityIssues.filter((issue) => issue.level === 'WARN');
  const readiness = readinessStatus(verdict, integrityErrors.length > 0, Boolean(result?.pipeline?.validation?.research_ready));
  const gate = stages[stages.length - 1];
  const validation = result?.pipeline?.validation;
  const passed = stages.filter(s => s.qc?.status === 'PASS').length;
  const warned = stages.filter(s => s.qc?.status === 'WARN').length;
  const failed = stages.filter(s => s.qc?.status === 'FAIL').length;
  const readsLoaded = result?.requested?.reads_loaded && typeof result.requested.reads_loaded === 'object' ? result.requested.reads_loaded : {};
  const totalReads = Object.values(readsLoaded).reduce((a, b) => a + Number(b || 0), 0);
  const provenance = result?.pipeline?.provenance;
  const provenanceAnalysis = provenance?.analysis && typeof provenance.analysis === 'object' ? provenance.analysis as Record<string, unknown> : null;
  const provenanceReference = provenance?.reference && typeof provenance.reference === 'object' ? provenance.reference as Record<string, unknown> : null;
  const displayedReference = String(provenanceReference?.id ?? result?.requested?.reference ?? '—');
  const displayedSampleType = String(provenanceAnalysis?.sample_type ?? result?.detection?.sample_type ?? '—');

  return <div className="scientific-page max-w-6xl space-y-6 pb-12">
    <BackButton />
    <PageHeader title="NGS Analysis" subtitle="Raw FASTQ to auditable QC, alignment, variant evidence, genome inspection and an evidence-backed analysis-readiness decision." />

    {!result && <section className="data-card overflow-hidden">
      <div className="border-b border-glass-border p-5">
        <h2 className="text-sm font-semibold text-text-primary">Choose the execution engine</h2>
        <p className="mt-1 text-xs leading-5 text-text-muted">Both engines live in the same BioNexus NGS workspace. Production submits real Sarek runs to configured compute; preview remains a lightweight, separately identified test engine.</p>
      </div>
      <div className="grid gap-px bg-glass-border md:grid-cols-2">
        <button type="button" onClick={() => changeMode('production')} aria-pressed={analysisMode === 'production'} className={`group p-5 text-left transition ${analysisMode === 'production' ? 'bg-accent-cyan/10' : 'bg-surface-0 hover:bg-surface-1'}`}>
          <div className="flex items-start justify-between gap-4"><div><div className="flex flex-wrap items-center gap-2"><span className="text-sm font-semibold text-text-primary">Production WGS/WES</span><span className="rounded border border-info/20 bg-info/5 px-2 py-0.5 font-mono text-[9px] text-info">PLAN ONLY</span></div><p className="mt-2 text-xs leading-5 text-text-muted">Validate a pinned nf-core/sarek launch contract for external durable compute. BioNexus does not execute this run yet.</p></div><CaretRight className="mt-0.5 shrink-0 text-text-muted transition group-hover:translate-x-0.5"/></div>
        </button>
        <button type="button" onClick={() => changeMode('preview')} aria-pressed={analysisMode === 'preview'} className={`group p-5 text-left transition ${analysisMode === 'preview' ? 'bg-accent-cyan/10' : 'bg-surface-0 hover:bg-surface-1'}`}>
          <div className="flex items-start justify-between gap-4"><div><div className="flex flex-wrap items-center gap-2"><span className="text-sm font-semibold text-text-primary">Exploratory preview</span><span className="rounded border border-warn/20 bg-warn/5 px-2 py-0.5 font-mono text-[9px] text-warn">RUNS HERE</span></div><p className="mt-2 text-xs leading-5 text-text-muted">Run deterministic demonstrations or server-local FASTQ through the internal evidence preview. This is not Sarek or a clinical workflow.</p></div><CaretRight className="mt-0.5 shrink-0 text-text-muted transition group-hover:translate-x-0.5"/></div>
        </button>
      </div>
    </section>}

    {!result && analysisMode === 'production' && <>
      <NgsProductionSupportCard defaultReference="GRCh38" />
      {portableBenchmark && <NgsPortableBenchmarkCard report={portableBenchmark} />}
    </>}

    {!result && analysisMode === 'preview' && <>
      <motion.section variants={fadeUp} initial={{ y: 18 }} animate="show" className="data-card overflow-hidden">
        <div className="border-b border-glass-border p-5"><div className="flex items-center gap-2"><TestTube className="h-4 w-4 text-accent-cyan"/><h2 className="text-sm font-semibold text-text-primary">Try a complete analysis</h2></div><p className="mt-1 text-xs leading-5 text-text-muted">These deterministic synthetic FASTQ pairs run through the same validation and staged NGS analysis as supplied files.</p></div>
        <div className="grid gap-px bg-glass-border md:grid-cols-3">{DEMOS.map(demo => <button key={demo.id} disabled={loading} onClick={() => run(demo.id)} className="bg-surface-0 p-4 text-left transition hover:bg-surface-1 disabled:opacity-50"><div className="flex items-center justify-between"><span className="text-sm font-semibold text-text-primary">{demo.title}</span><span className="rounded border border-accent-cyan/20 bg-accent-cyan/5 px-1.5 py-0.5 font-mono text-[9px] text-accent-cyan">DEMO</span></div><p className="mt-1 text-xs text-text-muted">{demo.subtitle}</p><p className="mt-3 text-[11px] font-medium text-accent-cyan">{runningDemo === demo.id ? 'Running…' : 'Run demo →'}</p></button>)}</div>
      </motion.section>

      <section className="data-card p-5 space-y-4">
        <div><label className="mb-1.5 block text-sm font-medium text-text-primary">Or analyze server-local FASTQ files</label><FlatInput type="text" value={filePaths} onChange={(e) => { setFilePaths(e.target.value); setError(null); }} onKeyDown={(e) => e.key === 'Enter' && run()} placeholder="/data/SAMPLE_001_R1.fastq.gz, /data/SAMPLE_001_R2.fastq.gz" className="w-full px-4 py-3 text-sm font-mono"/></div>
        <div className="grid gap-4 md:grid-cols-2"><div><label className="mb-1.5 block text-xs text-text-muted">Assay</label><select value={assay} onChange={e => setAssay(e.target.value)} className="scientific-select">{ASSAY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</select></div><div><label className="mb-1.5 block text-xs text-text-muted">Reference build</label><select value={reference} onChange={e => setReference(e.target.value)} className="scientific-select"><option value="grch38">GRCh38</option><option value="grch37">GRCh37</option></select></div></div>
        <label className="flex items-start gap-2 rounded-lg border border-glass-border bg-surface-1 p-3"><input type="checkbox" checked={synthetic} onChange={e => setSynthetic(e.target.checked)} className="mt-0.5 accent-cyan-500"/><span><span className="block text-xs font-medium text-text-primary">Synthetic demonstration reference</span><span className="mt-0.5 block text-[11px] leading-4 text-text-muted">Useful for local testing only. Do not use synthetic-reference runs for biological interpretation.</span></span></label>
        <CriticalButton onClick={() => run()} disabled={loading || !filePaths.trim()} className="w-full py-3 flex items-center justify-center gap-2 disabled:opacity-50">{loading && !runningDemo ? <CircleNotch className="h-4 w-4 animate-spin"/> : <Dna className="h-4 w-4"/>}{loading && !runningDemo ? 'Running NGS pipeline…' : 'Run FASTQ analysis'}</CriticalButton>
      </section>
    </>}

    {error && <div className="rounded-xl border border-error/25 bg-error/10 p-4 text-sm text-error"><p>{error}</p><button onClick={() => setError(null)} className="mt-2 text-xs underline">Dismiss</button></div>}

    {result && <>
      <div className="flex justify-end"><button onClick={resetResult} className="inline-flex items-center gap-2 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs text-text-secondary hover:text-text-primary"><ArrowCounterClockwise/>Back to preview inputs</button></div>
      <ScientificResultsWorkspace
        title={result.demo ? result.demo.label : `${result.detection?.assay ?? 'NGS'} sequencing result`}
        subtitle={`${result.pipeline?.pipeline ?? 'NGS pipeline'} · ${displayedReference}${result.demo ? ' · SYNTHETIC DEMONSTRATION DATA' : ''}`}
        status={readiness.status}
        statusLabel={readiness.label}
        integrityNotice={integrityErrors.length > 0 ? <div className="flex items-start gap-2 rounded-lg border border-error/20 bg-error/5 p-3 text-xs leading-5 text-text-secondary"><ShieldWarning className="mt-0.5 h-4 w-4 shrink-0 text-error"/><span><strong className="text-error">Result structure validation failed.</strong> {integrityErrors.length} structural evidence issue{integrityErrors.length === 1 ? '' : 's'} must be resolved before the result can be reviewed. Raw evidence remains visible for debugging.</span></div> : <div className="flex items-start gap-2 rounded-lg border border-good/20 bg-good/5 p-3 text-xs leading-5 text-text-secondary"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-good"/><span><strong className="text-text-primary">Result structure validation passed.</strong> The response schema contains no duplicate stages or metrics, invalid QC states, or non-finite values. This check does not establish biological accuracy, production readiness, or clinical validity.{integrityWarnings.length ? ` ${integrityWarnings.length} non-blocking provenance warning${integrityWarnings.length === 1 ? '' : 's'} remain.` : ''}</span></div>}
        metadata={[{ label: 'Assay', value: result.detection?.assay ?? '—' }, { label: 'Library', value: result.detection?.library_type ?? '—' }, { label: 'Sample type', value: displayedSampleType }, { label: 'Reference', value: displayedReference }, { label: 'Pipeline', value: result.pipeline?.pipeline ?? '—' }, { label: 'Final gate', value: gate?.qc?.status ?? '—' }]}
        metrics={[{ label: 'Reads loaded', value: totalReads.toLocaleString() }, { label: 'Reads analyzed', value: result.requested?.reads_analyzed?.toLocaleString?.() ?? totalReads.toLocaleString() }, { label: 'Stages', value: stages.length }, { label: 'PASS', value: passed, status: 'PASS' }, { label: 'WARN', value: warned, status: warned ? 'WARN' : 'PASS' }, { label: 'FAIL', value: failed, status: failed ? 'FAIL' : 'PASS' }, { label: 'Mapped reads', value: Number(visualization.n_mapped || 0).toLocaleString() }, { label: 'Variants', value: Number(visualization.n_variants || 0).toLocaleString() }]}
        overview={<div className="space-y-5">{result.demo && <div className="rounded-lg border border-info/20 bg-info/5 p-4 text-xs leading-5 text-text-secondary"><strong className="text-text-primary">Demonstration dataset:</strong> {result.demo.description} This is synthetic test data, not a biological sample and cannot establish pipeline accuracy.</div>}<div className="grid gap-3 md:grid-cols-3"><div className="result-callout"><Database/><div><b>Assay routing</b><p>{result.detection?.assay ?? 'Unknown'} · {result.detection?.library_type ?? 'Unknown'}.</p></div></div><div className="result-callout"><FileText/><div><b>Evidence chain</b><p>{stages.length} unique stages returned with QC and decision records.</p></div></div><div className="result-callout"><MapTrifold/><div><b>Genome evidence</b><p>{visualization.n_mapped || 0} mapped reads and {visualization.n_variants || 0} variants.</p></div></div></div>{warnings.length > 0 && <div className="rounded-lg border border-warn/20 bg-warn/5 p-4"><div className="flex items-center gap-2 text-xs font-semibold text-warn"><Warning/>Warnings ({warnings.length})</div><ul className="mt-2 space-y-1 text-[11px] text-text-muted">{warnings.map((w)=><li key={w}>• {w}</li>)}</ul></div>}<NgsBenchmarkPanel claim={validation?.claim} summary={validation?.summary} sameOrBetterSupported={validation?.same_or_better_supported} comparisons={validation?.comparisons} analysisGrade={validation?.analysis_grade} researchReady={validation?.research_ready} requirements={validation?.production_requirements} inputSampling={validation?.input_sampling}/></div>}
        qc={<div className="space-y-4"><div className="rounded-lg border border-glass-border bg-surface-1 p-4 text-xs leading-5 text-text-secondary">QC contains observed values only. WARN and FAIL states are derived from the stage contracts; missing/partial fields are labelled rather than guessed.</div><StageEvidenceTable stages={stages}/></div>}
        results={<div className="space-y-5">{(visualization.sam || visualization.vcf) ? <div><div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-semibold text-text-primary">Genome evidence viewer</h3><span className="font-mono text-[10px] text-text-muted">{visualization.n_mapped || 0} mapped · {visualization.n_variants || 0} variants</span></div><GenomeViewer samText={visualization.sam || ''} vcfText={visualization.vcf || ''} locus={visualization.locus ?? undefined}/></div> : <div className="rounded-lg border border-glass-border bg-surface-1 p-4 text-sm text-text-muted">No SAM/VCF visualization was emitted. Review QC to identify the stopping or warning stage.</div>}<StageEvidenceTable stages={stages}/></div>}
        raw={<NgsArtifactPanel vcf={visualization.vcf || ''} sam={visualization.sam || ''} pipeline={result.pipeline}/>} 
        methods={<ProvenancePanel provenance={result.pipeline?.provenance ?? {}}/>}
        interpretation={<NgsEvidenceInterpretation stages={stages} pipelineStatus={verdict} warnings={warnings} integrityErrors={integrityErrors.map((issue) => issue.message)} demonstration={Boolean(result.demo)}/>} 
      />
    </>}
  </div>;
}

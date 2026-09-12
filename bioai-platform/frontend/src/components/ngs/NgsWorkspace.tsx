'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  ArrowCounterClockwise,
  ChartBar,
  CheckCircle,
  CircleNotch,
  Database,
  Dna,
  DownloadSimple,
  FileArrowDown,
  Flask,
  MapTrifold,
  ShieldCheck,
  TestTube,
  Warning,
} from '@phosphor-icons/react';
import { motion } from 'framer-motion';

import { fadeUp } from '@/lib/animations';
import { getNgsPortableBenchmark, runNgs2Analyze } from '@/lib/api';
import type { Ngs2AnalyzeResult, Ngs2Stage, NgsPortableBenchmark } from '@/lib/api';
import { validateScientificStages } from '@/lib/scientificIntegrity';
import { downloadNgsDemoFile, getNgsDemoCatalog, type NgsDemoCatalogItem } from '@/lib/ngsDemoApi';
import { BackButton, CriticalButton, FlatInput, PageHeader } from '@/components/ui';
import ScientificResultsWorkspace, { type ScientificStatus } from '@/components/results/ScientificResultsWorkspace';
import StageEvidenceTable from '@/components/results/StageEvidenceTable';
import { ProvenancePanel } from '@/components/results/ProvenancePanel';
import NgsArtifactPanel from '@/components/results/NgsArtifactPanel';
import NgsEvidenceInterpretation from '@/components/results/NgsEvidenceInterpretation';
import { NgsBenchmarkPanel } from '@/components/results/NgsBenchmarkPanel';
import { NgsPortableBenchmarkCard } from '@/components/results/NgsPortableBenchmarkCard';
import { NgsProductionSupportCard } from '@/components/results/NgsProductionSupportCard';
import { RnaSeqProductionSupportCard } from '@/components/results/RnaSeqProductionSupportCard';
import { AIResultSummary } from '@/components/results/AIResultSummary';
import GenomeViewer from '@/components/GenomeViewer';

const ASSAY_OPTIONS = [
  { value: '', label: 'Auto-detect assay' },
  { value: 'WGS', label: 'Whole Genome Sequencing (WGS)' },
  { value: 'WES', label: 'Whole Exome Sequencing (WES)' },
  { value: 'RNA-seq', label: 'RNA-seq read-level preview' },
];

const FALLBACK_DEMOS: NgsDemoCatalogItem[] = [
  { id: 'wgs-truth-control', label: 'WGS variant control', assay: 'WGS', description: 'Paired-end synthetic control containing one declared heterozygous SNV.', purpose: 'Variant calling and expected-vs-observed functional control', read_pairs: 16, read_length: 150, paired_end: true, truth_bearing: true, downloads: { r1: '', r2: '', reference: '' } },
  { id: 'wgs-clean', label: 'Clean WGS', assay: 'WGS', description: 'High-quality paired-end reads for a clean baseline run.', purpose: 'Clean paired-end WGS baseline', read_pairs: 180, read_length: 150, paired_end: true, truth_bearing: false, downloads: { r1: '', r2: '' } },
  { id: 'wgs-mixed-quality', label: 'Mixed-quality WGS', assay: 'WGS', description: 'Low-quality tails and duplicate burden for a realistic QC warning run.', purpose: 'QC/trimming warning demonstration', read_pairs: 180, read_length: 150, paired_end: true, truth_bearing: false, downloads: { r1: '', r2: '' } },
  { id: 'wes-small', label: 'Compact WES', assay: 'WES', description: 'Small exome-style paired-end demo for quickly exercising the WES route.', purpose: 'Compact WES-style workflow demonstration', read_pairs: 120, read_length: 150, paired_end: true, truth_bearing: false, downloads: { r1: '', r2: '' } },
];

type DemoMeta = {
  profile: string;
  label: string;
  description: string;
  synthetic: boolean;
  read_pairs: number;
  truth_set?: Array<Record<string, unknown>>;
  truth_scope?: string;
  functional_benchmark?: {
    classification: string;
    status: string;
    tp: number;
    fp: number;
    fn: number;
    precision: number | null;
    recall: number | null;
    claim: string;
  };
};

type ExtendedResult = Ngs2AnalyzeResult & {
  demo?: DemoMeta | null;
  requested: Ngs2AnalyzeResult['requested'] & { demo_profile?: string | null; reads_analyzed?: number };
};

type AnalysisMode = 'production-dna' | 'production-rna' | 'preview';
type AnyRecord = Record<string, unknown>;

function asRecord(value: unknown): AnyRecord {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as AnyRecord : {};
}

function finiteNumber(value: unknown): number | null {
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

function formatNumber(value: unknown, digits = 0): string {
  const n = finiteNumber(value);
  if (n === null) return '—';
  return n.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function formatPercent(value: unknown, digits = 1): string {
  const n = finiteNumber(value);
  return n === null ? '—' : `${n.toFixed(digits)}%`;
}

function findStage(stages: Ngs2Stage[], step: string): Ngs2Stage | undefined {
  return stages.find(stage => stage.step === step);
}

function notEvaluated(stage?: Ngs2Stage): boolean {
  if (!stage) return true;
  const data = asRecord(stage.data);
  return data.status === 'NOT_EVALUATED' || Boolean(data.unevaluated);
}

function displayStatus(stage?: Ngs2Stage): 'PASS' | 'WARN' | 'FAIL' | 'NA' {
  if (!stage || notEvaluated(stage)) return 'NA';
  const status = stage.qc?.status;
  if (status === 'PASS' || status === 'WARN' || status === 'FAIL') return status;
  return 'NA';
}

function worstStatus(stages: Array<Ngs2Stage | undefined>): 'PASS' | 'WARN' | 'FAIL' | 'NA' {
  const statuses = stages.map(displayStatus).filter(status => status !== 'NA');
  if (!statuses.length) return 'NA';
  if (statuses.includes('FAIL')) return 'FAIL';
  if (statuses.includes('WARN')) return 'WARN';
  return 'PASS';
}

function presentationStatus(core: Ngs2Stage[], demo: boolean): { status: ScientificStatus; label: string } {
  const statuses = core.map(displayStatus).filter(status => status !== 'NA');
  if (statuses.includes('FAIL')) return { status: 'FAIL', label: 'REVIEW REQUIRED' };
  if (statuses.includes('WARN')) return { status: 'WARN', label: demo ? 'DEMO COMPLETE · QC FLAGS' : 'PREVIEW COMPLETE · QC FLAGS' };
  return { status: 'PASS', label: demo ? 'DEMO COMPLETE' : 'PREVIEW COMPLETE' };
}

function statusClass(status: 'PASS' | 'WARN' | 'FAIL' | 'NA') {
  if (status === 'PASS') return 'border-good/25 bg-good/5 text-good';
  if (status === 'WARN') return 'border-warn/25 bg-warn/5 text-warn';
  if (status === 'FAIL') return 'border-error/25 bg-error/5 text-error';
  return 'border-glass-border bg-surface-1 text-text-muted';
}

function measuredMetric(stage: Ngs2Stage | undefined, name: string): unknown {
  return stage?.qc?.metrics?.find(metric => metric.name === name)?.value ?? null;
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
    <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-text-muted">{label}</p>
    <p className="mt-1 font-mono text-lg font-semibold text-text-primary">{value}</p>
    {detail && <p className="mt-1 text-[11px] leading-4 text-text-muted">{detail}</p>}
  </div>;
}

function PhaseCard({ label, detail, status }: { label: string; detail: string; status: 'PASS' | 'WARN' | 'FAIL' | 'NA' }) {
  return <div className={`rounded-xl border p-3 ${statusClass(status)}`}>
    <div className="flex items-center justify-between gap-2">
      <span className="text-xs font-semibold text-text-primary">{label}</span>
      <span className="font-mono text-[9px]">{status === 'NA' ? 'NOT EVALUATED' : status}</span>
    </div>
    <p className="mt-1 text-[11px] leading-4 text-text-muted">{detail}</p>
  </div>;
}

export default function NgsWorkspace() {
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode | null>('preview');
  const [filePaths, setFilePaths] = useState('');
  const [assay, setAssay] = useState('');
  const [reference, setReference] = useState('grch38');
  const [synthetic, setSynthetic] = useState(false);
  const [loading, setLoading] = useState(false);
  const [runningDemo, setRunningDemo] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExtendedResult | null>(null);
  const [portableBenchmark, setPortableBenchmark] = useState<NgsPortableBenchmark | null>(null);
  const [demos, setDemos] = useState<NgsDemoCatalogItem[]>(FALLBACK_DEMOS);

  useEffect(() => {
    getNgsPortableBenchmark().then(setPortableBenchmark).catch(() => setPortableBenchmark(null));
    getNgsDemoCatalog().then(items => { if (items.length) setDemos(items); }).catch(() => {});
  }, []);

  const resetResult = () => { setResult(null); setError(null); setRunningDemo(null); };
  const changeMode = (mode: AnalysisMode) => { setAnalysisMode(mode); setResult(null); setError(null); setRunningDemo(null); };

  const run = async (demoProfile?: string) => {
    const files = filePaths.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean);
    if (!demoProfile && files.length === 0) return;
    setLoading(true);
    setRunningDemo(demoProfile ?? null);
    setError(null);
    setResult(null);
    try {
      const payload = {
        file_paths: demoProfile ? [] : files,
        reference: reference || undefined,
        assay: demoProfile ? undefined : (assay || undefined),
        metadata: { platform: 'illumina', source: demoProfile ? 'bionexus-demo' : 'user', demonstration_data: Boolean(demoProfile) },
        synthetic_reference: demoProfile ? true : synthetic,
        demo_profile: demoProfile,
      };
      const response = await runNgs2Analyze(payload as Parameters<typeof runNgs2Analyze>[0] & { demo_profile?: string });
      setResult(response as ExtendedResult);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to run NGS analysis');
    } finally {
      setLoading(false);
      setRunningDemo(null);
    }
  };

  const downloadDemo = async (profile: string, kind: 'r1' | 'r2' | 'reference') => {
    const key = `${profile}:${kind}`;
    setDownloading(key);
    try {
      await downloadNgsDemoFile(profile, kind);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Demo file download failed');
    } finally {
      setDownloading(null);
    }
  };

  const stages = Array.isArray(result?.pipeline?.stages) ? result!.pipeline.stages : [];
  const visualization = result?.visualization ?? { sam: '', vcf: '', locus: null, n_reads: 0, n_mapped: 0, n_variants: 0 };
  const integrityIssues = validateScientificStages(stages);
  const integrityErrors = integrityIssues.filter(issue => issue.level === 'ERROR');
  const integrityWarnings = integrityIssues.filter(issue => issue.level === 'WARN');

  const inputStage = findStage(stages, 'input_validation');
  const rawQcStage = findStage(stages, 'raw_read_qc');
  const preprocessStage = findStage(stages, 'preprocessing');
  const referenceStage = findStage(stages, 'reference_validation');
  const alignmentStage = findStage(stages, 'alignment');
  const bamStage = findStage(stages, 'bam_processing');
  const alignmentQcStage = findStage(stages, 'alignment_qc');
  const coverageStage = findStage(stages, 'coverage');
  const variantStage = findStage(stages, 'variant_calling');
  const filterStage = findStage(stages, 'variant_filter');
  const annotationStage = findStage(stages, 'annotation');
  const gateStage = findStage(stages, 'final_gate');

  const rawQc = asRecord(rawQcStage?.data);
  const preprocessing = asRecord(preprocessStage?.data);
  const alignmentQc = asRecord(alignmentQcStage?.data);
  const coverage = asRecord(asRecord(coverageStage?.data).genome);
  const calledVariants = Array.isArray(asRecord(variantStage?.data).variants) ? asRecord(variantStage?.data).variants as AnyRecord[] : [];
  const filteredVariants = Array.isArray(asRecord(filterStage?.data).final) ? asRecord(filterStage?.data).final as AnyRecord[] : calledVariants;

  const optionalNotEvaluated = stages.filter(stage => notEvaluated(stage));
  const actionableWarnings = (result?.pipeline?.warnings ?? []).filter(warning => !warning.startsWith('[contamination] Not evaluated:') && !warning.startsWith('[identity] Not evaluated:'));
  const coreStages = [inputStage, rawQcStage, preprocessStage, referenceStage, alignmentStage, bamStage, alignmentQcStage, coverageStage, variantStage, filterStage, annotationStage, gateStage].filter(Boolean) as Ngs2Stage[];
  const mainStatus = presentationStatus(coreStages, Boolean(result?.demo));

  const readsLoaded = result?.requested?.reads_loaded && typeof result.requested.reads_loaded === 'object' ? result.requested.reads_loaded : {};
  const totalReads = Object.values(readsLoaded).reduce((sum, value) => sum + Number(value || 0), 0);
  const q30 = finiteNumber(rawQc.q30_percent);
  const q20 = finiteNumber(rawQc.q20_percent);
  const gc = finiteNumber(rawQc.gc_percent);
  const meanQuality = finiteNumber(rawQc.mean_quality);
  const retention = finiteNumber(preprocessing.read_loss_percent) === null ? null : 100 - Number(preprocessing.read_loss_percent);
  const mappingRate = finiteNumber(alignmentQc.mapping_rate) ?? finiteNumber(measuredMetric(alignmentStage, 'mapping_ok'));
  const duplicationRate = finiteNumber(alignmentQc.duplicate_rate) ?? finiteNumber(asRecord(bamStage?.data).duplicate_rate);
  const meanDepth = finiteNumber(coverage.mean_depth);
  const coverage1x = finiteNumber(coverage.coverage_1x);
  const coverage20x = finiteNumber(coverage.coverage_20x);
  const uniformity = finiteNumber(coverage.uniformity);
  const displayedVariantCount = filteredVariants.length || (variantStage ? calledVariants.length : null);

  const provenance = result?.pipeline?.provenance;
  const provenanceAnalysis = provenance?.analysis && typeof provenance.analysis === 'object' ? provenance.analysis as Record<string, unknown> : null;
  const provenanceReference = provenance?.reference && typeof provenance.reference === 'object' ? provenance.reference as Record<string, unknown> : null;
  const displayedReference = String(provenanceReference?.id ?? result?.requested?.reference ?? '—');
  const displayedSampleType = String(provenanceAnalysis?.sample_type ?? result?.detection?.sample_type ?? '—');

  const phaseCards = useMemo(() => [
    { label: 'Input & pairing', detail: `${formatNumber(totalReads)} reads loaded across ${Object.keys(readsLoaded).length || '—'} FASTQ file(s).`, status: worstStatus([inputStage]) },
    { label: 'Read QC', detail: `Q30 ${q30 === null ? '—' : q30.toFixed(1) + '%'} · GC ${gc === null ? '—' : gc.toFixed(1) + '%'}.`, status: worstStatus([rawQcStage]) },
    { label: 'Preprocessing', detail: `Read retention ${retention === null ? '—' : retention.toFixed(1) + '%'}.`, status: worstStatus([preprocessStage]) },
    { label: 'Reference', detail: displayedReference, status: worstStatus([referenceStage]) },
    { label: 'Alignment', detail: `Mapping ${mappingRate === null ? '—' : mappingRate.toFixed(1) + '%'}.`, status: worstStatus([alignmentStage, alignmentQcStage]) },
    { label: 'Coverage', detail: `Mean depth ${meanDepth === null ? '—' : meanDepth.toFixed(1) + '×'}.`, status: worstStatus([coverageStage]) },
    { label: 'Variants', detail: displayedVariantCount === null ? 'Not measured.' : `${displayedVariantCount} candidate variant${displayedVariantCount === 1 ? '' : 's'} after filtering.`, status: worstStatus([variantStage, filterStage, annotationStage]) },
    { label: 'Readiness', detail: gateStage ? `Final preview gate: ${gateStage.qc?.status ?? 'not reported'}.` : 'No final gate emitted.', status: worstStatus([gateStage]) },
  ], [totalReads, readsLoaded, q30, gc, retention, displayedReference, mappingRate, meanDepth, displayedVariantCount, inputStage, rawQcStage, preprocessStage, referenceStage, alignmentStage, alignmentQcStage, coverageStage, variantStage, filterStage, annotationStage, gateStage]);

  return <div className="scientific-page max-w-6xl space-y-6 pb-12">
    <BackButton />
    <PageHeader
      title="NGS Analysis Workspace"
      subtitle="Run a complete built-in dataset in one click, inspect measured QC and variant evidence, or move to durable nf-core production execution."
    />

    {!result && <>
      <section className="data-card overflow-hidden">
        <div className="border-b border-glass-border p-5">
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-text-muted">Choose analysis mode</p>
          <h2 className="mt-1 text-base font-semibold text-text-primary">One workspace, three execution paths</h2>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted">Start with a runnable demo to see the complete interface, then use the production lanes when compute and staged inputs are available.</p>
        </div>
        <div className="grid gap-px bg-glass-border lg:grid-cols-3">
          {[
            { id: 'preview' as const, title: 'Run demo / preview', text: 'Immediate deterministic runs with downloadable paired FASTQ inputs.', icon: TestTube },
            { id: 'production-dna' as const, title: 'WGS / WES production', text: 'Pinned nf-core/sarek execution on configured durable compute.', icon: Dna },
            { id: 'production-rna' as const, title: 'RNA-seq production', text: 'Pinned nf-core/rnaseq execution with transcriptomics-specific settings.', icon: Flask },
          ].map(option => {
            const Icon = option.icon;
            const active = analysisMode === option.id;
            return <button key={option.id} type="button" onClick={() => changeMode(option.id)} className={`p-5 text-left transition ${active ? 'bg-accent-cyan/10' : 'bg-surface-0 hover:bg-surface-1'}`}>
              <div className="flex items-start gap-3"><Icon className={`mt-0.5 h-5 w-5 ${active ? 'text-accent-cyan' : 'text-text-muted'}`}/><div><p className="text-sm font-semibold text-text-primary">{option.title}</p><p className="mt-1 text-xs leading-5 text-text-muted">{option.text}</p></div></div>
            </button>;
          })}
        </div>
      </section>

      {analysisMode === 'preview' && <>
        <motion.section variants={fadeUp} initial={{ y: 18 }} animate="show" className="data-card overflow-hidden">
          <div className="flex flex-col justify-between gap-3 border-b border-glass-border p-5 md:flex-row md:items-end">
            <div><p className="font-mono text-[10px] uppercase tracking-[0.14em] text-accent-cyan">Built-in datasets</p><h2 className="mt-1 text-base font-semibold text-text-primary">Run NGS without uploading a file</h2><p className="mt-1 max-w-2xl text-xs leading-5 text-text-muted">Every dataset is deterministic, paired-end and downloadable, so you can inspect the exact FASTQ used by BioNexus and rerun the same input later.</p></div>
            <span className="rounded-md border border-good/20 bg-good/5 px-2.5 py-1 text-[10px] font-medium text-good">READY TO RUN</span>
          </div>
          <div className="grid gap-px bg-glass-border md:grid-cols-2">
            {demos.map((demo, index) => <div key={demo.id} className="bg-surface-0 p-5">
              <div className="flex items-start justify-between gap-3">
                <div><div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold text-text-primary">{demo.label}</h3>{index === 0 && <span className="rounded border border-accent-cyan/25 bg-accent-cyan/5 px-1.5 py-0.5 text-[9px] font-medium text-accent-cyan">RECOMMENDED</span>}{demo.truth_bearing && <span className="rounded border border-good/25 bg-good/5 px-1.5 py-0.5 text-[9px] font-medium text-good">KNOWN TRUTH</span>}</div><p className="mt-1 text-xs leading-5 text-text-muted">{demo.description}</p></div>
                <span className="rounded border border-glass-border bg-surface-1 px-2 py-1 font-mono text-[9px] text-text-secondary">{demo.assay}</span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-[11px]"><div><span className="text-text-muted">Layout</span><p className="mt-0.5 font-mono text-text-primary">2×{demo.read_length} bp</p></div><div><span className="text-text-muted">Pairs</span><p className="mt-0.5 font-mono text-text-primary">{demo.read_pairs}</p></div><div><span className="text-text-muted">Purpose</span><p className="mt-0.5 text-text-primary">{demo.truth_bearing ? 'Variant control' : 'Workflow QC'}</p></div></div>
              <p className="mt-3 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-[11px] leading-4 text-text-muted">{demo.purpose}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                <CriticalButton onClick={() => run(demo.id)} disabled={loading} className="px-4 py-2 text-xs disabled:opacity-50">{runningDemo === demo.id ? <CircleNotch className="h-3.5 w-3.5 animate-spin"/> : <Dna className="h-3.5 w-3.5"/>}{runningDemo === demo.id ? 'Running…' : 'Run complete demo'}</CriticalButton>
                <button onClick={() => downloadDemo(demo.id, 'r1')} disabled={Boolean(downloading)} className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs text-text-secondary hover:text-text-primary disabled:opacity-50"><DownloadSimple className="h-3.5 w-3.5"/>R1</button>
                <button onClick={() => downloadDemo(demo.id, 'r2')} disabled={Boolean(downloading)} className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs text-text-secondary hover:text-text-primary disabled:opacity-50"><DownloadSimple className="h-3.5 w-3.5"/>R2</button>
                {demo.truth_bearing && <button onClick={() => downloadDemo(demo.id, 'reference')} disabled={Boolean(downloading)} className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs text-text-secondary hover:text-text-primary disabled:opacity-50"><FileArrowDown className="h-3.5 w-3.5"/>Reference</button>}
              </div>
            </div>)}
          </div>
        </motion.section>

        <details className="data-card overflow-hidden">
          <summary className="cursor-pointer list-none p-5 text-sm font-semibold text-text-primary">Advanced: analyze FASTQ already staged on a self-hosted BioNexus server</summary>
          <div className="space-y-4 border-t border-glass-border p-5">
            <div><label className="mb-1.5 block text-xs font-medium text-text-secondary">Server-local FASTQ paths</label><FlatInput type="text" value={filePaths} onChange={event => { setFilePaths(event.target.value); setError(null); }} placeholder="/data/SAMPLE_R1.fastq.gz, /data/SAMPLE_R2.fastq.gz" className="w-full px-4 py-3 font-mono text-sm"/><p className="mt-1.5 text-[11px] leading-4 text-text-muted">For self-hosted deployments only. Paths must be inside the configured NGS import root.</p></div>
            <div className="grid gap-4 md:grid-cols-2"><div><label className="mb-1.5 block text-xs text-text-muted">Assay</label><select value={assay} onChange={event => setAssay(event.target.value)} className="scientific-select">{ASSAY_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div><div><label className="mb-1.5 block text-xs text-text-muted">Reference</label><select value={reference} onChange={event => setReference(event.target.value)} className="scientific-select"><option value="grch38">GRCh38</option><option value="grch37">GRCh37</option></select></div></div>
            <label className="flex items-start gap-2 rounded-lg border border-glass-border bg-surface-1 p-3"><input type="checkbox" checked={synthetic} onChange={event => setSynthetic(event.target.checked)} className="mt-0.5"/><span><span className="block text-xs font-medium text-text-primary">Use a synthetic reference for interface testing</span><span className="mt-0.5 block text-[11px] text-text-muted">Leave off for real staged FASTQ inputs.</span></span></label>
            <CriticalButton onClick={() => run()} disabled={loading || !filePaths.trim()} className="w-full justify-center py-3 disabled:opacity-50">{loading && !runningDemo ? <CircleNotch className="h-4 w-4 animate-spin"/> : <Dna className="h-4 w-4"/>}{loading && !runningDemo ? 'Running preview…' : 'Analyze staged FASTQ'}</CriticalButton>
          </div>
        </details>
      </>}

      {analysisMode === 'production-dna' && <><NgsProductionSupportCard defaultReference="GRCh38"/>{portableBenchmark && <NgsPortableBenchmarkCard report={portableBenchmark}/>}</>}
      {analysisMode === 'production-rna' && <RnaSeqProductionSupportCard/>}
    </>}

    {error && <div className="rounded-xl border border-error/25 bg-error/10 p-4 text-sm text-error"><div className="flex items-start gap-2"><Warning className="mt-0.5 h-4 w-4 shrink-0"/><span>{error}</span></div><button onClick={() => setError(null)} className="mt-2 text-xs underline">Dismiss</button></div>}

    {result && <>
      <div className="flex justify-end"><button onClick={resetResult} className="inline-flex items-center gap-2 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs text-text-secondary hover:text-text-primary"><ArrowCounterClockwise/>Run another dataset</button></div>
      <ScientificResultsWorkspace
        title={result.demo ? result.demo.label : `${result.detection?.assay ?? 'NGS'} sequencing analysis`}
        subtitle={`${result.pipeline?.pipeline ?? 'NGS pipeline'} · ${displayedReference}${result.demo ? ' · built-in synthetic dataset' : ''}`}
        status={integrityErrors.length ? 'FAIL' : mainStatus.status}
        statusLabel={integrityErrors.length ? 'RESULT STRUCTURE ERROR' : mainStatus.label}
        integrityNotice={integrityErrors.length ? <div className="flex items-start gap-2 rounded-lg border border-error/20 bg-error/5 p-3 text-xs leading-5 text-text-secondary"><Warning className="mt-0.5 h-4 w-4 shrink-0 text-error"/><span><strong className="text-error">Result structure validation failed.</strong> {integrityErrors.length} blocking issue{integrityErrors.length === 1 ? '' : 's'} need review before interpretation.</span></div> : <div className="flex items-start gap-2 rounded-lg border border-good/20 bg-good/5 p-3 text-xs leading-5 text-text-secondary"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-good"/><span><strong className="text-text-primary">Result package is structurally valid.</strong> Measured values, provenance and stage decisions are internally consistent.{integrityWarnings.length ? ` ${integrityWarnings.length} non-blocking provenance warning${integrityWarnings.length === 1 ? '' : 's'} remain in Methods.` : ''}</span></div>}
        metadata={[
          { label: 'Assay', value: result.detection?.assay ?? '—' },
          { label: 'Library', value: result.detection?.library_type ?? '—' },
          { label: 'Sample', value: displayedSampleType },
          { label: 'Reference', value: displayedReference },
          { label: 'Input scope', value: result.requested?.all_records_processed ? 'All supplied records' : 'Sampled preview' },
          { label: 'Pipeline', value: result.pipeline?.pipeline ?? '—' },
        ]}
        metrics={[
          { label: 'Reads analyzed', value: formatNumber(result.requested?.reads_analyzed ?? totalReads) },
          { label: 'Q30 bases', value: q30 === null ? '—' : `${q30.toFixed(1)}%`, status: q30 === null ? undefined : q30 >= 80 ? 'PASS' : q30 >= 70 ? 'WARN' : 'FAIL' },
          { label: 'Read retention', value: retention === null ? '—' : `${retention.toFixed(1)}%` },
          { label: 'Mapping rate', value: mappingRate === null ? '—' : `${mappingRate.toFixed(1)}%` },
          { label: 'Mean depth', value: meanDepth === null ? '—' : `${meanDepth.toFixed(1)}×` },
          { label: 'Variants', value: displayedVariantCount === null ? '—' : displayedVariantCount },
          { label: 'Optional checks', value: optionalNotEvaluated.length ? `${optionalNotEvaluated.length} not evaluated` : 'All assessed' },
          { label: 'Core stages', value: `${coreStages.length} completed` },
        ]}
        overview={<div className="space-y-5">
          {result.demo && <div className="rounded-xl border border-accent-cyan/20 bg-accent-cyan/5 p-4"><div className="flex items-start gap-3"><TestTube className="mt-0.5 h-4 w-4 shrink-0 text-accent-cyan"/><div><p className="text-sm font-semibold text-text-primary">Built-in demonstration dataset</p><p className="mt-1 text-xs leading-5 text-text-secondary">{result.demo.description}</p><p className="mt-1 text-[11px] text-text-muted">Synthetic input is used to exercise the complete interface reproducibly. Biological validation is reported separately in the Methods tab.</p></div></div></div>}

          <div><div className="mb-2 flex items-center gap-2"><ChartBar className="h-4 w-4 text-accent-cyan"/><h3 className="text-sm font-semibold text-text-primary">Analysis at a glance</h3></div><div className="grid gap-3 md:grid-cols-4">{phaseCards.map(phase => <PhaseCard key={phase.label} {...phase}/>)}</div></div>

          <div className="grid gap-3 md:grid-cols-3">
            <MetricCard label="Read quality" value={q30 === null ? 'Not measured' : `Q30 ${q30.toFixed(1)}%`} detail={`Mean quality ${meanQuality === null ? '—' : meanQuality.toFixed(1)} · GC ${gc === null ? '—' : gc.toFixed(1) + '%'}`}/>
            <MetricCard label="Alignment" value={mappingRate === null ? 'Not measured' : `${mappingRate.toFixed(1)}% mapped`} detail={`Duplicate rate ${duplicationRate === null ? '—' : duplicationRate.toFixed(1) + '%'}`}/>
            <MetricCard label="Coverage" value={meanDepth === null ? 'Not measured' : `${meanDepth.toFixed(1)}× mean`} detail={`≥1× ${coverage1x === null ? '—' : coverage1x.toFixed(1) + '%'} · uniformity ${uniformity === null ? '—' : uniformity.toFixed(1) + '%'}`}/>
          </div>

          {result.demo?.functional_benchmark && <div className={`rounded-xl border p-4 ${result.demo.functional_benchmark.status === 'PASS' ? 'border-good/25 bg-good/5' : 'border-error/25 bg-error/5'}`}><div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-xs font-medium uppercase tracking-[0.1em] text-text-muted">Expected vs observed control</p><p className="mt-1 text-sm font-semibold text-text-primary">Declared synthetic variant recovery</p></div><span className={`rounded border px-2 py-1 font-mono text-[10px] ${result.demo.functional_benchmark.status === 'PASS' ? 'border-good/25 text-good' : 'border-error/25 text-error'}`}>{result.demo.functional_benchmark.status}</span></div><div className="mt-3 grid grid-cols-3 gap-3"><MetricCard label="True positive" value={String(result.demo.functional_benchmark.tp)}/><MetricCard label="False positive" value={String(result.demo.functional_benchmark.fp)}/><MetricCard label="False negative" value={String(result.demo.functional_benchmark.fn)}/></div></div>}

          {actionableWarnings.length > 0 && <div className="rounded-xl border border-warn/20 bg-warn/5 p-4"><div className="flex items-center gap-2 text-xs font-semibold text-warn"><Warning/>QC observations that need attention</div><ul className="mt-2 space-y-1.5 text-[11px] leading-4 text-text-secondary">{actionableWarnings.map(warning => <li key={warning}>• {warning}</li>)}</ul></div>}

          {optionalNotEvaluated.length > 0 && <div className="rounded-xl border border-glass-border bg-surface-1 p-4 text-xs leading-5 text-text-muted"><strong className="text-text-secondary">Optional preview checks:</strong> {optionalNotEvaluated.map(stage => stage.step.replaceAll('_', ' ')).join(', ')} were not evaluated in this lightweight run. They are listed in Methods instead of being shown as zero-valued failures.</div>}
        </div>}
        qc={<div className="space-y-5">
          <div className="grid gap-3 md:grid-cols-4"><MetricCard label="Q20" value={q20 === null ? '—' : `${q20.toFixed(1)}%`}/><MetricCard label="Q30" value={q30 === null ? '—' : `${q30.toFixed(1)}%`}/><MetricCard label="GC" value={gc === null ? '—' : `${gc.toFixed(1)}%`}/><MetricCard label="Mean quality" value={meanQuality === null ? '—' : meanQuality.toFixed(1)}/></div>
          <div className="grid gap-3 md:grid-cols-4"><MetricCard label="Retention" value={retention === null ? '—' : `${retention.toFixed(1)}%`}/><MetricCard label="Mapping" value={mappingRate === null ? '—' : `${mappingRate.toFixed(1)}%`}/><MetricCard label="Duplicate rate" value={duplicationRate === null ? '—' : `${duplicationRate.toFixed(1)}%`}/><MetricCard label="≥20× coverage" value={coverage20x === null ? '—' : `${coverage20x.toFixed(1)}%`}/></div>
          <div><h3 className="mb-2 text-sm font-semibold text-text-primary">Detailed stage evidence</h3><StageEvidenceTable stages={stages}/></div>
        </div>}
        results={<div className="space-y-5">
          <div><div className="mb-3 flex items-center justify-between gap-3"><div><h3 className="text-sm font-semibold text-text-primary">Candidate variants</h3><p className="mt-0.5 text-[11px] text-text-muted">Filtered candidates emitted by this run; unavailable fields remain blank rather than defaulting to zero.</p></div><span className="rounded border border-glass-border bg-surface-1 px-2 py-1 font-mono text-[10px] text-text-secondary">{displayedVariantCount === null ? 'not measured' : `${displayedVariantCount} total`}</span></div>
            {filteredVariants.length ? <div className="overflow-x-auto rounded-xl border border-glass-border"><table className="w-full text-xs"><thead className="bg-surface-1 text-text-muted"><tr><th className="px-3 py-2 text-left">Chrom</th><th className="px-3 py-2 text-left">Position</th><th className="px-3 py-2 text-left">Ref</th><th className="px-3 py-2 text-left">Alt</th><th className="px-3 py-2 text-left">Depth</th><th className="px-3 py-2 text-left">AF</th><th className="px-3 py-2 text-left">Callers</th></tr></thead><tbody className="divide-y divide-glass-border">{filteredVariants.slice(0, 50).map((variant, index) => <tr key={`${String(variant.chrom)}-${String(variant.pos)}-${index}`}><td className="px-3 py-2 font-mono text-text-primary">{String(variant.chrom ?? '—')}</td><td className="px-3 py-2 font-mono text-text-primary">{formatNumber(variant.pos)}</td><td className="px-3 py-2 font-mono text-good">{String(variant.ref ?? '—')}</td><td className="px-3 py-2 font-mono text-accent-cyan">{String(variant.alt ?? '—')}</td><td className="px-3 py-2 font-mono text-text-primary">{formatNumber(variant.dp)}</td><td className="px-3 py-2 font-mono text-text-primary">{finiteNumber(variant.af) === null ? '—' : `${(Number(variant.af) * 100).toFixed(1)}%`}</td><td className="px-3 py-2 text-text-muted">{Array.isArray(variant.callers) ? variant.callers.join(', ') : '—'}</td></tr>)}</tbody></table></div> : <div className="rounded-xl border border-good/20 bg-good/5 p-4 text-sm text-text-secondary"><div className="flex items-center gap-2"><CheckCircle className="h-4 w-4 text-good"/><span>{variantStage ? 'No candidate variants passed this preview.' : 'Variant calling was not evaluated for this assay.'}</span></div></div>}
          </div>
          {(visualization.sam || visualization.vcf) ? <div><div className="mb-3 flex items-center justify-between"><div><h3 className="text-sm font-semibold text-text-primary">Genome evidence viewer</h3><p className="mt-0.5 text-[11px] text-text-muted">Aligned reads and VCF evidence returned by this run.</p></div><span className="font-mono text-[10px] text-text-muted">{formatNumber(visualization.n_mapped)} mapped · {formatNumber(visualization.n_variants)} variants</span></div><GenomeViewer samText={visualization.sam || ''} vcfText={visualization.vcf || ''} locus={visualization.locus ?? undefined}/></div> : <div className="rounded-xl border border-glass-border bg-surface-1 p-4 text-sm text-text-muted">Genome visualization was not emitted for this result.</div>}
        </div>}
        raw={<NgsArtifactPanel vcf={visualization.vcf || ''} sam={visualization.sam || ''} pipeline={result.pipeline}/>} 
        methods={<div className="space-y-5"><ProvenancePanel provenance={result.pipeline?.provenance ?? {}}/><NgsBenchmarkPanel claim={result.pipeline?.validation?.claim} summary={result.pipeline?.validation?.summary} sameOrBetterSupported={result.pipeline?.validation?.same_or_better_supported} comparisons={result.pipeline?.validation?.comparisons} analysisGrade={result.pipeline?.validation?.analysis_grade} researchReady={result.pipeline?.validation?.research_ready} requirements={result.pipeline?.validation?.production_requirements} inputSampling={result.pipeline?.validation?.input_sampling} demonstration={Boolean(result.demo)}/><div><h3 className="mb-2 text-sm font-semibold text-text-primary">Complete stage ledger</h3><StageEvidenceTable stages={stages}/></div></div>}
        interpretation={<NgsEvidenceInterpretation stages={stages} pipelineStatus={result.pipeline?.pipeline_status ?? 'INFO'} warnings={actionableWarnings} integrityErrors={integrityErrors.map(issue => issue.message)} demonstration={Boolean(result.demo)}/>} 
        ai={<AIResultSummary toolName="ngs" result={result as unknown as Record<string, unknown>} title="AI explanation"/>}
      />
    </>}
  </div>;
}

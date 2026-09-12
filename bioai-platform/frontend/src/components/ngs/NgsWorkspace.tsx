'use client';

import { useEffect, useState } from 'react';
import {
  ArrowCounterClockwise,
  ChartBar,
  CheckCircle,
  CircleNotch,
  Dna,
  DownloadSimple,
  FileArrowDown,
  Flask,
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
  {
    id: 'wgs-truth-control', label: 'WGS variant control', assay: 'WGS',
    description: 'Paired-end synthetic control containing one declared heterozygous SNV.',
    purpose: 'Variant calling and expected-vs-observed functional control',
    read_pairs: 16, read_length: 150, paired_end: true, truth_bearing: true,
    downloads: { r1: '', r2: '', reference: '' },
  },
  {
    id: 'wgs-clean', label: 'Clean WGS', assay: 'WGS',
    description: 'High-quality paired-end reads for a clean baseline run.',
    purpose: 'Clean paired-end WGS baseline',
    read_pairs: 180, read_length: 150, paired_end: true, truth_bearing: false,
    downloads: { r1: '', r2: '' },
  },
  {
    id: 'wgs-mixed-quality', label: 'Mixed-quality WGS', assay: 'WGS',
    description: 'Low-quality tails and duplicate burden for a realistic QC-warning run.',
    purpose: 'QC and trimming warning demonstration',
    read_pairs: 180, read_length: 150, paired_end: true, truth_bearing: false,
    downloads: { r1: '', r2: '' },
  },
  {
    id: 'wes-small', label: 'Compact WES', assay: 'WES',
    description: 'Small exome-style paired-end dataset for quickly exercising the WES route.',
    purpose: 'Compact WES workflow demonstration',
    read_pairs: 120, read_length: 150, paired_end: true, truth_bearing: false,
    downloads: { r1: '', r2: '' },
  },
];

type DemoBenchmark = {
  classification: string;
  status: string;
  tp: number;
  fp: number;
  fn: number;
  precision: number | null;
  recall: number | null;
  claim: string;
};

type DemoMeta = {
  profile: string;
  label: string;
  description: string;
  synthetic: boolean;
  read_pairs: number;
  truth_set?: Array<Record<string, unknown>>;
  truth_scope?: string;
  functional_benchmark?: DemoBenchmark;
};

type ExtendedResult = Ngs2AnalyzeResult & {
  demo?: DemoMeta | null;
  requested: Ngs2AnalyzeResult['requested'] & {
    demo_profile?: string | null;
    reads_analyzed?: number;
  };
};

type AnalysisMode = 'preview' | 'production-dna' | 'production-rna';
type StagePresentationStatus = 'PASS' | 'WARN' | 'FAIL' | 'NA';
type UnknownRecord = Record<string, unknown>;

function record(value: unknown): UnknownRecord {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as UnknownRecord
    : {};
}

function numberOrNull(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null;
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function numberLabel(value: unknown, digits = 0): string {
  const parsed = numberOrNull(value);
  return parsed === null
    ? '—'
    : parsed.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function stage(stages: Ngs2Stage[], name: string): Ngs2Stage | undefined {
  return stages.find(item => item.step === name);
}

function isNotEvaluated(item?: Ngs2Stage): boolean {
  if (!item) return true;
  const data = record(item.data);
  return data.status === 'NOT_EVALUATED' || Boolean(data.unevaluated);
}

function stageStatus(item?: Ngs2Stage): StagePresentationStatus {
  if (!item || isNotEvaluated(item)) return 'NA';
  const status = item.qc?.status;
  if (status === 'PASS' || status === 'WARN' || status === 'FAIL') return status;
  return 'NA';
}

function combinedStatus(items: Array<Ngs2Stage | undefined>): StagePresentationStatus {
  const values = items.map(stageStatus).filter(value => value !== 'NA');
  if (!values.length) return 'NA';
  if (values.includes('FAIL')) return 'FAIL';
  if (values.includes('WARN')) return 'WARN';
  return 'PASS';
}

function overallPresentationStatus(items: Ngs2Stage[], demo: boolean): { status: ScientificStatus; label: string } {
  const statuses = items.map(stageStatus).filter(value => value !== 'NA');
  if (statuses.includes('FAIL')) return { status: 'FAIL', label: 'REVIEW REQUIRED' };
  if (statuses.includes('WARN')) {
    return { status: 'WARN', label: demo ? 'DEMO COMPLETE · QC FLAGS' : 'PREVIEW COMPLETE · QC FLAGS' };
  }
  return { status: 'PASS', label: demo ? 'DEMO COMPLETE' : 'PREVIEW COMPLETE' };
}

function metric(item: Ngs2Stage | undefined, name: string): unknown {
  return item?.qc?.metrics?.find(entry => entry.name === name)?.value ?? null;
}

function badgeClass(status: StagePresentationStatus): string {
  if (status === 'PASS') return 'border-good/25 bg-good/5 text-good';
  if (status === 'WARN') return 'border-warn/25 bg-warn/5 text-warn';
  if (status === 'FAIL') return 'border-error/25 bg-error/5 text-error';
  return 'border-glass-border bg-surface-1 text-text-muted';
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
      <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-text-muted">{label}</p>
      <p className="mt-1 font-mono text-lg font-semibold text-text-primary">{value}</p>
      {detail && <p className="mt-1 text-[11px] leading-4 text-text-muted">{detail}</p>}
    </div>
  );
}

function PhaseCard({ label, detail, status }: { label: string; detail: string; status: StagePresentationStatus }) {
  return (
    <div className={`rounded-xl border p-3 ${badgeClass(status)}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-text-primary">{label}</span>
        <span className="font-mono text-[9px]">{status === 'NA' ? 'NOT EVALUATED' : status}</span>
      </div>
      <p className="mt-1 text-[11px] leading-4 text-text-muted">{detail}</p>
    </div>
  );
}

export default function NgsWorkspace() {
  const [mode, setMode] = useState<AnalysisMode>('preview');
  const [filePaths, setFilePaths] = useState('');
  const [assay, setAssay] = useState('');
  const [reference, setReference] = useState('grch38');
  const [syntheticReference, setSyntheticReference] = useState(false);
  const [loading, setLoading] = useState(false);
  const [runningDemo, setRunningDemo] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExtendedResult | null>(null);
  const [demos, setDemos] = useState<NgsDemoCatalogItem[]>(FALLBACK_DEMOS);
  const [portableBenchmark, setPortableBenchmark] = useState<NgsPortableBenchmark | null>(null);

  useEffect(() => {
    getNgsDemoCatalog().then(items => {
      if (items.length) setDemos(items);
    }).catch(() => undefined);
    getNgsPortableBenchmark().then(setPortableBenchmark).catch(() => setPortableBenchmark(null));
  }, []);

  const reset = () => {
    setResult(null);
    setError(null);
    setRunningDemo(null);
  };

  const selectMode = (nextMode: AnalysisMode) => {
    setMode(nextMode);
    reset();
  };

  const run = async (demoProfile?: string) => {
    const files = filePaths.split(/[\n,]+/).map(value => value.trim()).filter(Boolean);
    if (!demoProfile && !files.length) return;

    setLoading(true);
    setRunningDemo(demoProfile ?? null);
    setError(null);
    setResult(null);
    try {
      const response = await runNgs2Analyze({
        file_paths: demoProfile ? [] : files,
        reference: reference || undefined,
        assay: demoProfile ? undefined : (assay || undefined),
        metadata: {
          platform: 'illumina',
          source: demoProfile ? 'bionexus-demo' : 'user',
          demonstration_data: Boolean(demoProfile),
        },
        synthetic_reference: demoProfile ? true : syntheticReference,
        demo_profile: demoProfile,
      } as Parameters<typeof runNgs2Analyze>[0] & { demo_profile?: string });
      setResult(response as ExtendedResult);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'NGS analysis could not be completed.');
    } finally {
      setLoading(false);
      setRunningDemo(null);
    }
  };

  const download = async (profile: string, kind: 'r1' | 'r2' | 'reference') => {
    const key = `${profile}:${kind}`;
    setDownloading(key);
    setError(null);
    try {
      await downloadNgsDemoFile(profile, kind);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'Demo file download failed.');
    } finally {
      setDownloading(null);
    }
  };

  const stages = result?.pipeline?.stages ?? [];
  const input = stage(stages, 'input_validation');
  const rawQc = stage(stages, 'raw_read_qc');
  const preprocess = stage(stages, 'preprocessing');
  const referenceStage = stage(stages, 'reference_validation');
  const alignment = stage(stages, 'alignment');
  const bam = stage(stages, 'bam_processing');
  const alignmentQc = stage(stages, 'alignment_qc');
  const coverageStage = stage(stages, 'coverage');
  const variants = stage(stages, 'variant_calling');
  const variantFilter = stage(stages, 'variant_filter');
  const annotation = stage(stages, 'annotation');
  const finalGate = stage(stages, 'final_gate');

  const rawQcData = record(rawQc?.data);
  const preprocessingData = record(preprocess?.data);
  const alignmentQcData = record(alignmentQc?.data);
  const coverageData = record(record(coverageStage?.data).genome);
  const variantData = record(variants?.data);
  const filterData = record(variantFilter?.data);
  const calledVariants = Array.isArray(variantData.variants) ? variantData.variants as UnknownRecord[] : [];
  const filteredVariants = Array.isArray(filterData.final) ? filterData.final as UnknownRecord[] : calledVariants;

  const readsLoaded = result?.requested?.reads_loaded ?? {};
  const totalReads = Object.values(readsLoaded).reduce((sum, value) => sum + Number(value || 0), 0);
  const q20 = numberOrNull(rawQcData.q20_percent);
  const q30 = numberOrNull(rawQcData.q30_percent);
  const gc = numberOrNull(rawQcData.gc_percent);
  const meanQuality = numberOrNull(rawQcData.mean_quality);
  const readLoss = numberOrNull(preprocessingData.read_loss_percent);
  const retention = readLoss === null ? null : 100 - readLoss;
  const mappingRate = numberOrNull(alignmentQcData.mapping_rate) ?? numberOrNull(metric(alignment, 'mapping_ok'));
  const duplicationRate = numberOrNull(alignmentQcData.duplicate_rate) ?? numberOrNull(record(bam?.data).duplicate_rate);
  const meanDepth = numberOrNull(coverageData.mean_depth);
  const coverage1x = numberOrNull(coverageData.coverage_1x);
  const coverage20x = numberOrNull(coverageData.coverage_20x);
  const uniformity = numberOrNull(coverageData.uniformity);
  const variantCount = variantFilter ? filteredVariants.length : variants ? calledVariants.length : null;

  const provenance = result?.pipeline?.provenance ?? {};
  const provenanceAnalysis = record(record(provenance).analysis);
  const provenanceReference = record(record(provenance).reference);
  const displayedReference = String(provenanceReference.id ?? result?.requested?.reference ?? '—');
  const displayedSample = String(provenanceAnalysis.sample_type ?? result?.detection?.sample_type ?? '—');

  const optionalNotEvaluated = stages.filter(isNotEvaluated);
  const actionableWarnings = (result?.pipeline?.warnings ?? []).filter(message => {
    return !message.startsWith('[contamination] Not evaluated:') && !message.startsWith('[identity] Not evaluated:');
  });

  // The primary result status is based on measured scientific stages only. The final
  // software gate and explicit NOT_EVALUATED stages remain visible in Methods.
  const measuredCoreStages = [
    input, rawQc, preprocess, referenceStage, alignment, bam, alignmentQc,
    coverageStage, variants, variantFilter, annotation,
  ].filter(Boolean) as Ngs2Stage[];
  const presentation = overallPresentationStatus(measuredCoreStages, Boolean(result?.demo));

  const integrityIssues = validateScientificStages(stages);
  const integrityErrors = integrityIssues.filter(issue => issue.level === 'ERROR');
  const integrityWarnings = integrityIssues.filter(issue => issue.level === 'WARN');
  const visualization = result?.visualization ?? {
    sam: '', vcf: '', locus: null, n_reads: 0, n_mapped: 0, n_variants: 0,
  };

  const phaseCards = [
    {
      label: 'Input & pairing',
      detail: `${numberLabel(totalReads)} reads across ${Object.keys(readsLoaded).length || '—'} FASTQ file(s).`,
      status: combinedStatus([input]),
    },
    {
      label: 'Read QC',
      detail: `Q30 ${q30 === null ? '—' : `${q30.toFixed(1)}%`} · GC ${gc === null ? '—' : `${gc.toFixed(1)}%`}.`,
      status: combinedStatus([rawQc]),
    },
    {
      label: 'Preprocessing',
      detail: `Read retention ${retention === null ? '—' : `${retention.toFixed(1)}%`}.`,
      status: combinedStatus([preprocess]),
    },
    {
      label: 'Alignment',
      detail: `Mapping ${mappingRate === null ? '—' : `${mappingRate.toFixed(1)}%`}.`,
      status: combinedStatus([alignment, alignmentQc]),
    },
    {
      label: 'Coverage',
      detail: `Mean depth ${meanDepth === null ? '—' : `${meanDepth.toFixed(1)}×`}.`,
      status: combinedStatus([coverageStage]),
    },
    {
      label: 'Variants',
      detail: variantCount === null ? 'Not measured.' : `${variantCount} candidate variant${variantCount === 1 ? '' : 's'} after filtering.`,
      status: combinedStatus([variants, variantFilter, annotation]),
    },
    {
      label: 'Readiness',
      detail: finalGate
        ? String(record(finalGate.data).verdict ?? finalGate.qc?.status ?? 'Not reported')
        : 'Not reported',
      status: combinedStatus([finalGate]),
    },
  ];

  return (
    <div className="scientific-page max-w-6xl space-y-6 pb-12">
      <BackButton />
      <PageHeader
        title="NGS Analysis Workspace"
        subtitle="Run a complete built-in dataset, inspect measured QC and variant evidence, or submit durable nf-core production workflows."
      />

      {!result && (
        <>
          <section className="data-card overflow-hidden">
            <div className="border-b border-glass-border p-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-text-muted">Analysis mode</p>
              <h2 className="mt-1 text-base font-semibold text-text-primary">Choose the execution path that matches your data</h2>
              <p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted">
                The demo path is immediately runnable. Production WGS/WES and RNA-seq keep their durable nf-core execution contracts separate from the in-process preview.
              </p>
            </div>
            <div className="grid gap-px bg-glass-border lg:grid-cols-3">
              {[
                { id: 'preview' as const, title: 'Demo / preview', text: 'Downloadable paired FASTQ datasets and immediate measured results.', icon: TestTube },
                { id: 'production-dna' as const, title: 'WGS / WES production', text: 'Pinned nf-core/sarek workflow on configured durable compute.', icon: Dna },
                { id: 'production-rna' as const, title: 'RNA-seq production', text: 'Pinned nf-core/rnaseq workflow with transcriptomics-specific settings.', icon: Flask },
              ].map(option => {
                const Icon = option.icon;
                const active = mode === option.id;
                return (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => selectMode(option.id)}
                    className={`p-5 text-left transition ${active ? 'bg-accent-cyan/10' : 'bg-surface-0 hover:bg-surface-1'}`}
                  >
                    <div className="flex items-start gap-3">
                      <Icon className={`mt-0.5 h-5 w-5 ${active ? 'text-accent-cyan' : 'text-text-muted'}`} />
                      <div>
                        <p className="text-sm font-semibold text-text-primary">{option.title}</p>
                        <p className="mt-1 text-xs leading-5 text-text-muted">{option.text}</p>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          {mode === 'preview' && (
            <>
              <motion.section variants={fadeUp} initial={{ y: 18 }} animate="show" className="data-card overflow-hidden">
                <div className="flex flex-col justify-between gap-3 border-b border-glass-border p-5 md:flex-row md:items-end">
                  <div>
                    <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-accent-cyan">Built-in datasets</p>
                    <h2 className="mt-1 text-base font-semibold text-text-primary">Run the complete NGS interface without uploading anything</h2>
                    <p className="mt-1 max-w-2xl text-xs leading-5 text-text-muted">
                      Every dataset is deterministic, paired-end and downloadable. The exact R1/R2 inputs used by the demo are available beside the run button.
                    </p>
                  </div>
                  <span className="rounded-md border border-good/20 bg-good/5 px-2.5 py-1 text-[10px] font-medium text-good">READY TO RUN</span>
                </div>

                <div className="grid gap-px bg-glass-border md:grid-cols-2">
                  {demos.map((demo, index) => (
                    <article key={demo.id} className="bg-surface-0 p-5">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-sm font-semibold text-text-primary">{demo.label}</h3>
                            {index === 0 && <span className="rounded border border-accent-cyan/25 bg-accent-cyan/5 px-1.5 py-0.5 text-[9px] font-medium text-accent-cyan">RECOMMENDED</span>}
                            {demo.truth_bearing && <span className="rounded border border-good/25 bg-good/5 px-1.5 py-0.5 text-[9px] font-medium text-good">KNOWN TRUTH</span>}
                          </div>
                          <p className="mt-1 text-xs leading-5 text-text-muted">{demo.description}</p>
                        </div>
                        <span className="rounded border border-glass-border bg-surface-1 px-2 py-1 font-mono text-[9px] text-text-secondary">{demo.assay}</span>
                      </div>

                      <div className="mt-3 grid grid-cols-3 gap-2 text-[11px]">
                        <div><span className="text-text-muted">Layout</span><p className="mt-0.5 font-mono text-text-primary">2×{demo.read_length} bp</p></div>
                        <div><span className="text-text-muted">Pairs</span><p className="mt-0.5 font-mono text-text-primary">{demo.read_pairs}</p></div>
                        <div><span className="text-text-muted">Purpose</span><p className="mt-0.5 text-text-primary">{demo.truth_bearing ? 'Variant control' : 'Workflow QC'}</p></div>
                      </div>

                      <p className="mt-3 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-[11px] leading-4 text-text-muted">{demo.purpose}</p>

                      <div className="mt-4 flex flex-wrap gap-2">
                        <CriticalButton onClick={() => run(demo.id)} disabled={loading} className="px-4 py-2 text-xs disabled:opacity-50">
                          {runningDemo === demo.id ? <CircleNotch className="h-3.5 w-3.5 animate-spin" /> : <Dna className="h-3.5 w-3.5" />}
                          {runningDemo === demo.id ? 'Running…' : 'Run complete demo'}
                        </CriticalButton>
                        <button onClick={() => download(demo.id, 'r1')} disabled={Boolean(downloading)} className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs text-text-secondary hover:text-text-primary disabled:opacity-50"><DownloadSimple className="h-3.5 w-3.5" />R1</button>
                        <button onClick={() => download(demo.id, 'r2')} disabled={Boolean(downloading)} className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs text-text-secondary hover:text-text-primary disabled:opacity-50"><DownloadSimple className="h-3.5 w-3.5" />R2</button>
                        {demo.truth_bearing && (
                          <button onClick={() => download(demo.id, 'reference')} disabled={Boolean(downloading)} className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs text-text-secondary hover:text-text-primary disabled:opacity-50"><FileArrowDown className="h-3.5 w-3.5" />Reference</button>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              </motion.section>

              <details className="data-card overflow-hidden">
                <summary className="cursor-pointer list-none p-5 text-sm font-semibold text-text-primary">Advanced: analyze FASTQ already staged on a self-hosted BioNexus server</summary>
                <div className="space-y-4 border-t border-glass-border p-5">
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-text-secondary">Server-local FASTQ paths</label>
                    <FlatInput
                      type="text"
                      value={filePaths}
                      onChange={event => { setFilePaths(event.target.value); setError(null); }}
                      placeholder="/data/SAMPLE_R1.fastq.gz, /data/SAMPLE_R2.fastq.gz"
                      className="w-full px-4 py-3 font-mono text-sm"
                    />
                    <p className="mt-1.5 text-[11px] leading-4 text-text-muted">For self-hosted deployments only. Paths must be inside the configured NGS import root.</p>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div>
                      <label className="mb-1.5 block text-xs text-text-muted">Assay</label>
                      <select value={assay} onChange={event => setAssay(event.target.value)} className="scientific-select">
                        {ASSAY_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="mb-1.5 block text-xs text-text-muted">Reference</label>
                      <select value={reference} onChange={event => setReference(event.target.value)} className="scientific-select">
                        <option value="grch38">GRCh38</option>
                        <option value="grch37">GRCh37</option>
                      </select>
                    </div>
                  </div>
                  <label className="flex items-start gap-2 rounded-lg border border-glass-border bg-surface-1 p-3">
                    <input type="checkbox" checked={syntheticReference} onChange={event => setSyntheticReference(event.target.checked)} className="mt-0.5" />
                    <span>
                      <span className="block text-xs font-medium text-text-primary">Use synthetic reference for interface testing</span>
                      <span className="mt-0.5 block text-[11px] text-text-muted">Leave disabled for real staged inputs.</span>
                    </span>
                  </label>
                  <CriticalButton onClick={() => run()} disabled={loading || !filePaths.trim()} className="w-full justify-center py-3 disabled:opacity-50">
                    {loading && !runningDemo ? <CircleNotch className="h-4 w-4 animate-spin" /> : <Dna className="h-4 w-4" />}
                    {loading && !runningDemo ? 'Running preview…' : 'Analyze staged FASTQ'}
                  </CriticalButton>
                </div>
              </details>
            </>
          )}

          {mode === 'production-dna' && (
            <>
              <NgsProductionSupportCard defaultReference="GRCh38" />
              {portableBenchmark && <NgsPortableBenchmarkCard report={portableBenchmark} />}
            </>
          )}
          {mode === 'production-rna' && <RnaSeqProductionSupportCard />}
        </>
      )}

      {error && (
        <div className="rounded-xl border border-error/25 bg-error/10 p-4 text-sm text-error">
          <div className="flex items-start gap-2"><Warning className="mt-0.5 h-4 w-4 shrink-0" /><span>{error}</span></div>
          <button onClick={() => setError(null)} className="mt-2 text-xs underline">Dismiss</button>
        </div>
      )}

      {result && (
        <>
          <div className="flex justify-end">
            <button onClick={reset} className="inline-flex items-center gap-2 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs text-text-secondary hover:text-text-primary">
              <ArrowCounterClockwise /> Run another dataset
            </button>
          </div>

          <ScientificResultsWorkspace
            title={result.demo ? result.demo.label : `${result.detection?.assay ?? 'NGS'} sequencing analysis`}
            subtitle={`${result.pipeline?.pipeline ?? 'NGS pipeline'} · ${displayedReference}${result.demo ? ' · built-in synthetic dataset' : ''}`}
            status={integrityErrors.length ? 'FAIL' : presentation.status}
            statusLabel={integrityErrors.length ? 'RESULT STRUCTURE ERROR' : presentation.label}
            integrityNotice={integrityErrors.length ? (
              <div className="flex items-start gap-2 rounded-lg border border-error/20 bg-error/5 p-3 text-xs leading-5 text-text-secondary">
                <Warning className="mt-0.5 h-4 w-4 shrink-0 text-error" />
                <span><strong className="text-error">Result structure validation failed.</strong> {integrityErrors.length} blocking issue{integrityErrors.length === 1 ? '' : 's'} require review.</span>
              </div>
            ) : (
              <div className="flex items-start gap-2 rounded-lg border border-good/20 bg-good/5 p-3 text-xs leading-5 text-text-secondary">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-good" />
                <span><strong className="text-text-primary">Result package is structurally valid.</strong> Measured values and provenance are internally consistent.{integrityWarnings.length ? ` ${integrityWarnings.length} non-blocking provenance warning${integrityWarnings.length === 1 ? '' : 's'} remain in Methods.` : ''}</span>
              </div>
            )}
            metadata={[
              { label: 'Assay', value: result.detection?.assay ?? '—' },
              { label: 'Library', value: result.detection?.library_type ?? '—' },
              { label: 'Sample', value: displayedSample },
              { label: 'Reference', value: displayedReference },
              { label: 'Input scope', value: result.requested?.all_records_processed ? 'All supplied records' : 'Sampled preview' },
              { label: 'Pipeline', value: result.pipeline?.pipeline ?? '—' },
            ]}
            metrics={[
              { label: 'Reads analyzed', value: numberLabel(result.requested?.reads_analyzed ?? totalReads) },
              { label: 'Q30 bases', value: q30 === null ? '—' : `${q30.toFixed(1)}%`, status: q30 === null ? undefined : q30 >= 80 ? 'PASS' : q30 >= 70 ? 'WARN' : 'FAIL' },
              { label: 'Read retention', value: retention === null ? '—' : `${retention.toFixed(1)}%` },
              { label: 'Mapping rate', value: mappingRate === null ? '—' : `${mappingRate.toFixed(1)}%` },
              { label: 'Mean depth', value: meanDepth === null ? '—' : `${meanDepth.toFixed(1)}×` },
              { label: 'Filtered variants', value: variantCount === null ? '—' : variantCount },
              { label: 'Optional checks', value: optionalNotEvaluated.length ? `${optionalNotEvaluated.length} not evaluated` : 'All assessed' },
              { label: 'Measured stages', value: `${measuredCoreStages.length} completed` },
            ]}
            overview={(
              <div className="space-y-5">
                {result.demo && (
                  <div className="rounded-xl border border-accent-cyan/20 bg-accent-cyan/5 p-4">
                    <div className="flex items-start gap-3">
                      <TestTube className="mt-0.5 h-4 w-4 shrink-0 text-accent-cyan" />
                      <div>
                        <p className="text-sm font-semibold text-text-primary">Built-in demonstration dataset</p>
                        <p className="mt-1 text-xs leading-5 text-text-secondary">{result.demo.description}</p>
                        <p className="mt-1 text-[11px] text-text-muted">Synthetic data makes the workflow reproducible and inspectable. It does not substitute for external biological benchmarking.</p>
                      </div>
                    </div>
                  </div>
                )}

                <div>
                  <div className="mb-2 flex items-center gap-2"><ChartBar className="h-4 w-4 text-accent-cyan" /><h3 className="text-sm font-semibold text-text-primary">Analysis at a glance</h3></div>
                  <div className="grid gap-3 md:grid-cols-4">{phaseCards.map(item => <PhaseCard key={item.label} {...item} />)}</div>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  <MetricCard label="Read quality" value={q30 === null ? 'Not measured' : `Q30 ${q30.toFixed(1)}%`} detail={`Mean Q ${meanQuality === null ? '—' : meanQuality.toFixed(1)} · GC ${gc === null ? '—' : `${gc.toFixed(1)}%`}`} />
                  <MetricCard label="Alignment" value={mappingRate === null ? 'Not measured' : `${mappingRate.toFixed(1)}% mapped`} detail={`Duplicate rate ${duplicationRate === null ? '—' : `${duplicationRate.toFixed(1)}%`}`} />
                  <MetricCard label="Coverage" value={meanDepth === null ? 'Not measured' : `${meanDepth.toFixed(1)}× mean`} detail={`≥1× ${coverage1x === null ? '—' : `${coverage1x.toFixed(1)}%`} · uniformity ${uniformity === null ? '—' : `${uniformity.toFixed(1)}%`}`} />
                </div>

                {result.demo?.functional_benchmark && (
                  <div className={`rounded-xl border p-4 ${result.demo.functional_benchmark.status === 'PASS' ? 'border-good/25 bg-good/5' : 'border-error/25 bg-error/5'}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div><p className="text-[10px] font-medium uppercase tracking-[0.1em] text-text-muted">Expected vs observed control</p><p className="mt-1 text-sm font-semibold text-text-primary">Declared synthetic variant recovery</p></div>
                      <span className={`rounded border px-2 py-1 font-mono text-[10px] ${result.demo.functional_benchmark.status === 'PASS' ? 'border-good/25 text-good' : 'border-error/25 text-error'}`}>{result.demo.functional_benchmark.status}</span>
                    </div>
                    <div className="mt-3 grid grid-cols-3 gap-3">
                      <MetricCard label="True positive" value={String(result.demo.functional_benchmark.tp)} />
                      <MetricCard label="False positive" value={String(result.demo.functional_benchmark.fp)} />
                      <MetricCard label="False negative" value={String(result.demo.functional_benchmark.fn)} />
                    </div>
                  </div>
                )}

                {actionableWarnings.length > 0 && (
                  <div className="rounded-xl border border-warn/20 bg-warn/5 p-4">
                    <div className="flex items-center gap-2 text-xs font-semibold text-warn"><Warning />Measured QC observations</div>
                    <ul className="mt-2 space-y-1.5 text-[11px] leading-4 text-text-secondary">{actionableWarnings.map(message => <li key={message}>• {message}</li>)}</ul>
                  </div>
                )}

                {optionalNotEvaluated.length > 0 && (
                  <div className="rounded-xl border border-glass-border bg-surface-1 p-4 text-xs leading-5 text-text-muted">
                    <strong className="text-text-secondary">Not evaluated in this preview:</strong> {optionalNotEvaluated.map(item => item.step.replaceAll('_', ' ')).join(', ')}. These remain missing evidence; they are not displayed as zero, PASS, WARN, FAIL, or a negative biological finding.
                  </div>
                )}
              </div>
            )}
            qc={(
              <div className="space-y-5">
                <div className="grid gap-3 md:grid-cols-4">
                  <MetricCard label="Q20" value={q20 === null ? '—' : `${q20.toFixed(1)}%`} />
                  <MetricCard label="Q30" value={q30 === null ? '—' : `${q30.toFixed(1)}%`} />
                  <MetricCard label="GC" value={gc === null ? '—' : `${gc.toFixed(1)}%`} />
                  <MetricCard label="Mean quality" value={meanQuality === null ? '—' : meanQuality.toFixed(1)} />
                </div>
                <div className="grid gap-3 md:grid-cols-4">
                  <MetricCard label="Retention" value={retention === null ? '—' : `${retention.toFixed(1)}%`} />
                  <MetricCard label="Mapping" value={mappingRate === null ? '—' : `${mappingRate.toFixed(1)}%`} />
                  <MetricCard label="Duplicate rate" value={duplicationRate === null ? '—' : `${duplicationRate.toFixed(1)}%`} />
                  <MetricCard label="≥20× coverage" value={coverage20x === null ? '—' : `${coverage20x.toFixed(1)}%`} />
                </div>
                <div><h3 className="mb-2 text-sm font-semibold text-text-primary">Detailed stage evidence</h3><StageEvidenceTable stages={stages} /></div>
              </div>
            )}
            results={(
              <div className="space-y-5">
                <div>
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div><h3 className="text-sm font-semibold text-text-primary">Filtered candidate variants</h3><p className="mt-0.5 text-[11px] text-text-muted">Only post-filter candidates are counted here. Missing fields remain blank rather than becoming zero.</p></div>
                    <span className="rounded border border-glass-border bg-surface-1 px-2 py-1 font-mono text-[10px] text-text-secondary">{variantCount === null ? 'not measured' : `${variantCount} total`}</span>
                  </div>

                  {filteredVariants.length > 0 ? (
                    <div className="overflow-x-auto rounded-xl border border-glass-border">
                      <table className="w-full text-xs">
                        <thead className="bg-surface-1 text-text-muted"><tr><th className="px-3 py-2 text-left">Chrom</th><th className="px-3 py-2 text-left">Position</th><th className="px-3 py-2 text-left">Ref</th><th className="px-3 py-2 text-left">Alt</th><th className="px-3 py-2 text-left">Depth</th><th className="px-3 py-2 text-left">AF</th><th className="px-3 py-2 text-left">Callers</th></tr></thead>
                        <tbody className="divide-y divide-glass-border">
                          {filteredVariants.slice(0, 50).map((variant, index) => (
                            <tr key={`${String(variant.chrom)}-${String(variant.pos)}-${index}`}>
                              <td className="px-3 py-2 font-mono text-text-primary">{String(variant.chrom ?? '—')}</td>
                              <td className="px-3 py-2 font-mono text-text-primary">{numberLabel(variant.pos)}</td>
                              <td className="px-3 py-2 font-mono text-good">{String(variant.ref ?? '—')}</td>
                              <td className="px-3 py-2 font-mono text-accent-cyan">{String(variant.alt ?? '—')}</td>
                              <td className="px-3 py-2 font-mono text-text-primary">{numberLabel(variant.dp)}</td>
                              <td className="px-3 py-2 font-mono text-text-primary">{numberOrNull(variant.af) === null ? '—' : `${(Number(variant.af) * 100).toFixed(1)}%`}</td>
                              <td className="px-3 py-2 text-text-muted">{Array.isArray(variant.callers) ? variant.callers.join(', ') : '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="rounded-xl border border-good/20 bg-good/5 p-4 text-sm text-text-secondary">
                      <div className="flex items-center gap-2"><CheckCircle className="h-4 w-4 text-good" /><span>{variants ? 'No candidate variants passed filtering.' : 'Variant calling was not evaluated for this assay.'}</span></div>
                    </div>
                  )}
                </div>

                {(visualization.sam || visualization.vcf) ? (
                  <div>
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <div><h3 className="text-sm font-semibold text-text-primary">Genome evidence viewer</h3><p className="mt-0.5 text-[11px] text-text-muted">Aligned reads and VCF evidence emitted by this run.</p></div>
                      <span className="font-mono text-[10px] text-text-muted">{numberLabel(visualization.n_mapped)} mapped · {numberLabel(visualization.n_variants)} variants</span>
                    </div>
                    <GenomeViewer samText={visualization.sam || ''} vcfText={visualization.vcf || ''} locus={visualization.locus ?? undefined} />
                  </div>
                ) : (
                  <div className="rounded-xl border border-glass-border bg-surface-1 p-4 text-sm text-text-muted">Genome visualization was not emitted for this result.</div>
                )}
              </div>
            )}
            raw={<NgsArtifactPanel vcf={visualization.vcf || ''} sam={visualization.sam || ''} pipeline={result.pipeline} />}
            methods={(
              <div className="space-y-5">
                <ProvenancePanel provenance={result.pipeline?.provenance ?? {}} />
                <NgsBenchmarkPanel
                  claim={result.pipeline?.validation?.claim}
                  summary={result.pipeline?.validation?.summary}
                  sameOrBetterSupported={result.pipeline?.validation?.same_or_better_supported}
                  comparisons={result.pipeline?.validation?.comparisons}
                  analysisGrade={result.pipeline?.validation?.analysis_grade}
                  researchReady={result.pipeline?.validation?.research_ready}
                  requirements={result.pipeline?.validation?.production_requirements}
                  inputSampling={result.pipeline?.validation?.input_sampling}
                  demonstration={Boolean(result.demo)}
                />
                <div><h3 className="mb-2 text-sm font-semibold text-text-primary">Complete stage ledger</h3><StageEvidenceTable stages={stages} /></div>
              </div>
            )}
            interpretation={<NgsEvidenceInterpretation stages={stages} pipelineStatus={result.pipeline?.pipeline_status ?? 'INFO'} warnings={actionableWarnings} integrityErrors={integrityErrors.map(issue => issue.message)} demonstration={Boolean(result.demo)} />}
            ai={<AIResultSummary toolName="ngs" result={result as unknown as Record<string, unknown>} title="AI explanation" />}
          />
        </>
      )}
    </div>
  );
}

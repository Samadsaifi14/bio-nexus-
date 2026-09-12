'use client';

import { useEffect, useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  ArrowsOut,
  CheckCircle,
  CircleNotch,
  Dna,
  DownloadSimple,
  FileText,
  Flask,
  Play,
  ShieldCheck,
  Table,
  TestTube,
  Warning,
  X,
} from '@phosphor-icons/react';

import { BackButton, CriticalButton, PageHeader } from '@/components/ui';
import GenomeViewer from '@/components/GenomeViewer';
import NgsArtifactPanel from '@/components/results/NgsArtifactPanel';
import { ProvenancePanel } from '@/components/results/ProvenancePanel';
import { NgsProductionSupportCard } from '@/components/results/NgsProductionSupportCard';
import { RnaSeqProductionSupportCard } from '@/components/results/RnaSeqProductionSupportCard';
import { RnaSeqExpressionWorkspace } from '@/components/results/RnaSeqExpressionWorkspace';
import NgsVisualizationHub from '@/components/results/NgsVisualizationHub';
import { runNgs2Analyze, type Ngs2AnalyzeResult, type Ngs2Stage } from '@/lib/api';
import { downloadNgsDemoFile, getNgsDemoCatalog, type NgsDemoCatalogItem } from '@/lib/ngsDemoApi';

type UnknownRecord = Record<string, unknown>;
type PipelineFamily = 'dna' | 'rna';
type StepStatus = 'PASS' | 'WARN' | 'FAIL' | 'NA' | 'PENDING';

type DemoMeta = {
  profile: string;
  label: string;
  description: string;
  synthetic: boolean;
  read_pairs: number;
  truth_set?: Array<Record<string, unknown>>;
  functional_benchmark?: {
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
  requested: Ngs2AnalyzeResult['requested'] & {
    demo_profile?: string | null;
    reads_analyzed?: number;
  };
};

type PipelineStep = {
  id: string;
  title: string;
  short: string;
  description: string;
  productionTools: string;
  stageKeys: string[];
  output: string;
};

const FALLBACK_DEMOS: NgsDemoCatalogItem[] = [
  {
    id: 'wgs-truth-control',
    label: 'WGS variant control',
    assay: 'WGS',
    description: 'Paired-end synthetic control containing one declared heterozygous SNV.',
    purpose: 'Variant calling and expected-vs-observed functional control',
    read_pairs: 16,
    read_length: 150,
    paired_end: true,
    truth_bearing: true,
    downloads: { r1: '', r2: '', reference: '' },
  },
  {
    id: 'wgs-clean',
    label: 'Clean WGS',
    assay: 'WGS',
    description: 'High-quality paired-end reads for a clean baseline run.',
    purpose: 'Clean paired-end WGS baseline',
    read_pairs: 180,
    read_length: 150,
    paired_end: true,
    truth_bearing: false,
    downloads: { r1: '', r2: '' },
  },
  {
    id: 'wgs-mixed-quality',
    label: 'Mixed-quality WGS',
    assay: 'WGS',
    description: 'Low-quality tails and duplicate burden for QC and trimming inspection.',
    purpose: 'QC and trimming warning demonstration',
    read_pairs: 180,
    read_length: 150,
    paired_end: true,
    truth_bearing: false,
    downloads: { r1: '', r2: '' },
  },
  {
    id: 'wes-small',
    label: 'Compact WES',
    assay: 'WES',
    description: 'Small exome-style paired-end dataset for exercising the WES route.',
    purpose: 'Compact WES workflow demonstration',
    read_pairs: 120,
    read_length: 150,
    paired_end: true,
    truth_bearing: false,
    downloads: { r1: '', r2: '' },
  },
];

const DNA_STEPS: PipelineStep[] = [
  {
    id: 'input',
    title: 'Acquire & validate reads',
    short: 'Input',
    description: 'Start with SRA Toolkit output or paired FASTQ files, verify FASTQ structure, pairing and checksums before analysis.',
    productionTools: 'SRA Toolkit / FASTQ + SHA-256',
    stageKeys: ['input_validation'],
    output: 'Validated R1/R2 FASTQ and immutable input checksums',
  },
  {
    id: 'raw-qc',
    title: 'Inspect raw-read quality',
    short: 'Raw QC',
    description: 'Measure base quality, GC, adapters, duplication and ambiguous bases before any trimming decision is made.',
    productionTools: 'FastQC + MultiQC',
    stageKeys: ['raw_read_qc', 'multiqc'],
    output: 'Raw QC metrics and per-file evidence',
  },
  {
    id: 'trim',
    title: 'Trim adapters & low-quality bases',
    short: 'Trim',
    description: 'Apply the preprocessing plan, then compare authentic before/after sequences and measured read retention.',
    productionTools: 'fastp',
    stageKeys: ['preprocessing'],
    output: 'Clean R1/R2 FASTQ, retention and trimming evidence',
  },
  {
    id: 'post-qc',
    title: 'Re-check trimmed reads',
    short: 'Post-QC',
    description: 'Confirm that quality improved without unacceptable read loss. Do not call trimming accurate from a single percentage.',
    productionTools: 'FastQC + MultiQC after fastp',
    stageKeys: ['preprocessing'],
    output: 'Before/after Q20, Q30, mean quality and read length',
  },
  {
    id: 'align',
    title: 'Validate reference & align',
    short: 'Align',
    description: 'Resolve the declared genome build before mapping. Production execution belongs to the pinned Sarek workflow.',
    productionTools: 'nf-core/sarek 3.10.0 · BWA-MEM2/DRAGMAP workflow path',
    stageKeys: ['reference_validation', 'alignment'],
    output: 'Reference provenance and aligned-read evidence',
  },
  {
    id: 'bam-qc',
    title: 'Process BAM & mapping QC',
    short: 'BAM QC',
    description: 'Sort/index alignment output and inspect mapping, duplication, insert-size and related alignment-quality evidence.',
    productionTools: 'samtools / Picard-compatible Sarek stages',
    stageKeys: ['bam_processing', 'alignment_qc'],
    output: 'Indexed alignment artifacts and mapping QC',
  },
  {
    id: 'coverage',
    title: 'Measure coverage',
    short: 'Coverage',
    description: 'Assess depth and breadth of coverage before interpreting variant calls.',
    productionTools: 'mosdepth / samtools coverage-compatible outputs',
    stageKeys: ['coverage'],
    output: 'Depth, breadth and coverage-uniformity evidence',
  },
  {
    id: 'variants',
    title: 'Call, normalize & filter variants',
    short: 'Variants',
    description: 'Inspect candidate variants only after alignment QC and coverage are available. Preview calls are not production VCF claims.',
    productionTools: 'Sarek germline caller + normalization/filtering',
    stageKeys: ['variant_calling', 'variant_normalization', 'variant_qc', 'variant_filter'],
    output: 'Filtered variant candidates and VCF evidence',
  },
  {
    id: 'interpret',
    title: 'Annotate & interpret',
    short: 'Annotate',
    description: 'Attach evidence-backed annotation and prioritization without converting missing evidence into a biological conclusion.',
    productionTools: 'Workflow-emitted annotation artifacts',
    stageKeys: ['annotation', 'knowledge', 'prioritization'],
    output: 'Annotated result table with evidence boundaries',
  },
  {
    id: 'report',
    title: 'Review & export the complete run',
    short: 'Report',
    description: 'Collect native scientific files, provenance, checksums and the final readiness gate. No new graph is invented at this stage.',
    productionTools: 'MultiQC + provenance + native BAM/VCF/report artifacts',
    stageKeys: ['final_gate'],
    output: 'Downloadable native artifacts and reproducibility record',
  },
];

const RNA_BLUEPRINT: PipelineStep[] = [
  {
    id: 'rna-input', title: 'Acquire reads', short: 'Input',
    description: 'Use SRA Toolkit for an accession or begin from paired FASTQ. Record sample metadata and checksums.',
    productionTools: 'SRA Toolkit / FASTQ + SHA-256', stageKeys: [], output: 'Validated FASTQ + sample sheet',
  },
  {
    id: 'rna-raw-qc', title: 'Raw FASTQ QC', short: 'Raw QC',
    description: 'Inspect per-base quality, GC, sequence content, duplication, adapters and overrepresented sequences.',
    productionTools: 'FastQC + MultiQC', stageKeys: [], output: 'FastQC HTML/ZIP + MultiQC evidence',
  },
  {
    id: 'rna-trim', title: 'Trim & filter', short: 'Trim',
    description: 'Remove adapters and low-quality tails, preserving the before/after read evidence and filtering reasons.',
    productionTools: 'fastp', stageKeys: [], output: 'Trimmed FASTQ + fastp HTML/JSON',
  },
  {
    id: 'rna-post-qc', title: 'Post-trim QC', short: 'Post-QC',
    description: 'Re-run QC to confirm improvement and quantify any read loss before alignment.',
    productionTools: 'FastQC + MultiQC', stageKeys: [], output: 'Post-trim QC comparison',
  },
  {
    id: 'rna-align', title: 'Splice-aware alignment & quantification', short: 'Align',
    description: 'Map reads with a splice-aware workflow and quantify gene/transcript abundance using the pinned production workflow.',
    productionTools: 'nf-core/rnaseq 3.26.0 · STAR + Salmon default path', stageKeys: [], output: 'BAM/index + Salmon abundance',
  },
  {
    id: 'rna-counts', title: 'Build count matrix', short: 'Counts',
    description: 'Merge sample-level quantification into a genes × samples integer count matrix with matching metadata.',
    productionTools: 'Salmon/featureCounts-compatible workflow outputs', stageKeys: [], output: 'Raw count matrix + metadata',
  },
  {
    id: 'rna-normalize', title: 'Normalize with DESeq2', short: 'Normalize',
    description: 'Use raw integer counts and DESeq2 size-factor normalization. Do not substitute TPM/FPKM for DESeq2 input.',
    productionTools: 'R / Bioconductor DESeq2', stageKeys: [], output: 'Size factors + normalized counts + dispersion evidence',
  },
  {
    id: 'rna-expression-qc', title: 'PCA & sample-distance QC', short: 'PCA / distance',
    description: 'Run VST/rlog-derived sample QC before differential testing. A sample-distance heatmap belongs here.',
    productionTools: 'DESeq2 + R heatmap/ComplexHeatmap', stageKeys: [], output: 'PCA coordinates + sample-distance matrix/heatmap',
  },
  {
    id: 'rna-de', title: 'Differential expression', short: 'DEG',
    description: 'Fit the DESeq2 model and report baseMean, log2 fold-change, standard error, statistic, p-value and adjusted p-value.',
    productionTools: 'DESeq2', stageKeys: [], output: 'DEG table + MA plot + volcano plot',
  },
  {
    id: 'rna-heatmap', title: 'Expression heatmap', short: 'Heatmap',
    description: 'Generate the heatmap from the actual transformed count matrix, declared gene-selection rule and clustering method.',
    productionTools: 'R / ComplexHeatmap', stageKeys: [], output: 'SVG/PDF/PNG heatmap + plotted matrix TSV',
  },
  {
    id: 'rna-report', title: 'Export & provenance', short: 'Report',
    description: 'Bundle figures, matrices, tool versions, parameters and provenance. AI interpretation remains downstream of deterministic results.',
    productionTools: 'nf-core reports + BioNexus provenance layer', stageKeys: [], output: 'Reproducibility bundle',
  },
];

function asRecord(value: unknown): UnknownRecord {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as UnknownRecord : {};
}

function asNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null;
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatNumber(value: unknown, digits = 1): string {
  const parsed = asNumber(value);
  return parsed === null ? '—' : parsed.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function findStage(stages: Ngs2Stage[], key: string): Ngs2Stage | undefined {
  return stages.find(item => item.step === key);
}

function statusOf(stage?: Ngs2Stage): StepStatus {
  if (!stage) return 'PENDING';
  const data = asRecord(stage.data);
  if (data.status === 'NOT_EVALUATED' || data.status === 'NOT_EXECUTED_IN_PREVIEW' || data.unevaluated) return 'NA';
  const status = stage.qc?.status;
  if (status === 'PASS' || status === 'WARN' || status === 'FAIL') return status;
  return 'NA';
}

function combinedStatus(stages: Ngs2Stage[], keys: string[]): StepStatus {
  const statuses = keys.map(key => statusOf(findStage(stages, key))).filter(status => status !== 'PENDING');
  if (!statuses.length) return 'PENDING';
  if (statuses.includes('FAIL')) return 'FAIL';
  if (statuses.includes('WARN')) return 'WARN';
  if (statuses.includes('NA') && !statuses.includes('PASS')) return 'NA';
  return 'PASS';
}

function statusClass(status: StepStatus): string {
  if (status === 'PASS') return 'border-good/30 bg-good/5 text-good';
  if (status === 'WARN') return 'border-warn/30 bg-warn/5 text-warn';
  if (status === 'FAIL') return 'border-error/30 bg-error/5 text-error';
  if (status === 'NA') return 'border-glass-border bg-surface-1 text-text-muted';
  return 'border-glass-border bg-surface-0 text-text-muted';
}

function saveBlob(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function saveJson(filename: string, value: unknown) {
  saveBlob(filename, JSON.stringify(value, null, 2), 'application/json;charset=utf-8');
}

function saveTsv(filename: string, rows: Array<Record<string, unknown>>) {
  if (!rows.length) return;
  const columns = Array.from(new Set(rows.flatMap(row => Object.keys(row))));
  const text = [
    columns.join('\t'),
    ...rows.map(row => columns.map(column => {
      const value = row[column];
      if (Array.isArray(value)) return value.join(',');
      if (value && typeof value === 'object') return JSON.stringify(value);
      return value === null || value === undefined ? '' : String(value);
    }).join('\t')),
  ].join('\n');
  saveBlob(filename, text, 'text/tab-separated-values;charset=utf-8');
}

function Metric({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-lg border border-glass-border bg-surface-1 p-3">
      <p className="text-[10px] uppercase tracking-[0.12em] text-text-muted">{label}</p>
      <p className="mt-1 font-mono text-base font-semibold text-text-primary">{value}</p>
      {note && <p className="mt-1 text-[10px] leading-4 text-text-muted">{note}</p>}
    </div>
  );
}

function StageEvidence({ stage }: { stage?: Ngs2Stage }) {
  if (!stage) return <p className="text-xs text-text-muted">This evidence is not present in the current result.</p>;
  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-4">
        <Metric label="Implementation" value={stage.tool || '—'} />
        <Metric label="Version" value={stage.version || '—'} />
        <Metric label="Evidence" value={stage.evidence_level || '—'} />
        <Metric label="QC" value={statusOf(stage)} />
      </div>
      {stage.qc?.metrics?.length ? (
        <div className="overflow-x-auto rounded-lg border border-glass-border">
          <table className="w-full text-xs">
            <thead className="bg-surface-1 text-text-muted">
              <tr><th className="px-3 py-2 text-left">Metric</th><th className="px-3 py-2 text-left">Value</th><th className="px-3 py-2 text-left">Status</th><th className="px-3 py-2 text-left">Expectation</th></tr>
            </thead>
            <tbody className="divide-y divide-glass-border">
              {stage.qc.metrics.map(metric => (
                <tr key={metric.name}>
                  <td className="px-3 py-2 text-text-primary">{metric.name.replaceAll('_', ' ')}</td>
                  <td className="px-3 py-2 font-mono text-text-primary">{metric.value === null ? '—' : String(metric.value)}</td>
                  <td className="px-3 py-2 font-mono text-text-secondary">{metric.status}</td>
                  <td className="px-3 py-2 text-text-muted">{metric.expected ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function Blueprint({ family }: { family: PipelineFamily }) {
  const steps = family === 'rna' ? RNA_BLUEPRINT : DNA_STEPS;
  return (
    <section className="data-card overflow-hidden">
      <div className="border-b border-glass-border p-5">
        <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-accent-cyan">Scientific workflow</p>
        <h2 className="mt-1 text-base font-semibold text-text-primary">
          {family === 'rna' ? 'RNA-seq: reads → counts → DESeq2 → expression figures' : 'WGS/WES: reads → alignment → coverage → variants'}
        </h2>
        <p className="mt-1 max-w-3xl text-xs leading-5 text-text-muted">
          Each stage produces evidence that must exist before the next stage is interpreted. Visualizations are created only from their declared scientific source data.
        </p>
      </div>
      <div className="divide-y divide-glass-border">
        {steps.map((step, index) => (
          <div key={step.id} className="grid gap-3 p-4 md:grid-cols-[46px_1fr_220px] md:items-start">
            <div className="flex h-8 w-8 items-center justify-center rounded-full border border-glass-border bg-surface-1 font-mono text-xs text-text-primary">{index + 1}</div>
            <div>
              <h3 className="text-sm font-semibold text-text-primary">{step.title}</h3>
              <p className="mt-1 text-xs leading-5 text-text-muted">{step.description}</p>
              <p className="mt-2 text-[11px] text-text-secondary"><span className="text-text-muted">Output:</span> {step.output}</p>
            </div>
            <div className="rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-[11px] leading-4 text-text-secondary">
              <span className="text-text-muted">Production toolchain</span>
              <p className="mt-1 font-medium text-text-primary">{step.productionTools}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function GuidedNgsWorkspace() {
  const [family, setFamily] = useState<PipelineFamily>('dna');
  const [demos, setDemos] = useState<NgsDemoCatalogItem[]>(FALLBACK_DEMOS);
  const [result, setResult] = useState<ExtendedResult | null>(null);
  const [activeStep, setActiveStep] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [runningDemo, setRunningDemo] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getNgsDemoCatalog().then(items => {
      if (items.length) setDemos(items);
    }).catch(() => undefined);
  }, []);

  const stages = result?.pipeline?.stages ?? [];
  const step = DNA_STEPS[activeStep];
  const visualization = result?.visualization ?? { sam: '', vcf: '', locus: null, n_reads: 0, n_mapped: 0, n_variants: 0 };

  const runDemo = async (demo: NgsDemoCatalogItem) => {
    setRunningDemo(demo.id);
    setError(null);
    try {
      const response = await runNgs2Analyze({
        file_paths: [],
        reference: 'grch38',
        metadata: { platform: 'illumina', source: 'bionexus-demo', demonstration_data: true },
        synthetic_reference: true,
        demo_profile: demo.id,
      } as Parameters<typeof runNgs2Analyze>[0] & { demo_profile?: string });
      setResult(response as ExtendedResult);
      setActiveStep(0);
      setExpanded(false);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'The NGS demonstration could not be completed.');
    } finally {
      setRunningDemo(null);
    }
  };

  const downloadDemo = async (profile: string, kind: 'r1' | 'r2' | 'reference') => {
    const key = `${profile}:${kind}`;
    setDownloading(key);
    setError(null);
    try {
      await downloadNgsDemoFile(profile, kind);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'The demo file could not be downloaded.');
    } finally {
      setDownloading(null);
    }
  };

  const renderInput = () => {
    const inputStage = findStage(stages, 'input_validation');
    const inputs = Array.isArray(asRecord(result?.pipeline?.provenance).inputs)
      ? asRecord(result?.pipeline?.provenance).inputs as unknown[]
      : [];
    return (
      <div className="space-y-4">
        <StageEvidence stage={inputStage} />
        <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
          <h4 className="text-xs font-semibold text-text-primary">Input files used by this run</h4>
          <div className="mt-3 space-y-2">
            {inputs.map((item, index) => {
              const row = asRecord(item);
              const checksum = asRecord(row.checksum);
              return (
                <div key={`${String(row.name)}-${index}`} className="grid gap-2 rounded-lg border border-glass-border bg-surface-0 p-3 text-[11px] sm:grid-cols-[1fr_2fr]">
                  <span className="font-mono text-text-primary">{String(row.name ?? 'FASTQ')}</span>
                  <span className="break-all font-mono text-text-muted">{checksum.value ? `${String(checksum.algorithm)}:${String(checksum.value)}` : 'Checksum unavailable'}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  };

  const renderRawQc = () => {
    const raw = findStage(stages, 'raw_read_qc');
    const data = asRecord(raw?.data);
    const perFile = asRecord(data.per_file);
    const rows: Array<UnknownRecord & { file: string }> = Object.entries(perFile).map(([file, value]) => ({ file: file.split('/').pop() ?? file, ...asRecord(value) }));
    return (
      <div className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-4">
          <Metric label="Q20 bases" value={`${formatNumber(data.q20_percent)}%`} />
          <Metric label="Q30 bases" value={`${formatNumber(data.q30_percent)}%`} />
          <Metric label="GC" value={`${formatNumber(data.gc_percent)}%`} />
          <Metric label="Duplication" value={`${formatNumber(data.duplication_percent)}%`} />
        </div>
        <StageEvidence stage={raw} />
        {rows.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-glass-border">
            <table className="w-full text-xs">
              <thead className="bg-surface-1 text-text-muted"><tr><th className="px-3 py-2 text-left">FASTQ</th><th className="px-3 py-2 text-left">Reads evaluated</th><th className="px-3 py-2 text-left">Q30 %</th><th className="px-3 py-2 text-left">GC %</th><th className="px-3 py-2 text-left">Adapter %</th></tr></thead>
              <tbody className="divide-y divide-glass-border">
                {rows.map(row => <tr key={String(row.file)}><td className="px-3 py-2 font-mono text-text-primary">{String(row.file)}</td><td className="px-3 py-2 font-mono text-text-primary">{formatNumber(row.total_reads, 0)}</td><td className="px-3 py-2 font-mono text-text-primary">{formatNumber(row.q30_percent)}</td><td className="px-3 py-2 font-mono text-text-primary">{formatNumber(row.gc_percent)}</td><td className="px-3 py-2 font-mono text-text-primary">{formatNumber(row.adapter_percent)}</td></tr>)}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  };

  const preprocessing = findStage(stages, 'preprocessing');
  const preprocessingData = asRecord(preprocessing?.data);

  const renderTrim = () => {
    const perFile = asRecord(preprocessingData.per_file);
    const examples: Array<UnknownRecord & { file: string }> = Object.entries(perFile).flatMap(([file, value]) => {
      const rows = Array.isArray(asRecord(value).trim_examples) ? asRecord(value).trim_examples as unknown[] : [];
      return rows.map(row => ({ file: file.split('/').pop() ?? file, ...asRecord(row) }));
    });
    return (
      <div className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-4">
          <Metric label="Raw reads" value={formatNumber(preprocessingData.raw_reads, 0)} />
          <Metric label="Retained reads" value={formatNumber(preprocessingData.retained_reads, 0)} />
          <Metric label="Read loss" value={`${formatNumber(preprocessingData.read_loss_percent)}%`} />
          <Metric label="Mean length after" value={`${formatNumber(preprocessingData.avg_read_length_after)} bp`} />
        </div>
        <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div><h4 className="text-xs font-semibold text-text-primary">Authentic trimming map</h4><p className="mt-1 text-[11px] leading-4 text-text-muted">These sequences are read from the actual input and written trimmed FASTQ files. They are not decorative examples.</p></div>
            {examples.length > 0 && <button onClick={() => saveTsv('bionexus_trim_examples.tsv', examples)} className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-0 px-3 py-2 text-[11px] text-text-secondary hover:text-text-primary"><DownloadSimple /> TSV</button>}
          </div>
          <div className="mt-4 space-y-4">
            {examples.slice(0, 6).map((example, index) => (
              <div key={`${String(example.file)}-${String(example.name)}-${index}`} className="rounded-lg border border-glass-border bg-surface-0 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] text-text-muted"><span className="font-mono">{String(example.file)} · {String(example.name)}</span><span>{formatNumber(example.before_length, 0)} bp → {formatNumber(example.after_length, 0)} bp · removed {formatNumber(example.removed_bases, 0)} bp</span></div>
                <div className="mt-3 grid gap-3 lg:grid-cols-2">
                  <div><p className="mb-1 text-[10px] uppercase tracking-[0.12em] text-text-muted">Before</p><div className="overflow-x-auto rounded border border-glass-border bg-surface-1 p-2 font-mono text-[10px] leading-5 text-text-secondary">{String(example.before ?? '—')}</div></div>
                  <div><p className="mb-1 text-[10px] uppercase tracking-[0.12em] text-text-muted">After</p><div className="overflow-x-auto rounded border border-good/20 bg-good/5 p-2 font-mono text-[10px] leading-5 text-text-primary">{String(example.after ?? '—')}</div></div>
                </div>
              </div>
            ))}
          </div>
        </div>
        <StageEvidence stage={preprocessing} />
      </div>
    );
  };

  const renderPostQc = () => {
    const raw = asRecord(findStage(stages, 'raw_read_qc')?.data);
    const rows = [
      { metric: 'Q20 %', before: raw.q20_percent, after: preprocessingData.q20_after },
      { metric: 'Q30 %', before: raw.q30_percent, after: preprocessingData.q30_after },
      { metric: 'Mean quality', before: raw.mean_quality, after: preprocessingData.mean_quality_after },
      { metric: 'Average read length (bp)', before: raw.avg_read_length, after: preprocessingData.avg_read_length_after },
    ];
    return (
      <div className="space-y-4">
        <div className="overflow-x-auto rounded-lg border border-glass-border">
          <table className="w-full text-xs">
            <thead className="bg-surface-1 text-text-muted"><tr><th className="px-3 py-2 text-left">Measured quantity</th><th className="px-3 py-2 text-left">Before trimming</th><th className="px-3 py-2 text-left">After trimming</th></tr></thead>
            <tbody className="divide-y divide-glass-border">{rows.map(row => <tr key={row.metric}><td className="px-3 py-2 text-text-primary">{row.metric}</td><td className="px-3 py-2 font-mono text-text-secondary">{formatNumber(row.before)}</td><td className="px-3 py-2 font-mono text-text-primary">{formatNumber(row.after)}</td></tr>)}</tbody>
          </table>
        </div>
        <div className="rounded-lg border border-accent-cyan/20 bg-accent-cyan/5 p-3 text-[11px] leading-5 text-text-secondary">
          <ShieldCheck className="mr-2 inline h-4 w-4 text-accent-cyan" />
          BioNexus reports the measurements rather than inventing a single “trimming accuracy” score. Production fastp/FastQC artifacts remain the authoritative source for full-run QC.
        </div>
      </div>
    );
  };

  const renderGenericStages = (keys: string[]) => (
    <div className="space-y-4">
      {keys.map(key => <div key={key}><h4 className="mb-2 text-xs font-semibold capitalize text-text-primary">{key.replaceAll('_', ' ')}</h4><StageEvidence stage={findStage(stages, key)} /></div>)}
    </div>
  );

  const renderCoverage = () => {
    const coverage = findStage(stages, 'coverage');
    const genome = asRecord(asRecord(coverage?.data).genome);
    return (
      <div className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-4">
          <Metric label="Mean depth" value={`${formatNumber(genome.mean_depth)}×`} />
          <Metric label="≥1×" value={`${formatNumber(genome.coverage_1x)}%`} />
          <Metric label="≥20×" value={`${formatNumber(genome.coverage_20x)}%`} />
          <Metric label="Uniformity" value={`${formatNumber(genome.uniformity)}%`} />
        </div>
        <StageEvidence stage={coverage} />
      </div>
    );
  };

  const renderVariants = () => {
    const calling = findStage(stages, 'variant_calling');
    const filtering = findStage(stages, 'variant_filter');
    const called = Array.isArray(asRecord(calling?.data).variants) ? asRecord(calling?.data).variants as unknown[] : [];
    const filtered = Array.isArray(asRecord(filtering?.data).final) ? asRecord(filtering?.data).final as unknown[] : called;
    const rows = filtered.map(item => asRecord(item));
    return (
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-text-muted">{rows.length} post-filter candidate variant{rows.length === 1 ? '' : 's'} in this preview.</p>
          {rows.length > 0 && <button onClick={() => saveTsv('bionexus_filtered_variants.tsv', rows)} className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-[11px] text-text-secondary hover:text-text-primary"><DownloadSimple /> Download TSV</button>}
        </div>
        {rows.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border border-glass-border">
            <table className="w-full text-xs"><thead className="bg-surface-1 text-text-muted"><tr><th className="px-3 py-2 text-left">Chrom</th><th className="px-3 py-2 text-left">Position</th><th className="px-3 py-2 text-left">Ref</th><th className="px-3 py-2 text-left">Alt</th><th className="px-3 py-2 text-left">Depth</th><th className="px-3 py-2 text-left">AF</th></tr></thead><tbody className="divide-y divide-glass-border">{rows.slice(0, 100).map((row, index) => <tr key={`${String(row.chrom)}-${String(row.pos)}-${index}`}><td className="px-3 py-2 font-mono text-text-primary">{String(row.chrom ?? '—')}</td><td className="px-3 py-2 font-mono text-text-primary">{formatNumber(row.pos, 0)}</td><td className="px-3 py-2 font-mono text-text-primary">{String(row.ref ?? '—')}</td><td className="px-3 py-2 font-mono text-text-primary">{String(row.alt ?? '—')}</td><td className="px-3 py-2 font-mono text-text-primary">{formatNumber(row.dp, 0)}</td><td className="px-3 py-2 font-mono text-text-primary">{asNumber(row.af) === null ? '—' : `${(Number(row.af) * 100).toFixed(1)}%`}</td></tr>)}</tbody></table>
          </div>
        ) : <div className="rounded-lg border border-glass-border bg-surface-1 p-4 text-xs text-text-muted">No candidate variants passed filtering in this result.</div>}
        {(visualization.sam || visualization.vcf) && <div className="rounded-xl border border-glass-border bg-surface-0 p-3"><GenomeViewer samText={visualization.sam || ''} vcfText={visualization.vcf || ''} locus={visualization.locus ?? undefined} /></div>}
        {renderGenericStages(['variant_calling', 'variant_normalization', 'variant_qc', 'variant_filter'])}
      </div>
    );
  };

  const renderReport = () => (
    <div className="space-y-5">
      {result?.demo?.functional_benchmark && (
        <div className={`rounded-xl border p-4 ${result.demo.functional_benchmark.status === 'PASS' ? 'border-good/25 bg-good/5' : 'border-error/25 bg-error/5'}`}>
          <div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-[10px] uppercase tracking-[0.12em] text-text-muted">Expected vs observed control</p><h4 className="mt-1 text-sm font-semibold text-text-primary">Synthetic truth recovery</h4></div><span className="font-mono text-xs">{result.demo.functional_benchmark.status}</span></div>
          <div className="mt-3 grid gap-2 sm:grid-cols-3"><Metric label="TP" value={String(result.demo.functional_benchmark.tp)} /><Metric label="FP" value={String(result.demo.functional_benchmark.fp)} /><Metric label="FN" value={String(result.demo.functional_benchmark.fn)} /></div>
          <p className="mt-3 text-[11px] leading-5 text-text-muted">{result.demo.functional_benchmark.claim}</p>
        </div>
      )}
      <NgsArtifactPanel vcf={visualization.vcf || ''} sam={visualization.sam || ''} pipeline={result?.pipeline} />
      <ProvenancePanel provenance={result?.pipeline?.provenance ?? {}} />
      {renderGenericStages(['final_gate'])}
    </div>
  );

  const renderStep = () => {
    if (!result) return null;
    if (step.id === 'input') return renderInput();
    if (step.id === 'raw-qc') return renderRawQc();
    if (step.id === 'trim') return renderTrim();
    if (step.id === 'post-qc') return renderPostQc();
    if (step.id === 'align') return renderGenericStages(['reference_validation', 'alignment']);
    if (step.id === 'bam-qc') return renderGenericStages(['bam_processing', 'alignment_qc']);
    if (step.id === 'coverage') return renderCoverage();
    if (step.id === 'variants') return renderVariants();
    if (step.id === 'interpret') return renderGenericStages(['annotation', 'knowledge', 'prioritization']);
    return renderReport();
  };

  if (result) {
    const assay = result.detection?.assay ?? result.requested?.assay ?? 'NGS';
    return (
      <div className="scientific-page max-w-7xl space-y-5 pb-12">
        <BackButton />
        <PageHeader title="Guided NGS analysis" subtitle={`${result.demo?.label ?? assay} · one scientific stage at a time`} />

        <div className="rounded-xl border border-accent-cyan/20 bg-accent-cyan/5 p-4 text-xs leading-5 text-text-secondary">
          <ShieldCheck className="mr-2 inline h-4 w-4 text-accent-cyan" />
          Figures and tables in this workspace are rendered only from data present in the run. Missing production evidence stays missing; BioNexus does not replace it with a decorative plot.
        </div>

        <NgsVisualizationHub stages={stages} />

        <div className="grid gap-5 lg:grid-cols-[270px_minmax(0,1fr)]">
          <aside className="h-fit overflow-hidden rounded-xl border border-glass-border bg-surface-0 lg:sticky lg:top-4">
            <div className="border-b border-glass-border p-4"><p className="text-[10px] uppercase tracking-[0.12em] text-text-muted">Pipeline progress</p><p className="mt-1 text-sm font-semibold text-text-primary">{assay}</p></div>
            <div className="divide-y divide-glass-border">
              {DNA_STEPS.map((item, index) => {
                const status = combinedStatus(stages, item.stageKeys);
                const active = activeStep === index;
                return (
                  <button key={item.id} type="button" onClick={() => { setActiveStep(index); setExpanded(false); }} className={`flex w-full items-center gap-3 px-4 py-3 text-left transition ${active ? 'bg-accent-cyan/10' : 'hover:bg-surface-1'}`}>
                    <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[10px] ${statusClass(status)}`}>{status === 'PASS' ? <CheckCircle weight="fill" /> : index + 1}</div>
                    <div className="min-w-0 flex-1"><p className={`truncate text-xs font-medium ${active ? 'text-text-primary' : 'text-text-secondary'}`}>{item.short}</p><p className="mt-0.5 font-mono text-[9px] text-text-muted">{status}</p></div>
                  </button>
                );
              })}
            </div>
          </aside>

          <section className={`${expanded ? 'fixed inset-4 z-50 overflow-auto rounded-2xl border border-glass-border bg-surface-0 p-5 shadow-2xl' : 'data-card p-5'}`}>
            <div className="mb-5 flex flex-wrap items-start justify-between gap-3 border-b border-glass-border pb-4">
              <div className="max-w-3xl">
                <div className="flex items-center gap-2"><span className="flex h-7 w-7 items-center justify-center rounded-full border border-glass-border bg-surface-1 font-mono text-[11px] text-text-primary">{activeStep + 1}</span><span className={`rounded border px-2 py-1 font-mono text-[9px] ${statusClass(combinedStatus(stages, step.stageKeys))}`}>{combinedStatus(stages, step.stageKeys)}</span></div>
                <h2 className="mt-3 text-xl font-semibold text-text-primary">{step.title}</h2>
                <p className="mt-1 text-xs leading-5 text-text-muted">{step.description}</p>
                <div className="mt-3 grid gap-2 text-[11px] sm:grid-cols-2"><div className="rounded-lg border border-glass-border bg-surface-1 p-3"><span className="text-text-muted">Production toolchain</span><p className="mt-1 font-medium text-text-primary">{step.productionTools}</p></div><div className="rounded-lg border border-glass-border bg-surface-1 p-3"><span className="text-text-muted">Expected output</span><p className="mt-1 font-medium text-text-primary">{step.output}</p></div></div>
              </div>
              <div className="flex gap-2">
                <button onClick={() => saveJson(`bionexus_${step.id}_evidence.json`, step.stageKeys.map(key => findStage(stages, key)).filter(Boolean))} className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-[11px] text-text-secondary hover:text-text-primary"><DownloadSimple /> Evidence JSON</button>
                <button onClick={() => setExpanded(value => !value)} className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-[11px] text-text-secondary hover:text-text-primary">{expanded ? <X /> : <ArrowsOut />}{expanded ? 'Close' : 'Enlarge'}</button>
              </div>
            </div>

            {renderStep()}

            <div className="mt-6 flex items-center justify-between border-t border-glass-border pt-4">
              <button disabled={activeStep === 0} onClick={() => { setActiveStep(index => Math.max(0, index - 1)); setExpanded(false); }} className="inline-flex items-center gap-2 rounded-lg border border-glass-border px-3 py-2 text-xs text-text-secondary disabled:opacity-30"><ArrowLeft /> Previous</button>
              <span className="font-mono text-[10px] text-text-muted">Step {activeStep + 1} of {DNA_STEPS.length}</span>
              {activeStep < DNA_STEPS.length - 1 ? <CriticalButton onClick={() => { setActiveStep(index => Math.min(DNA_STEPS.length - 1, index + 1)); setExpanded(false); }} className="px-4 py-2 text-xs">Continue <ArrowRight /></CriticalButton> : <button onClick={() => { setResult(null); setActiveStep(0); setExpanded(false); }} className="inline-flex items-center gap-2 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs text-text-secondary">Run another dataset</button>}
            </div>
          </section>
        </div>
      </div>
    );
  }

  return (
    <div className="scientific-page max-w-7xl space-y-6 pb-12">
      <BackButton />
      <PageHeader title="NGS Pipeline" subtitle="A guided sequencing workflow: finish one scientific stage, inspect its evidence, then continue." />

      <section className="data-card overflow-hidden">
        <div className="grid gap-px bg-glass-border md:grid-cols-2">
          <button type="button" onClick={() => setFamily('dna')} className={`p-5 text-left ${family === 'dna' ? 'bg-accent-cyan/10' : 'bg-surface-0 hover:bg-surface-1'}`}><div className="flex items-start gap-3"><Dna className={`mt-0.5 h-5 w-5 ${family === 'dna' ? 'text-accent-cyan' : 'text-text-muted'}`} /><div><p className="text-sm font-semibold text-text-primary">WGS / WES</p><p className="mt-1 text-xs leading-5 text-text-muted">FASTQ QC → trimming → alignment → BAM QC → coverage → variants → annotation.</p></div></div></button>
          <button type="button" onClick={() => setFamily('rna')} className={`p-5 text-left ${family === 'rna' ? 'bg-accent-cyan/10' : 'bg-surface-0 hover:bg-surface-1'}`}><div className="flex items-start gap-3"><Flask className={`mt-0.5 h-5 w-5 ${family === 'rna' ? 'text-accent-cyan' : 'text-text-muted'}`} /><div><p className="text-sm font-semibold text-text-primary">RNA-seq</p><p className="mt-1 text-xs leading-5 text-text-muted">FASTQ QC → trimming → STAR/Salmon → count matrix → DESeq2 → PCA/heatmap → DEG.</p></div></div></button>
        </div>
      </section>

      <Blueprint family={family} />

      {family === 'dna' ? (
        <>
          <section className="data-card overflow-hidden">
            <div className="flex flex-col justify-between gap-3 border-b border-glass-border p-5 md:flex-row md:items-end">
              <div><p className="font-mono text-[10px] uppercase tracking-[0.14em] text-accent-cyan">Runnable demo inputs</p><h2 className="mt-1 text-base font-semibold text-text-primary">Start the guided pipeline without uploading anything</h2><p className="mt-1 max-w-2xl text-xs leading-5 text-text-muted">The same deterministic FASTQ files can be downloaded before running. The truth-bearing control is the best option for checking expected-versus-observed variant behavior.</p></div>
              <span className="rounded border border-good/20 bg-good/5 px-2.5 py-1 text-[10px] text-good">DOWNLOADABLE INPUTS</span>
            </div>
            <div className="divide-y divide-glass-border">
              {demos.map(demo => (
                <article key={demo.id} className="grid gap-4 p-5 lg:grid-cols-[1fr_auto] lg:items-center">
                  <div><div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold text-text-primary">{demo.label}</h3><span className="rounded border border-glass-border bg-surface-1 px-2 py-0.5 font-mono text-[9px] text-text-muted">{demo.assay}</span>{demo.truth_bearing && <span className="rounded border border-good/20 bg-good/5 px-2 py-0.5 text-[9px] text-good">KNOWN SYNTHETIC TRUTH</span>}</div><p className="mt-1 text-xs leading-5 text-text-muted">{demo.description}</p><p className="mt-2 text-[11px] text-text-secondary">2×{demo.read_length} bp · {demo.read_pairs} pairs · {demo.purpose}</p></div>
                  <div className="flex flex-wrap gap-2"><CriticalButton disabled={Boolean(runningDemo)} onClick={() => runDemo(demo)} className="px-4 py-2 text-xs disabled:opacity-50">{runningDemo === demo.id ? <CircleNotch className="animate-spin" /> : <Play />} {runningDemo === demo.id ? 'Running…' : 'Run guided demo'}</CriticalButton><button disabled={Boolean(downloading)} onClick={() => downloadDemo(demo.id, 'r1')} className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs text-text-secondary disabled:opacity-40"><DownloadSimple /> R1</button><button disabled={Boolean(downloading)} onClick={() => downloadDemo(demo.id, 'r2')} className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs text-text-secondary disabled:opacity-40"><DownloadSimple /> R2</button>{demo.truth_bearing && <button disabled={Boolean(downloading)} onClick={() => downloadDemo(demo.id, 'reference')} className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs text-text-secondary disabled:opacity-40"><FileText /> Reference</button>}</div>
                </article>
              ))}
            </div>
          </section>
          <div><p className="mb-3 flex items-center gap-2 text-xs font-semibold text-text-primary"><Dna /> Production WGS/WES execution</p><NgsProductionSupportCard defaultReference="GRCh38" /></div>
        </>
      ) : (
        <>
          <div className="rounded-xl border border-accent-cyan/20 bg-accent-cyan/5 p-4 text-xs leading-5 text-text-secondary"><ShieldCheck className="mr-2 inline h-4 w-4 text-accent-cyan" /><strong className="text-text-primary">Expression statistics are now executed, not mocked.</strong> The workspace below accepts raw integer counts plus explicit sample metadata and emits R/DESeq2 tables and R-generated figures. The upstream FASTQ production lane remains separate and continues through nf-core/rnaseq.</div>
          <RnaSeqExpressionWorkspace />
          <div><p className="mb-3 flex items-center gap-2 text-xs font-semibold text-text-primary"><Flask /> Upstream production RNA-seq execution</p><RnaSeqProductionSupportCard /></div>
        </>
      )}

      {error && <div className="rounded-xl border border-error/25 bg-error/10 p-4 text-sm text-error"><Warning className="mr-2 inline h-4 w-4" />{error}</div>}

      <section className="grid gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-glass-border bg-surface-0 p-4"><Table className="h-5 w-5 text-accent-cyan" /><h3 className="mt-3 text-sm font-semibold text-text-primary">Data behind every result</h3><p className="mt-1 text-xs leading-5 text-text-muted">Tables and plotted values must remain exportable as TSV/CSV/JSON alongside the native scientific artifact.</p></div>
        <div className="rounded-xl border border-glass-border bg-surface-0 p-4"><ArrowsOut className="h-5 w-5 text-accent-cyan" /><h3 className="mt-3 text-sm font-semibold text-text-primary">Enlarge before interpretation</h3><p className="mt-1 text-xs leading-5 text-text-muted">Every guided stage can be expanded to a full-screen workspace rather than squeezing complex evidence into dashboard cards.</p></div>
        <div className="rounded-xl border border-glass-border bg-surface-0 p-4"><TestTube className="h-5 w-5 text-accent-cyan" /><h3 className="mt-3 text-sm font-semibold text-text-primary">Authenticity over decoration</h3><p className="mt-1 text-xs leading-5 text-text-muted">FastQC, fastp, Sarek, nf-core/rnaseq and R/Bioconductor outputs stay attributable to their real generating tool and parameters.</p></div>
      </section>
    </div>
  );
}

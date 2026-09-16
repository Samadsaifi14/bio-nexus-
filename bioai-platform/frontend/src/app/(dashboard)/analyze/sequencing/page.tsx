'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Warning as AlertTriangle,
  CheckCircle,
  CircleNotch as LoaderCircle,
  Dna,
  DownloadSimple,
  FileText,
  Flask,
  XCircle,
} from '@phosphor-icons/react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { fadeUp } from '@/lib/animations';
import { getSequencingStatus, listSequencingReferences, runSequencing } from '@/lib/api';
import type { SequencingReference } from '@/lib/api';
import { AIResultSummary } from '@/components/results/AIResultSummary';
import { BackButton, CriticalButton, FlatInput, PageHeader } from '@/components/ui';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import {
  isScientificResult,
  type ScientificArtifact,
  type ScientificPlot,
  type ScientificResult,
} from '@/types/scientific-result';

const DEFAULT_REFERENCES: SequencingReference[] = [
  { id: 'sars-cov-2', name: 'Sars Cov 2' },
  { id: 'lambda', name: 'Lambda' },
];

const EXAMPLES = [{ label: 'Explicit synthetic demo', value: 'synthetic' }];

type ConsensusVariant = {
  pos: number;
  ref: string;
  alt: string;
  depth: number;
  alt_count: number;
  freq: number;
  type: string;
  forward_depth: number;
  reverse_depth: number;
};

type ConsensusResults = Record<string, unknown> & {
  reference: string;
  reference_length: number;
  fastq_source: string;
  synthetic_demo: boolean;
  qc: {
    total_reads: number;
    total_bases: number;
    avg_read_length: number;
    gc_percent: number;
    mean_quality: number;
    q20_percent: number;
    q30_percent: number;
  };
  alignment: {
    total_alignments: number;
    mapped_reads: number;
    unmapped_reads: number;
    passing_mapq_reads: number;
    forward_mapped_reads: number;
    reverse_mapped_reads: number;
    reference_positions: number;
    callable_positions: number;
    callable_fraction: number;
  };
  variants: ConsensusVariant[];
  consensus_sequence: string;
  consensus_callable_fraction: number;
  variant_summary: {
    total_variants: number;
    snv_count: number;
    insertion_count: number;
    deletion_count: number;
  };
  warnings: string[];
  steps_completed: string[];
};

type JobEnvelope = {
  id?: string;
  job_id?: string;
  status: string;
  result?: unknown;
  error?: string | null;
};

function getPlot(result: ScientificResult<ConsensusResults>, id: string): ScientificPlot | undefined {
  return result.plots.find((plot) => plot.id === id);
}

function DownloadList({ artifacts }: { artifacts: ScientificArtifact[] }) {
  const available = artifacts.filter((artifact) => artifact.available !== false && artifact.url);
  if (!available.length) {
    return <p className="text-xs text-text-muted">No durable artifact URLs were emitted for this run.</p>;
  }
  return (
    <div className="grid gap-2 md:grid-cols-2">
      {available.map((artifact) => (
        <a
          key={artifact.name}
          href={String(artifact.url)}
          target="_blank"
          rel="noreferrer"
          className="flex items-center justify-between rounded-xl border border-glass-border bg-surface-1 px-3 py-2 text-xs text-text-primary hover:border-accent-cyan/40"
        >
          <span className="min-w-0 truncate font-mono">{artifact.name}</span>
          <DownloadSimple className="h-4 w-4 flex-none text-accent-cyan" />
        </a>
      ))}
    </div>
  );
}

function ScientificStatusCard({ result }: { result: ScientificResult<ConsensusResults> }) {
  const tone = result.status === 'VALID'
    ? 'text-good border-good/25 bg-good/5'
    : result.status === 'DEGRADED' || result.status === 'NOT_EVALUATED'
      ? 'text-warn border-warn/25 bg-warn/5'
      : 'text-error border-error/25 bg-error/5';
  const Icon = result.status === 'VALID' ? CheckCircle : result.status === 'FAILED' ? XCircle : AlertTriangle;

  return (
    <div className={`data-card border p-5 ${tone}`}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <Icon className="mt-0.5 h-5 w-5 flex-none" />
          <div>
            <p className="text-sm font-semibold">Scientific status: {result.status}</p>
            <p className="mt-1 text-xs text-text-secondary">{result.method}</p>
          </div>
        </div>
        <span className="rounded-lg border border-glass-border bg-surface-1 px-2.5 py-1 font-mono text-xs text-text-secondary">
          {result.engine} {result.engine_version}
        </span>
      </div>
      <div className="grid gap-3 text-xs md:grid-cols-2">
        <div>
          <p className="text-text-muted">Input SHA-256</p>
          <p className="break-all font-mono text-text-secondary">{result.input_sha256}</p>
        </div>
        <div>
          <p className="text-text-muted">Output SHA-256</p>
          <p className="break-all font-mono text-text-secondary">{result.output_sha256}</p>
        </div>
      </div>
      {result.fallback_used && (
        <p className="mt-3 text-xs">
          Fallback executed: <span className="font-mono">{result.fallback_method || 'unspecified'}</span>
        </p>
      )}
    </div>
  );
}

export default function SequencingPage() {
  const audit = useAuditTrail();
  const [fastqUrl, setFastqUrl] = useState('');
  const [reference, setReference] = useState('sars-cov-2');
  const [references, setReferences] = useState<SequencingReference[]>(DEFAULT_REFERENCES);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<JobEnvelope | null>(null);
  const [loading, setLoading] = useState(false);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listSequencingReferences().then((items) => items.length && setReferences(items)).catch(() => undefined);
  }, []);

  const scientific = useMemo(() => {
    if (!job?.result || !isScientificResult(job.result)) return null;
    return job.result as ScientificResult<ConsensusResults>;
  }, [job]);

  const startPipeline = async () => {
    if (!fastqUrl.trim()) return;
    const inputSummary = `ref:${reference},fastq:${fastqUrl.trim().slice(0, 60)}`;
    setLoading(true);
    setError(null);
    setJob(null);
    setJobId(null);
    audit.emitStarted('sequencing_run', 'SequencingPipeline', inputSummary);
    try {
      const response = await runSequencing(fastqUrl.trim(), reference);
      setJobId(response.job_id);
      setPolling(true);
      audit.emitSuccess('sequencing_run', 'SequencingPipeline', inputSummary, `job_id:${response.job_id}`);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Failed to start pipeline';
      setError(message);
      audit.emitFailed('sequencing_run', 'SequencingPipeline', inputSummary, message);
    } finally {
      setLoading(false);
    }
  };

  const poll = useCallback(async () => {
    if (!jobId) return;
    try {
      const response = await getSequencingStatus(jobId);
      const envelope = response as unknown as JobEnvelope;
      setJob(envelope);
      if (envelope.status === 'complete' || envelope.status === 'failed') setPolling(false);
    } catch {
      setPolling(false);
      setError('Failed to check pipeline status');
    }
  }, [jobId]);

  useEffect(() => {
    if (jobId) void poll();
  }, [jobId, poll]);

  useEffect(() => {
    if (!polling) return;
    const timer = setInterval(() => void poll(), 3000);
    return () => clearInterval(timer);
  }, [polling, poll]);

  const results = scientific?.results;
  const depthPlot = scientific ? getPlot(scientific, 'depth_vs_position') : undefined;
  const qualityPlot = scientific ? getPlot(scientific, 'base_quality_distribution') : undefined;
  const afPlot = scientific ? getPlot(scientific, 'allele_fraction_vs_position') : undefined;
  const typePlot = scientific ? getPlot(scientific, 'variant_type_summary') : undefined;

  return (
    <div className="max-w-5xl">
      <BackButton />
      <PageHeader
        title="Consensus Sequencing"
        subtitle="Reference-guided consensus with explicit depth, base-quality, MAPQ and allele-fraction evidence. Alignment failure stops the workflow."
      />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card mb-6 space-y-4 p-5">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-text-primary">FASTQ URL</label>
          <FlatInput
            value={fastqUrl}
            onChange={(event) => { setFastqUrl(event.target.value); setJob(null); setError(null); }}
            onKeyDown={(event) => event.key === 'Enter' && void startPipeline()}
            placeholder="https://example.org/sample.fastq"
            className="w-full font-mono text-sm"
          />
          <div className="mt-2 flex gap-2">
            {EXAMPLES.map((example) => (
              <button key={example.value} onClick={() => setFastqUrl(example.value)} className="text-xs text-accent-cyan hover:underline">
                {example.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium text-text-primary">Reference genome</label>
          <select value={reference} onChange={(event) => setReference(event.target.value)} className="w-full rounded-xl border border-glass-border bg-surface-1 px-4 py-3 text-sm text-text-primary">
            {references.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </div>
        <p className="text-xs text-text-muted">
          The exact consensus thresholds used by the backend are recorded in each result. Synthetic reads are generated only when explicitly selected above.
        </p>
        <CriticalButton onClick={startPipeline} disabled={loading || polling || !fastqUrl.trim()} className="w-full justify-center py-3">
          {loading || polling ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Dna className="h-4 w-4" />}
          {loading ? 'Submitting…' : polling ? 'Scientific pipeline running…' : 'Run consensus sequencing'}
        </CriticalButton>
      </motion.div>

      {error && (
        <div className="mb-6 rounded-xl border border-error/25 bg-error/5 p-4 text-sm text-error">
          {error}
        </div>
      )}

      {job && !scientific && (
        <div className="data-card mb-6 flex items-center gap-3 p-5">
          {job.status === 'failed' ? <XCircle className="h-5 w-5 text-error" /> : <LoaderCircle className="h-5 w-5 animate-spin text-accent-cyan" />}
          <div>
            <p className="text-sm font-medium text-text-primary">Job state: {job.status}</p>
            <p className="text-xs text-text-muted">A scientific result has not been emitted yet.</p>
            {job.error && <p className="mt-1 text-xs text-error">{job.error}</p>}
          </div>
        </div>
      )}

      {scientific && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-4">
          <ScientificStatusCard result={scientific} />

          {scientific.status !== 'FAILED' && results && (
            <>
              {results.synthetic_demo && (
                <div className="rounded-xl border border-warn/25 bg-warn/5 p-4 text-xs text-warn">
                  SYNTHETIC DEMONSTRATION DATA — implementation behavior only; this run does not establish biological accuracy.
                </div>
              )}

              <div className="data-card p-5">
                <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary"><Flask className="h-4 w-4 text-accent-cyan" /> Declared method and parameters</h3>
                <div className="grid gap-3 md:grid-cols-3">
                  {Object.entries(scientific.parameters).map(([key, value]) => (
                    <div key={key} className="rounded-xl bg-surface-1 p-3">
                      <p className="text-xs text-text-muted">{key}</p>
                      <p className="mt-1 font-mono text-sm text-text-primary">{String(value)}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="data-card p-5">
                <h3 className="mb-4 text-sm font-semibold text-text-primary">FASTQ QC</h3>
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  {[
                    ['Total reads', results.qc.total_reads],
                    ['Total bases', results.qc.total_bases],
                    ['Mean quality', results.qc.mean_quality],
                    ['Q30 %', results.qc.q30_percent],
                    ['Q20 %', results.qc.q20_percent],
                    ['GC %', results.qc.gc_percent],
                    ['Mean read length', results.qc.avg_read_length],
                    ['Source', results.fastq_source],
                  ].map(([label, value]) => (
                    <div key={String(label)} className="rounded-xl bg-surface-1 p-3">
                      <p className="text-xs text-text-muted">{label}</p>
                      <p className="mt-1 break-words font-mono text-sm text-text-primary">{String(value)}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="data-card p-5">
                <h3 className="mb-4 text-sm font-semibold text-text-primary">Alignment and consensus evidence</h3>
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  {[
                    ['Mapped reads', results.alignment.mapped_reads],
                    ['Unmapped reads', results.alignment.unmapped_reads],
                    ['Passing MAPQ reads', results.alignment.passing_mapq_reads],
                    ['Forward mapped', results.alignment.forward_mapped_reads],
                    ['Reverse mapped', results.alignment.reverse_mapped_reads],
                    ['Callable positions', results.alignment.callable_positions],
                    ['Reference positions', results.alignment.reference_positions],
                    ['Callable fraction', results.alignment.callable_fraction],
                  ].map(([label, value]) => (
                    <div key={String(label)} className="rounded-xl bg-surface-1 p-3">
                      <p className="text-xs text-text-muted">{label}</p>
                      <p className="mt-1 font-mono text-sm text-text-primary">{String(value)}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 xl:grid-cols-2">
                {depthPlot && Array.isArray(depthPlot.data) && (
                  <div className="data-card p-5">
                    <h3 className="mb-3 text-sm font-semibold text-text-primary">{depthPlot.title}</h3>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={depthPlot.data as Array<Record<string, number>>}>
                          <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                          <XAxis dataKey="position" tick={{ fontSize: 10 }} />
                          <YAxis tick={{ fontSize: 10 }} />
                          <Tooltip />
                          <Line dataKey="depth" type="linear" dot={false} isAnimationActive={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                    {'calculated_points' in depthPlot && 'displayed_points' in depthPlot && (
                      <p className="mt-2 text-xs text-text-muted">Displaying {String(depthPlot.displayed_points)} of {String(depthPlot.calculated_points)} calculated points. Download depth.tsv for the complete result.</p>
                    )}
                  </div>
                )}

                {qualityPlot && Array.isArray(qualityPlot.data) && (
                  <div className="data-card p-5">
                    <h3 className="mb-3 text-sm font-semibold text-text-primary">{qualityPlot.title}</h3>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={qualityPlot.data as Array<Record<string, number>>}>
                          <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                          <XAxis dataKey="quality" tick={{ fontSize: 10 }} />
                          <YAxis tick={{ fontSize: 10 }} />
                          <Tooltip />
                          <Bar dataKey="count" isAnimationActive={false} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {afPlot && Array.isArray(afPlot.data) && (
                  <div className="data-card p-5">
                    <h3 className="mb-3 text-sm font-semibold text-text-primary">{afPlot.title}</h3>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <ScatterChart>
                          <CartesianGrid opacity={0.15} />
                          <XAxis dataKey="position" name="position" tick={{ fontSize: 10 }} />
                          <YAxis dataKey="allele_fraction" name="allele fraction" domain={[0, 1]} tick={{ fontSize: 10 }} />
                          <Tooltip />
                          <Scatter data={afPlot.data as Array<Record<string, number>>} isAnimationActive={false} />
                        </ScatterChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {typePlot && Array.isArray(typePlot.data) && (
                  <div className="data-card p-5">
                    <h3 className="mb-3 text-sm font-semibold text-text-primary">{typePlot.title}</h3>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={typePlot.data as Array<Record<string, number | string>>}>
                          <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                          <XAxis dataKey="type" tick={{ fontSize: 10 }} />
                          <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                          <Tooltip />
                          <Bar dataKey="count" isAnimationActive={false} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}
              </div>

              <div className="data-card p-5">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-text-primary">Called variants</h3>
                  <div className="flex gap-3 text-xs text-text-muted">
                    <span>Total {results.variant_summary.total_variants}</span>
                    <span>SNV {results.variant_summary.snv_count}</span>
                    <span>INS {results.variant_summary.insertion_count}</span>
                    <span>DEL {results.variant_summary.deletion_count}</span>
                  </div>
                </div>
                {results.variants.length ? (
                  <div className="max-h-96 overflow-auto">
                    <table className="w-full text-xs">
                      <thead className="sticky top-0 bg-surface-1 text-text-muted">
                        <tr>
                          {['Type', 'Pos', 'Ref', 'Alt', 'Depth', 'Alt count', 'AF', 'Forward', 'Reverse'].map((heading) => <th key={heading} className="px-2 py-2 text-left font-medium">{heading}</th>)}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-glass-border">
                        {results.variants.map((variant, index) => (
                          <tr key={`${variant.pos}-${variant.ref}-${variant.alt}-${index}`}>
                            <td className="px-2 py-2 font-mono">{variant.type}</td>
                            <td className="px-2 py-2 font-mono">{variant.pos}</td>
                            <td className="px-2 py-2 font-mono">{variant.ref}</td>
                            <td className="px-2 py-2 font-mono">{variant.alt}</td>
                            <td className="px-2 py-2 font-mono">{variant.depth}</td>
                            <td className="px-2 py-2 font-mono">{variant.alt_count}</td>
                            <td className="px-2 py-2 font-mono">{variant.freq}</td>
                            <td className="px-2 py-2 font-mono">{variant.forward_depth}</td>
                            <td className="px-2 py-2 font-mono">{variant.reverse_depth}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-text-secondary">{String(scientific.validation.no_variant_wording || 'No variant call was emitted.')}</p>
                )}
              </div>

              {!!results.warnings?.length && (
                <div className="rounded-xl border border-warn/25 bg-warn/5 p-4 text-xs text-warn">
                  {results.warnings.map((warning) => <p key={warning}>{warning}</p>)}
                </div>
              )}

              <div className="data-card p-5">
                <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary"><FileText className="h-4 w-4 text-accent-cyan" /> Scientific artifacts</h3>
                <DownloadList artifacts={scientific.artifacts} />
              </div>
            </>
          )}

          <AIResultSummary toolName="sequencing" result={scientific as unknown as Record<string, unknown>} />
        </motion.div>
      )}
    </div>
  );
}

'use client';

import { useState, useEffect, useCallback, lazy, Suspense } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  CircleNotch as LoaderCircle,
  CheckCircle,
  XCircle,
  Warning as AlertTriangle,
  Dna,
  ChartBar as BarChart3,
  Scissors,
  MapTrifold as Map,
  Bug,
  Note,
  Binoculars,
  Download,
  FileText,
  MagnifyingGlass as Search,
} from '@phosphor-icons/react';
import { fadeUp } from '@/lib/animations';
import { runNGS, getNGSStatus, listNGSReferences } from '@/lib/api';
import type { NGSResult, NGSReference } from '@/lib/api';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import { BackButton, CriticalButton, FlatInput, PageHeader, ResultsReadyBanner } from '@/components/ui';

const GenomeViewer = lazy(() => import('@/components/GenomeViewer'));

const DEFAULT_REFERENCES = [
  { id: 'sars-cov-2', name: 'SARS-CoV-2' },
  { id: 'lambda', name: 'Lambda Phage' },
  { id: 'ecoli-k12', name: 'E. coli K-12' },
];

const EXAMPLE_FASTQ = [
  { label: 'Demo (synthetic reads)', value: 'synthetic' },
];

const STEPS = [
  { id: 'qc',            label: 'Quality Control',     icon: BarChart3, description: 'Per-base quality, GC content, adapter detection' },
  { id: 'trim',          label: 'Trimming / Filtering', icon: Scissors, description: 'Adapter removal, quality filtering (Q≥20, len≥50)' },
  { id: 'align',         label: 'Read Alignment',       icon: Map,      description: 'minimap2 / samtools → sorted, indexed BAM' },
  { id: 'variants',      label: 'Variant Calling',      icon: Bug,      description: 'bcftools mpileup + call → VCF' },
  { id: 'annotate',      label: 'Annotation',           icon: Note,     description: 'SnpEff / cross-reference lookup' },
  { id: 'visualization', label: 'Visualization (igv.js)', icon: Binoculars, description: 'Genome browser: BAM + VCF tracks' },
];

const REFERENCE_LOCUS: Record<string, string> = {
  'sars-cov-2': 'NC_045512v2:21000-25000',
  'lambda': 'NC_001416:1-5000',
  'ecoli-k12': 'U00096.3:1-5000',
};

export default function NGSPage() {
  const router = useRouter();
  const [fastqUrl, setFastqUrl] = useState('');
  const [reference, setReference] = useState('sars-cov-2');
  const audit = useAuditTrail();
  const [references, setReferences] = useState<NGSReference[]>(DEFAULT_REFERENCES);
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<NGSResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

  useEffect(() => {
    listNGSReferences().then((r) => { if (r.length > 0) setReferences(r); }).catch(() => {});
  }, []);

  const startPipeline = async () => {
    if (!fastqUrl.trim()) return;
    const inputSummary = `ref:${reference},fastq:${fastqUrl.trim().slice(0, 60)}`;
    audit.emitStarted('ngs_run', 'NGSPipeline', inputSummary);
    setLoading(true);
    setError(null);
    setResult(null);
    setJobId(null);
    try {
      const { job_id } = await runNGS(fastqUrl.trim(), reference);
      setJobId(job_id);
      setPolling(true);
      audit.emitSuccess('ngs_run', 'NGSPipeline', inputSummary, `job_id:${job_id}`);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Failed to start NGS pipeline';
      audit.emitFailed('ngs_run', 'NGSPipeline', inputSummary, errMsg);
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  const poll = useCallback(async () => {
    if (!jobId) return;
    try {
      const status = await getNGSStatus(jobId);
      setResult(status);
      if (status.status === 'complete' || status.status === 'failed') {
        setPolling(false);
      }
    } catch {
      setPolling(false);
      setError('Failed to check NGS pipeline status');
    }
  }, [jobId]);

  useEffect(() => {
    if (!polling) return;
    const interval = setInterval(poll, 3000);
    return () => clearInterval(interval);
  }, [polling, poll]);

  useEffect(() => {
    if (jobId) poll();
  }, [jobId, poll]);

  const statusIcon = (status?: string) => {
    if (!status || status === 'queued') return <LoaderCircle className="w-4 h-4 text-text-muted animate-pulse" />;
    if (status === 'complete') return <CheckCircle className="w-5 h-5 text-good" />;
    if (status === 'failed') return <XCircle className="w-5 h-5 text-error" />;
    return <LoaderCircle className="w-5 h-5 text-accent-cyan animate-spin" />;
  };

  const stepStatus = (stepId: string): 'pending' | 'running' | 'done' | 'failed' => {
    if (!result?.result) return 'pending';
    if (result.status === 'failed') return 'failed';
    const completed = result.result.steps_completed || [];
    if (completed.includes(stepId)) return 'done';
    if (result.status === 'running' || result.status === 'downloading') {
      const idx = STEPS.findIndex(s => s.id === stepId);
      const lastDone = completed.length;
      if (idx === lastDone) return 'running';
      if (idx < lastDone) return 'done';
    }
    return 'pending';
  };

  const isComplete = result?.status === 'complete';
  const hasFiles = !!(result?.result?.file_urls?.bam || result?.result?.file_urls?.sam);

  return (
    <div className="max-w-4xl">
      <BackButton />

      <PageHeader
        title="NGS Pipeline"
        subtitle="Full 6-step analysis: QC → Trimming → Alignment → Variant Calling → Annotation → Visualization"
      />

      {/* Input Form */}
      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-text-primary mb-1.5">FASTQ URL</label>
          <FlatInput
            type="text"
            value={fastqUrl}
            onChange={(e) => { setFastqUrl(e.target.value); setResult(null); setError(null); }}
            onKeyDown={(e) => e.key === 'Enter' && startPipeline()}
            placeholder="https://example.com/sample.fastq"
            className="w-full px-4 py-3 rounded-xl text-sm font-mono"
          />
          <div className="flex gap-2 mt-2 flex-wrap">
            <span className="text-xs text-text-muted">Example:</span>
            {EXAMPLE_FASTQ.map((ex) => (
              <button
                key={ex.label}
                onClick={() => setFastqUrl(ex.value)}
                className="px-2 py-1 text-xs rounded bg-accent-cyan/10 text-accent-cyan hover:bg-accent-cyan/20 transition font-mono"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-text-primary mb-1.5">Reference Genome</label>
          <select
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            className="w-full px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm bg-surface-1 text-text-primary"
          >
            {references.map((ref) => (
              <option key={ref.id} value={ref.id}>{ref.name}</option>
            ))}
          </select>
        </div>

        <CriticalButton onClick={startPipeline} disabled={loading || !fastqUrl.trim() || polling}
          className="w-full py-3 flex items-center justify-center gap-2 disabled:opacity-50">
          {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Dna className="w-4 h-4" />}
          {loading ? 'Starting...' : polling ? 'Running NGS Pipeline...' : 'Run NGS Pipeline'}
        </CriticalButton>
      </motion.div>

      {/* Error */}
      {error && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-4 mb-6 border border-error/20">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-error flex-shrink-0 mt-0.5" />
            <p className="text-sm text-error">{error}</p>
          </div>
        </motion.div>
      )}

      {/* Results */}
      {result && (
        <motion.div id="ngs-results" variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-4">
          {isComplete && (
            <ResultsReadyBanner
              title="NGS Pipeline complete"
              subtitle={`${result.result?.reference ?? ''} · All 6 steps finished · igv.js viewer ready`}
            />
          )}

          {/* Pipeline Progress */}
          <div className="data-card p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                {statusIcon(result.status)}
                <span className="text-sm font-medium text-text-primary capitalize">{result.status}</span>
              </div>
              <span className="text-xs text-text-muted font-mono">{result.result?.reference}</span>
            </div>

            <div className="space-y-1">
              {STEPS.map((step, i) => {
                const Icon = step.icon;
                const s = stepStatus(step.id);
                return (
                  <div key={step.id}>
                    <div className="flex items-center gap-3 py-2 px-2 rounded-lg hover:bg-surface-1/50 transition">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                        s === 'done' ? 'bg-good/10 text-good' :
                        s === 'running' ? 'bg-accent-cyan/10 text-accent-cyan' :
                        s === 'failed' ? 'bg-error/10 text-error' :
                        'bg-surface-1 text-text-muted'
                      }`}>
                        {s === 'done' ? <CheckCircle className="w-4 h-4" /> :
                         s === 'running' ? <LoaderCircle className="w-4 h-4 animate-spin" /> :
                         <Icon className="w-4 h-4" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm font-medium ${
                          s === 'done' ? 'text-good' :
                          s === 'running' ? 'text-accent-cyan' :
                          s === 'failed' ? 'text-error' :
                          'text-text-muted'
                        }`}>{step.label}</p>
                        <p className="text-[11px] text-text-muted truncate">{step.description}</p>
                      </div>
                      {result.result?.tools_used && step.id !== 'visualization' && (
                        <span className="text-[10px] text-text-muted font-mono flex-shrink-0">{result.result.tools_used[step.id === 'annotate' ? 'annotate' : step.id === 'trim' ? 'trim' : step.id]}</span>
                      )}
                    </div>
                    {i < STEPS.length - 1 && (
                      <div className={`w-px h-2 ml-5.5 ${s === 'done' ? 'bg-good/30' : 'bg-glass-border'}`} />
                    )}
                  </div>
                );
              })}
            </div>

            {result.status === 'failed' && result.error && (
              <div className="p-3 rounded-lg bg-error/5 border border-error/20 mt-4">
                <pre className="text-xs text-error whitespace-pre-wrap font-mono">{result.error}</pre>
              </div>
            )}
          </div>

          {/* Step 1: QC Results */}
          {result.result?.qc && (
            <div className="data-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-accent-cyan" /> Step 1 — Quality Control
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                {[
                  { label: 'Total Reads', value: result.result.qc.total_reads.toLocaleString() },
                  { label: 'Total Bases', value: result.result.qc.total_bases.toLocaleString() },
                  { label: 'Avg Length', value: `${result.result.qc.avg_read_length} bp` },
                  { label: 'GC Content', value: `${result.result.qc.gc_percent}%` },
                  { label: 'Mean Quality', value: `${result.result.qc.mean_quality}`, color: result.result.qc.mean_quality >= 30 ? 'text-good' : result.result.qc.mean_quality >= 20 ? 'text-warn' : 'text-error' },
                  { label: 'Q30', value: `${result.result.qc.q30_percent}%` },
                  { label: 'Q20', value: `${result.result.qc.q20_percent}%` },
                  { label: 'Read Range', value: `${result.result.qc.min_read_length}–${result.result.qc.max_read_length}` },
                ].map(({ label, value, color }) => (
                  <div key={label} className="p-3 rounded-xl bg-surface-1">
                    <p className="text-[11px] text-text-muted">{label}</p>
                    <p className={`text-base font-bold font-mono ${color || 'text-text-primary'}`}>{value}</p>
                  </div>
                ))}
              </div>

              {/* Quality by position chart */}
              {result.result.qc.quality_by_position && result.result.qc.quality_by_position.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs text-text-muted mb-2">Per-Base Quality Distribution</p>
                  <div className="relative h-40 bg-surface-1 rounded-lg overflow-hidden p-2">
                    {(() => {
                      const qbp = result.result!.qc.quality_by_position!;
                      const n = qbp.length;
                      return (
                        <svg viewBox={`0 0 ${n} 40`} className="w-full h-full" preserveAspectRatio="none">
                          <line x1={0} y1={10} x2={n} y2={10}
                            stroke="#22c55e" strokeWidth={0.3} strokeDasharray="2,2" opacity={0.4} />
                          <line x1={0} y1={20} x2={n} y2={20}
                            stroke="#eab308" strokeWidth={0.3} strokeDasharray="2,2" opacity={0.4} />
                          <polyline
                            points={qbp.map((p, i) => `${i},${40 - (p.mean / 40) * 40}`).join(' ')}
                            fill="none"
                            stroke="#06b6d4"
                            strokeWidth={0.8}
                          />
                          <polygon
                            points={[
                              ...qbp.map((p, i) => `${i},${40 - (p.q90 / 40) * 40}`),
                              ...qbp.map((p, i) => `${n - 1 - i},${40 - (qbp[n - 1 - i].q10 / 40) * 40}`),
                            ].join(' ')}
                            fill="#06b6d4"
                            opacity={0.1}
                          />
                        </svg>
                      );
                    })()}
                    <div className="absolute top-1 right-2 flex items-center gap-3 text-[9px] text-text-muted">
                      <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-accent-cyan inline-block" /> Mean</span>
                      <span className="text-good">Q30</span>
                      <span className="text-warn">Q20</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Overrepresented sequences */}
              {result.result.qc.overrepresented_sequences && result.result.qc.overrepresented_sequences.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs text-text-muted mb-1">Overrepresented Sequences (top 5)</p>
                  <div className="space-y-1">
                    {result.result.qc.overrepresented_sequences.slice(0, 5).map((s, i) => (
                      <div key={i} className="flex items-center gap-2 text-[11px]">
                        <span className="font-mono text-text-primary truncate max-w-[200px]">{s.sequence}</span>
                        <span className="text-text-muted">{s.count}x ({s.percent}%)</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Step 2: Trimming */}
          {result.result?.trimming && (
            <div className="data-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                <Scissors className="w-4 h-4 text-accent-cyan" /> Step 2 — Trimming / Filtering
              </h3>
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-[11px] text-text-muted">Reads Before</p>
                  <p className="text-base font-bold text-text-primary font-mono">{result.result.trimming.reads_before.toLocaleString()}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-[11px] text-text-muted">Reads After</p>
                  <p className="text-base font-bold text-good font-mono">{result.result.trimming.reads_after.toLocaleString()}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-[11px] text-text-muted">Discarded</p>
                  <p className="text-base font-bold text-warn font-mono">{result.result.trimming.reads_discarded.toLocaleString()}</p>
                </div>
              </div>
              {result.result.trimming.reads_before > 0 && (
                <div className="mt-3">
                  <div className="flex items-center gap-2 text-xs text-text-muted mb-1">
                    <span>Retention Rate:</span>
                    <span className="font-mono text-text-primary">
                      {(result.result.trimming.reads_after / result.result.trimming.reads_before * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-surface-1 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-good transition-all"
                      style={{ width: `${(result.result.trimming.reads_after / result.result.trimming.reads_before * 100)}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Step 3: Alignment */}
          {result.result?.alignment && (
            <div className="data-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                <Map className="w-4 h-4 text-accent-cyan" /> Step 3 — Read Alignment
              </h3>
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-[11px] text-text-muted">Total Alignments</p>
                  <p className="text-base font-bold text-text-primary font-mono">{result.result.alignment.total_alignments.toLocaleString()}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-[11px] text-text-muted">Mapped</p>
                  <p className="text-base font-bold text-good font-mono">{result.result.alignment.mapped_reads.toLocaleString()}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-[11px] text-text-muted">Unmapped</p>
                  <p className="text-base font-bold text-warn font-mono">{result.result.alignment.unmapped_reads.toLocaleString()}</p>
                </div>
              </div>
              {result.result.alignment.total_alignments > 0 && (
                <div className="mt-3">
                  <div className="flex items-center gap-2 text-xs text-text-muted mb-1">
                    <span>Mapping Rate:</span>
                    <span className="font-mono text-text-primary">
                      {(result.result.alignment.mapped_reads / result.result.alignment.total_alignments * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-surface-1 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-accent-cyan transition-all"
                      style={{ width: `${(result.result.alignment.mapped_reads / result.result.alignment.total_alignments * 100)}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Step 4: Variants */}
          {result.result?.variants && result.result.variants.length > 0 && (
            <div className="data-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                <Bug className="w-4 h-4 text-accent-cyan" /> Step 4 — Variant Calling ({result.result.variants.length} variants)
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[11px] text-text-muted uppercase border-b border-glass-border">
                      <th className="text-left py-2 pr-4">Pos</th>
                      <th className="text-left py-2 pr-4">Ref</th>
                      <th className="text-left py-2 pr-4">Alt</th>
                      <th className="text-left py-2 pr-4">Depth</th>
                      <th className="text-left py-2 pr-4">Alt Count</th>
                      <th className="text-left py-2">Frequency</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-glass-border">
                    {result.result.variants.map((v, i) => (
                      <tr key={i} className="text-text-primary">
                        <td className="py-2 pr-4 font-mono">{v.pos.toLocaleString()}</td>
                        <td className="py-2 pr-4 font-mono text-good">{v.ref}</td>
                        <td className="py-2 pr-4 font-mono text-accent-cyan">{v.alt}</td>
                        <td className="py-2 pr-4 font-mono">{v.depth}</td>
                        <td className="py-2 pr-4 font-mono">{v.alt_count}</td>
                        <td className="py-2 font-mono text-warn">{(v.freq * 100).toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Step 5: Annotation */}
          {result.result?.annotation && result.result.annotation.annotations.length > 0 && (
            <div className="data-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                <Note className="w-4 h-4 text-accent-cyan" /> Step 5 — Annotation ({result.result.annotation.total_annotated})
              </h3>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-[11px] text-text-muted">Known Variants</p>
                  <p className="text-base font-bold text-good font-mono">{result.result.annotation.known_variants_found}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-[11px] text-text-muted">Novel Variants</p>
                  <p className="text-base font-bold text-warn font-mono">{result.result.annotation.total_annotated - result.result.annotation.known_variants_found}</p>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[11px] text-text-muted uppercase border-b border-glass-border">
                      <th className="text-left py-2 pr-4">Position</th>
                      <th className="text-left py-2 pr-4">Mutation</th>
                      <th className="text-left py-2 pr-4">Gene</th>
                      <th className="text-left py-2 pr-4">Protein</th>
                      <th className="text-left py-2">Significance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-glass-border">
                    {result.result.annotation.annotations.slice(0, 20).map((a, i) => (
                      <tr key={i} className="text-text-primary">
                        <td className="py-2 pr-4 font-mono">{a.pos.toLocaleString()}</td>
                        <td className="py-2 pr-4 font-mono text-accent-cyan">{a.mutation}</td>
                        <td className="py-2 pr-4 font-mono text-good">{a.gene}</td>
                        <td className="py-2 pr-4 font-mono text-text-muted">{(a as any).protein_change || '—'}</td>
                        <td className="py-2 text-xs">{a.significance}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Step 6: igv.js Visualization */}
          {isComplete && hasFiles && (
            <div className="data-card p-5">
               <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                <Binoculars className="w-4 h-4 text-accent-cyan" /> Step 6 — Genome Viewer
              </h3>
              <p className="text-xs text-text-muted mb-4">
                Interactive alignment &amp; variant viewer — click on reads or variants to zoom. Use toolbar to navigate.
              </p>
              <div className="rounded-xl overflow-hidden border border-glass-border bg-white">
                <Suspense fallback={
                  <div className="flex items-center justify-center h-[500px] bg-surface-1 rounded-xl">
                    <LoaderCircle className="w-6 h-6 text-accent-cyan animate-spin" />
                    <span className="ml-2 text-sm text-text-muted">Loading genome viewer...</span>
                  </div>
                }>
                   <GenomeViewer
                    samUrl={result.result!.file_urls!.sam}
                    vcfUrl={result.result!.file_urls!.vcf}
                    locus={result.result!.alignment?.read_region || REFERENCE_LOCUS[result.result!.reference] || undefined}
                  />
                </Suspense>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {result.result!.file_urls!.bam && (
                  <a href={result.result!.file_urls!.bam} target="_blank" rel="noopener noreferrer"
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-1 text-xs text-text-muted hover:text-text-primary transition">
                    <Download className="w-3.5 h-3.5" /> BAM
                  </a>
                )}
                {result.result!.file_urls!.sam && (
                  <a href={result.result!.file_urls!.sam} target="_blank" rel="noopener noreferrer"
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-1 text-xs text-text-muted hover:text-text-primary transition">
                    <Download className="w-3.5 h-3.5" /> SAM
                  </a>
                )}
                {result.result!.file_urls!.vcf && (
                  <a href={result.result!.file_urls!.vcf} target="_blank" rel="noopener noreferrer"
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-1 text-xs text-text-muted hover:text-text-primary transition">
                    <Download className="w-3.5 h-3.5" /> VCF
                  </a>
                )}
                {result.result!.file_urls!.reference && (
                  <a href={result.result!.file_urls!.reference} target="_blank" rel="noopener noreferrer"
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-1 text-xs text-text-muted hover:text-text-primary transition">
                    <Download className="w-3.5 h-3.5" /> Reference FASTA
                  </a>
                )}
              </div>
            </div>
          )}

          {/* Summary Report */}
          {result.result?.report && (
            <div className="data-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                <FileText className="w-4 h-4 text-accent-cyan" /> Summary Report
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-[11px] text-text-muted">Reference</p>
                  <p className="text-sm font-bold text-text-primary font-mono">{result.result.report.reference}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-[11px] text-text-muted">Total Variants</p>
                  <p className="text-base font-bold text-text-primary font-mono">{result.result.report.variant_summary.total_variants}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-[11px] text-text-muted">SNVs</p>
                  <p className="text-base font-bold text-text-primary font-mono">{result.result.report.variant_summary.snv_count}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-[11px] text-text-muted">Known / Novel</p>
                  <p className="text-base font-bold text-text-primary font-mono">
                    {result.result.report.variant_summary.known_variants} / {result.result.report.variant_summary.novel_variants}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-[11px] text-text-muted">Mapping Rate</p>
                  <p className="text-base font-bold text-accent-cyan font-mono">{result.result.report.alignment_summary.mapping_rate}%</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-[11px] text-text-muted">Reads After Trim</p>
                  <p className="text-base font-bold text-text-primary font-mono">{result.result.report.trimming_summary.reads_after.toLocaleString()}</p>
                </div>
              </div>
            </div>
          )}

          {/* No Variants */}
          {result.result?.variants && result.result.variants.length === 0 && (
            <div className="data-card p-5">
              <div className="flex items-center gap-2 text-text-muted">
                <CheckCircle className="w-4 h-4 text-good" />
                <p className="text-sm">No variants detected in the sample.</p>
              </div>
            </div>
          )}

          {/* Download + Bridge */}
          {isComplete && (
            <div className="data-card p-4 space-y-3">
              {result.result?.consensus_sequence && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-muted">Consensus Sequence (SNVs applied)</span>
                  <button
                    onClick={() => {
                      const a = document.createElement('a');
                      a.download = `${result.result?.reference}-consensus.fasta`;
                      a.href = 'data:text/fasta;charset=utf-8,' + encodeURIComponent(result.result!.consensus_sequence!);
                      a.click();
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-cyan/10 text-accent-cyan text-xs font-medium hover:bg-accent-cyan/20 transition border border-accent-cyan/20"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download consensus FASTA
                  </button>
                </div>
              )}
              <div className="flex items-center justify-between pt-2 border-t border-glass-border">
                <span className="text-xs text-text-muted">Bridge: BLAST Analysis</span>
                <button
                  onClick={() => {
                    if (result.result?.consensus_sequence) {
                      sessionStorage.setItem('blast_sequence', result.result.consensus_sequence);
                    }
                    router.push('/analyze/blast');
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-cyan/10 text-accent-cyan text-xs font-medium hover:bg-accent-cyan/20 transition border border-accent-cyan/20"
                >
                  <Search className="w-3.5 h-3.5" />
                  Identify assembled sequence with BLAST
                </button>
              </div>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}

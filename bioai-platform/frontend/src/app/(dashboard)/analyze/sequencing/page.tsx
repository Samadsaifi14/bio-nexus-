'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { CircleNotch as LoaderCircle, CheckCircle, XCircle, Warning as AlertTriangle, Dna, ChartBar as BarChart3, MapTrifold as Map, Bug, FileText, MagnifyingGlass as Search } from '@phosphor-icons/react';
import { fadeUp } from '@/lib/animations';
import { runSequencing, getSequencingStatus, listSequencingReferences } from '@/lib/api';
import type { SequencingResult, SequencingReference } from '@/lib/api';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import { BackButton, CriticalButton, FlatInput, PageHeader, ResultsReadyBanner } from '@/components/ui';
import { AIResultSummary } from '@/components/results/AIResultSummary';

const DEFAULT_REFERENCES = [
  { id: 'sars-cov-2', name: 'Sars Cov 2' },
  { id: 'lambda', name: 'Lambda' },
];

const EXAMPLE_FASTQ = [
  { label: 'Demo (synthetic reads)', value: 'synthetic' },
];

const STEPS = [
  { id: 'qc',       label: 'Quality Control',     icon: BarChart3 },
  { id: 'align',    label: 'Read Alignment',       icon: Map },
  { id: 'variants', label: 'Variant Calling',      icon: Bug },
  { id: 'report',   label: 'Summary Report',        icon: FileText },
];

export default function SequencingPage() {
  const router = useRouter();
  const [fastqUrl, setFastqUrl] = useState('');
  const [reference, setReference] = useState('sars-cov-2');
  const audit = useAuditTrail();
  const [references, setReferences] = useState<SequencingReference[]>(DEFAULT_REFERENCES);
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<SequencingResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

  useEffect(() => {
    listSequencingReferences().then((r) => { if (r.length > 0) setReferences(r); }).catch(() => {});
  }, []);

  const startPipeline = async () => {
    if (!fastqUrl.trim()) return;
    const inputSummary = `ref:${reference},fastq:${fastqUrl.trim().slice(0,60)}`;
    audit.emitStarted('sequencing_run', 'SequencingPipeline', inputSummary);
    setLoading(true);
    setError(null);
    setResult(null);
    setJobId(null);
    try {
      const { job_id } = await runSequencing(fastqUrl.trim(), reference);
      setJobId(job_id);
      setPolling(true);
      audit.emitSuccess('sequencing_run', 'SequencingPipeline', inputSummary, `job_id:${job_id}`);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Failed to start pipeline';
      audit.emitFailed('sequencing_run', 'SequencingPipeline', inputSummary, errMsg);
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  const poll = useCallback(async () => {
    if (!jobId) return;
    try {
      const status = await getSequencingStatus(jobId);
      setResult(status);
      if (status.status === 'complete' || status.status === 'failed') {
        setPolling(false);
      }
    } catch {
      setPolling(false);
      setError('Failed to check pipeline status');
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

  const stepStatus = (stepId: string): 'pending' | 'running' | 'done' | 'failed' | 'skipped' => {
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

  return (
    <div className="max-w-3xl">
      <BackButton />

      <PageHeader
        title="Sequencing Pipeline"
        subtitle="Raw FASTQ → QC → alignment → variant calling → report. Supports viral/bacterial genomes (cpu-basic tier)."
      />

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
          {loading ? 'Starting...' : polling ? 'Running Pipeline...' : 'Run Pipeline'}
        </CriticalButton>
      </motion.div>

      {error && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-4 mb-6 border border-error/20">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-error flex-shrink-0 mt-0.5" />
            <p className="text-sm text-error">{error}</p>
          </div>
        </motion.div>
      )}

      {result && (
        <motion.div id="sequencing-results" variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-4">
          <AIResultSummary toolName="sequencing" result={result as unknown as Record<string, unknown>} />
          {result.status === 'complete' && (
            <ResultsReadyBanner
              title="Pipeline complete"
              subtitle={result.result?.consensus_sequence ? `Consensus sequence ready · ${result.result.reference ?? ''}` : 'All pipeline steps finished'}
            />
          )}
            <div className="data-card p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                {statusIcon(result.status)}
                <span className="text-sm font-medium text-text-primary capitalize">{result.status}</span>
              </div>
              <span className="text-xs text-text-muted font-mono">{result.result?.reference}</span>
            </div>

            <div className="space-y-3">
              {STEPS.map((step, i) => {
                const Icon = step.icon;
                const s = stepStatus(step.id);
                return (
                  <div key={step.id} className="flex items-center gap-3">
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
                    <div className="flex-1">
                      <p className={`text-sm font-medium ${
                        s === 'done' ? 'text-good' :
                        s === 'running' ? 'text-accent-cyan' :
                        s === 'failed' ? 'text-error' :
                        'text-text-muted'
                      }`}>{step.label}</p>
                    </div>
                    {i < STEPS.length - 1 && (
                      <div className={`w-px h-4 mx-2 ${
                        s === 'done' ? 'bg-good/30' : 'bg-glass-border'
                      }`} />
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

          {result.result?.qc && (
            <div className="data-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-accent-cyan" /> Quality Control
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-xs text-text-muted">Total Reads</p>
                  <p className="text-lg font-bold text-text-primary font-mono">{result.result.qc.total_reads.toLocaleString()}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-xs text-text-muted">Total Bases</p>
                  <p className="text-lg font-bold text-text-primary font-mono">{result.result.qc.total_bases.toLocaleString()}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-xs text-text-muted">Avg Read Length</p>
                  <p className="text-lg font-bold text-text-primary font-mono">{result.result.qc.avg_read_length}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-xs text-text-muted">GC Content</p>
                  <p className="text-lg font-bold text-text-primary font-mono">{result.result.qc.gc_percent}%</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-xs text-text-muted">Mean Quality</p>
                  <p className={`text-lg font-bold font-mono ${
                    result.result.qc.mean_quality >= 30 ? 'text-good' :
                    result.result.qc.mean_quality >= 20 ? 'text-warn' : 'text-text-muted'
                  }`}>{result.result.qc.mean_quality}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-xs text-text-muted">Q30</p>
                  <p className="text-lg font-bold text-text-primary font-mono">{result.result.qc.q30_percent}%</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-xs text-text-muted">Min Quality</p>
                  <p className="text-lg font-bold text-text-primary font-mono">{result.result.qc.min_quality}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-xs text-text-muted">Max Quality</p>
                  <p className="text-lg font-bold text-text-primary font-mono">{result.result.qc.max_quality}</p>
                </div>
              </div>
              {result.result.qc.overrepresented_sequences.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs text-text-muted mb-2">Overrepresented Sequences (top 5)</p>
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {result.result.qc.overrepresented_sequences.slice(0, 5).map((s, i) => (
                      <div key={i} className="text-xs font-mono text-text-secondary flex gap-2">
                        <span className="text-text-muted w-12 text-right">{s.percent.toFixed(1)}%</span>
                        <span className="truncate">{s.sequence}</span>
                        <span className="text-text-muted flex-shrink-0">x{s.count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {result.result?.alignment && (
            <div className="data-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                <Map className="w-4 h-4 text-accent-cyan" /> Alignment Results
              </h3>
              <div className="grid grid-cols-3 gap-4">
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-xs text-text-muted">Total Alignments</p>
                  <p className="text-lg font-bold text-text-primary font-mono">{result.result.alignment.total_alignments.toLocaleString()}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-xs text-text-muted">Mapped</p>
                  <p className="text-lg font-bold text-good font-mono">{result.result.alignment.mapped_reads.toLocaleString()}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-xs text-text-muted">Unmapped</p>
                  <p className="text-lg font-bold text-warn font-mono">{result.result.alignment.unmapped_reads.toLocaleString()}</p>
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

          {result.result?.variants && result.result.variants.length > 0 && (
            <div className="data-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                <Bug className="w-4 h-4 text-accent-cyan" /> Variants Detected ({result.result.variants.length})
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-text-muted uppercase border-b border-glass-border">
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

          {result.result?.report && (
            <div className="data-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                <FileText className="w-4 h-4 text-accent-cyan" /> Summary Report
              </h3>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-xs text-text-muted">Reference</p>
                  <p className="text-sm font-bold text-text-primary font-mono">{result.result.report.reference}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-xs text-text-muted">Total Variants</p>
                  <p className="text-lg font-bold text-text-primary font-mono">{result.result.report.variant_summary.total_variants}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-xs text-text-muted">SNVs</p>
                  <p className="text-lg font-bold text-text-primary font-mono">{result.result.report.variant_summary.snv_count}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-xs text-text-muted">Avg Depth</p>
                  <p className="text-lg font-bold text-text-primary font-mono">{result.result.report.variant_summary.avg_depth}</p>
                </div>
              </div>
            </div>
          )}

          {result.result?.variants && result.result.variants.length === 0 && (
          <div className="data-card p-5">
              <div className="flex items-center gap-2 text-text-muted">
                <CheckCircle className="w-4 h-4 text-good" />
                <p className="text-sm">No variants detected in the sample.</p>
              </div>
            </div>
          )}

          {result.status === 'complete' && (
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
                    <Dna className="w-3.5 h-3.5" />
                    Download consensus FASTA
                  </button>
                </div>
              )}
              <div className="flex items-center justify-between pt-2 border-t border-glass-border">
                <span className="text-xs text-text-muted">Bridge: BLAST Analysis</span>
                <button
                  onClick={() => {
                    if (result.result?.consensus_sequence) {
                      const seq = result.result.consensus_sequence;
                      sessionStorage.setItem('blast_sequence', seq);
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

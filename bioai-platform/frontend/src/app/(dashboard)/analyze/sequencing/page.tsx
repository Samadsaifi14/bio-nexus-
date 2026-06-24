'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { ArrowLeft, LoaderCircle, CheckCircle, XCircle, AlertTriangle, Dna, BarChart3, Map, Bug, FileText } from 'lucide-react';
import { fadeUp } from '@/lib/animations';
import { runSequencing, getSequencingStatus, listSequencingReferences } from '@/lib/api';
import type { SequencingResult, SequencingReference } from '@/lib/api';

const DEFAULT_REFERENCES = [
  { id: 'sars-cov-2', name: 'Sars Cov 2' },
  { id: 'lambda', name: 'Lambda' },
];

const EXAMPLE_FASTQ = [
  { label: 'SARS-CoV-2 (small)', value: 'https://raw.githubusercontent.com/jeffkaufman/small-fastq-files/main/sars-cov-2_sample.fastq' },
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
    setLoading(true);
    setError(null);
    setResult(null);
    setJobId(null);
    try {
      const { job_id } = await runSequencing(fastqUrl.trim(), reference);
      setJobId(job_id);
      setPolling(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to start pipeline');
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
    if (status === 'complete') return <CheckCircle className="w-5 h-5 text-green-400" />;
    if (status === 'failed') return <XCircle className="w-5 h-5 text-red-400" />;
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
      <button onClick={() => router.push('/analyze')} className="flex items-center gap-1 text-sm text-text-muted hover:text-text-primary mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Choose a different operation
      </button>

      <motion.div variants={fadeUp} initial="hidden" animate="show" className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary mb-1">Sequencing Pipeline</h1>
        <p className="text-sm text-text-secondary">Raw FASTQ → QC → alignment → variant calling → report. Supports viral/bacterial genomes (cpu-basic tier).</p>
      </motion.div>

      <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-5 mb-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-text-primary mb-1.5">FASTQ URL</label>
          <input
            type="text"
            value={fastqUrl}
            onChange={(e) => setFastqUrl(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && startPipeline()}
            placeholder="https://example.com/sample.fastq"
            className="w-full px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm font-mono bg-surface-1 text-text-primary"
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

        <button onClick={startPipeline} disabled={loading || !fastqUrl.trim() || polling}
          className="btn-primary w-full py-3 flex items-center justify-center gap-2 disabled:opacity-50">
          {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Dna className="w-4 h-4" />}
          {loading ? 'Starting...' : polling ? 'Running Pipeline...' : 'Run Pipeline'}
        </button>
      </motion.div>

      {error && (
        <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-4 mb-6 border border-red-400/20">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-400">{error}</p>
          </div>
        </motion.div>
      )}

      {result && (
        <motion.div variants={fadeUp} initial="hidden" animate="show" className="space-y-4">

          <div className="glass-card p-5">
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
                      s === 'done' ? 'bg-green-400/10 text-green-400' :
                      s === 'running' ? 'bg-accent-cyan/10 text-accent-cyan' :
                      s === 'failed' ? 'bg-red-400/10 text-red-400' :
                      'bg-surface-1 text-text-muted'
                    }`}>
                      {s === 'done' ? <CheckCircle className="w-4 h-4" /> :
                       s === 'running' ? <LoaderCircle className="w-4 h-4 animate-spin" /> :
                       <Icon className="w-4 h-4" />}
                    </div>
                    <div className="flex-1">
                      <p className={`text-sm font-medium ${
                        s === 'done' ? 'text-green-400' :
                        s === 'running' ? 'text-accent-cyan' :
                        s === 'failed' ? 'text-red-400' :
                        'text-text-muted'
                      }`}>{step.label}</p>
                    </div>
                    {i < STEPS.length - 1 && (
                      <div className={`w-px h-4 mx-2 ${
                        s === 'done' ? 'bg-green-400/30' : 'bg-glass-border'
                      }`} />
                    )}
                  </div>
                );
              })}
            </div>

            {result.status === 'failed' && result.error && (
              <div className="p-3 rounded-lg bg-red-400/5 border border-red-400/20 mt-4">
                <pre className="text-xs text-red-400 whitespace-pre-wrap font-mono">{result.error}</pre>
              </div>
            )}
          </div>

          {result.result?.qc && (
            <div className="glass-card p-5">
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
                    result.result.qc.mean_quality >= 30 ? 'text-green-400' :
                    result.result.qc.mean_quality >= 20 ? 'text-amber-400' : 'text-red-400'
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
            <div className="glass-card p-5">
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
                  <p className="text-lg font-bold text-green-400 font-mono">{result.result.alignment.mapped_reads.toLocaleString()}</p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-xs text-text-muted">Unmapped</p>
                  <p className="text-lg font-bold text-red-400 font-mono">{result.result.alignment.unmapped_reads.toLocaleString()}</p>
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
            <div className="glass-card p-5">
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
                        <td className="py-2 pr-4 font-mono text-green-400">{v.ref}</td>
                        <td className="py-2 pr-4 font-mono text-accent-cyan">{v.alt}</td>
                        <td className="py-2 pr-4 font-mono">{v.depth}</td>
                        <td className="py-2 pr-4 font-mono">{v.alt_count}</td>
                        <td className="py-2 font-mono text-amber-400">{(v.freq * 100).toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {result.result?.report && (
            <div className="glass-card p-5">
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
            <div className="glass-card p-5">
              <div className="flex items-center gap-2 text-text-muted">
                <CheckCircle className="w-4 h-4 text-green-400" />
                <p className="text-sm">No variants detected in the sample.</p>
              </div>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}

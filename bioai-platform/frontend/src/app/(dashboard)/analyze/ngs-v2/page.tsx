'use client';

import { useState } from 'react';
import type { ReactElement } from 'react';
import { motion } from 'framer-motion';
import {
  Dna,
  CheckCircle,
  Warning as WarningCircle,
  XCircle,
  CircleNotch as LoaderCircle,
  FlowArrow as GitBranch,
  ShieldCheck,
  Exam,
  Fingerprint,
  ListChecks,
  SealCheck,
  MapTrifold,
} from '@phosphor-icons/react';
import { fadeUp } from '@/lib/animations';
import { runNgs2Analyze } from '@/lib/api';
import type { Ngs2AnalyzeResult, Ngs2Stage, Ngs2Metric } from '@/lib/api';
import { BackButton, CriticalButton, FlatInput, PageHeader } from '@/components/ui';
import GenomeViewer from '@/components/GenomeViewer';

const ASSAY_OPTIONS = [
  { value: '', label: 'Auto-detect assay' },
  { value: 'WGS', label: 'Whole Genome Sequencing (WGS)' },
  { value: 'WES', label: 'Whole Exome Sequencing (WES)' },
  { value: 'RNA-seq', label: 'RNA-seq' },
  { value: 'Amplicon', label: 'Targeted Amplicon' },
];

const STATUS_PALETTE: Record<string, { text: string; chip: string; icon: ReactElement }> = {
  PASS: {
    text: 'text-good',
    chip: 'bg-good/10 text-good border-good/25',
    icon: <CheckCircle className="w-4 h-4" weight="fill" />,
  },
  WARN: {
    text: 'text-warn',
    chip: 'bg-warn/10 text-warn border-warn/25',
    icon: <WarningCircle className="w-4 h-4" weight="fill" />,
  },
  FAIL: {
    text: 'text-error',
    chip: 'bg-error/10 text-error border-error/25',
    icon: <XCircle className="w-4 h-4" weight="fill" />,
  },
};

export default function NgsV2Page() {
  const [filePaths, setFilePaths] = useState('');
  const [assay, setAssay] = useState('');
  const [reference, setReference] = useState('grch38');
  const [synthetic, setSynthetic] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Ngs2AnalyzeResult | null>(null);

  const run = async () => {
    const files = filePaths.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean);
    if (files.length === 0) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await runNgs2Analyze({
        file_paths: files,
        reference: reference || undefined,
        assay: assay || undefined,
        metadata: { platform: 'illumina' },
        synthetic_reference: synthetic,
      });
      setResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to run analysis');
    } finally {
      setLoading(false);
    }
  };

  const verdict = result?.pipeline.pipeline_status ?? null;
  const gate = result?.pipeline.stages[result.pipeline.stages.length - 1];

  const statusChip = (s?: string) => STATUS_PALETTE[s ?? ''] ?? {
    text: 'text-text-muted',
    chip: 'bg-surface-1 text-text-muted border-glass-border',
    icon: <ListChecks className="w-4 h-4" />,
  };

  const metricValue = (m: Ngs2Metric) =>
    typeof m.value === 'number' ? m.value : '—';

  const renderMetric = (m: Ngs2Metric) => {
    const pal = statusChip(m.status);
    return (
      <div key={m.name} className={`flex items-center gap-2 text-[11px] px-2.5 py-1 rounded-md border ${pal.chip}`}>
        <span className="font-mono">{metricValue(m)}</span>
        <span className="opacity-70">{m.name}</span>
      </div>
    );
  };

  return (
    <div className="max-w-4xl">
      <BackButton />
      <PageHeader
        title="Multi-Assay NGS Platform"
        subtitle="Assay router · QC contract engine · evidence chain · analysis-readiness gate"
      />

      {/* Input */}
      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-text-primary mb-1.5">FASTQ file paths (server-local)</label>
          <FlatInput
            type="text"
            value={filePaths}
            onChange={(e) => { setFilePaths(e.target.value); setResult(null); setError(null); }}
            onKeyDown={(e) => e.key === 'Enter' && run()}
            placeholder="/data/SAMPLE_001_R1.fastq.gz, /data/SAMPLE_001_R2.fastq.gz"
            className="w-full px-4 py-3 rounded-xl text-sm font-mono"
          />
          <p className="text-[11px] text-text-muted mt-1.5">
            The v2 engine runs in-process on the platform backend and reads local FASTQ files. Separate paths with commas.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">Assay</label>
            <select
              value={assay}
              onChange={(e) => setAssay(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm bg-surface-1 text-text-primary"
            >
              {ASSAY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">Reference build</label>
            <select
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm bg-surface-1 text-text-primary"
            >
              <option value="grch38">GRCh38</option>
              <option value="grch37">GRCh37</option>
            </select>
          </div>
        </div>

        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={synthetic}
            onChange={(e) => setSynthetic(e.target.checked)}
            className="accent-cyan-500 w-4 h-4"
          />
          <span className="text-sm text-text-primary">Run on a synthetic demonstration reference</span>
          <span className="text-[11px] text-text-muted">so all 21 stages (alignment → final gate) compute real metrics</span>
        </label>

        <CriticalButton onClick={run} disabled={loading || !filePaths.trim()} className="w-full py-3 flex items-center justify-center gap-2 disabled:opacity-50">
          {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Dna className="w-4 h-4" />}
          {loading ? 'Running 21-stage DAG...' : 'Run Full Analysis'}
        </CriticalButton>
      </motion.div>

      {error && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-4 mb-6 border border-error/20">
          <div className="flex items-center gap-2">
            <XCircle className="w-5 h-5 text-error flex-shrink-0" />
            <p className="text-sm text-error">{error}</p>
          </div>
        </motion.div>
      )}

      {result && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-4">
          {/* Readiness gate banner */}
          <div className={`rounded-xl border px-4 py-4 flex items-start gap-3 ${
            verdict === 'PASS' ? 'bg-good/10 border-good/25' :
            verdict === 'WARN' ? 'bg-warn/10 border-warn/25' :
            'bg-error/10 border-error/25'
          }`}>
            {verdict === 'PASS' ? <SealCheck className="w-6 h-6 text-good shrink-0 mt-0.5" />
              : verdict === 'WARN' ? <WarningCircle className="w-6 h-6 text-warn shrink-0 mt-0.5" />
              : <XCircle className="w-6 h-6 text-error shrink-0 mt-0.5" />}
            <div className="min-w-0">
              <p className="text-sm font-bold text-text-primary">
                {verdict === 'PASS' ? 'ANALYSIS READY'
                  : verdict === 'WARN' ? 'ANALYSIS READY — WITH WARNINGS'
                  : 'NOT ANALYSIS READY'}
              </p>
              <p className="text-xs text-text-muted mt-0.5">
                Final gate: {gate?.qc?.status ?? '—'} · stopped at{' '}
                <span className="font-mono">{result.pipeline.stopped_at ?? 'none'}</span>
              </p>
            </div>
          </div>

          {/* Detection summary */}
          <div className="data-card p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-accent-cyan" /> Assay Router — Detection
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              {[
                { label: 'Assay', value: result.detection.assay },
                { label: 'Sample Type', value: result.detection.sample_type },
                { label: 'Library', value: result.detection.library_type },
                { label: 'Confidence', value: `${(result.detection.confidence * 100).toFixed(0)}%` },
              ].map(({ label, value }) => (
                <div key={label} className="p-3 rounded-xl bg-surface-1">
                  <p className="text-[11px] text-text-muted">{label}</p>
                  <p className="text-sm font-bold text-text-primary font-mono">{value}</p>
                </div>
              ))}
            </div>
            <p className="text-xs text-text-muted mb-1">Evidence:</p>
            <div className="flex flex-wrap gap-1.5">
              {result.detection.evidence.map((ev, i) => (
                <span key={i} className="text-[11px] px-2 py-0.5 rounded bg-accent-cyan/10 text-accent-cyan font-mono">{ev}</span>
              ))}
            </div>
          </div>

          {/* IGV visualization (Stage 20) */}
          {result.visualization && (result.visualization.sam || result.visualization.vcf) && (
            <div className="data-card p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                  <MapTrifold className="w-4 h-4 text-accent-cyan" /> IGV — Alignment & Variant Tracks
                </h3>
                <span className="text-[11px] text-text-muted font-mono">
                  {result.visualization.n_mapped} mapped · {result.visualization.n_variants} variants
                </span>
              </div>
              <p className="text-[11px] text-text-muted mb-3">
                Tracks serialized from the real pipeline state (mapping decisions and variant calls) —
                recompute metrics, never fabricated clinical results.
              </p>
              <GenomeViewer
                samText={result.visualization.sam}
                vcfText={result.visualization.vcf}
                locus={result.visualization.locus ?? undefined}
              />
            </div>
          )}

          {/* Stage contracts / evidence chain */}
          <div className="data-card p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                <ListChecks className="w-4 h-4 text-accent-cyan" /> Stage Evidence Chain ({result.pipeline.stages.length})
              </h3>
              <span className="text-[11px] text-text-muted font-mono">pipeline: {result.pipeline.pipeline}</span>
            </div>

            <div className="space-y-2">
              {result.pipeline.stages.map((stage: Ngs2Stage, i: number) => {
                const pal = statusChip(stage.qc?.status);
                return (
                  <div key={stage.step}>
                    <div className="border border-glass-border rounded-xl p-3">
                      <div className="flex items-center gap-3">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${pal.chip}`}>
                          {pal.icon}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-text-primary">{stage.step}</span>
                            {stage.decision === 'STOP' && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-error/15 text-error font-semibold">BLOCKING</span>
                            )}
                          </div>
                          <p className="text-[11px] text-text-muted truncate font-mono">{stage.tool}</p>
                        </div>
                        <span className={`text-[11px] font-semibold uppercase ${pal.text}`}>{stage.qc?.status ?? '—'}</span>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1.5 pl-11">
                        {stage.qc?.metrics?.map((m) => renderMetric(m))}
                      </div>
                    </div>
                    {i < result.pipeline.stages.length - 1 && (
                      <div className={`w-px h-2 ml-5.5 ${stage.decision === 'STOP' ? 'bg-error/40' : 'bg-glass-border'}`} />
                    )}
                  </div>
                );
              })}
            </div>

            {result.pipeline.warnings.length > 0 && (
              <div className="mt-4 p-3 rounded-lg bg-warn/5 border border-warn/20">
                <p className="text-xs font-semibold text-warn mb-1 flex items-center gap-1">
                  <WarningCircle className="w-4 h-4" /> Warnings ({result.pipeline.warnings.length})
                </p>
                <ul className="text-[11px] text-text-muted space-y-0.5">
                  {result.pipeline.warnings.map((w, idx) => (
                    <li key={idx} className="font-mono">• {w}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="flex items-center gap-4 text-[11px] text-text-muted">
            <span className="flex items-center gap-1"><ShieldCheck className="w-3.5 h-3.5 text-good" /> PASS — continue</span>
            <span className="flex items-center gap-1"><Exam className="w-3.5 h-3.5 text-warn" /> WARN — continue with warning</span>
            <span className="flex items-center gap-1"><Fingerprint className="w-3.5 h-3.5 text-error" /> FAIL — STOP (blocking gates)</span>
          </div>
        </motion.div>
      )}
    </div>
  );
}

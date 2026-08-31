'use client';

import { useState } from 'react';
import type { ReactElement } from 'react';
import { motion } from 'framer-motion';
import {
  Atom,
  CheckCircle,
  Warning as WarningCircle,
  XCircle,
  CircleNotch as LoaderCircle,
  ListChecks,
  ShieldCheck,
  Exam,
  Fingerprint,
  Cpu,
  SealCheck,
} from '@phosphor-icons/react';
import { fadeUp } from '@/lib/animations';
import { runMd2Analyze } from '@/lib/api';
import type { Md2Stage, Md2Metric } from '@/lib/api';
import { BackButton, CriticalButton, FlatInput, PageHeader } from '@/components/ui';

const FORCEFIELD_OPTIONS = [
  { value: '', label: 'Default (AMBER14)' },
  { value: 'amber14', label: 'amber14' },
  { value: 'ff14sb', label: 'ff14SB' },
  { value: 'ff19sb', label: 'ff19SB' },
  { value: 'amberfb15', label: 'amberfb15' },
  { value: 'charmm36', label: 'CHARMM36' },
];

const SOLVENT_OPTIONS = [
  { value: '', label: 'Default (OBC2)' },
  { value: 'obc2', label: 'OBC2 · Implicit GB' },
  { value: 'gbn2', label: 'GBN2 · Implicit GB' },
  { value: 'obc1', label: 'OBC1 · Implicit GB' },
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

export default function MdV2Page() {
  const [pdbId, setPdbId] = useState('');
  const [forcefield, setForcefield] = useState('');
  const [solvent, setSolvent] = useState('');
  const [productionPs, setProductionPs] = useState(50);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Awaited<ReturnType<typeof runMd2Analyze>> | null>(null);

  const run = async () => {
    if (!pdbId.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await runMd2Analyze({
        pdb_id: pdbId.trim(),
        forcefield: forcefield || undefined,
        solvent: solvent || undefined,
        production_ps: productionPs,
      });
      setResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to run analysis');
    } finally {
      setLoading(false);
    }
  };

  const verdict = result?.pipeline.pipeline_status ?? null;

  const statusChip = (s?: string) => STATUS_PALETTE[s ?? ''] ?? {
    text: 'text-text-muted',
    chip: 'bg-surface-1 text-text-muted border-glass-border',
    icon: <ListChecks className="w-4 h-4" />,
  };

  const metricValue = (m: Md2Metric) =>
    typeof m.value === 'number' ? m.value : '—';

  const renderMetric = (m: Md2Metric) => {
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
        title="Staged Molecular Dynamics"
        subtitle="Structure QC → prep → force-field gate → build → EM → NVT → NPT → production → trajectory QC → convergence"
      />

      {/* Input */}
      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-text-primary mb-1.5">PDB ID · structure</label>
          <FlatInput
            type="text"
            value={pdbId}
            onChange={(e) => { setPdbId(e.target.value); setResult(null); setError(null); }}
            onKeyDown={(e) => e.key === 'Enter' && run()}
            placeholder="e.g. 1CRN"
            className="w-full px-4 py-3 rounded-xl text-sm font-mono"
          />
          <p className="text-[11px] text-text-muted mt-1.5">
            Fetched from RCSB and run through the 10-stage MD DAG on the backend. OpenMM is the
            primary engine; GROMACS availability is gated honestly.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">Force field</label>
            <select
              value={forcefield}
              onChange={(e) => setForcefield(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm bg-surface-1 text-text-primary"
            >
              {FORCEFIELD_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">Solvent</label>
            <select
              value={solvent}
              onChange={(e) => setSolvent(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm bg-surface-1 text-text-primary"
            >
              {SOLVENT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">Production (ps)</label>
            <FlatInput
              type="number"
              min={20}
              max={300}
              value={productionPs}
              onChange={(e) => setProductionPs(Number(e.target.value) || 0)}
              className="w-full px-4 py-3 rounded-xl text-sm font-mono"
            />
          </div>
        </div>
        <p className="text-[11px] text-text-muted -mt-2">
          Production is capped by a short wall-clock budget on the backend, so the synchronous run
          completes within the gateway timeout (large requests are clamped to a quick real trajectory).
        </p>

        <CriticalButton onClick={run} disabled={loading || !pdbId.trim()} className="w-full py-3 flex items-center justify-center gap-2 disabled:opacity-50">
          {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Atom className="w-4 h-4" />}
          {loading ? 'Running 10-stage MD DAG...' : 'Run Staged MD Pipeline'}
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
          {/* Readiness banner */}
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
                {verdict === 'PASS' ? 'TRAJECTORY ANALYSIS READY'
                  : verdict === 'WARN' ? 'TRAJECTORY ANALYSIS READY — WITH WARNINGS'
                  : 'NOT ANALYSIS READY'}
              </p>
              <p className="text-xs text-text-muted mt-0.5">
                Pipeline decision: <span className="font-mono">{result.pipeline.pipeline_decision}</span> ·
                stopped at <span className="font-mono">{result.pipeline.stopped_at ?? 'none'}</span>
              </p>
            </div>
          </div>

          <div className="data-card p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
              <Cpu className="w-4 h-4 text-accent-cyan" /> Requested Run
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { label: 'PDB ID', value: result.requested.pdb_id },
                { label: 'Source', value: result.requested.source },
                { label: 'Force field', value: result.requested.forcefield },
                { label: 'Solvent', value: result.requested.solvent },
              ].map(({ label, value }) => (
                <div key={label} className="p-3 rounded-xl bg-surface-1">
                  <p className="text-[11px] text-text-muted">{label}</p>
                  <p className="text-sm font-bold text-text-primary font-mono">{value}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Stage evidence chain */}
          <div className="data-card p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                <ListChecks className="w-4 h-4 text-accent-cyan" /> Stage Evidence Chain ({result.pipeline.stages.length})
              </h3>
              <span className="text-[11px] text-text-muted font-mono">pipeline: {result.pipeline.pipeline}</span>
            </div>

            <div className="space-y-2">
              {result.pipeline.stages.map((stage: Md2Stage, i: number) => {
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

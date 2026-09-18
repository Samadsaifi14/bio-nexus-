'use client';

import { useEffect, useState } from 'react';
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
  ChartLine,
  DownloadSimple,
  Flask,
} from '@phosphor-icons/react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { fadeUp } from '@/lib/animations';
import { runMd2Analyze } from '@/lib/api';
import type { Md2Stage, Md2Metric } from '@/lib/api';
import { BackButton, CriticalButton, FlatInput, PageHeader } from '@/components/ui';
import { consumeParam, getAnalysisHandoff } from '@/lib/cross-link';

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

type MdPlot = {
  id: string;
  title: string;
  kind: 'line';
  x_label: string;
  y_label: string;
  x_key: string;
  y_key: string;
  source_stage: string;
  data: Array<Record<string, string | number | null>>;
};

type ScientificMdEnvelope = {
  status?: 'VALID' | 'DEGRADED' | 'NOT_EVALUATED' | 'FAILED';
  method?: string;
  engine?: string;
  engine_version?: string;
  input_sha256?: string;
  output_sha256?: string;
  plots?: MdPlot[];
  validation?: {
    scope?: string;
    stage_errors?: Array<{ stage: string; error: string }>;
    real_trajectory_emitted?: boolean;
    trajectory_qc_emitted?: boolean;
    convergence_assessment_emitted?: boolean;
  };
};

function stageData(stages: Md2Stage[], step: string): Record<string, unknown> {
  return stages.find((stage) => stage.step === step)?.data ?? {};
}

function scalarEntries(data: Record<string, unknown>): Array<[string, string | number | boolean]> {
  return Object.entries(data)
    .filter(([, value]) => typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean')
    .filter(([key]) => key !== 'error' && key !== 'note' && key !== 'reason') as Array<[string, string | number | boolean]>;
}

function displayValue(value: unknown, suffix = ''): string {
  if (value === null || value === undefined || value === '') return 'Not emitted';
  if (typeof value === 'number') return `${value}${suffix}`;
  if (typeof value === 'string' || typeof value === 'boolean') return `${String(value)}${suffix}`;
  return 'Not emitted';
}

function ResultPlot({ plot }: { plot: MdPlot }) {
  if (!Array.isArray(plot.data) || plot.data.length === 0) return null;
  return (
    <div className="data-card p-4 min-w-0">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <p className="text-sm font-semibold text-text-primary">{plot.title}</p>
          <p className="text-[10px] text-text-muted font-mono">source: {plot.source_stage}</p>
        </div>
        <span className="text-[10px] text-text-muted">{plot.data.length} retained points</span>
      </div>
      <div className="h-[220px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={plot.data} margin={{ top: 8, right: 12, bottom: 22, left: 6 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.22} />
            <XAxis dataKey={plot.x_key} tick={{ fontSize: 10 }} label={{ value: plot.x_label, position: 'insideBottom', offset: -14, fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} width={58} label={{ value: plot.y_label, angle: -90, position: 'insideLeft', fontSize: 10 }} />
            <Tooltip />
            <Line type="monotone" dataKey={plot.y_key} stroke="currentColor" className="text-accent-cyan" dot={false} isAnimationActive={false} connectNulls={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function MdV2Page() {
  const [pdbId, setPdbId] = useState('');
  const [forcefield, setForcefield] = useState('');
  const [solvent, setSolvent] = useState('');
  const [productionPs, setProductionPs] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Awaited<ReturnType<typeof runMd2Analyze>> | null>(null);

  useEffect(() => {
    const handoff = getAnalysisHandoff();
    const carried = consumeParam('md_pdb_id') || handoff?.pdbId || null;
    if (carried) setPdbId(carried);
  }, []);

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
      const message = err instanceof Error ? err.message : 'Failed to run analysis';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const verdict = result?.pipeline.pipeline_status ?? null;
  const scientific = (result ?? {}) as unknown as ScientificMdEnvelope;
  const plots = scientific.plots ?? [];
  const stages = result?.pipeline.stages ?? [];
  const production = stageData(stages, 'md_production');
  const trajectory = stageData(stages, 'md_traj');
  const convergence = stageData(stages, 'md_convergence');
  const stageErrors = scientific.validation?.stage_errors ?? stages
    .filter((stage) => typeof stage.data?.error === 'string')
    .map((stage) => ({ stage: stage.step, error: String(stage.data.error) }));

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
      <div key={m.name} className={`flex items-center gap-2 text-[11px] px-2.5 py-1 rounded-md border ${pal.chip}`} title={m.detail ?? m.expected ?? undefined}>
        <span className="font-mono">{metricValue(m)}</span>
        <span className="opacity-70">{m.name}</span>
      </div>
    );
  };

  const downloadResult = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${result.requested.pdb_id || 'md'}-staged-md-result.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-6xl">
      <BackButton />
      <PageHeader
        title="Staged Molecular Dynamics"
        subtitle="Short implicit-solvent OpenMM MD · structure QC → preparation → minimization → NVT → production → trajectory analysis → convergence"
      />

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
            The backend is authoritative for all scientific values. This page renders retained OpenMM stage data and does not invent missing points.
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
              {FORCEFIELD_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">Solvent</label>
            <select
              value={solvent}
              onChange={(e) => setSolvent(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm bg-surface-1 text-text-primary"
            >
              {SOLVENT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">Production (ps)</label>
            <FlatInput
              type="number"
              min={1}
              max={20}
              value={productionPs}
              onChange={(e) => setProductionPs(Number(e.target.value) || 0)}
              className="w-full px-4 py-3 rounded-xl text-sm font-mono"
            />
          </div>
        </div>
        <p className="text-[11px] text-text-muted -mt-2">
          Hosted staged MD is intentionally capped at 20 ps and uses implicit solvent. It is a short computational workflow, not an explicit-solvent production MD protocol.
        </p>

        <CriticalButton onClick={run} disabled={loading || !pdbId.trim()} className="w-full py-3 flex items-center justify-center gap-2 disabled:opacity-50">
          {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Atom className="w-4 h-4" />}
          {loading ? 'Running OpenMM stages...' : 'Run Staged MD Pipeline'}
        </CriticalButton>
      </motion.div>

      {error && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-4 mb-6 border border-error/20">
          <div className="flex items-start gap-2">
            <XCircle className="w-5 h-5 text-error flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-error">Staged MD request failed</p>
              <p className="text-xs text-error/90 mt-1 break-words">{error}</p>
            </div>
          </div>
        </motion.div>
      )}

      {result && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-4">
          <div className={`rounded-xl border px-4 py-4 flex items-start gap-3 ${
            verdict === 'PASS' ? 'bg-good/10 border-good/25' :
            verdict === 'WARN' ? 'bg-warn/10 border-warn/25' :
            'bg-error/10 border-error/25'
          }`}>
            {verdict === 'PASS' ? <SealCheck className="w-6 h-6 text-good shrink-0 mt-0.5" />
              : verdict === 'WARN' ? <WarningCircle className="w-6 h-6 text-warn shrink-0 mt-0.5" />
              : <XCircle className="w-6 h-6 text-error shrink-0 mt-0.5" />}
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold text-text-primary">
                {verdict === 'PASS' ? 'TRAJECTORY RESULT EMITTED'
                  : verdict === 'WARN' ? 'TRAJECTORY RESULT EMITTED — WITH WARNINGS'
                  : 'SCIENTIFIC PROCESSING STOPPED'}
              </p>
              <p className="text-xs text-text-muted mt-0.5">
                Scientific status: <span className="font-mono">{scientific.status ?? verdict}</span> · method: <span className="font-mono">{scientific.method ?? 'Short implicit-solvent OpenMM MD'}</span>
              </p>
              <p className="text-xs text-text-muted mt-0.5">
                Pipeline decision: <span className="font-mono">{result.pipeline.pipeline_decision}</span> · stopped at <span className="font-mono">{result.pipeline.stopped_at ?? 'none'}</span>
              </p>
            </div>
            <button onClick={downloadResult} className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-glass-border text-xs text-text-secondary hover:text-text-primary">
              <DownloadSimple className="w-3.5 h-3.5" /> JSON
            </button>
          </div>

          {stageErrors.length > 0 && (
            <div className="data-card p-4 border border-error/25">
              <p className="text-sm font-semibold text-error flex items-center gap-2 mb-2"><XCircle className="w-4 h-4" /> Backend stage failure</p>
              <div className="space-y-2">
                {stageErrors.map((item) => (
                  <div key={`${item.stage}-${item.error}`} className="rounded-lg bg-error/5 border border-error/15 p-3">
                    <p className="text-xs font-mono text-error">{item.stage}</p>
                    <p className="text-xs text-text-secondary mt-1 break-words">{item.error}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="data-card p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2"><Cpu className="w-4 h-4 text-accent-cyan" /> Run provenance</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { label: 'PDB ID', value: result.requested.pdb_id },
                { label: 'Force field', value: result.requested.forcefield },
                { label: 'Solvent', value: result.requested.solvent },
                { label: 'OpenMM', value: scientific.engine_version ?? 'version unavailable' },
              ].map(({ label, value }) => (
                <div key={label} className="p-3 rounded-xl bg-surface-1">
                  <p className="text-[11px] text-text-muted">{label}</p>
                  <p className="text-sm font-bold text-text-primary font-mono break-words">{value}</p>
                </div>
              ))}
            </div>
            {scientific.input_sha256 && scientific.output_sha256 && (
              <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2 text-[10px] text-text-muted font-mono">
                <p className="truncate" title={scientific.input_sha256}>input SHA-256: {scientific.input_sha256}</p>
                <p className="truncate" title={scientific.output_sha256}>output SHA-256: {scientific.output_sha256}</p>
              </div>
            )}
          </div>

          {(Object.keys(production).length > 0 || Object.keys(trajectory).length > 0 || Object.keys(convergence).length > 0) && (
            <div className="data-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2"><Flask className="w-4 h-4 text-accent-cyan" /> Scientific results</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: 'Executed production', value: displayValue(production.production_ps, ' ps') },
                  { label: 'Trajectory frames', value: displayValue(production.n_frames) },
                  { label: 'Final energy', value: displayValue(production.final_energy_kj_mol, ' kJ/mol') },
                  { label: 'Average RMSD', value: displayValue(trajectory.rmsd_avg_angstrom, ' Å') },
                  { label: 'Final RMSD', value: displayValue(trajectory.rmsd_final_angstrom, ' Å') },
                  { label: 'Average Rg', value: displayValue(trajectory.rg_avg_angstrom, ' Å') },
                  { label: 'Average SASA', value: displayValue(trajectory.sasa_avg_angstrom2, ' Å²') },
                  { label: 'Convergence', value: displayValue(convergence.readiness) },
                ].map(({ label, value }) => (
                  <div key={label} className="p-3 rounded-xl bg-surface-1">
                    <p className="text-[11px] text-text-muted">{label}</p>
                    <p className="text-sm font-bold text-text-primary font-mono break-words">{value}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {plots.length > 0 ? (
            <div>
              <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2"><ChartLine className="w-4 h-4 text-accent-cyan" /> Retained trajectory plots</h3>
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {plots.map((plot) => <ResultPlot key={plot.id} plot={plot} />)}
              </div>
              <p className="text-[10px] text-text-muted mt-2">Plots render exact arrays emitted by the scientific backend. Missing data is not replaced with zeroes.</p>
            </div>
          ) : verdict !== 'FAIL' ? (
            <div className="data-card p-4 border border-warn/20">
              <p className="text-sm font-semibold text-warn">No plottable trajectory arrays were emitted</p>
              <p className="text-xs text-text-muted mt-1">The UI will not draw zero-valued placeholder graphs. Inspect the stage evidence below for the first missing or warning-producing stage.</p>
            </div>
          ) : null}

          <div className="data-card p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2"><ListChecks className="w-4 h-4 text-accent-cyan" /> Stage Evidence Chain ({stages.length})</h3>
              <span className="text-[11px] text-text-muted font-mono">pipeline: {result.pipeline.pipeline}</span>
            </div>

            <div className="space-y-2">
              {stages.map((stage: Md2Stage, i: number) => {
                const pal = statusChip(stage.qc?.status);
                const backendError = typeof stage.data?.error === 'string' ? stage.data.error : null;
                const scalars = scalarEntries(stage.data ?? {});
                return (
                  <div key={stage.step}>
                    <div className={`border rounded-xl p-3 ${backendError ? 'border-error/30' : 'border-glass-border'}`}>
                      <div className="flex items-center gap-3">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${pal.chip}`}>{pal.icon}</div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-text-primary">{stage.step}</span>
                            {stage.decision === 'STOP' && <span className="text-[10px] px-1.5 py-0.5 rounded bg-error/15 text-error font-semibold">BLOCKING</span>}
                          </div>
                          <p className="text-[11px] text-text-muted truncate font-mono">{stage.tool}{stage.version ? ` · ${stage.version}` : ''}</p>
                        </div>
                        <span className={`text-[11px] font-semibold uppercase ${pal.text}`}>{stage.qc?.status ?? '—'}</span>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1.5 pl-11">{stage.qc?.metrics?.map((m) => renderMetric(m))}</div>
                      {backendError && <p className="mt-2 ml-11 text-xs text-error break-words">{backendError}</p>}
                      {scalars.length > 0 && (
                        <div className="mt-3 ml-11 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-1">
                          {scalars.slice(0, 12).map(([key, value]) => (
                            <p key={key} className="text-[10px] text-text-muted"><span className="font-mono text-text-secondary">{key}</span>: {String(value)}</p>
                          ))}
                        </div>
                      )}
                    </div>
                    {i < stages.length - 1 && <div className={`w-px h-2 ml-5.5 ${stage.decision === 'STOP' ? 'bg-error/40' : 'bg-glass-border'}`} />}
                  </div>
                );
              })}
            </div>

            {result.pipeline.warnings.length > 0 && (
              <div className="mt-4 p-3 rounded-lg bg-warn/5 border border-warn/20">
                <p className="text-xs font-semibold text-warn mb-1 flex items-center gap-1"><WarningCircle className="w-4 h-4" /> Warnings ({result.pipeline.warnings.length})</p>
                <ul className="text-[11px] text-text-muted space-y-0.5">
                  {result.pipeline.warnings.map((w, idx) => <li key={idx} className="font-mono">• {w}</li>)}
                </ul>
              </div>
            )}
          </div>

          <div className="data-card p-4 text-xs text-text-muted">
            <p className="font-semibold text-text-primary mb-1">Method boundary</p>
            <p>{scientific.validation?.scope ?? 'Short implicit-solvent OpenMM MD. Completion and grounding do not constitute independent experimental or biological validation.'}</p>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-[11px] text-text-muted">
            <span className="flex items-center gap-1"><ShieldCheck className="w-3.5 h-3.5 text-good" /> PASS — continue</span>
            <span className="flex items-center gap-1"><Exam className="w-3.5 h-3.5 text-warn" /> WARN — continue with warning</span>
            <span className="flex items-center gap-1"><Fingerprint className="w-3.5 h-3.5 text-error" /> FAIL — STOP</span>
          </div>
        </motion.div>
      )}
    </div>
  );
}

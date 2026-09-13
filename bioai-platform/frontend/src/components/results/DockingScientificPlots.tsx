'use client';

import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { DownloadSimple as Download } from '@phosphor-icons/react';
import { downloadTsv } from '@/lib/export-utils';

type Pose = { affinity: number | null; rmsd_lb?: number | null; rmsd_ub?: number | null; mode?: number | null };
const tooltipStyle = { background: 'var(--chart-tooltip-bg)', border: '1px solid var(--chart-tooltip-border)', borderRadius: 8, fontSize: 12 };

export function DockingScientificPlots({ poses }: { poses: Pose[] | undefined | null }) {
  const rows = (poses ?? []).map((p, i) => ({
    pose: p.mode ?? i + 1,
    affinity: typeof p.affinity === 'number' && Number.isFinite(p.affinity) ? p.affinity : null,
    rmsdLb: typeof p.rmsd_lb === 'number' && Number.isFinite(p.rmsd_lb) ? p.rmsd_lb : null,
    rmsdUb: typeof p.rmsd_ub === 'number' && Number.isFinite(p.rmsd_ub) ? p.rmsd_ub : null,
  }));
  if (!rows.length) return null;
  const affinityRows = rows.filter(r => r.affinity !== null);
  const rmsdRows = rows.filter(r => r.rmsdLb !== null || r.rmsdUb !== null);

  return (
    <div className="data-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Docking scientific plots</h3>
          <p className="mt-1 text-xs text-text-muted">Affinity and Vina RMSD lower/upper bounds are plotted directly from scored poses. These bounds are pose-cluster diagnostics; they are not crystallographic redocking RMSD unless a separate truth-pose benchmark is supplied.</p>
        </div>
        <button onClick={() => downloadTsv(['pose','affinity_kcal_mol','rmsd_lb_angstrom','rmsd_ub_angstrom'], rows.map(r => [String(r.pose),String(r.affinity ?? ''),String(r.rmsdLb ?? ''),String(r.rmsdUb ?? '')]), 'docking-pose-plot-source.tsv')} className="btn-ghost flex items-center gap-1 px-2 py-1 text-xs"><Download className="h-3.5 w-3.5" /> Source TSV</button>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {affinityRows.length > 0 && <div className="rounded-xl border border-glass-border bg-surface-0 p-3"><h4 className="text-xs font-semibold text-text-primary">Binding score by pose</h4><p className="mt-1 text-[11px] text-text-muted">More negative Vina scores indicate more favorable values within the Vina scoring function; they are not measured binding free energies.</p><div className="mt-2 h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={affinityRows}><CartesianGrid strokeDasharray="3 3" opacity={0.25} /><XAxis dataKey="pose" label={{ value: 'Pose', position: 'insideBottom', offset: -5 }} /><YAxis label={{ value: 'Affinity (kcal/mol)', angle: -90, position: 'insideLeft' }} /><Tooltip contentStyle={tooltipStyle} /><Bar dataKey="affinity" fill="#0891b2" /></BarChart></ResponsiveContainer></div></div>}
        {rmsdRows.length > 0 && <div className="rounded-xl border border-glass-border bg-surface-0 p-3"><h4 className="text-xs font-semibold text-text-primary">Vina RMSD bounds by pose</h4><p className="mt-1 text-[11px] text-text-muted">Lower and upper RMSD bounds are those emitted by Vina relative to its first ranked mode.</p><div className="mt-2 h-64"><ResponsiveContainer width="100%" height="100%"><LineChart data={rmsdRows}><CartesianGrid strokeDasharray="3 3" opacity={0.25} /><XAxis dataKey="pose" /><YAxis label={{ value: 'RMSD (Å)', angle: -90, position: 'insideLeft' }} /><Tooltip contentStyle={tooltipStyle} /><Legend /><Line type="monotone" dataKey="rmsdLb" name="RMSD lower bound" stroke="#0891b2" /><Line type="monotone" dataKey="rmsdUb" name="RMSD upper bound" stroke="#64748b" /></LineChart></ResponsiveContainer></div></div>}
      </div>
    </div>
  );
}

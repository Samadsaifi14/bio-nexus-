'use client';

import { useMemo, useState } from 'react';
import { ChartLine, Table, Database, DownloadSimple, CaretDown, CaretRight, SlidersHorizontal } from '@phosphor-icons/react';
import { downloadJson } from '@/lib/export-utils';

type ScientificDataViewsProps = { toolName: string; result: Record<string, unknown> };
type ScalarRow = { path: string; label: string; value: string };
type SeriesBlock = { path: string; rows: Record<string, unknown>[] };

const X_KEYS = ['model', 'time_ps', 'time_ns', 'time', 'step', 'frame', 'residue', 'position', 'cycle', 'iteration', 'index', 'rank', 'mode'];
const Y_PRIORITY = ['affinity', 'binding_affinity', 'rmsd_lb', 'rmsd_ub', 'rmsd', 'energy', 'score', 'hbonds', 'hydrophobic', 'pi_stacking', 'salt_bridges'];
const OMIT_KEYS = new Set([
  'pdb', 'pdb_text', 'cif', 'mmcif', 'ligand_pdb', 'trajectory', 'raw_output', 'raw', 'log', 'vina_log',
  'query_alignment', 'hit_alignment', 'midline', 'sequence', 'query_sequence', 'context_json', 'request', 'response',
  'storage_url', 'file_urls', 'download_url', 'url', 'error_message', 'stack', 'traceback',
]);
const LOW_VALUE_KEYS = new Set(['job_id', 'experiment_id', 'created_at', 'updated_at', 'completed_at', 'captured_at', 'from_cache', 'status', 'source_url']);
const BOOKKEEPING_Y_KEYS = new Set(['atoms', 'hydrogens', 'atom_count', 'total_atoms', 'heavy_atoms', 'model', 'mode', 'index', 'rank', 'id', 'num_poses', 'count']);

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return '—';
    const abs = Math.abs(value);
    if ((abs > 0 && abs < 1e-4) || abs >= 1e6) return value.toExponential(3);
    return Number.isInteger(value) ? value.toLocaleString() : Number(value.toPrecision(6)).toString();
  }
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'string') return value.length > 220 ? `${value.slice(0, 217)}…` : value;
  return '';
}

function humanize(key: string): string {
  const unit = key.endsWith('_angstrom2') ? ' (Å²)'
    : key.endsWith('_angstrom') || key.includes('rmsd') || key.includes('rmsf') ? ' (Å)'
    : key.endsWith('_kj_mol') || key === 'energy' ? ' (kJ/mol)'
    : key === 'affinity' || key === 'binding_affinity' ? ' (kcal/mol)'
    : key.endsWith('_k') || key.includes('temperature') ? ' (K)'
    : key.endsWith('_percent') || key.endsWith('_pct') ? ' (%)'
    : '';
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) + unit;
}

function collectScalars(value: unknown, prefix = '', depth = 0, out: ScalarRow[] = []): ScalarRow[] {
  if (depth > 3 || out.length >= 80 || value == null) return out;
  if (typeof value === 'object' && !Array.isArray(value)) {
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
      if (OMIT_KEYS.has(key) || LOW_VALUE_KEYS.has(key)) continue;
      const path = prefix ? `${prefix}.${key}` : key;
      if (child == null) continue;
      if (['number', 'boolean'].includes(typeof child)) out.push({ path, label: humanize(key), value: formatValue(child) });
      else if (typeof child === 'string' && child.length <= 220) out.push({ path, label: humanize(key), value: formatValue(child) });
      else if (typeof child === 'object' && !Array.isArray(child)) collectScalars(child, path, depth + 1, out);
    }
  }
  return out;
}

function collectSeries(value: unknown, prefix = '', depth = 0, out: SeriesBlock[] = []): SeriesBlock[] {
  if (depth > 4 || value == null || out.length >= 16) return out;
  if (Array.isArray(value)) {
    if (value.length && value.every(row => row && typeof row === 'object' && !Array.isArray(row))) {
      const rows = value as Record<string, unknown>[];
      const columns = Array.from(new Set(rows.slice(0, 40).flatMap(row => Object.keys(row))));
      const numericCount = columns.filter(key => rows.some(row => typeof row[key] === 'number')).length;
      if (columns.some(key => X_KEYS.includes(key)) || numericCount >= 2) out.push({ path: prefix || 'rows', rows });
    }
    return out;
  }
  if (typeof value === 'object') {
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
      if (!OMIT_KEYS.has(key)) collectSeries(child, prefix ? `${prefix}.${key}` : key, depth + 1, out);
    }
  }
  return out;
}

function finiteValues(rows: Record<string, unknown>[], key: string): number[] {
  return rows.map(row => row[key]).filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
}

function varies(rows: Record<string, unknown>[], key: string): boolean {
  const values = finiteValues(rows, key);
  return values.length >= 2 && Math.max(...values) - Math.min(...values) > 1e-12;
}

function chooseYKey(block: SeriesBlock, numericKeys: string[], xKey: string): string | null {
  const path = block.path.toLowerCase();
  const candidates = numericKeys.filter(key => key !== xKey);

  // Docking pose plots must represent docking score / pose displacement, not
  // bookkeeping quantities such as atom counts.
  if (path.endsWith('poses') || path.includes('.poses')) {
    return ['affinity', 'rmsd_lb', 'rmsd_ub'].find(key => candidates.includes(key) && varies(block.rows, key)) ?? null;
  }

  // Interaction counts are valid even when zero, but a constant/all-zero line
  // is not an informative graph. Prefer whichever computed contact class has
  // real variation; exact zero counts remain visible in the table.
  if (path.includes('pose_interactions')) {
    return ['hbonds', 'hydrophobic', 'pi_stacking', 'salt_bridges'].find(key => candidates.includes(key) && varies(block.rows, key)) ?? null;
  }

  const ordered = [
    ...Y_PRIORITY.filter(key => candidates.includes(key)),
    ...candidates.filter(key => !Y_PRIORITY.includes(key) && !BOOKKEEPING_Y_KEYS.has(key)),
  ];
  return ordered.find(key => varies(block.rows, key)) ?? null;
}

function NumericSeriesChart({ block }: { block: SeriesBlock }) {
  const rows = block.rows;
  if (rows.length < 2) return null;

  const keys = Array.from(new Set(rows.slice(0, 100).flatMap(row => Object.keys(row))));
  const numericKeys = keys.filter(key => {
    const values = rows.slice(0, 100).map(row => row[key]).filter(value => value !== null && value !== undefined);
    return values.length >= 2 && values.every(value => typeof value === 'number' && Number.isFinite(value));
  });
  if (numericKeys.length < 2) return null;

  const xKey = X_KEYS.find(key => numericKeys.includes(key)) ?? numericKeys[0];
  const yKey = chooseYKey(block, numericKeys, xKey);
  if (!yKey) return null;

  const points = rows.map((row, index) => {
    const x = typeof row[xKey] === 'number' ? row[xKey] as number : index;
    const y = row[yKey];
    return typeof y === 'number' && Number.isFinite(y) ? { x, y } : null;
  }).filter((point): point is { x: number; y: number } => !!point);
  if (points.length < 2) return null;

  const width = 720, height = 240, left = 66, right = 18, top = 18, bottom = 48;
  const xMin = Math.min(...points.map(p => p.x));
  const xMax = Math.max(...points.map(p => p.x));
  const yMin = Math.min(...points.map(p => p.y));
  const yMax = Math.max(...points.map(p => p.y));
  if (xMax - xMin <= 1e-12 || yMax - yMin <= 1e-12) return null;

  const xPad = Math.max((xMax - xMin) * 0.02, 0.02);
  const yPad = Math.max((yMax - yMin) * 0.08, 1e-6);
  const xa = xMin - xPad, xb = xMax + xPad, ya = yMin - yPad, yb = yMax + yPad;
  const sx = (x: number) => left + ((x - xa) / (xb - xa)) * (width - left - right);
  const sy = (y: number) => top + (height - top - bottom) - ((y - ya) / (yb - ya)) * (height - top - bottom);
  const pathData = points.map((p, i) => `${i ? 'L' : 'M'} ${sx(p.x).toFixed(2)} ${sy(p.y).toFixed(2)}`).join(' ');
  const ticks = [0, .25, .5, .75, 1];

  return <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
    <div className="mb-3 flex items-center gap-2">
      <ChartLine className="h-4 w-4 text-accent-cyan"/>
      <div>
        <p className="text-sm font-semibold text-text-primary">{humanize(yKey)} vs {humanize(xKey)}</p>
        <p className="text-[11px] text-text-muted">{block.path} · {points.length.toLocaleString()} computed points</p>
      </div>
    </div>
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label={`${humanize(yKey)} versus ${humanize(xKey)}`}>
      {ticks.map(t => {
        const y = top + t * (height - top - bottom);
        const value = yb - t * (yb - ya);
        return <g key={`y-${t}`}>
          <line x1={left} x2={width - right} y1={y} y2={y} stroke="currentColor" className="text-white/5"/>
          <text x={left - 8} y={y + 3} textAnchor="end" fontSize="9" fill="currentColor" className="text-text-muted">{formatValue(value)}</text>
        </g>;
      })}
      {ticks.map(t => {
        const x = left + t * (width - left - right);
        const value = xa + t * (xb - xa);
        return <text key={`x-${t}`} x={x} y={height - 22} textAnchor="middle" fontSize="9" fill="currentColor" className="text-text-muted">{formatValue(value)}</text>;
      })}
      <path d={pathData} fill="none" stroke="currentColor" strokeWidth="2" className="text-accent-cyan" vectorEffect="non-scaling-stroke"/>
      {points.map((p, i) => <circle key={i} cx={sx(p.x)} cy={sy(p.y)} r="2.5" fill="currentColor" className="text-accent-cyan"/>)}
      <text x={(left + width - right) / 2} y={height - 4} textAnchor="middle" fontSize="10" fill="currentColor" className="text-text-muted">{humanize(xKey)}</text>
      <text x="12" y={height / 2} textAnchor="middle" fontSize="10" fill="currentColor" className="text-text-muted" transform={`rotate(-90 12 ${height / 2})`}>{humanize(yKey)}</text>
    </svg>
    <p className="mt-1 text-[10px] text-text-muted">Direct backend values only. Constant/all-zero series are preserved in tables instead of rendered as misleading flat plots.</p>
  </div>;
}

function DataTable({ block }: { block: SeriesBlock }) {
  const [open, setOpen] = useState(false);
  const columns = Array.from(new Set(block.rows.slice(0, 80).flatMap(row => Object.keys(row))))
    .filter(column => !OMIT_KEYS.has(column))
    .slice(0, 12);
  if (!columns.length) return null;
  const previewRows = block.rows.slice(0, open ? 100 : 8);
  return <div className="overflow-hidden rounded-xl border border-glass-border bg-surface-1">
    <button type="button" onClick={() => setOpen(v => !v)} className="flex w-full items-center gap-2 px-4 py-3 text-left hover:bg-white/[0.02]">
      {open ? <CaretDown className="h-4 w-4 text-text-muted"/> : <CaretRight className="h-4 w-4 text-text-muted"/>}
      <Table className="h-4 w-4 text-accent-purple"/>
      <span className="text-sm font-semibold text-text-primary">{humanize(block.path.split('.').pop() || block.path)}</span>
      <span className="ml-auto text-[10px] text-text-muted">{block.rows.length.toLocaleString()} rows</span>
    </button>
    {open && <div className="overflow-x-auto border-t border-glass-border">
      <table className="min-w-full text-xs">
        <thead><tr className="bg-white/[0.02] text-text-muted">{columns.map(column => <th key={column} className="whitespace-nowrap px-3 py-2 text-left font-medium">{humanize(column)}</th>)}</tr></thead>
        <tbody className="divide-y divide-glass-border">{previewRows.map((row, i) => <tr key={i}>{columns.map(column => <td key={column} className="max-w-[320px] whitespace-pre-wrap break-words px-3 py-2 align-top font-mono text-text-secondary">{formatValue(row[column]) || '—'}</td>)}</tr>)}</tbody>
      </table>
      {block.rows.length > previewRows.length && <p className="border-t border-glass-border px-4 py-2 text-[10px] text-text-muted">Showing the first {previewRows.length} rows. Download the scientific JSON for the complete machine-readable result.</p>}
    </div>}
  </div>;
}

export function ScientificDataViews({ toolName, result }: ScientificDataViewsProps) {
  const scalars = useMemo(() => collectScalars(result), [result]);
  const series = useMemo(() => collectSeries(result), [result]);
  const [showMoreMetrics, setShowMoreMetrics] = useState(false);
  const visibleMetrics = showMoreMetrics ? scalars.slice(0, 48) : scalars.slice(0, 12);
  const chartBlocks = series.slice(0, 6);
  const tableBlocks = series.slice(0, 8);

  return <section className="space-y-4 rounded-2xl border border-glass-border bg-surface-0 p-5" aria-label="Scientific result data views">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-2"><Database className="h-5 w-5 text-accent-cyan"/><div><h3 className="font-semibold text-text-primary">Scientific result details</h3><p className="mt-0.5 text-[10px] text-text-muted">Curated computed results, plots and tables derived only from the returned scientific result.</p></div></div>
      <button type="button" onClick={() => downloadJson(result, `${toolName || 'analysis'}_scientific_result.json`)} className="flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs text-text-secondary hover:text-accent-cyan"><DownloadSimple className="h-3.5 w-3.5"/>Download full data</button>
    </div>

    {visibleMetrics.length > 0 && <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
      <div className="mb-3 flex items-center gap-2"><SlidersHorizontal className="h-4 w-4 text-accent-cyan"/><span className="text-sm font-semibold text-text-primary">Key measurements</span></div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{visibleMetrics.map(row => <div key={row.path} className="rounded-lg border border-glass-border/70 bg-surface-0 px-3 py-2"><p className="text-[10px] text-text-muted">{row.label}</p><p className="mt-1 break-words font-mono text-sm text-text-primary">{row.value}</p></div>)}</div>
      {scalars.length > 12 && <button type="button" onClick={() => setShowMoreMetrics(v => !v)} className="mt-3 text-xs text-accent-cyan hover:underline">{showMoreMetrics ? 'Show fewer measurements' : `Show more measurements (${Math.min(scalars.length, 48)})`}</button>}
    </div>}

    {chartBlocks.map(block => <NumericSeriesChart key={`chart-${block.path}`} block={block}/>)}

    {tableBlocks.length > 0 && <div className="space-y-2"><p className="text-xs font-medium uppercase tracking-wide text-text-muted">Detailed result tables</p>{tableBlocks.map(block => <DataTable key={`table-${block.path}`} block={block}/>)}</div>}

    <p className="text-[10px] leading-relaxed text-text-muted">Docking charts now plot score/displacement metrics (affinity and RMSD) rather than atom-count bookkeeping. Interaction charts appear only when returned contact counts vary across poses. Constant or zero values remain visible in tables for scientific completeness.</p>
  </section>;
}

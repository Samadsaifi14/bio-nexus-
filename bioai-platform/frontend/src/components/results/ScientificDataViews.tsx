'use client';

import { useMemo, useState } from 'react';
import { ChartLine, Table, Database, DownloadSimple, CaretDown, CaretRight, SlidersHorizontal } from '@phosphor-icons/react';
import { downloadJson } from '@/lib/export-utils';

type ScientificDataViewsProps = {
  toolName: string;
  result: Record<string, unknown>;
};

type ScalarRow = { path: string; label: string; value: string };
type SeriesBlock = { path: string; rows: Record<string, unknown>[] };

const X_KEYS = ['time_ps', 'time_ns', 'time', 'step', 'frame', 'residue', 'position', 'cycle', 'iteration', 'index', 'rank', 'mode'];
const OMIT_KEYS = new Set([
  'pdb', 'pdb_text', 'cif', 'mmcif', 'ligand_pdb', 'trajectory', 'raw_output', 'raw', 'log', 'vina_log',
  'query_alignment', 'hit_alignment', 'midline', 'sequence', 'query_sequence', 'context_json', 'request', 'response',
  'storage_url', 'file_urls', 'download_url', 'url', 'error_message', 'stack', 'traceback',
]);
const LOW_VALUE_KEYS = new Set([
  'job_id', 'experiment_id', 'created_at', 'updated_at', 'completed_at', 'captured_at', 'from_cache', 'status', 'source_url',
]);

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
    : key.endsWith('_k') || key.includes('temperature') ? ' (K)'
    : key.endsWith('_percent') || key.endsWith('_pct') ? ' (%)'
    : '';
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) + unit;
}

function collectScalars(value: unknown, prefix = '', depth = 0, out: ScalarRow[] = []): ScalarRow[] {
  if (depth > 3 || out.length >= 80 || value === null || value === undefined) return out;
  if (typeof value === 'object' && !Array.isArray(value)) {
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
      if (OMIT_KEYS.has(key) || LOW_VALUE_KEYS.has(key)) continue;
      const path = prefix ? `${prefix}.${key}` : key;
      if (child === null || child === undefined) continue;
      if (['number', 'boolean'].includes(typeof child)) {
        out.push({ path, label: humanize(key), value: formatValue(child) });
      } else if (typeof child === 'string' && child.length <= 220) {
        out.push({ path, label: humanize(key), value: formatValue(child) });
      } else if (typeof child === 'object' && !Array.isArray(child)) {
        collectScalars(child, path, depth + 1, out);
      }
    }
  }
  return out;
}

function collectSeries(value: unknown, prefix = '', depth = 0, out: SeriesBlock[] = []): SeriesBlock[] {
  if (depth > 4 || value === null || value === undefined || out.length >= 16) return out;
  if (Array.isArray(value)) {
    if (value.length && value.every(row => row && typeof row === 'object' && !Array.isArray(row))) {
      const rows = value as Record<string, unknown>[];
      const columns = Array.from(new Set(rows.slice(0, 40).flatMap(row => Object.keys(row))));
      const meaningful = columns.some(key => X_KEYS.includes(key)) || columns.filter(key => rows.some(row => typeof row[key] === 'number')).length >= 2;
      if (meaningful) out.push({ path: prefix || 'rows', rows });
    }
    return out;
  }
  if (typeof value === 'object') {
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
      if (OMIT_KEYS.has(key)) continue;
      collectSeries(child, prefix ? `${prefix}.${key}` : key, depth + 1, out);
    }
  }
  return out;
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
  const yKey = numericKeys.find(key => key !== xKey);
  if (!yKey) return null;

  const points = rows.map((row, index) => {
    const x = typeof row[xKey] === 'number' ? row[xKey] as number : index;
    const y = row[yKey];
    return typeof y === 'number' && Number.isFinite(y) ? { x, y } : null;
  }).filter((point): point is { x: number; y: number } => !!point);
  if (points.length < 2) return null;

  const width = 720, height = 230, left = 56, right = 18, top = 18, bottom = 40;
  const xMin = Math.min(...points.map(p => p.x)), xMax = Math.max(...points.map(p => p.x));
  const yMin = Math.min(...points.map(p => p.y)), yMax = Math.max(...points.map(p => p.y));
  const xSpan = Math.max(1e-12, xMax - xMin), ySpan = Math.max(1e-12, yMax - yMin);
  const sx = (x: number) => left + ((x - xMin) / xSpan) * (width - left - right);
  const sy = (y: number) => top + (height - top - bottom) - ((y - yMin) / ySpan) * (height - top - bottom);
  const d = points.map((p, i) => `${i ? 'L' : 'M'} ${sx(p.x).toFixed(2)} ${sy(p.y).toFixed(2)}`).join(' ');

  return <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
    <div className="mb-3 flex items-center gap-2"><ChartLine className="h-4 w-4 text-accent-cyan"/><div><p className="text-sm font-semibold text-text-primary">{humanize(yKey)} vs {humanize(xKey)}</p><p className="text-[11px] text-text-muted">{block.path} · {points.length.toLocaleString()} measured points</p></div></div>
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label={`${humanize(yKey)} versus ${humanize(xKey)}`}>
      {[0, .25, .5, .75, 1].map(t => {
        const y = top + t * (height - top - bottom);
        return <line key={t} x1={left} x2={width - right} y1={y} y2={y} stroke="currentColor" className="text-white/5"/>;
      })}
      <path d={d} fill="none" stroke="currentColor" strokeWidth="2" className="text-accent-cyan" vectorEffect="non-scaling-stroke"/>
      <text x={(left + width - right) / 2} y={height - 4} textAnchor="middle" fontSize="10" fill="currentColor" className="text-text-muted">{humanize(xKey)}</text>
    </svg>
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
      <Table className="h-4 w-4 text-accent-purple"/><span className="text-sm font-semibold text-text-primary">{humanize(block.path.split('.').pop() || block.path)}</span><span className="ml-auto text-[10px] text-text-muted">{block.rows.length.toLocaleString()} rows</span>
    </button>
    {open && <div className="overflow-x-auto border-t border-glass-border"><table className="min-w-full text-xs"><thead><tr className="bg-white/[0.02] text-text-muted">{columns.map(col => <th key={col} className="whitespace-nowrap px-3 py-2 text-left font-medium">{humanize(col)}</th>)}</tr></thead><tbody className="divide-y divide-glass-border">{previewRows.map((row, i) => <tr key={i}>{columns.map(col => <td key={col} className="max-w-[320px] whitespace-pre-wrap break-words px-3 py-2 align-top font-mono text-text-secondary">{formatValue(row[col]) || '—'}</td>)}</tr>)}</tbody></table>{block.rows.length > previewRows.length && <p className="border-t border-glass-border px-4 py-2 text-[10px] text-text-muted">Showing the first {previewRows.length} rows. Download the scientific JSON for the complete machine-readable result.</p>}</div>}
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
      <div className="flex items-center gap-2"><Database className="h-5 w-5 text-accent-cyan"/><div><h3 className="font-semibold text-text-primary">Scientific result details</h3><p className="mt-0.5 text-[10px] text-text-muted">Curated measurements, plots and tables derived only from the returned scientific result.</p></div></div>
      <button type="button" onClick={() => downloadJson(result, `${toolName || 'analysis'}_scientific_result.json`)} className="flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs text-text-secondary hover:text-accent-cyan"><DownloadSimple className="h-3.5 w-3.5"/>Download full data</button>
    </div>

    {visibleMetrics.length > 0 && <div className="rounded-xl border border-glass-border bg-surface-1 p-4"><div className="mb-3 flex items-center gap-2"><SlidersHorizontal className="h-4 w-4 text-accent-cyan"/><span className="text-sm font-semibold text-text-primary">Key measurements</span></div><div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{visibleMetrics.map(row => <div key={row.path} className="rounded-lg border border-glass-border/70 bg-surface-0 px-3 py-2"><p className="text-[10px] text-text-muted">{row.label}</p><p className="mt-1 break-words font-mono text-sm text-text-primary">{row.value}</p></div>)}</div>{scalars.length > 12 && <button type="button" onClick={() => setShowMoreMetrics(v => !v)} className="mt-3 text-xs text-accent-cyan hover:underline">{showMoreMetrics ? 'Show fewer measurements' : `Show more measurements (${Math.min(scalars.length, 48)})`}</button>}</div>}

    {chartBlocks.map(block => <NumericSeriesChart key={`chart-${block.path}`} block={block}/>)}

    {tableBlocks.length > 0 && <div className="space-y-2"><p className="text-xs font-medium uppercase tracking-wide text-text-muted">Detailed result tables</p>{tableBlocks.map(block => <DataTable key={`table-${block.path}`} block={block}/>)}</div>}

    <p className="text-[10px] leading-relaxed text-text-muted">Technical transport fields, raw logs, long sequence strings, URLs and backend payload internals are intentionally hidden from the main UX. They remain available through the downloaded scientific JSON when needed for audit or reproducibility.</p>
  </section>;
}

'use client';

import { useMemo, useState } from 'react';
import { ChartLine, Table, Database, DownloadSimple, CaretDown, CaretRight } from '@phosphor-icons/react';
import { downloadJson } from '@/lib/export-utils';

type ScientificDataViewsProps = {
  toolName: string;
  result: Record<string, unknown>;
};

type ScalarRow = { path: string; value: string };
type SeriesBlock = { path: string; rows: Record<string, unknown>[] };

const X_KEYS = ['time_ps', 'time', 'step', 'frame', 'residue', 'position', 'cycle', 'iteration', 'index'];
const OMIT_FROM_INLINE = new Set(['pdb', 'pdb_text', 'cif', 'mmcif', 'ligand_pdb', 'trajectory', 'raw_output']);

function formatValue(value: unknown): string {
  if (value === null) return 'null';
  if (value === undefined) return '—';
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : 'non-finite';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}

function labelForKey(key: string): string {
  const unit = key.endsWith('_angstrom2') ? ' (Å²)'
    : key.endsWith('_angstrom') || key.includes('rmsd') || key.includes('rmsf') ? ' (Å)'
    : key.endsWith('_kj_mol') || key === 'energy' ? ' (kJ/mol)'
    : key.endsWith('_k') || key.includes('temperature') ? ' (K)'
    : key.endsWith('_percent') || key.endsWith('_pct') ? ' (%)'
    : '';
  return key.replace(/_/g, ' ') + unit;
}

function collectScalars(value: unknown, prefix = '', depth = 0, out: ScalarRow[] = []): ScalarRow[] {
  if (depth > 4) return out;
  if (value === null || value === undefined || typeof value === 'number' || typeof value === 'boolean') {
    out.push({ path: prefix || 'value', value: formatValue(value) });
    return out;
  }
  if (typeof value === 'string') {
    const leaf = prefix.split('.').pop() || '';
    if (OMIT_FROM_INLINE.has(leaf) || value.length > 2000) {
      out.push({ path: prefix || 'value', value: `[text payload: ${value.length.toLocaleString()} characters]` });
    } else {
      out.push({ path: prefix || 'value', value });
    }
    return out;
  }
  if (Array.isArray(value)) return out;
  if (typeof value === 'object') {
    Object.entries(value as Record<string, unknown>).forEach(([key, child]) => {
      collectScalars(child, prefix ? `${prefix}.${key}` : key, depth + 1, out);
    });
  }
  return out;
}

function collectSeries(value: unknown, prefix = '', depth = 0, out: SeriesBlock[] = []): SeriesBlock[] {
  if (depth > 4 || value === null || value === undefined) return out;
  if (Array.isArray(value)) {
    if (value.length && value.every(row => row && typeof row === 'object' && !Array.isArray(row))) {
      out.push({ path: prefix || 'rows', rows: value as Record<string, unknown>[] });
    }
    return out;
  }
  if (typeof value === 'object') {
    Object.entries(value as Record<string, unknown>).forEach(([key, child]) => {
      collectSeries(child, prefix ? `${prefix}.${key}` : key, depth + 1, out);
    });
  }
  return out;
}

function NumericSeriesChart({ block }: { block: SeriesBlock }) {
  const rows = block.rows;
  if (rows.length < 2) return null;
  const keys = Array.from(new Set(rows.flatMap(row => Object.keys(row))));
  const numericKeys = keys.filter(key => rows.some(row => typeof row[key] === 'number' && Number.isFinite(row[key] as number)));
  if (!numericKeys.length) return null;
  const xKey = X_KEYS.find(key => keys.includes(key)) ?? numericKeys[0];
  const yKeys = numericKeys.filter(key => key !== xKey).slice(0, 4);
  if (!yKeys.length) return null;

  const width = 760;
  const height = 250;
  const left = 56;
  const right = 18;
  const top = 20;
  const bottom = 42;
  const innerW = width - left - right;
  const innerH = height - top - bottom;
  const xValues = rows.map((row, i) => typeof row[xKey] === 'number' ? row[xKey] as number : i);
  const yValues = rows.flatMap(row => yKeys.map(key => row[key])).filter((v): v is number => typeof v === 'number' && Number.isFinite(v));
  if (!yValues.length) return null;
  const xMin = Math.min(...xValues), xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues), yMax = Math.max(...yValues);
  const xSpan = Math.max(1e-12, xMax - xMin);
  const ySpan = Math.max(1e-12, yMax - yMin);
  const sx = (x: number) => left + ((x - xMin) / xSpan) * innerW;
  const sy = (y: number) => top + innerH - ((y - yMin) / ySpan) * innerH;

  return <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
    <div className="mb-3 flex items-center gap-2"><ChartLine className="h-4 w-4 text-accent-cyan"/><div><p className="text-sm font-semibold text-text-primary">{block.path}</p><p className="text-[11px] text-text-muted">Direct visualization of numeric values returned by the backend. No interpolated or synthetic points.</p></div></div>
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="min-w-[620px] w-full" role="img" aria-label={`${block.path} scientific result chart`}>
        {[0, .25, .5, .75, 1].map(t => <g key={`y-${t}`}><line x1={left} x2={left + innerW} y1={top + innerH * t} y2={top + innerH * t} stroke="currentColor" className="text-white/5"/><text x={left - 8} y={top + innerH * t + 3} textAnchor="end" fontSize="9" fill="currentColor" className="text-text-muted">{(yMax - ySpan * t).toPrecision(4)}</text></g>)}
        {[0, .25, .5, .75, 1].map(t => <g key={`x-${t}`}><line x1={left + innerW * t} x2={left + innerW * t} y1={top} y2={top + innerH} stroke="currentColor" className="text-white/5"/><text x={left + innerW * t} y={height - 16} textAnchor="middle" fontSize="9" fill="currentColor" className="text-text-muted">{(xMin + xSpan * t).toPrecision(4)}</text></g>)}
        {yKeys.map((key, seriesIndex) => {
          const points = rows.map((row, i) => {
            const y = row[key];
            if (typeof y !== 'number' || !Number.isFinite(y)) return null;
            return `${sx(xValues[i])},${sy(y)}`;
          }).filter(Boolean).join(' ');
          return <polyline key={key} points={points} fill="none" stroke="currentColor" strokeWidth={1.7 + seriesIndex * 0.15} className={seriesIndex === 0 ? 'text-accent-cyan' : seriesIndex === 1 ? 'text-accent-purple' : seriesIndex === 2 ? 'text-accent-amber' : 'text-good'} vectorEffect="non-scaling-stroke"/>;
        })}
        <text x={left + innerW / 2} y={height - 2} textAnchor="middle" fontSize="10" fill="currentColor" className="text-text-muted">{labelForKey(xKey)}</text>
      </svg>
    </div>
    <div className="mt-2 flex flex-wrap gap-3 text-[10px] text-text-muted">{yKeys.map(key => <span key={key}>{labelForKey(key)}</span>)}</div>
  </div>;
}

function DataTable({ block }: { block: SeriesBlock }) {
  const [open, setOpen] = useState(false);
  const columns = Array.from(new Set(block.rows.flatMap(row => Object.keys(row))));
  const previewRows = open ? block.rows : block.rows.slice(0, 20);
  return <div className="overflow-hidden rounded-xl border border-glass-border bg-surface-1">
    <button type="button" onClick={() => setOpen(v => !v)} className="flex w-full items-center gap-2 px-4 py-3 text-left hover:bg-white/[0.02]">
      {open ? <CaretDown className="h-4 w-4 text-text-muted"/> : <CaretRight className="h-4 w-4 text-text-muted"/>}
      <Table className="h-4 w-4 text-accent-purple"/><span className="text-sm font-semibold text-text-primary">{block.path}</span><span className="ml-auto text-[10px] text-text-muted">{block.rows.length.toLocaleString()} rows × {columns.length} fields</span>
    </button>
    <div className="overflow-x-auto border-t border-glass-border">
      <table className="min-w-full text-xs"><thead><tr className="bg-white/[0.02] text-text-muted">{columns.map(col => <th key={col} className="whitespace-nowrap px-3 py-2 text-left font-medium">{col}</th>)}</tr></thead><tbody className="divide-y divide-glass-border">{previewRows.map((row, i) => <tr key={i}>{columns.map(col => <td key={col} className="max-w-[360px] whitespace-pre-wrap break-words px-3 py-2 align-top font-mono text-text-secondary">{formatValue(row[col])}</td>)}</tr>)}</tbody></table>
    </div>
    {!open && block.rows.length > 20 && <button type="button" onClick={() => setOpen(true)} className="w-full border-t border-glass-border px-4 py-2 text-xs text-accent-cyan hover:bg-white/[0.02]">Show all {block.rows.length.toLocaleString()} returned rows</button>}
  </div>;
}

export function ScientificDataViews({ toolName, result }: ScientificDataViewsProps) {
  const scalars = useMemo(() => collectScalars(result), [result]);
  const series = useMemo(() => collectSeries(result), [result]);
  const [showRecord, setShowRecord] = useState(false);

  const downloadFullRecord = () => downloadJson(result, `${toolName || 'analysis'}_scientific_result.json`);

  return <section className="space-y-4 rounded-2xl border border-glass-border bg-surface-0 p-5" aria-label="Scientific result data views">
    <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-2"><Database className="h-5 w-5 text-accent-cyan"/><div><h3 className="font-semibold text-text-primary">Scientific data views</h3><p className="mt-0.5 text-[10px] text-text-muted">Tables and charts are generated only from fields actually returned by the scientific backend.</p></div></div><button type="button" onClick={downloadFullRecord} className="flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs text-text-secondary hover:text-accent-cyan"><DownloadSimple className="h-3.5 w-3.5"/>Full JSON</button></div>

    {scalars.length > 0 && <div className="overflow-hidden rounded-xl border border-glass-border"><div className="flex items-center gap-2 bg-surface-1 px-4 py-3"><Table className="h-4 w-4 text-accent-cyan"/><span className="text-sm font-semibold text-text-primary">Returned metrics and metadata</span><span className="ml-auto text-[10px] text-text-muted">{scalars.length} scalar fields</span></div><div className="max-h-[420px] overflow-auto border-t border-glass-border"><table className="w-full text-xs"><tbody className="divide-y divide-glass-border">{scalars.map(row => <tr key={row.path}><td className="w-[42%] px-3 py-2 align-top font-medium text-text-muted">{row.path}</td><td className="px-3 py-2 whitespace-pre-wrap break-words font-mono text-text-secondary">{row.value}</td></tr>)}</tbody></table></div></div>}

    {series.map(block => <NumericSeriesChart key={`chart-${block.path}`} block={block}/>)}
    {series.map(block => <DataTable key={`table-${block.path}`} block={block}/>)}

    <div className="rounded-xl border border-glass-border bg-surface-1"><button type="button" onClick={() => setShowRecord(v => !v)} className="flex w-full items-center gap-2 px-4 py-3 text-left">{showRecord ? <CaretDown className="h-4 w-4 text-text-muted"/> : <CaretRight className="h-4 w-4 text-text-muted"/>}<span className="text-sm font-semibold text-text-primary">Raw backend record</span><span className="ml-auto text-[10px] text-text-muted">authoritative machine-readable payload</span></button>{showRecord && <pre className="max-h-[600px] overflow-auto border-t border-glass-border p-4 text-[11px] leading-relaxed text-text-secondary">{JSON.stringify(result, null, 2)}</pre>}</div>

    <p className="text-[10px] leading-relaxed text-text-muted">Visualisation does not add biological meaning to missing values. Empty, absent or non-finite fields are not converted into positive or negative findings.</p>
  </section>;
}

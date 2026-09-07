'use client';

import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { ChartLine, Database, FileCode, Table, WarningCircle } from '@phosphor-icons/react';

type JsonRecord = Record<string, unknown>;
type CapturedResult = {
  url: string;
  capturedAt: string;
  data: unknown;
};

type TableModel = {
  path: string;
  rows: JsonRecord[];
  columns: string[];
};

type SeriesModel = {
  path: string;
  xKey: string;
  yKey: string;
  rows: JsonRecord[];
};

const MAX_ROWS_RENDERED = 250;
const MAX_JSON_CHARS = 250000;

function isRecord(value: unknown): value is JsonRecord {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function isScientificPayload(value: unknown): boolean {
  if (!value) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (!isRecord(value)) return false;
  const keys = Object.keys(value);
  if (!keys.length) return false;
  if (keys.length <= 3 && keys.every(k => ['job_id', 'status', 'message'].includes(k))) return false;
  if ('result' in value && value.result) return true;
  return keys.some(k => Array.isArray(value[k]) || isRecord(value[k])) || keys.length >= 4;
}

function unwrapPayload(payload: unknown): unknown {
  if (isRecord(payload) && payload.result && (isRecord(payload.result) || Array.isArray(payload.result))) {
    return payload.result;
  }
  return payload;
}

function humanize(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, c => c.toUpperCase());
}

function displayValue(value: unknown): string {
  if (value === null) return 'null';
  if (value === undefined) return '—';
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return String(value);
    if (Math.abs(value) >= 100000 || (Math.abs(value) > 0 && Math.abs(value) < 0.001)) return value.toExponential(4);
    return Number.isInteger(value) ? String(value) : value.toPrecision(6).replace(/0+$/, '').replace(/\.$/, '');
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}

function collectScalars(value: unknown, prefix = '', depth = 0, out: Array<{ path: string; value: unknown }> = []) {
  if (depth > 5 || out.length >= 160) return out;
  if (isRecord(value)) {
    for (const [key, child] of Object.entries(value)) {
      const path = prefix ? `${prefix}.${key}` : key;
      if (child === null || ['string', 'number', 'boolean'].includes(typeof child)) out.push({ path, value: child });
      else if (isRecord(child)) collectScalars(child, path, depth + 1, out);
    }
  }
  return out;
}

function collectTables(value: unknown, prefix = 'result', depth = 0, out: TableModel[] = []) {
  if (depth > 5 || out.length >= 30) return out;
  if (!isRecord(value)) return out;
  for (const [key, child] of Object.entries(value)) {
    const path = `${prefix}.${key}`;
    if (Array.isArray(child) && child.length && child.every(isRecord)) {
      const rows = child as JsonRecord[];
      const columns = Array.from(new Set(rows.slice(0, 50).flatMap(row => Object.keys(row))));
      if (columns.length) out.push({ path, rows, columns });
    } else if (isRecord(child)) {
      collectTables(child, path, depth + 1, out);
    }
  }
  return out;
}

function numericKeys(rows: JsonRecord[]): string[] {
  if (!rows.length) return [];
  const keys = Array.from(new Set(rows.slice(0, 50).flatMap(row => Object.keys(row))));
  return keys.filter(key => {
    const vals = rows.slice(0, 50).map(row => row[key]).filter(v => v !== null && v !== undefined);
    return vals.length >= 2 && vals.every(v => typeof v === 'number' && Number.isFinite(v));
  });
}

function chooseSeries(table: TableModel): SeriesModel | null {
  const nums = numericKeys(table.rows);
  if (nums.length < 1) return null;
  const preferredX = ['time', 'time_ps', 'time_ns', 'step', 'frame', 'position', 'residue', 'residue_index', 'cycle', 'iteration', 'rank', 'mode'];
  let xKey = preferredX.find(k => nums.includes(k));
  let yKey: string | undefined;
  if (xKey) yKey = nums.find(k => k !== xKey);
  if (!xKey && nums.length >= 2) {
    [xKey, yKey] = nums;
  }
  if (!xKey || !yKey) return null;
  return { path: table.path, xKey, yKey, rows: table.rows };
}

function SvgSeries({ series }: { series: SeriesModel }) {
  const points = series.rows
    .map(row => ({ x: row[series.xKey], y: row[series.yKey] }))
    .filter((p): p is { x: number; y: number } => typeof p.x === 'number' && Number.isFinite(p.x) && typeof p.y === 'number' && Number.isFinite(p.y));
  if (points.length < 2) return null;
  const width = 720;
  const height = 260;
  const pad = { left: 64, right: 24, top: 22, bottom: 48 };
  const minX = Math.min(...points.map(p => p.x));
  const maxX = Math.max(...points.map(p => p.x));
  const minY = Math.min(...points.map(p => p.y));
  const maxY = Math.max(...points.map(p => p.y));
  const spanX = Math.max(Math.abs(maxX - minX), 1e-12);
  const spanY = Math.max(Math.abs(maxY - minY), 1e-12);
  const sx = (x: number) => pad.left + ((x - minX) / spanX) * (width - pad.left - pad.right);
  const sy = (y: number) => height - pad.bottom - ((y - minY) / spanY) * (height - pad.top - pad.bottom);
  const path = points.map((p, i) => `${i ? 'L' : 'M'} ${sx(p.x).toFixed(2)} ${sy(p.y).toFixed(2)}`).join(' ');
  const ticks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
      <div className="mb-2 flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-text-primary">{humanize(series.yKey)} vs {humanize(series.xKey)}</p>
          <p className="text-[11px] text-text-muted font-mono break-all">{series.path}</p>
        </div>
        <span className="rounded border border-glass-border px-2 py-1 text-[10px] text-text-muted">{points.length} returned points</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label={`${humanize(series.yKey)} versus ${humanize(series.xKey)}`}>
        {ticks.map(t => {
          const y = pad.top + t * (height - pad.top - pad.bottom);
          const value = maxY - t * spanY;
          return <g key={`y-${t}`}><line x1={pad.left} x2={width - pad.right} y1={y} y2={y} stroke="currentColor" className="text-white/5"/><text x={pad.left - 8} y={y + 4} textAnchor="end" fontSize="10" fill="currentColor" className="text-text-muted">{displayValue(value)}</text></g>;
        })}
        {ticks.map(t => {
          const x = pad.left + t * (width - pad.left - pad.right);
          const value = minX + t * spanX;
          return <g key={`x-${t}`}><line x1={x} x2={x} y1={pad.top} y2={height - pad.bottom} stroke="currentColor" className="text-white/5"/><text x={x} y={height - 22} textAnchor="middle" fontSize="10" fill="currentColor" className="text-text-muted">{displayValue(value)}</text></g>;
        })}
        <path d={path} fill="none" stroke="currentColor" strokeWidth="2" className="text-accent-cyan" vectorEffect="non-scaling-stroke"/>
        {points.length <= 80 && points.map((p, i) => <circle key={i} cx={sx(p.x)} cy={sy(p.y)} r="2.2" fill="currentColor" className="text-accent-cyan"/>)}
        <text x={(pad.left + width - pad.right) / 2} y={height - 4} textAnchor="middle" fontSize="11" fill="currentColor" className="text-text-secondary">{humanize(series.xKey)}</text>
        <text x="14" y={height / 2} textAnchor="middle" fontSize="11" fill="currentColor" className="text-text-secondary" transform={`rotate(-90 14 ${height / 2})`}>{humanize(series.yKey)}</text>
      </svg>
      <p className="mt-2 text-[10px] text-text-muted">Plotted directly from backend numeric fields; no interpolation, smoothing, or invented points.</p>
    </div>
  );
}

function DataTable({ table }: { table: TableModel }) {
  const rows = table.rows.slice(0, MAX_ROWS_RENDERED);
  return (
    <details className="rounded-xl border border-glass-border bg-surface-1" open={table.rows.length <= 40}>
      <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-text-primary">
        {humanize(table.path.split('.').pop() || table.path)} <span className="ml-2 text-xs font-normal text-text-muted">{table.rows.length} row{table.rows.length === 1 ? '' : 's'}</span>
      </summary>
      <div className="overflow-x-auto border-t border-glass-border">
        <table className="min-w-full text-xs">
          <thead><tr>{table.columns.map(col => <th key={col} className="whitespace-nowrap px-3 py-2 text-left font-semibold text-text-secondary">{humanize(col)}</th>)}</tr></thead>
          <tbody className="divide-y divide-glass-border">
            {rows.map((row, i) => <tr key={i}>{table.columns.map(col => <td key={col} className="max-w-[360px] whitespace-pre-wrap break-words px-3 py-2 align-top font-mono text-text-primary">{displayValue(row[col])}</td>)}</tr>)}
          </tbody>
        </table>
      </div>
      {table.rows.length > MAX_ROWS_RENDERED && <p className="border-t border-glass-border px-4 py-2 text-[10px] text-text-muted">Showing first {MAX_ROWS_RENDERED} rows for browser performance. The complete backend object remains available in Raw scientific payload below.</p>}
    </details>
  );
}

export function ScientificResultWorkspace() {
  const [captured, setCaptured] = useState<CapturedResult | null>(null);
  const [portalTarget, setPortalTarget] = useState<Element | null>(null);

  useEffect(() => {
    const OriginalXHR = window.XMLHttpRequest;
    const originalOpen = OriginalXHR.prototype.open;
    const originalSend = OriginalXHR.prototype.send;
    const urlMap = new WeakMap<XMLHttpRequest, string>();

    OriginalXHR.prototype.open = function(method: string, url: string | URL, ...rest: unknown[]) {
      urlMap.set(this, String(url));
      return originalOpen.call(this, method, url, ...(rest as [boolean?, string?, string?]));
    } as typeof originalOpen;

    OriginalXHR.prototype.send = function(body?: Document | XMLHttpRequestBodyInit | null) {
      this.addEventListener('load', () => {
        try {
          const url = urlMap.get(this) || '';
          if (!url.includes('/api/backend')) return;
          const contentType = this.getResponseHeader('content-type') || '';
          if (!contentType.includes('application/json') && typeof this.responseText !== 'string') return;
          const payload = typeof this.response === 'object' && this.response !== null ? this.response : JSON.parse(this.responseText);
          if (!isScientificPayload(payload)) return;
          setCaptured({ url, capturedAt: new Date().toISOString(), data: unwrapPayload(payload) });
        } catch {
          // Capture is observational only; it must never affect the scientific request.
        }
      });
      return originalSend.call(this, body as XMLHttpRequestBodyInit | null | undefined);
    } as typeof originalSend;

    return () => {
      OriginalXHR.prototype.open = originalOpen;
      OriginalXHR.prototype.send = originalSend;
    };
  }, []);

  useEffect(() => {
    if (!captured) return;
    const locate = () => {
      const nodes = Array.from(document.querySelectorAll('[id$="-results"], #results'));
      const visible = nodes.reverse().find(node => (node as HTMLElement).offsetParent !== null);
      setPortalTarget(visible || document.querySelector('main'));
    };
    locate();
    const timer = window.setInterval(locate, 1000);
    return () => window.clearInterval(timer);
  }, [captured]);

  const data = captured?.data;
  const scalars = useMemo(() => collectScalars(data), [data]);
  const tables = useMemo(() => collectTables(data), [data]);
  const series = useMemo(() => tables.map(chooseSeries).filter((s): s is SeriesModel => !!s).slice(0, 12), [tables]);
  const rawJson = useMemo(() => {
    if (!data) return '';
    try {
      const text = JSON.stringify(data, null, 2);
      return text.length > MAX_JSON_CHARS ? `${text.slice(0, MAX_JSON_CHARS)}\n\n[Display truncated at ${MAX_JSON_CHARS} characters; export the endpoint response for the complete payload.]` : text;
    } catch {
      return String(data);
    }
  }, [data]);

  if (!captured || !portalTarget) return null;

  const workspace = (
    <section className="mt-6 space-y-4" data-scientific-result-workspace="true">
      <div className="data-card overflow-hidden">
        <div className="border-b border-glass-border p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Database className="h-5 w-5 text-accent-cyan" />
                <h2 className="text-base font-semibold text-text-primary">Complete Scientific Result Workspace</h2>
              </div>
              <p className="mt-1 text-xs text-text-muted">A lossless UI view of the latest scientific backend response on this page.</p>
            </div>
            <div className="text-right text-[10px] text-text-muted">
              <div className="font-mono break-all max-w-[440px]">{captured.url}</div>
              <div>{captured.capturedAt}</div>
            </div>
          </div>
        </div>

        <div className="grid gap-3 p-5 sm:grid-cols-2 lg:grid-cols-4">
          {scalars.slice(0, 24).map(item => (
            <div key={item.path} className="rounded-lg border border-glass-border bg-surface-1 p-3">
              <p className="truncate text-[10px] text-text-muted" title={item.path}>{humanize(item.path.split('.').pop() || item.path)}</p>
              <p className="mt-1 break-words font-mono text-sm text-text-primary">{displayValue(item.value)}</p>
              <p className="mt-1 truncate text-[9px] text-text-muted/70" title={item.path}>{item.path}</p>
            </div>
          ))}
        </div>

        <div className="border-t border-glass-border px-5 py-3 text-xs text-text-secondary flex gap-2">
          <WarningCircle className="mt-0.5 h-4 w-4 shrink-0 text-accent-amber" />
          <p>Values, tables and plots in this workspace are rendered only from fields returned by the scientific backend. No placeholder measurements are generated. A missing field is not interpreted as a negative biological finding, and computational outputs do not establish experimental efficacy or biological correctness.</p>
        </div>
      </div>

      {series.length > 0 && (
        <div className="data-card p-5">
          <div className="mb-4 flex items-center gap-2"><ChartLine className="h-4 w-4 text-accent-cyan"/><h3 className="text-sm font-semibold text-text-primary">Backend-Derived Charts</h3></div>
          <div className="grid gap-4 xl:grid-cols-2">{series.map(s => <SvgSeries key={`${s.path}:${s.xKey}:${s.yKey}`} series={s}/>)}</div>
        </div>
      )}

      {tables.length > 0 && (
        <div className="data-card p-5">
          <div className="mb-4 flex items-center gap-2"><Table className="h-4 w-4 text-accent-purple"/><h3 className="text-sm font-semibold text-text-primary">Complete Returned Tables</h3></div>
          <div className="space-y-3">{tables.map(t => <DataTable key={t.path} table={t}/>)}</div>
        </div>
      )}

      <div className="data-card p-5">
        <details>
          <summary className="cursor-pointer flex items-center gap-2 text-sm font-semibold text-text-primary"><FileCode className="h-4 w-4 text-accent-amber"/>Raw Scientific Payload</summary>
          <p className="mt-2 text-[11px] text-text-muted">Machine-readable source used by this workspace. This preserves nested fields that are not suitable for cards, charts or compact tables.</p>
          <pre className="mt-3 max-h-[680px] overflow-auto rounded-lg border border-glass-border bg-surface-1 p-4 text-[11px] leading-relaxed text-text-secondary">{rawJson}</pre>
        </details>
      </div>
    </section>
  );

  return createPortal(workspace, portalTarget);
}

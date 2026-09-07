'use client';

import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { ChartLine, Database, FileCode, Table as TableIcon, WarningCircle } from '@phosphor-icons/react';

type Obj = Record<string, unknown>;
type Capture = { key: string; url: string; at: string; payload: unknown };
type TableModel = { path: string; rows: Obj[]; columns: string[] };
type SeriesModel = { path: string; rows: Obj[]; xKey: string; yKey: string };

const EXCLUDED_URL_PARTS = [
  '/api/ai/', '/api/keys', '/api/jobs/count', '/health', '/forcefields', '/menu',
  '/auth/', '/api/share', '/api/export/', '/api/benchmarks', '/api/analytics',
];
const RESULT_ANCHORS = '[id$="-results"], #results, [data-results-root="true"]';
const X_KEYS = ['time', 'time_ps', 'time_ns', 'step', 'frame', 'position', 'cycle', 'iteration', 'rank', 'mode', 'residue', 'residue_index', 'base', 'coordinate', 'generation'];

function obj(v: unknown): v is Obj { return !!v && typeof v === 'object' && !Array.isArray(v); }
function endpointKey(url: string): string {
  try {
    const u = new URL(url, window.location.origin);
    return u.pathname.replace(/\/[0-9a-f]{8}-[0-9a-f-]{27,}$/i, '/:id').replace(/\/\d+$/i, '/:id');
  } catch { return url.split('?')[0]; }
}
function excluded(url: string): boolean { return EXCLUDED_URL_PARTS.some(part => url.includes(part)); }
function unwrap(v: unknown): unknown {
  if (obj(v) && v.result && (obj(v.result) || Array.isArray(v.result))) return v.result;
  return v;
}
function scientific(v: unknown): boolean {
  if (Array.isArray(v)) return v.length > 0;
  if (!obj(v)) return false;
  const keys = Object.keys(v);
  if (!keys.length) return false;
  if (keys.length <= 3 && keys.every(k => ['job_id', 'status', 'message', 'detail'].includes(k))) return false;
  if (v.result && (obj(v.result) || Array.isArray(v.result))) return true;
  const signal = ['metrics', 'poses', 'hits', 'results', 'stages', 'rmsd', 'rmsf', 'energy', 'temperature', 'sasa', 'radius_of_gyration', 'variants', 'transcripts', 'alignment', 'newick', 'domains', 'pathways', 'interactions', 'chains', 'ligands', 'provenance', 'qc', 'statistics', 'summary'];
  return signal.some(k => k in v) || keys.length >= 5;
}
function human(key: string): string {
  return key.replace(/_/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').replace(/\b\w/g, c => c.toUpperCase());
}
function fmt(v: unknown): string {
  if (v === null) return 'null';
  if (v === undefined) return '—';
  if (typeof v === 'number') {
    if (!Number.isFinite(v)) return String(v);
    const a = Math.abs(v);
    if (a >= 1e5 || (a > 0 && a < 1e-3)) return v.toExponential(4);
    return Number.isInteger(v) ? String(v) : Number(v.toPrecision(6)).toString();
  }
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (typeof v === 'string') return v;
  try { return JSON.stringify(v); } catch { return String(v); }
}
function scalars(v: unknown, prefix = '', depth = 0, out: Array<{ path: string; value: unknown }> = []) {
  if (depth > 6 || out.length >= 240 || !obj(v)) return out;
  for (const [k, child] of Object.entries(v)) {
    const path = prefix ? `${prefix}.${k}` : k;
    if (child === null || ['string', 'number', 'boolean'].includes(typeof child)) out.push({ path, value: child });
    else if (obj(child)) scalars(child, path, depth + 1, out);
  }
  return out;
}
function tables(v: unknown, prefix = 'result', depth = 0, out: TableModel[] = []) {
  if (depth > 6 || out.length >= 50) return out;
  if (Array.isArray(v)) {
    if (v.length && v.every(obj)) {
      const rows = v as Obj[];
      out.push({ path: prefix, rows, columns: Array.from(new Set(rows.slice(0, 80).flatMap(r => Object.keys(r)))) });
    } else if (v.length && v.every(x => ['string', 'number', 'boolean'].includes(typeof x) || x === null)) {
      out.push({ path: prefix, rows: v.map((value, index) => ({ index, value })), columns: ['index', 'value'] });
    }
    return out;
  }
  if (!obj(v)) return out;
  for (const [k, child] of Object.entries(v)) {
    const path = `${prefix}.${k}`;
    if (Array.isArray(child)) tables(child, path, depth + 1, out);
    else if (obj(child)) tables(child, path, depth + 1, out);
  }
  return out;
}
function numericKeys(rows: Obj[]): string[] {
  const keys = Array.from(new Set(rows.slice(0, 80).flatMap(r => Object.keys(r))));
  return keys.filter(k => {
    const vals = rows.slice(0, 80).map(r => r[k]).filter(v => v !== null && v !== undefined);
    return vals.length >= 2 && vals.every(v => typeof v === 'number' && Number.isFinite(v));
  });
}
function seriesFor(t: TableModel): SeriesModel[] {
  const nums = numericKeys(t.rows);
  const xKey = X_KEYS.find(k => nums.includes(k));
  if (!xKey) return [];
  return nums.filter(k => k !== xKey).slice(0, 4).map(yKey => ({ path: t.path, rows: t.rows, xKey, yKey }));
}
function LinePlot({ s }: { s: SeriesModel }) {
  const pts = s.rows.map(r => ({ x: r[s.xKey], y: r[s.yKey] })).filter((p): p is { x: number; y: number } => typeof p.x === 'number' && Number.isFinite(p.x) && typeof p.y === 'number' && Number.isFinite(p.y));
  if (pts.length < 2) return null;
  const W = 680, H = 240, L = 62, R = 18, T = 18, B = 44;
  const minX = Math.min(...pts.map(p => p.x)), maxX = Math.max(...pts.map(p => p.x));
  const minY = Math.min(...pts.map(p => p.y)), maxY = Math.max(...pts.map(p => p.y));
  const dx = Math.max(maxX - minX, 1e-12), dy = Math.max(maxY - minY, 1e-12);
  const sx = (x: number) => L + ((x - minX) / dx) * (W - L - R);
  const sy = (y: number) => H - B - ((y - minY) / dy) * (H - T - B);
  const d = pts.map((p, i) => `${i ? 'L' : 'M'} ${sx(p.x).toFixed(2)} ${sy(p.y).toFixed(2)}`).join(' ');
  const tick = [0, .25, .5, .75, 1];
  return <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
    <div className="flex items-start justify-between gap-3"><div><p className="text-sm font-semibold text-text-primary">{human(s.yKey)} vs {human(s.xKey)}</p><p className="font-mono text-[10px] text-text-muted break-all">{s.path}</p></div><span className="text-[10px] text-text-muted">{pts.length} points</span></div>
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-2 w-full" role="img" aria-label={`${human(s.yKey)} versus ${human(s.xKey)}`}>
      {tick.map(t => { const y = T + t * (H - T - B), val = maxY - t * dy; return <g key={`y${t}`}><line x1={L} x2={W-R} y1={y} y2={y} stroke="currentColor" className="text-white/5"/><text x={L-7} y={y+4} textAnchor="end" fontSize="9" fill="currentColor" className="text-text-muted">{fmt(val)}</text></g>; })}
      {tick.map(t => { const x = L + t * (W-L-R), val = minX + t * dx; return <g key={`x${t}`}><line x1={x} x2={x} y1={T} y2={H-B} stroke="currentColor" className="text-white/5"/><text x={x} y={H-20} textAnchor="middle" fontSize="9" fill="currentColor" className="text-text-muted">{fmt(val)}</text></g>; })}
      <path d={d} fill="none" stroke="currentColor" strokeWidth="2" className="text-accent-cyan" vectorEffect="non-scaling-stroke"/>
      {pts.length <= 80 && pts.map((p, i) => <circle key={i} cx={sx(p.x)} cy={sy(p.y)} r="2" fill="currentColor" className="text-accent-cyan"/>)}
      <text x={(L+W-R)/2} y={H-3} textAnchor="middle" fontSize="10" fill="currentColor" className="text-text-secondary">{human(s.xKey)}</text>
      <text x="12" y={H/2} textAnchor="middle" fontSize="10" fill="currentColor" className="text-text-secondary" transform={`rotate(-90 12 ${H/2})`}>{human(s.yKey)}</text>
    </svg>
    <p className="mt-1 text-[10px] text-text-muted">Direct backend values only. No smoothing, interpolation or synthetic points.</p>
  </div>;
}
function ResultTable({ t }: { t: TableModel }) {
  const rows = t.rows.slice(0, 250);
  return <details className="overflow-hidden rounded-xl border border-glass-border bg-surface-1" open={t.rows.length <= 35}>
    <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-text-primary">{human(t.path.split('.').pop() || t.path)} <span className="ml-2 text-xs font-normal text-text-muted">{t.rows.length} rows</span></summary>
    <div className="overflow-x-auto border-t border-glass-border"><table className="min-w-full text-xs"><thead><tr>{t.columns.map(c => <th key={c} className="whitespace-nowrap px-3 py-2 text-left text-text-secondary">{human(c)}</th>)}</tr></thead><tbody className="divide-y divide-glass-border">{rows.map((r, i) => <tr key={i}>{t.columns.map(c => <td key={c} className="max-w-[420px] whitespace-pre-wrap break-words px-3 py-2 align-top font-mono text-text-primary">{fmt(r[c])}</td>)}</tr>)}</tbody></table></div>
    {t.rows.length > rows.length && <p className="border-t border-glass-border px-4 py-2 text-[10px] text-text-muted">Rendering first {rows.length} rows for browser performance; the raw payload below preserves the full response.</p>}
  </details>;
}
function PayloadPanel({ capture }: { capture: Capture }) {
  const sc = useMemo(() => scalars(capture.payload), [capture.payload]);
  const tb = useMemo(() => tables(capture.payload), [capture.payload]);
  const sr = useMemo(() => tb.flatMap(seriesFor).slice(0, 16), [tb]);
  const raw = useMemo(() => { try { return JSON.stringify(capture.payload, null, 2); } catch { return String(capture.payload); } }, [capture.payload]);
  return <div className="space-y-4">
    <div className="data-card overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-glass-border p-4"><div><p className="text-sm font-semibold text-text-primary">{human(capture.key.split('/').filter(Boolean).pop() || 'Scientific response')}</p><p className="max-w-3xl break-all font-mono text-[10px] text-text-muted">{capture.url}</p></div><span className="text-[10px] text-text-muted">{capture.at}</span></div>
      {sc.length > 0 && <div className="grid gap-2 p-4 sm:grid-cols-2 lg:grid-cols-4">{sc.slice(0, 32).map(x => <div key={x.path} className="rounded-lg border border-glass-border bg-surface-1 p-3"><p className="truncate text-[10px] text-text-muted" title={x.path}>{human(x.path.split('.').pop() || x.path)}</p><p className="mt-1 break-words font-mono text-sm text-text-primary">{fmt(x.value)}</p><p className="mt-1 truncate font-mono text-[9px] text-text-muted/70" title={x.path}>{x.path}</p></div>)}</div>}
    </div>
    {sr.length > 0 && <div className="data-card p-4"><div className="mb-3 flex items-center gap-2"><ChartLine className="h-4 w-4 text-accent-cyan"/><h3 className="text-sm font-semibold text-text-primary">Backend-Derived Charts</h3></div><div className="grid gap-4 xl:grid-cols-2">{sr.map(s => <LinePlot key={`${s.path}:${s.xKey}:${s.yKey}`} s={s}/>)}</div></div>}
    {tb.length > 0 && <div className="data-card p-4"><div className="mb-3 flex items-center gap-2"><TableIcon className="h-4 w-4 text-accent-purple"/><h3 className="text-sm font-semibold text-text-primary">Returned Tables and Series</h3></div><div className="space-y-3">{tb.map(t => <ResultTable key={t.path} t={t}/>)}</div></div>}
    <div className="data-card p-4"><details><summary className="flex cursor-pointer items-center gap-2 text-sm font-semibold text-text-primary"><FileCode className="h-4 w-4 text-accent-amber"/>Raw Scientific Payload</summary><p className="mt-2 text-[11px] text-text-muted">Lossless source for values shown above. Nested fields remain available even when they are not meaningful as a chart.</p><pre className="mt-3 max-h-[700px] overflow-auto rounded-lg border border-glass-border bg-surface-1 p-4 text-[11px] leading-relaxed text-text-secondary">{raw}</pre></details></div>
  </div>;
}

export function ScientificDataSurface() {
  const [captures, setCaptures] = useState<Capture[]>([]);
  const [target, setTarget] = useState<Element | null>(null);
  const [path, setPath] = useState('');

  useEffect(() => {
    setPath(window.location.pathname);
    let lastPath = window.location.pathname;
    const routeTimer = window.setInterval(() => {
      if (window.location.pathname !== lastPath) {
        lastPath = window.location.pathname;
        setPath(lastPath);
        setCaptures([]);
      }
    }, 500);
    return () => window.clearInterval(routeTimer);
  }, []);

  useEffect(() => {
    const commit = (url: string, data: unknown) => {
      if (!url.includes('/api/backend') || excluded(url) || !scientific(data)) return;
      const payload = unwrap(data);
      const key = endpointKey(url);
      setCaptures(prev => {
        const next = prev.filter(item => item.key !== key);
        next.push({ key, url, at: new Date().toISOString(), payload });
        return next.slice(-8);
      });
    };

    const originalFetch = window.fetch;
    window.fetch = async (...args) => {
      const response = await originalFetch(...args);
      try {
        const requestUrl = typeof args[0] === 'string' ? args[0] : args[0] instanceof URL ? args[0].toString() : args[0].url;
        const ct = response.headers.get('content-type') || '';
        if (requestUrl.includes('/api/backend') && ct.includes('application/json')) {
          response.clone().json().then(data => commit(requestUrl, data)).catch(() => undefined);
        }
      } catch { /* observational only */ }
      return response;
    };

    const XHR = window.XMLHttpRequest;
    const originalOpen = XHR.prototype.open;
    const originalSend = XHR.prototype.send;
    const urls = new WeakMap<XMLHttpRequest, string>();
    XHR.prototype.open = function(method: string, url: string | URL, ...rest: unknown[]) {
      urls.set(this, String(url));
      return (originalOpen as unknown as (...a: unknown[]) => void).apply(this, [method, url, ...rest]);
    } as typeof originalOpen;
    XHR.prototype.send = function(body?: Document | XMLHttpRequestBodyInit | null) {
      this.addEventListener('load', () => {
        try {
          const url = urls.get(this) || '';
          if (!url.includes('/api/backend')) return;
          const ct = this.getResponseHeader('content-type') || '';
          if (!ct.includes('application/json')) return;
          const data = typeof this.response === 'object' && this.response !== null ? this.response : JSON.parse(this.responseText);
          commit(url, data);
        } catch { /* observational only */ }
      });
      return (originalSend as unknown as (...a: unknown[]) => void).apply(this, [body]);
    } as typeof originalSend;

    return () => {
      window.fetch = originalFetch;
      XHR.prototype.open = originalOpen;
      XHR.prototype.send = originalSend;
    };
  }, [path]);

  useEffect(() => {
    if (!captures.length) { setTarget(null); return; }
    const locate = () => {
      const anchors = Array.from(document.querySelectorAll(RESULT_ANCHORS));
      const visible = anchors.reverse().find(el => (el as HTMLElement).offsetParent !== null);
      setTarget(visible || document.querySelector('main'));
    };
    locate();
    const t = window.setInterval(locate, 800);
    return () => window.clearInterval(t);
  }, [captures.length, path]);

  if (!captures.length || !target) return null;
  return createPortal(<section className="mt-6 space-y-5" data-scientific-data-surface="true">
    <div className="data-card overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-glass-border p-5"><div className="flex items-start gap-3"><Database className="mt-0.5 h-5 w-5 text-accent-cyan"/><div><h2 className="text-base font-semibold text-text-primary">Complete Scientific Backend Data</h2><p className="mt-1 text-xs text-text-muted">All captured scientific responses for this analysis are preserved below as metrics, scientifically appropriate plots, tables and raw machine-readable data.</p></div></div><span className="rounded border border-glass-border px-2 py-1 text-[10px] text-text-muted">{captures.length} scientific response{captures.length === 1 ? '' : 's'}</span></div>
      <div className="flex gap-2 px-5 py-3 text-xs text-text-secondary"><WarningCircle className="mt-0.5 h-4 w-4 shrink-0 text-accent-amber"/><p>No measurement is invented by this layer. Charts require an explicit backend coordinate/index field such as time, step, frame, position, residue, rank or mode. Missing output is not treated as a negative biological finding. Computational results remain distinct from experimental validation.</p></div>
    </div>
    {captures.map(c => <PayloadPanel key={c.key} capture={c}/>)}
  </section>, target);
}

'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { RnaSeqArtifact } from '@/lib/rnaseqExpressionApi';
import { evidencePoints, loadPlotEvidence, type EvidencePoint, type PlotRow } from '@/lib/rnaseqPlotData';

const palette = ['#2f6b75', '#b35c44', '#75644c', '#5b6573', '#7b627a', '#486b5a'];
type Bounds = { xmin: number; xmax: number; ymin: number; ymax: number };
const left = 64, right = 20, top = 20, bottom = 52;

function extent(points: EvidencePoint[]): Bounds {
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
  for (const p of points) { xmin = Math.min(xmin, p.x); xmax = Math.max(xmax, p.x); ymin = Math.min(ymin, p.y); ymax = Math.max(ymax, p.y); }
  const dx = (xmax - xmin || 1) * .07, dy = (ymax - ymin || 1) * .07;
  return { xmin: xmin - dx, xmax: xmax + dx, ymin: ymin - dy, ymax: ymax + dy };
}

/** Draw every finite emitted point without SVG element counts or downsampling. */
export function RnaSeqInteractivePlot({ artifact, kind, condition, variance, alpha, lfc }: {
  artifact: RnaSeqArtifact; kind: 'pca' | 'volcano'; condition: string;
  variance?: { PC1: number; PC2: number }; alpha?: number; lfc?: number;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [rows, setRows] = useState<PlotRow[] | null>(null);
  const [error, setError] = useState('');
  const [colourBy, setColourBy] = useState(kind === 'pca' ? condition : 'direction');
  const [query, setQuery] = useState('');
  const [hidden, setHidden] = useState<string[]>([]);
  const [selected, setSelected] = useState<EvidencePoint | null>(null);
  const [view, setView] = useState<Bounds | null>(null);
  const [size, setSize] = useState({ width: 700, height: 400 });
  const [showTable, setShowTable] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    void loadPlotEvidence(artifact, controller.signal).then(data => { if (!controller.signal.aborted) setRows(data); }).catch(err => { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Plot evidence could not load.'); });
    return () => controller.abort();
  }, [artifact]);
  useEffect(() => {
    if (!canvas.current) return;
    const observer = new ResizeObserver(entries => setSize({ width: entries[0].contentRect.width, height: 400 }));
    observer.observe(canvas.current);
    return () => observer.disconnect();
  }, [rows]);
  const parsed = useMemo(() => {
    try { return { ...evidencePoints(rows ?? [], kind, colourBy), error: '' }; }
    catch (err) { return { points: [], excluded: 0, error: err instanceof Error ? err.message : 'Invalid plot evidence.' }; }
  }, [rows, kind, colourBy]);
  const groups = useMemo(() => [...new Set(parsed.points.map(p => p.group))].sort(), [parsed.points]);
  const visible = useMemo(() => parsed.points.filter(p => !hidden.includes(p.group)), [parsed.points, hidden]);
  const matches = useMemo(() => query.trim() ? visible.filter(p => p.id.toLowerCase().includes(query.trim().toLowerCase())) : [], [visible, query]);
  const bounds = view ?? (parsed.points.length ? extent(parsed.points) : { xmin: -1, xmax: 1, ymin: -1, ymax: 1 });
  const xpixel = (x: number) => left + (x - bounds.xmin) / (bounds.xmax - bounds.xmin) * (size.width - left - right);
  const ypixel = (y: number) => top + (bounds.ymax - y) / (bounds.ymax - bounds.ymin) * (size.height - top - bottom);
  useEffect(() => {
    const el = canvas.current, ctx = el?.getContext('2d');
    if (!el || !ctx) return;
    const ratio = window.devicePixelRatio || 1;
    el.width = size.width * ratio; el.height = size.height * ratio;
    ctx.scale(ratio, ratio); ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, size.width, size.height);
    const px = (x: number) => left + (x - bounds.xmin) / (bounds.xmax - bounds.xmin) * (size.width - left - right);
    const py = (y: number) => top + (bounds.ymax - y) / (bounds.ymax - bounds.ymin) * (size.height - top - bottom);
    ctx.font = '11px sans-serif'; ctx.fillStyle = '#334155'; ctx.strokeStyle = '#d9e1e7';
    for (let i = 0; i <= 5; i++) {
      const x = bounds.xmin + (bounds.xmax - bounds.xmin) * i / 5, y = bounds.ymin + (bounds.ymax - bounds.ymin) * i / 5;
      ctx.beginPath(); ctx.moveTo(px(x), top); ctx.lineTo(px(x), size.height - bottom); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(left, py(y)); ctx.lineTo(size.width - right, py(y)); ctx.stroke();
      ctx.textAlign = 'center'; ctx.fillText(x.toPrecision(3), px(x), size.height - bottom + 18);
      ctx.textAlign = 'right'; ctx.fillText(y.toPrecision(3), left - 8, py(y) + 4);
    }
    ctx.save(); ctx.beginPath(); ctx.rect(left, top, size.width - left - right, size.height - top - bottom); ctx.clip();
    if (kind === 'volcano' && alpha !== undefined && lfc !== undefined) {
      ctx.strokeStyle = '#64748b'; ctx.setLineDash([4, 4]);
      for (const x of [-lfc, lfc]) { ctx.beginPath(); ctx.moveTo(px(x), top); ctx.lineTo(px(x), size.height - bottom); ctx.stroke(); }
      ctx.beginPath(); ctx.moveTo(left, py(-Math.log10(alpha))); ctx.lineTo(size.width - right, py(-Math.log10(alpha))); ctx.stroke(); ctx.setLineDash([]);
    }
    const matching = new Set(matches.map(p => p.id));
    for (const p of visible) {
      ctx.globalAlpha = query && !matching.has(p.id) ? .12 : kind === 'volcano' ? .6 : .85;
      ctx.fillStyle = palette[groups.indexOf(p.group) % palette.length];
      ctx.beginPath(); ctx.arc(px(p.x), py(p.y), kind === 'pca' ? 5 : 2, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
    for (const p of selected ? [selected] : matches.slice(0, 20)) {
      ctx.strokeStyle = '#0f172a'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(px(p.x), py(p.y), 7, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = '#0f172a'; ctx.textAlign = 'left'; ctx.fillText(p.id, px(p.x) + 9, py(p.y) - 6);
    }
    ctx.restore(); ctx.textAlign = 'center'; ctx.fillStyle = '#334155';
    ctx.fillText(kind === 'pca' ? `PC1 (${variance?.PC1 ?? '—'}%)` : 'log2 fold change', (left + size.width - right) / 2, size.height - 9);
    ctx.save(); ctx.translate(14, (top + size.height - bottom) / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillText(kind === 'pca' ? `PC2 (${variance?.PC2 ?? '—'}%)` : '-log10 adjusted p-value', 0, 0); ctx.restore();
  }, [visible, matches, selected, groups, bounds.xmin, bounds.xmax, bounds.ymin, bounds.ymax, size, kind, alpha, lfc, query, variance]);
  const zoom = (factor: number) => {
    const cx = selected?.x ?? (bounds.xmin + bounds.xmax) / 2, cy = selected?.y ?? (bounds.ymin + bounds.ymax) / 2;
    const dx = (bounds.xmax - bounds.xmin) * factor / 2, dy = (bounds.ymax - bounds.ymin) * factor / 2;
    if (dx > 1e-10 && dy > 1e-10 && dx < 1e12 && dy < 1e12) setView({ xmin: cx - dx, xmax: cx + dx, ymin: cy - dy, ymax: cy + dy });
  };
  const fields = rows?.length ? Object.keys(rows[0]).filter(k => !['sample', 'PC1', 'PC2', 'name', 'group'].includes(k)) : [];
  const problem = error || parsed.error;
  if (problem) return <p role="alert" className="p-4 text-xs text-error">{problem} Use the original R figure and TSV below.</p>;
  if (!rows) return <p role="status" className="p-4 text-xs text-text-muted">Loading and verifying plot evidence…</p>;
  if (!parsed.points.length) return <p className="p-4 text-xs text-text-muted">No finite points were emitted for this plot. Missing values remain missing.</p>;
  return <div className="space-y-3 rounded-xl border border-glass-border p-4">
    <h4 className="text-sm font-semibold">Interactive {kind === 'pca' ? 'PCA' : 'volcano'}</h4>
    <div className="flex flex-wrap items-end gap-3 text-xs">
      <label>Find {kind === 'pca' ? 'sample' : 'gene'}<input aria-label={`Find ${kind === 'pca' ? 'sample' : 'gene'}`} className="ml-2 rounded border border-glass-border bg-surface-1 px-2 py-1" value={query} onChange={e => { setQuery(e.target.value); setSelected(null); }} /></label>
      {kind === 'pca' && <label>Colour by<select aria-label="PCA colour by" className="ml-2 rounded border border-glass-border bg-surface-1 px-2 py-1" value={colourBy} onChange={e => { setColourBy(e.target.value); setHidden([]); setSelected(null); }}>{fields.map(k => <option key={k} value={k}>{k}</option>)}</select></label>}
      <button type="button" onClick={() => zoom(.5)} className="rounded border border-glass-border px-2 py-1">Zoom in</button>
      <button type="button" onClick={() => zoom(2)} className="rounded border border-glass-border px-2 py-1">Zoom out</button>
      <button type="button" onClick={() => { setView(null); setHidden([]); setQuery(''); setSelected(null); }} className="rounded border border-glass-border px-2 py-1">Reset view</button>
    </div>
    <div className="flex max-h-24 flex-wrap gap-3 overflow-auto text-xs">{groups.map((g, i) => <label key={g} style={{ color: palette[i % palette.length] }}><input type="checkbox" checked={!hidden.includes(g)} onChange={e => { setHidden(e.target.checked ? hidden.filter(x => x !== g) : [...hidden, g]); setSelected(null); }} /> {g}</label>)}</div>
    <canvas ref={canvas} style={{ width: '100%', height: 400 }} role="img" aria-label={`${kind} scatter plot. Search and evidence table provide access to every plotted point.`} onClick={event => {
      const rect = event.currentTarget.getBoundingClientRect(), x = event.clientX - rect.left, y = event.clientY - rect.top;
      let best: EvidencePoint | null = null, distance = 100;
      for (const p of visible) {
        const px = xpixel(p.x), py = ypixel(p.y);
        if (px < left || px > size.width - right || py < top || py > size.height - bottom) continue;
        const d = (px - x) ** 2 + (py - y) ** 2;
        if (d < distance) { best = p; distance = d; }
      }
      setSelected(best);
    }} />
    <p className="text-xs text-text-muted">{visible.length.toLocaleString()} of {parsed.points.length.toLocaleString()} finite points enabled. {parsed.excluded} rows excluded for missing or invalid coordinates. All points come from checksum-verified R output. Click a point or search, then zoom to inspect it.</p>
    {query && <p role="status" className="text-xs">{matches.length.toLocaleString()} matching identifiers. <select aria-label="Select matching point" value={selected?.id ?? ''} onChange={e => setSelected(matches.find(p => p.id === e.target.value) ?? null)} className="ml-2 max-w-xs rounded border border-glass-border bg-surface-1 px-2 py-1"><option value="">Choose a point</option>{matches.slice(0, 100).map(p => <option key={p.id} value={p.id}>{p.id}</option>)}</select>{matches.length > 100 && ' Refine your search to narrow the selection.'}</p>}
    {selected && <dl className="flex flex-wrap gap-x-5 gap-y-2 text-xs" aria-live="polite">{Object.entries(selected.row).map(([k, v]) => <div key={k}><dt className="text-text-muted">{k}</dt><dd className="font-mono">{v || 'Missing'}</dd></div>)}</dl>}
    <button type="button" onClick={() => setShowTable(!showTable)} aria-expanded={showTable} className="text-xs text-accent-cyan">{showTable ? 'Hide' : 'Show'} accessible evidence table</button>
    {showTable && <div className="max-h-64 overflow-auto"><table className="w-full whitespace-nowrap text-left text-xs"><thead><tr><th className="px-2 py-1">Identifier</th><th className="px-2 py-1">X</th><th className="px-2 py-1">Y</th><th className="px-2 py-1">{colourBy}</th></tr></thead><tbody>{(query ? matches : visible).slice(0, 100).map(p => <tr key={p.id}><td className="px-2 py-1"><button type="button" onClick={() => setSelected(p)} className="text-accent-cyan">{p.id}</button></td><td className="px-2 py-1">{p.x.toPrecision(6)}</td><td className="px-2 py-1">{p.y.toPrecision(6)}</td><td className="px-2 py-1">{p.group}</td></tr>)}</tbody></table><p>First 100 matching rows, coordinates shown to six significant digits. Scroll for more columns. Select a row for full precision, search for any identifier or download the complete TSV.</p></div>}
  </div>;
}

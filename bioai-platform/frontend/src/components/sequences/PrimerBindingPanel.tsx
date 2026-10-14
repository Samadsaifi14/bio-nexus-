'use client';

import { useEffect, useRef, useState } from 'react';
import { longApi } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';

type BindingMap = {
  length: number; topology: string; coordinate_convention: string; assumptions: string; diagnostics: string[];
  sites: Array<{ primer: string; strand: number; start: number; end: number; spans_origin: boolean; three_prime_position: number }>;
  products: Array<{ start: number; end: number; length: number; spans_origin: boolean; plus_primer: string; minus_primer: string; sha256: string }>;
};

export function PrimerBindingPanel({ sequence, circular }: { sequence: string; circular: boolean }) {
  const [forward, setForward] = useState('');
  const [reverse, setReverse] = useState('');
  const [minimum, setMinimum] = useState(1);
  const [maximum, setMaximum] = useState(200000);
  const [result, setResult] = useState<BindingMap | null>(null);
  const [evidence, setEvidence] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const key = JSON.stringify({ sequence, circular, forward, reverse, minimum, maximum });
  const latest = useRef(key);
  latest.current = key;
  useEffect(() => { setResult(null); setEvidence(null); setError(''); }, [key]);
  async function run() {
    const submitted = key;
    setBusy(true); setError(''); setResult(null); setEvidence(null);
    try {
      const { data } = await longApi.post('/api/seq-tools/primer-binding-map', { sequence, circular, forward, reverse, min_product: minimum, max_product: maximum });
      if (latest.current !== submitted) return;
      setResult(data.results); setEvidence(data);
    } catch (err) { if (latest.current === submitted) setError(extractErrorMessage(err, 'Primer mapping failed')); }
    finally { setBusy(false); }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(evidence, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'primer-binding-evidence.json'; anchor.click(); URL.revokeObjectURL(url);
  }
  async function exportGenBank() {
    if (!result) return;
    const submitted = key;
    setBusy(true); setError('');
    try {
      const features = result.sites.map(s => ({ label: `${s.primer} primer (exact match)`, start: s.start, end: s.end, strand: s.strand, type: 'primer_bind' }));
      const { data } = await longApi.post('/api/seq-tools/annotated-genbank', { sequence, circular, name: 'BioNexus_primer_map', features, enzymes: [] });
      if (latest.current !== submitted) return;
      const url = URL.createObjectURL(new Blob([data.results.genbank], { type: 'text/plain' }));
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = data.results.filename; anchor.click(); URL.revokeObjectURL(url);
    } catch (err) { if (latest.current === submitted) setError(extractErrorMessage(err, 'Primer GenBank export failed')); }
    finally { setBusy(false); }
  }
  return <details className="space-y-3">
    <summary className="text-sm cursor-pointer">Primer binding and predicted amplicons</summary>
    <p className="text-xs text-text-secondary">Enter both primers in 5′ to 3′ direction. Uses the DNA and topology selected above. Exact full-length matches only; use primer QC separately for thermodynamics.</p>
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="text-sm">Forward primer (5′→3′)<input className="block w-full border border-glass-border rounded p-2 bg-transparent font-mono" value={forward} onChange={e => setForward(e.target.value)} /></label>
      <label className="text-sm">Reverse primer (5′→3′)<input className="block w-full border border-glass-border rounded p-2 bg-transparent font-mono" value={reverse} onChange={e => setReverse(e.target.value)} /></label>
      <label className="text-sm">Minimum product (bp)<input type="number" min={1} max={200000} className="block w-full border border-glass-border rounded p-2 bg-transparent" value={minimum} onChange={e => setMinimum(Number(e.target.value))} /></label>
      <label className="text-sm">Maximum product (bp)<input type="number" min={1} max={200000} className="block w-full border border-glass-border rounded p-2 bg-transparent" value={maximum} onChange={e => setMaximum(Number(e.target.value))} /></label>
    </div>
    <button disabled={busy || !sequence.trim() || !forward.trim() || !reverse.trim()} className="px-3 py-2 rounded border border-glass-border text-sm" onClick={run}>{busy ? 'Mapping primers…' : 'Map primers'}</button>
    {error && <p role="alert" className="text-sm text-error">{error}</p>}
    {result && <div className="space-y-3">
      <p className="text-sm">{result.length} bp · {result.topology} · {result.sites.length} binding orientations · {result.products.length} candidate products</p>
      {result.diagnostics.map(d => <p key={d} className="text-sm">{d}</p>)}
      <div className="overflow-x-auto"><table className="w-full text-xs"><caption className="text-left">Exact binding sites</caption><thead><tr>{['Primer', 'Strand', 'Start–end', '3′ position'].map(h => <th key={h} className="p-2 text-left">{h}</th>)}</tr></thead><tbody>{result.sites.map((s, i) => <tr key={i}><td className="p-2">{s.primer}</td><td className="p-2">{s.strand === 1 ? '+' : '−'}</td><td className="p-2">{s.start}–{s.end}{s.spans_origin ? ' (origin)' : ''}</td><td className="p-2">{s.three_prime_position}</td></tr>)}</tbody></table></div>
      <div className="overflow-x-auto"><table className="w-full text-xs"><caption className="text-left">Predicted linear PCR products</caption><thead><tr>{['Start–end', 'Length (bp)', 'Plus / minus primer'].map(h => <th key={h} className="p-2 text-left">{h}</th>)}</tr></thead><tbody>{result.products.map((p, i) => <tr key={i}><td className="p-2">{p.start}–{p.end}{p.spans_origin ? ' (origin)' : ''}</td><td className="p-2">{p.length}</td><td className="p-2">{p.plus_primer} / {p.minus_primer}</td></tr>)}</tbody></table></div>
      <p className="text-xs text-text-muted">{result.coordinate_convention}</p>
      <p className="text-xs text-text-muted">{result.assumptions}</p>
      <button className="text-sm underline" onClick={download}>Download primer map evidence JSON</button>
      <button className="block text-sm underline" disabled={busy} onClick={exportGenBank}>Download DNA with mapped primer features (.gb)</button>
    </div>}
  </details>;
}

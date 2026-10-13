'use client';

import { useEffect, useRef, useState } from 'react';
import { longApi } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';

const ENZYMES = ['EcoRI', 'BamHI', 'HindIII', 'SalI', 'XbaI', 'XhoI', 'NotI', 'KpnI', 'SmaI', 'PstI', 'SacI', 'BsaI', 'BsmBI'];
type MapResult = {
  length: number; topology: string; cut_boundaries: number[]; fragment_lengths: number[]; product_topology: string;
  coordinate_convention: string; digest_assumptions: string;
  provenance: { source: string; version: string; source_url: string };
  sites: Array<{ enzyme: string; recognition: string; start: number; end: number; strand: string; spans_origin: boolean; top_cut_boundary: number; bottom_cut_boundary: number; complete_cut: boolean }>;
};

export function RestrictionMapPanel({ sequence }: { sequence: string }) {
  const [selected, setSelected] = useState(['EcoRI', 'BamHI', 'HindIII']);
  const [circular, setCircular] = useState(true);
  const [result, setResult] = useState<MapResult | null>(null);
  const [evidence, setEvidence] = useState<unknown>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const inputKey = JSON.stringify({ sequence, enzymes: selected, circular });
  const latestInput = useRef(inputKey);
  latestInput.current = inputKey;
  useEffect(() => { setResult(null); setEvidence(null); setError(''); }, [inputKey]);
  async function run() {
    const submittedInput = inputKey;
    setBusy(true); setError(''); setResult(null); setEvidence(null);
    try {
      const { data } = await longApi.post('/api/seq-tools/restriction-map', { sequence, enzymes: selected, circular });
      if (latestInput.current !== submittedInput) return;
      setEvidence(data); setResult(data.results);
    } catch (err) { if (latestInput.current === submittedInput) setError(extractErrorMessage(err, 'Restriction map failed')); }
    finally { setBusy(false); }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(evidence, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'restriction-map-evidence.json'; anchor.click(); URL.revokeObjectURL(url);
  }
  return <section className="data-card p-5 space-y-4">
    <h2 className="font-medium text-text-primary">Restriction sites and plasmid map</h2>
    <p className="text-sm text-text-secondary">Paste unambiguous DNA above, select enzymes and choose topology. This computes recognition sites and complete-digest fragments.</p>
    <label className="flex gap-2 text-sm"><input type="checkbox" checked={circular} onChange={e => setCircular(e.target.checked)} />Circular DNA / plasmid</label>
    <fieldset className="flex flex-wrap gap-3"><legend className="text-xs text-text-muted mb-2">Supported enzymes</legend>{ENZYMES.map(name => <label key={name} className="flex gap-1 text-xs"><input type="checkbox" checked={selected.includes(name)} onChange={e => setSelected(e.target.checked ? [...selected, name] : selected.filter(n => n !== name))} />{name}</label>)}</fieldset>
    <button className="px-3 py-2 rounded border border-glass-border text-sm" disabled={busy || !sequence.trim() || !selected.length} onClick={run}>{busy ? 'Mapping…' : 'Build restriction map'}</button>
    {error && <p role="alert" className="text-sm text-error">{error}</p>}
    {result && <div className="space-y-3">
      <p className="text-sm">{result.length} bp · {result.topology} input · {result.sites.length} recognition sites · {result.product_topology} products</p>
      {result.topology === 'circular' && <svg viewBox="0 0 360 360" className="w-full max-w-sm mx-auto" role="img" aria-label={`Circular restriction map of ${result.length} bases with ${result.cut_boundaries.length} cut boundaries`}>
        <circle cx="180" cy="180" r="120" fill="none" stroke="currentColor" strokeWidth="2" />
        <text x="180" y="180" textAnchor="middle" fill="currentColor">{result.length} bp</text>
        {result.cut_boundaries.map((cut, i) => { const angle = 2 * Math.PI * cut / result.length - Math.PI / 2; return <g key={cut}><line x1={180 + 110 * Math.cos(angle)} y1={180 + 110 * Math.sin(angle)} x2={180 + 130 * Math.cos(angle)} y2={180 + 130 * Math.sin(angle)} stroke="currentColor" /><text x={180 + 148 * Math.cos(angle)} y={180 + 148 * Math.sin(angle)} fontSize="10" textAnchor="middle" fill="currentColor">{i + 1}: {cut}</text></g>; })}
      </svg>}
      <p className="text-sm">Fragment lengths (bp): {result.fragment_lengths.join(', ')}</p>
      <div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr>{['Enzyme', 'Recognition start–end', 'Strand', 'Top / bottom cut', 'Complete cut'].map(h => <th key={h} className="p-2 text-left">{h}</th>)}</tr></thead><tbody>{result.sites.map((s, i) => <tr key={i}><td className="p-2">{s.enzyme}</td><td className="p-2">{s.start}–{s.end}{s.spans_origin ? ' (origin)' : ''}</td><td className="p-2">{s.strand}</td><td className="p-2">{s.top_cut_boundary} / {s.bottom_cut_boundary}</td><td className="p-2">{s.complete_cut ? 'Yes' : 'Outside linear DNA'}</td></tr>)}</tbody></table></div>
      <p className="text-xs text-text-muted">{result.coordinate_convention}</p><p className="text-xs text-text-muted">{result.digest_assumptions}</p>
      <p className="text-xs text-text-muted">Definitions: <a href={result.provenance.source_url} target="_blank" rel="noreferrer">{result.provenance.source}</a> v{result.provenance.version}. In-silico restriction map; no cloning simulation or experimental validation.</p>
      <button onClick={download} className="text-sm underline">Download evidence JSON</button>
    </div>}
  </section>;
}

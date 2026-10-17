'use client';
import { useState } from 'react';
import { longApi } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import { BlastPanel } from './BlastPanel';
import type { BlastHitSummary } from '@/types/pipeline';

type Result = { hits: BlastHitSummary[]; count: number; source: string; engine_version: string;
  reference_records: number; provenance: Record<string, string>; claim: string };

export function LocalSimilarityPanel({ query, exampleReference, protein }: { query: string; exampleReference: string; protein: boolean }) {
  const [reference, setReference] = useState(exampleReference);
  const [saved, setSaved] = useState<{ query: string; data: Result } | null>(null);
  const result = saved?.query === query ? saved.data : null;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function run() {
    setBusy(true); setError(''); setSaved(null);
    try {
      const trimmed = query.trim();
      const response = await longApi.post<Result>('/api/similarity/custom-protein-database', {
        query_fasta: trimmed.startsWith('>') ? trimmed : `>query\n${trimmed}`,
        reference_fasta: reference, max_hits: 20,
      });
      setSaved({ query, data: response.data });
    } catch (caught) { setError(extractErrorMessage(caught, 'Custom database search failed')); }
    finally { setBusy(false); }
  }
  function exportResult() {
    if (!result) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'diamond-custom-search.json'; anchor.click(); URL.revokeObjectURL(url);
  }
  return <details className="data-card p-5 space-y-3">
    <summary className="cursor-pointer font-medium">Search your own protein reference · DIAMOND</summary>
    <p className="text-sm text-text-secondary">Run a real protein similarity search against the FASTA reference below. The preloaded reference contains only the two example proteins; replace it with your own database to search other sequences. This is separate from the NCBI/EBI search.</p>
    <label htmlFor="custom-protein-reference" className="block text-sm">Protein reference FASTA</label>
    <textarea id="custom-protein-reference" rows={6} disabled={busy} value={reference} onChange={event => { setReference(event.target.value); setSaved(null); }} className="w-full rounded border border-glass-border bg-surface-1 p-3 text-xs font-mono" />
    <p className="text-xs text-text-muted">Up to 5,000 proteins and 1,000,000 residues. Very-sensitive alignment; E-value threshold 0.001. Query: the protein entered above.</p>
    <button type="button" disabled={busy || !protein || !query.trim() || !reference.trim()} onClick={run} className="btn-primary disabled:opacity-40">{busy ? 'DIAMOND is building the database and searching…' : 'Run custom protein search'}</button>
    {!protein && <p className="text-xs text-text-secondary">Load or retrieve a protein query above to use this engine.</p>}
    {error && <p role="alert" className="text-sm text-error">{error}</p>}
    {result && <div className="space-y-3">
      <p className="text-xs text-text-secondary">{result.engine_version} · {result.reference_records} reference proteins · {result.claim}</p>
      <BlastPanel hits={result.hits} count={result.count} source={result.source} />
      <button type="button" onClick={exportResult} className="text-sm underline">Export hits, parameters and input/engine checksums</button>
    </div>}
  </details>;
}

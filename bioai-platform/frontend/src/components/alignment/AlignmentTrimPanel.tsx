'use client';
import { useState } from 'react';
import { trimAlignmentColumns, type AlignmentTrimResult } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';

export default function AlignmentTrimPanel() {
  const [fasta, setFasta] = useState('');
  const [molecule, setMolecule] = useState<'dna' | 'rna' | 'protein'>('protein');
  const [mode, setMode] = useState<'all_gap' | 'any_gap' | 'gap_percent'>('all_gap');
  const [percent, setPercent] = useState(50);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<AlignmentTrimResult | null>(null);
  const download = (name: string, value: string) => {
    const url = URL.createObjectURL(new Blob([value], { type: 'text/plain;charset=utf-8' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = name; anchor.click(); URL.revokeObjectURL(url);
  };
  const run = async () => {
    setBusy(true); setError(''); setResult(null);
    try { setResult((await trimAlignmentColumns(fasta, molecule, mode, percent)).results); }
    catch (e) { setError(extractErrorMessage(e, 'Column filtering failed')); }
    finally { setBusy(false); }
  };
  return <section className="data-card p-5 mt-6 space-y-4" aria-label="Alignment column filtering">
    <h2 className="text-lg font-semibold">Filter alignment columns</h2>
    <p className="text-sm text-text-muted">Paste an existing equal-width alignment. Canonical DNA, RNA or protein residues and hyphen gaps are accepted. Original alignment results stay intact; this operation does not realign sequences.</p>
    <label className="block text-sm">Aligned FASTA<textarea rows={6} value={fasta} onChange={e => setFasta(e.target.value)} className="block w-full bg-transparent border border-glass-border rounded p-2 font-mono mt-1" /></label>
    <div className="flex flex-wrap gap-4">
      <label className="text-sm">Molecule<select value={molecule} onChange={e => setMolecule(e.target.value as typeof molecule)} className="block bg-transparent border rounded p-2"><option value="protein">Protein</option><option value="dna">DNA</option><option value="rna">RNA</option></select></label>
      <label className="text-sm">Remove columns<select value={mode} onChange={e => setMode(e.target.value as typeof mode)} className="block bg-transparent border rounded p-2"><option value="all_gap">All residues are gaps (default)</option><option value="any_gap">At least one gap</option><option value="gap_percent">At least a chosen gap percentage</option></select></label>
      {mode === 'gap_percent' && <label className="text-sm">Gap threshold (%)<input type="number" min="0.01" max="100" step="0.01" value={percent} onChange={e => setPercent(Number(e.target.value))} className="block bg-transparent border rounded p-2 w-24" /></label>}
    </div>
    {mode !== 'all_gap' && <p className="text-sm">This policy can delete real residues and alter downstream phylogenetic or other inference. Review the exported column mask.</p>}
    <button disabled={busy || !fasta.trim()} onClick={run} className="border border-glass-border rounded px-3 py-2 disabled:opacity-50">{busy ? 'Filtering…' : 'Filter columns'}</button>
    {error && <p role="alert">{error}</p>}
    {result && <div className="space-y-3"><p>{result.mask.record_count} records · {result.mask.input_width} → {result.mask.output_width} columns · {result.mask.dropped_columns.length} columns removed · {result.mask.residues_removed} residues removed</p><p className="text-sm">{result.warning}</p><p className="text-xs text-text-muted">{result.mask.coordinate_convention}</p><div className="flex gap-4"><button className="underline" onClick={() => download('trimmed-alignment.fasta', result.trimmed_fasta)}>Download trimmed FASTA</button><button className="underline" onClick={() => download('alignment-column-mask.json', JSON.stringify(result.mask, null, 2))}>Download column mask and checksums</button></div></div>}
  </section>;
}

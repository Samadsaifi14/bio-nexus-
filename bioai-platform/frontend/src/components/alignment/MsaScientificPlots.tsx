'use client';

import { useMemo } from 'react';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { DownloadSimple as Download } from '@phosphor-icons/react';
import { downloadTsv } from '@/lib/export-utils';

const GAP = new Set(['-', '.']);

function columnStats(seqs: string[]) {
  if (!seqs.length) return [];
  const L = Math.max(...seqs.map(s => s.length));
  const n = seqs.length;
  return Array.from({ length: L }, (_, i) => {
    const chars = seqs.map(s => (s[i] ?? '-').toUpperCase());
    const nongap = chars.filter(c => !GAP.has(c));
    const counts = new Map<string, number>();
    nongap.forEach(c => counts.set(c, (counts.get(c) ?? 0) + 1));
    const max = counts.size ? Math.max(...Array.from(counts.values())) : 0;
    const conservation = nongap.length ? max / nongap.length : 0;
    let entropy = 0;
    if (nongap.length) {
      for (const count of Array.from(counts.values())) {
        const p = count / nongap.length;
        entropy -= p * Math.log2(p);
      }
    }
    const gapFraction = chars.filter(c => GAP.has(c)).length / n;
    return { position: i + 1, conservation, entropy, gapFraction };
  });
}

function pairIdentity(a: string, b: string): number | null {
  const L = Math.max(a.length, b.length);
  let comparable = 0;
  let same = 0;
  for (let i = 0; i < L; i++) {
    const x = (a[i] ?? '-').toUpperCase();
    const y = (b[i] ?? '-').toUpperCase();
    if (GAP.has(x) || GAP.has(y)) continue;
    comparable++;
    if (x === y) same++;
  }
  return comparable ? same / comparable : null;
}

const tooltipStyle = { background: 'var(--chart-tooltip-bg)', border: '1px solid var(--chart-tooltip-border)', borderRadius: 8, fontSize: 12 };

export function MsaScientificPlots({ headers, alignedSeqs }: { headers: string[]; alignedSeqs: string[] }) {
  const columns = useMemo(() => columnStats(alignedSeqs), [alignedSeqs]);
  const matrix = useMemo(() => alignedSeqs.map((a, i) => alignedSeqs.map((b, j) => i === j ? 1 : pairIdentity(a, b))), [alignedSeqs]);
  if (alignedSeqs.length < 2 || columns.length === 0) return null;

  const avgEntropy = columns.reduce((s, c) => s + c.entropy, 0) / columns.length;
  const avgGap = columns.reduce((s, c) => s + c.gapFraction, 0) / columns.length;

  return (
    <div className="data-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">MSA scientific plots</h3>
          <p className="mt-1 text-xs text-text-muted">Entropy, gap fraction and pairwise identity are calculated directly from the returned aligned FASTA. No reference alignment is assumed here.</p>
        </div>
        <button onClick={() => downloadTsv(
          ['alignment_position', 'conservation_fraction', 'shannon_entropy_bits', 'gap_fraction'],
          columns.map(c => [String(c.position), String(c.conservation), String(c.entropy), String(c.gapFraction)]),
          'msa-column-statistics.tsv',
        )} className="btn-ghost flex items-center gap-1 px-2 py-1 text-xs"><Download className="h-3.5 w-3.5" /> Column TSV</button>
      </div>

      <div className="mt-3 flex flex-wrap gap-4 text-xs text-text-muted">
        <span>Mean entropy: <strong className="text-text-primary">{avgEntropy.toFixed(3)} bits</strong></span>
        <span>Mean gap fraction: <strong className="text-text-primary">{(avgGap * 100).toFixed(1)}%</strong></span>
        <span>Sequences: <strong className="text-text-primary">{alignedSeqs.length}</strong></span>
        <span>Columns: <strong className="text-text-primary">{columns.length}</strong></span>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-glass-border bg-surface-0 p-3">
          <h4 className="text-xs font-semibold text-text-primary">Shannon entropy by alignment column</h4>
          <p className="mt-1 text-[11px] text-text-muted">Lower entropy indicates a more compositionally conserved column; gaps are excluded from the residue distribution.</p>
          <div className="mt-2 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={columns} margin={{ left: 6, right: 12, top: 8, bottom: 12 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                <XAxis dataKey="position" label={{ value: 'Alignment position', position: 'insideBottom', offset: -6 }} />
                <YAxis label={{ value: 'Entropy (bits)', angle: -90, position: 'insideLeft' }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line type="monotone" dataKey="entropy" name="Entropy" stroke="#0891b2" dot={false} connectNulls={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-xl border border-glass-border bg-surface-0 p-3">
          <h4 className="text-xs font-semibold text-text-primary">Conservation and gap profile</h4>
          <p className="mt-1 text-[11px] text-text-muted">Conservation is the majority non-gap residue fraction; gap fraction is calculated across all sequences.</p>
          <div className="mt-2 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={columns} margin={{ left: 6, right: 12, top: 8, bottom: 12 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                <XAxis dataKey="position" label={{ value: 'Alignment position', position: 'insideBottom', offset: -6 }} />
                <YAxis domain={[0, 1]} label={{ value: 'Fraction', angle: -90, position: 'insideLeft' }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend />
                <Line type="monotone" dataKey="conservation" name="Conservation" stroke="#0891b2" dot={false} />
                <Line type="monotone" dataKey="gapFraction" name="Gap fraction" stroke="#64748b" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-xl border border-glass-border bg-surface-0 p-3 lg:col-span-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div><h4 className="text-xs font-semibold text-text-primary">Pairwise sequence identity matrix</h4><p className="mt-1 text-[11px] text-text-muted">Identity is calculated over columns where both sequences contain a non-gap residue.</p></div>
            <button onClick={() => downloadTsv(
              ['sequence', ...headers.map((h, i) => h || `seq_${i + 1}`)],
              matrix.map((row, i) => [headers[i] || `seq_${i + 1}`, ...row.map(v => v === null ? '' : String(v))]),
              'msa-pairwise-identity-matrix.tsv',
            )} className="btn-ghost flex items-center gap-1 px-2 py-1 text-xs"><Download className="h-3.5 w-3.5" /> Matrix TSV</button>
          </div>
          <div className="mt-3 overflow-auto">
            <table className="border-collapse text-[10px]">
              <thead><tr><th className="p-1 text-left text-text-muted">Sequence</th>{headers.map((h, i) => <th key={i} className="max-w-24 truncate p-1 font-mono text-text-muted" title={h}>{h || `seq_${i + 1}`}</th>)}</tr></thead>
              <tbody>{matrix.map((row, i) => <tr key={i}><th className="max-w-28 truncate p-1 text-left font-mono font-normal text-text-muted" title={headers[i]}>{headers[i] || `seq_${i + 1}`}</th>{row.map((value, j) => <td key={j} className="border border-glass-border p-1 text-center font-mono text-text-primary" style={{ background: value === null ? 'transparent' : `rgba(8,145,178,${0.08 + 0.72 * value})` }}>{value === null ? '—' : (value * 100).toFixed(1)}</td>)}</tr>)}</tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

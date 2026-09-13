'use client';

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { DownloadSimple as Download } from '@phosphor-icons/react';
import type { BlastHitSummary } from '@/types/pipeline';
import { downloadTsv } from '@/lib/export-utils';

function negLog10Evalue(value: number): number | null {
  if (!Number.isFinite(value) || value < 0) return null;
  if (value === 0) return 300;
  return Math.min(300, -Math.log10(value));
}

const tooltipStyle = {
  background: 'var(--chart-tooltip-bg)',
  border: '1px solid var(--chart-tooltip-border)',
  borderRadius: 8,
  fontSize: 12,
};

export function BlastScientificPlots({ hits }: { hits: BlastHitSummary[] | undefined | null }) {
  const safe = (hits ?? []).filter(h => Number.isFinite(h.identity_pct) || Number.isFinite(h.bit_score) || Number.isFinite(h.evalue));
  if (!safe.length) return null;

  const ranked = safe.map((h, i) => ({
    rank: i + 1,
    accession: h.accession,
    identity: Number.isFinite(h.identity_pct) ? h.identity_pct : null,
    coverage: Number.isFinite(h.query_coverage_pct ?? NaN) ? h.query_coverage_pct : null,
    bitScore: Number.isFinite(h.bit_score) ? h.bit_score : null,
    negLogE: negLog10Evalue(h.evalue),
    queryFrom: h.query_from ?? null,
    queryTo: h.query_to ?? null,
  }));
  const scatter = ranked.filter(d => d.identity !== null && d.coverage !== null);
  const coordinateHits = ranked.filter(d => typeof d.queryFrom === 'number' && typeof d.queryTo === 'number');

  return (
    <div className="data-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">BLAST scientific plots</h3>
          <p className="mt-1 text-xs text-text-muted">Plots are calculated only from the returned hit table. E-value 0 is represented as -log10(E)=300 for display and export, while the original E-value remains authoritative.</p>
        </div>
        <button
          onClick={() => downloadTsv(
            ['rank', 'accession', 'identity_pct', 'query_coverage_pct', 'bit_score', 'negative_log10_evalue', 'query_from', 'query_to'],
            ranked.map(d => [String(d.rank), d.accession, String(d.identity ?? ''), String(d.coverage ?? ''), String(d.bitScore ?? ''), String(d.negLogE ?? ''), String(d.queryFrom ?? ''), String(d.queryTo ?? '')]),
            'blast-plot-source.tsv',
          )}
          className="btn-ghost flex items-center gap-1 px-2 py-1 text-xs"
        ><Download className="h-3.5 w-3.5" /> Plot source TSV</button>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {scatter.length > 0 && (
          <div className="rounded-xl border border-glass-border bg-surface-0 p-3">
            <h4 className="text-xs font-semibold text-text-primary">Identity vs query coverage</h4>
            <p className="mt-1 text-[11px] text-text-muted">Each point is one returned hit.</p>
            <div className="mt-2 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ left: 6, right: 12, top: 8, bottom: 12 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis type="number" dataKey="coverage" domain={[0, 100]} name="Query coverage" unit="%" label={{ value: 'Query coverage (%)', position: 'insideBottom', offset: -6 }} />
                  <YAxis type="number" dataKey="identity" domain={[0, 100]} name="Identity" unit="%" label={{ value: 'Identity (%)', angle: -90, position: 'insideLeft' }} />
                  <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={tooltipStyle} />
                  <Scatter data={scatter} fill="#0891b2" />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {ranked.some(d => d.negLogE !== null) && (
          <div className="rounded-xl border border-glass-border bg-surface-0 p-3">
            <h4 className="text-xs font-semibold text-text-primary">E-value evidence by hit rank</h4>
            <p className="mt-1 text-[11px] text-text-muted">Higher -log10(E-value) indicates stronger statistical significance.</p>
            <div className="mt-2 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={ranked} margin={{ left: 6, right: 12, top: 8, bottom: 12 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis dataKey="rank" label={{ value: 'Hit rank', position: 'insideBottom', offset: -6 }} />
                  <YAxis label={{ value: '-log10(E-value)', angle: -90, position: 'insideLeft' }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Line type="monotone" dataKey="negLogE" stroke="#0891b2" dot={{ r: 2.5 }} connectNulls={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {ranked.some(d => d.bitScore !== null) && (
          <div className="rounded-xl border border-glass-border bg-surface-0 p-3">
            <h4 className="text-xs font-semibold text-text-primary">Bit score by hit rank</h4>
            <p className="mt-1 text-[11px] text-text-muted">Directly rendered from the returned BLAST bit scores.</p>
            <div className="mt-2 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={ranked} margin={{ left: 6, right: 12, top: 8, bottom: 12 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                  <XAxis dataKey="rank" label={{ value: 'Hit rank', position: 'insideBottom', offset: -6 }} />
                  <YAxis label={{ value: 'Bit score', angle: -90, position: 'insideLeft' }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Line type="monotone" dataKey="bitScore" stroke="#0f766e" dot={{ r: 2.5 }} connectNulls={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {coordinateHits.length > 0 && (
          <div className="rounded-xl border border-glass-border bg-surface-0 p-3">
            <h4 className="text-xs font-semibold text-text-primary">Query-coordinate coverage map</h4>
            <p className="mt-1 text-[11px] text-text-muted">Horizontal segments show the query span covered by each HSP/hit when coordinates were returned.</p>
            <div className="mt-3 max-h-64 space-y-2 overflow-y-auto">
              {coordinateHits.slice(0, 25).map(d => {
                const from = Math.min(Number(d.queryFrom), Number(d.queryTo));
                const to = Math.max(Number(d.queryFrom), Number(d.queryTo));
                const maxCoord = Math.max(...coordinateHits.map(x => Math.max(Number(x.queryFrom), Number(x.queryTo))));
                const left = maxCoord > 0 ? ((from - 1) / maxCoord) * 100 : 0;
                const width = maxCoord > 0 ? Math.max(0.5, ((to - from + 1) / maxCoord) * 100) : 0;
                return <div key={`${d.rank}-${d.accession}`} className="grid grid-cols-[80px_1fr] items-center gap-2 text-[10px]"><span className="truncate font-mono text-text-muted" title={d.accession}>{d.accession}</span><div className="relative h-3 rounded bg-surface-2"><span className="absolute top-0 h-3 rounded bg-accent-cyan/70" style={{ left: `${left}%`, width: `${width}%` }} /></div></div>;
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

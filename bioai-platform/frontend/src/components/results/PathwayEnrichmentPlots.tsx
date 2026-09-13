'use client';

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts';
import { DownloadSimple as Download } from '@phosphor-icons/react';
import type { EnrichmentResult } from '@/lib/api';
import { downloadTsv } from '@/lib/export-utils';

function negLog10(value: number): number | null {
  if (!Number.isFinite(value) || value < 0) return null;
  if (value === 0) return 300;
  return Math.min(300, -Math.log10(value));
}

const tooltipStyle = { background: 'var(--chart-tooltip-bg)', border: '1px solid var(--chart-tooltip-border)', borderRadius: 8, fontSize: 12 };

export function PathwayEnrichmentPlots({ result }: { result: EnrichmentResult }) {
  const rows = (result.pathways ?? []).map(p => ({
    id: p.stId,
    name: p.name,
    species: p.species,
    found: p.entitiesFound,
    total: p.entitiesTotal,
    geneRatio: p.geneRatio,
    pvalue: p.entitiesPValue,
    fdr: p.entitiesFDR,
    negLogFdr: negLog10(p.entitiesFDR),
  }));
  const scatter = rows.filter(r => Number.isFinite(r.geneRatio) && r.negLogFdr !== null);
  const top = [...rows].filter(r => r.negLogFdr !== null).sort((a, b) => (b.negLogFdr ?? 0) - (a.negLogFdr ?? 0)).slice(0, 15).reverse();
  if (!rows.length) return null;

  return (
    <div className="data-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Pathway enrichment plots</h3>
          <p className="mt-1 text-xs text-text-muted">Gene ratio, P-value and FDR are taken directly from the returned enrichment result. FDR=0 is capped at -log10(FDR)=300 for visualization.</p>
        </div>
        <button onClick={() => downloadTsv(
          ['stable_id', 'pathway', 'species', 'entities_found', 'entities_total', 'gene_ratio', 'p_value', 'fdr', 'negative_log10_fdr'],
          rows.map(r => [r.id, r.name, r.species, String(r.found), String(r.total), String(r.geneRatio ?? ''), String(r.pvalue ?? ''), String(r.fdr ?? ''), String(r.negLogFdr ?? '')]),
          'pathway-enrichment-plot-source.tsv',
        )} className="btn-ghost flex items-center gap-1 px-2 py-1 text-xs"><Download className="h-3.5 w-3.5" /> Source TSV</button>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {scatter.length > 0 && <div className="rounded-xl border border-glass-border bg-surface-0 p-3">
          <h4 className="text-xs font-semibold text-text-primary">Gene ratio vs statistical evidence</h4>
          <p className="mt-1 text-[11px] text-text-muted">Point size represents the number of submitted entities found in the pathway.</p>
          <div className="mt-2 h-72"><ResponsiveContainer width="100%" height="100%"><ScatterChart margin={{ left: 10, right: 16, top: 8, bottom: 16 }}><CartesianGrid opacity={0.25} /><XAxis type="number" dataKey="geneRatio" name="Gene ratio" label={{ value: 'Gene ratio', position: 'insideBottom', offset: -8 }} /><YAxis type="number" dataKey="negLogFdr" name="-log10(FDR)" label={{ value: '-log10(FDR)', angle: -90, position: 'insideLeft' }} /><ZAxis type="number" dataKey="found" range={[40, 300]} name="Entities found" /><Tooltip contentStyle={tooltipStyle} cursor={{ strokeDasharray: '3 3' }} /><Scatter data={scatter} fill="#0891b2" /></ScatterChart></ResponsiveContainer></div>
        </div>}

        {top.length > 0 && <div className="rounded-xl border border-glass-border bg-surface-0 p-3">
          <h4 className="text-xs font-semibold text-text-primary">Top pathways by FDR</h4>
          <p className="mt-1 text-[11px] text-text-muted">Ranked by -log10(FDR); pathway names are not altered.</p>
          <div className="mt-2 h-72"><ResponsiveContainer width="100%" height="100%"><BarChart data={top} layout="vertical" margin={{ left: 120, right: 16, top: 8, bottom: 8 }}><CartesianGrid strokeDasharray="3 3" opacity={0.25} /><XAxis type="number" /><YAxis type="category" dataKey="name" width={115} tick={{ fontSize: 10 }} /><Tooltip contentStyle={tooltipStyle} /><Bar dataKey="negLogFdr" name="-log10(FDR)" fill="#0891b2" /></BarChart></ResponsiveContainer></div>
        </div>}
      </div>
    </div>
  );
}

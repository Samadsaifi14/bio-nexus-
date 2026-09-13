'use client';

import {
  BarChart,
  Bar,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { DownloadSimple as Download, ArrowSquareOut as ExternalLink } from '@phosphor-icons/react';
import type { ComparisonSeries, ScientificComparison } from '@/lib/scientificComparisonApi';
import { downloadJson, downloadTsv } from '@/lib/export-utils';

const tooltipStyle = {
  background: 'var(--chart-tooltip-bg)',
  border: '1px solid var(--chart-tooltip-border)',
  borderRadius: 8,
  fontSize: 12,
};

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return 'Not evaluated';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return 'Not evaluated';
    if (Math.abs(value) < 0.001 && value !== 0) return value.toExponential(3);
    return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/0+$/, '').replace(/\.$/, '');
  }
  return String(value);
}

function PlotCard({ series }: { series: ComparisonSeries }) {
  const points = series.points ?? [];
  if (!points.length) return null;

  if (series.kind === 'blast_rank_profile') {
    const sources = Array.from(new Set(points.map(p => String(p.source ?? ''))));
    const byRank = new Map<number, Record<string, unknown>>();
    points.forEach(p => {
      const rank = Number(p.rank);
      if (!Number.isFinite(rank)) return;
      const row = byRank.get(rank) ?? { rank };
      const source = String(p.source ?? 'Source');
      row[`${source}_evalue`] = p.neglog10_evalue;
      row[`${source}_bit`] = p.bit_score;
      byRank.set(rank, row);
    });
    const data = Array.from(byRank.values()).sort((a, b) => Number(a.rank) - Number(b.rank));
    return (
      <div className="data-card p-4">
        <h4 className="text-sm font-semibold text-text-primary">BLAST rank concordance</h4>
        <p className="mt-1 text-xs text-text-muted">-log10(E-value) and bit score are plotted from the supplied hit tables. E-value 0 is capped at 300 for visualization only.</p>
        <div className="mt-4 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
              <XAxis dataKey="rank" label={{ value: 'Hit rank', position: 'insideBottom', offset: -4 }} />
              <YAxis label={{ value: '-log10(E-value)', angle: -90, position: 'insideLeft' }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend />
              {sources.map((source, i) => <Line key={source} type="monotone" dataKey={`${source}_evalue`} name={`${source} -log10(E)`} stroke={i === 0 ? '#0891b2' : '#64748b'} dot={false} connectNulls={false} />)}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  if (series.kind === 'paired_line') {
    const sources = Array.from(new Set(points.map(p => String(p.source ?? ''))));
    const xs = Array.from(new Set(points.map(p => Number(p.x)).filter(Number.isFinite))).sort((a, b) => a - b);
    const data = xs.map(x => {
      const row: Record<string, unknown> = { x };
      for (const source of sources) {
        const hit = points.find(p => Number(p.x) === x && String(p.source) === source);
        row[source] = hit?.y;
      }
      return row;
    });
    return (
      <div className="data-card p-4">
        <h4 className="text-sm font-semibold text-text-primary">{series.id.replace(/_/g, ' ')}</h4>
        <div className="mt-4 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
              <XAxis dataKey="x" label={{ value: series.x_label ?? 'Index', position: 'insideBottom', offset: -4 }} />
              <YAxis label={{ value: series.y_label ?? 'Value', angle: -90, position: 'insideLeft' }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend />
              {sources.map((source, i) => <Line key={source} type="monotone" dataKey={source} stroke={i === 0 ? '#0891b2' : '#64748b'} dot={false} connectNulls={false} />)}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  if (series.kind === 'reference_scatter') {
    const data = points.map(p => ({ x: p.reference_log2fc, y: p.bionexus_log2fc, gene: p.gene })).filter(p => typeof p.x === 'number' && typeof p.y === 'number');
    const vals = data.flatMap(p => [Number(p.x), Number(p.y)]);
    const lo = vals.length ? Math.min(...vals) : -1;
    const hi = vals.length ? Math.max(...vals) : 1;
    return (
      <div className="data-card p-4">
        <h4 className="text-sm font-semibold text-text-primary">BioNexus vs reference log2 fold change</h4>
        <p className="mt-1 text-xs text-text-muted">Each point is a shared gene. The diagonal is exact agreement, not a fitted regression.</p>
        <div className="mt-4 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart>
              <CartesianGrid opacity={0.25} />
              <XAxis type="number" dataKey="x" domain={[lo, hi]} name="Reference log2FC" />
              <YAxis type="number" dataKey="y" domain={[lo, hi]} name="BioNexus log2FC" />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={tooltipStyle} />
              <ReferenceLine segment={[{ x: lo, y: lo }, { x: hi, y: hi }]} stroke="#64748b" strokeDasharray="4 4" />
              <Scatter data={data} fill="#0891b2" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  if (series.kind === 'pathway_scatter') {
    const data = points.filter(p => typeof p.gene_ratio === 'number' && typeof p.neglog10_fdr === 'number');
    return (
      <div className="data-card p-4">
        <h4 className="text-sm font-semibold text-text-primary">Pathway enrichment evidence</h4>
        <p className="mt-1 text-xs text-text-muted">Gene ratio versus -log10(FDR), using only returned enrichment statistics.</p>
        <div className="mt-4 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart>
              <CartesianGrid opacity={0.25} />
              <XAxis type="number" dataKey="gene_ratio" name="Gene ratio" />
              <YAxis type="number" dataKey="neglog10_fdr" name="-log10(FDR)" />
              <Tooltip contentStyle={tooltipStyle} />
              <Scatter data={data} fill="#0891b2" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  if (series.kind === 'docking_pose_scores') {
    return (
      <div className="data-card p-4">
        <h4 className="text-sm font-semibold text-text-primary">Docking pose affinity comparison</h4>
        <div className="mt-4 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
              <XAxis dataKey="pose" name="Pose" />
              <YAxis name="Affinity" label={{ value: 'Affinity (kcal/mol)', angle: -90, position: 'insideLeft' }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend />
              <Line type="monotone" dataKey="bionexus_affinity" name="BioNexus" stroke="#0891b2" />
              <Line type="monotone" dataKey="reference_affinity" name="Reference" stroke="#64748b" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  if (series.kind === 'set_overlap') {
    return (
      <div className="data-card p-4">
        <h4 className="text-sm font-semibold text-text-primary">Reference identifier overlap</h4>
        <div className="mt-4 h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={points}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
              <XAxis dataKey="group" />
              <YAxis allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="count" fill="#0891b2" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  if (series.kind === 'metric_delta') {
    return (
      <div className="data-card p-4">
        <h4 className="text-sm font-semibold text-text-primary">Numeric metric relative error</h4>
        <div className="mt-4 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={points.slice(0, 30)} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
              <XAxis type="number" />
              <YAxis type="category" dataKey="metric" width={130} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="relative_error" fill="#0891b2" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  return null;
}

export function ScientificComparisonResult({ result }: { result: ScientificComparison }) {
  const score = result.concordance.score;
  return (
    <div className="space-y-4">
      <div className="data-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-text-muted">Reference comparison</p>
            <h3 className="mt-1 text-lg font-semibold text-text-primary">{result.analysis_type.toUpperCase()} · {result.concordance.status.replace(/_/g, ' ')}</h3>
            <p className="mt-1 max-w-3xl text-xs text-text-muted">{result.concordance.meaning}</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-text-muted">Composite concordance</p>
            <p className="text-2xl font-semibold text-text-primary">{score === null ? 'N/A' : `${(score * 100).toFixed(1)}%`}</p>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
          <a href={result.comparator.reference_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent-cyan hover:underline">
            {result.comparator.reference} <ExternalLink className="h-3.5 w-3.5" />
          </a>
          <span className="text-text-muted">· {result.comparator.kind.replace(/_/g, ' ')}</span>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button className="btn-ghost flex items-center gap-1 px-2 py-1 text-xs" onClick={() => downloadJson(result, `bionexus-${result.analysis_type}-reference-comparison.json`)}><Download className="h-3.5 w-3.5" /> JSON</button>
          <button className="btn-ghost flex items-center gap-1 px-2 py-1 text-xs" onClick={() => downloadTsv(['Metric', 'BioNexus/reference concordance value', 'Reference value', 'Unit', 'Note'], result.metrics.map(m => [m.label, formatValue(m.value), formatValue(m.reference_value), m.unit ?? '', m.note ?? '']), `bionexus-${result.analysis_type}-reference-comparison.tsv`)}><Download className="h-3.5 w-3.5" /> TSV</button>
        </div>
      </div>

      <div className="data-card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-surface-1 text-xs text-text-muted"><tr><th className="px-4 py-3 text-left">Metric</th><th className="px-4 py-3 text-left">Value</th><th className="px-4 py-3 text-left">Unit / interpretation</th></tr></thead>
          <tbody className="divide-y divide-glass-border">
            {result.metrics.map(metric => <tr key={metric.id}><td className="px-4 py-3 text-text-primary">{metric.label}</td><td className="px-4 py-3 font-mono text-text-secondary">{formatValue(metric.value)}</td><td className="px-4 py-3 text-xs text-text-muted">{metric.unit ?? metric.note ?? '—'}</td></tr>)}
          </tbody>
        </table>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {result.series.map(series => <PlotCard key={series.id} series={series} />)}
      </div>

      <div className="data-card border border-accent-amber/30 p-4 text-xs text-text-secondary">
        <strong className="text-text-primary">Scientific claim boundary.</strong> {result.claim_boundary.note} Missing measurements stay unevaluated and are not converted to zero.
      </div>
    </div>
  );
}

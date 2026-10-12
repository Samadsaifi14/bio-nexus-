'use client';

import { useState } from 'react';
import {
  ArrowsOut,
  ChartScatter,
  CircleNotch,
  DownloadSimple,
  Flask,
  GridFour,
  ShieldCheck,
  Table,
  Warning,
  X,
} from '@phosphor-icons/react';

import RnaSeqRecoveryPanel from '@/components/ngs/RnaSeqRecoveryPanel';
import { CriticalButton } from '@/components/ui';
import { EnrichmentRecovery } from './EnrichmentRecovery';
import { RnaSeqResultTables } from './RnaSeqResultTables';
import {
  runCerSalsDemo,
  type RnaSeqArtifact,
  type RnaSeqExpressionResult,
} from '@/lib/rnaseqExpressionApi';

function number(value: number | null | undefined, digits = 2) {
  return value !== null && value !== undefined && Number.isFinite(value)
    ? value.toLocaleString(undefined, { maximumFractionDigits: digits })
    : '—';
}

function stringList(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === 'string');
  return typeof value === 'string' ? [value] : [];
}

function artifact(result: RnaSeqExpressionResult | null, name: string) {
  return result?.artifacts.find(item => item.name === name) ?? null;
}

async function downloadRemote(item: RnaSeqArtifact) {
  const response = await fetch(item.url);
  if (!response.ok) throw new Error(`Could not download ${item.name}`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = item.name;
  a.click();
  URL.revokeObjectURL(url);
}

function Metric({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-lg border border-glass-border bg-surface-1 p-3">
      <p className="text-[10px] uppercase tracking-[0.12em] text-text-muted">{label}</p>
      <p className="mt-1 font-mono text-base font-semibold text-text-primary">{value}</p>
      {note && <p className="mt-1 text-[10px] leading-4 text-text-muted">{note}</p>}
    </div>
  );
}

function FigureCard({
  title,
  subtitle,
  image,
  data,
  onExpand,
}: {
  title: string;
  subtitle: string;
  image: RnaSeqArtifact | null;
  data?: RnaSeqArtifact | null;
  onExpand: (item: RnaSeqArtifact) => void;
}) {
  return (
    <article className="overflow-hidden rounded-xl border border-glass-border bg-surface-0">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-glass-border p-4">
        <div>
          <h4 className="text-sm font-semibold text-text-primary">{title}</h4>
          <p className="mt-1 max-w-xl text-[11px] leading-5 text-text-muted">{subtitle}</p>
        </div>
        <div className="flex gap-2">
          {data && <button type="button" onClick={() => downloadRemote(data)} className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-2.5 py-1.5 text-[10px] text-text-secondary"><Table /> Data TSV</button>}
          {image && <button type="button" onClick={() => downloadRemote(image)} className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-2.5 py-1.5 text-[10px] text-text-secondary"><DownloadSimple /> SVG</button>}
          {image && <button type="button" onClick={() => onExpand(image)} className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-2.5 py-1.5 text-[10px] text-text-secondary"><ArrowsOut /> Enlarge</button>}
        </div>
      </div>
      {image ? (
        <div className="bg-white p-3"><img loading="lazy" decoding="async" src={image.url} alt={title} className="mx-auto max-h-[520px] w-full object-contain" /></div>
      ) : (
        <div className="p-6 text-xs text-text-muted">This figure was not emitted by the analysis. BioNexus does not synthesize a replacement.</div>
      )}
    </article>
  );
}

export function RnaSeqExpressionWorkspace({ externalResult }: { externalResult?: RnaSeqExpressionResult | null }) {
  const [running, setRunning] = useState<'demo' | 'upload' | null>(null);
  const [localResult, setLocalResult] = useState<{ externalId: string | undefined; result: RnaSeqExpressionResult } | null>(null);
  const setResult = (value: RnaSeqExpressionResult) => setLocalResult({ externalId: externalResult?.run_id, result: value });
  const [recovered, setRecovered] = useState<{ sourceId: string; result: RnaSeqExpressionResult } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<RnaSeqArtifact | null>(null);

  const runDemo = async () => {
    setRunning('demo'); setError(null);
    try { setResult(await runCerSalsDemo()); }
    catch (caught: unknown) { setError(caught instanceof Error ? caught.message : 'The DESeq2 demo failed.'); }
    finally { setRunning(null); }
  };

  const baseResult = (localResult?.externalId === externalResult?.run_id ? localResult?.result : null) ?? externalResult ?? null;
  const displayedResult = recovered && recovered.sourceId === baseResult?.run_id ? recovered.result : baseResult;
  const summary = displayedResult?.summary;
  const pca = artifact(displayedResult, 'pca.svg');
  const pcaData = artifact(displayedResult, 'pca_coordinates.tsv');
  const distance = artifact(displayedResult, 'sample_distance_heatmap.svg');
  const distanceData = artifact(displayedResult, 'sample_distance_matrix.tsv');
  const ma = artifact(displayedResult, 'ma_plot.svg');
  const dispersion = artifact(displayedResult, 'dispersion_plot.svg');
  const volcano = artifact(displayedResult, 'volcano.svg');
  const resultsTable = artifact(displayedResult, 'deseq2_all_results.tsv');
  const enrichment = summary?.enrichment;
  const enrichmentPlot = artifact(displayedResult, 'go_enrichment.svg');
  const enrichmentTable = artifact(displayedResult, 'go_enrichment_significant.tsv');
  const heatmap = artifact(displayedResult, 'expression_heatmap.svg');
  const heatmapData = artifact(displayedResult, 'heatmap_matrix_zscore.tsv');
  const heatmapSelection = artifact(displayedResult, 'heatmap_gene_selection.tsv');
  const heatmapTitle = summary?.expression_heatmap_basis === 'significant_DE_genes'
    ? 'Top differential genes'
    : 'Top variable genes (QC)';
  const heatmapSubtitle = summary?.expression_heatmap_basis === 'significant_DE_genes'
    ? 'ComplexHeatmap generated from row-z-scored VST values for significant genes ranked by adjusted p-value. The exact plotted matrix and selection evidence are downloadable.'
    : 'ComplexHeatmap generated from the highest-variance VST genes because fewer than two genes met the declared DEG thresholds. This is a QC/exploratory view, not a list of differential-expression calls.';

  return (
    <section className="space-y-5">
      <details className="overflow-hidden rounded-xl border border-glass-border bg-surface-0">
        <summary className="cursor-pointer p-5 text-sm font-semibold text-text-primary">Analyze your own count matrix or run the SALS teaching demo</summary>
        <div className="border-b border-glass-border px-5 pb-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-accent-cyan">Real statistical execution</p>
              <h3 className="mt-1 text-base font-semibold text-text-primary">Count matrix → reviewed QC → DESeq2 figures</h3>
              <p className="mt-1 text-xs leading-5 text-text-muted">Raw counts and sample metadata are processed by R/DESeq2. PCA and heatmaps are generated in R from the exact transformed matrices, then stored with the tables that produced them.</p>
            </div>
            <CriticalButton onClick={runDemo} disabled={Boolean(running)} className="px-4 py-2 text-xs disabled:opacity-50">{running === 'demo' ? <CircleNotch className="animate-spin" /> : <Flask />} {running === 'demo' ? 'Running DESeq2…' : 'Run SALS DESeq2 demo'}</CriticalButton>
          </div>
          <div className="mt-4 rounded-lg border border-accent-cyan/20 bg-accent-cyan/5 p-3 text-[11px] leading-5 text-text-secondary"><ShieldCheck className="mr-2 inline h-4 w-4 text-accent-cyan" />The bundled demonstration is a deterministic every-100th-gene execution fixture from the user-supplied cerebellum count matrix. It preserves all 18 samples and their real counts, but it is not a substitute for full-study inference; upload the full matrix below to reproduce the complete practical. Healthy is the reference, SALS is the test level, and the practical pre-filter is ≥10 counts in ≥8 samples.</div>
        </div>

      </details>

      <RnaSeqRecoveryPanel onResult={setResult} />

      {error && <div className="rounded-xl border border-error/25 bg-error/10 p-4 text-sm text-error"><Warning className="mr-2 inline h-4 w-4" />{error}</div>}

      {summary && displayedResult && (
        <>
          <div className="rounded-xl border border-good/20 bg-good/5 p-4 text-[11px] leading-5 text-text-secondary"><ShieldCheck className="mr-2 inline h-4 w-4 text-good" />DESeq2 completed. These values are read from the emitted R artifacts; no result card below is populated from placeholder data.</div>

          <div className="rounded-xl border border-glass-border bg-surface-0 p-4">
            <h3 className="text-sm font-semibold text-text-primary">Ten-step practical workflow</h3>
            <ol className="mt-3 grid list-inside list-decimal gap-2 text-xs text-text-secondary sm:grid-cols-2">
              {['Inspect counts and library sizes', 'Build sample metadata', 'Construct DESeq2 object and design', 'Pre-filter low-count genes', summary.input_kind === 'salmon' ? 'tximport length-aware normalization' : 'Median-of-ratios normalization', 'PCA and sample-distance QC', 'Fit, shrink, filter and export DEGs', 'Volcano plot', 'Expression heatmap'].map(step => <li key={step}>{step}</li>)}
              <li>Functional enrichment — {enrichment?.status === 'SUCCEEDED' ? 'completed' : enrichment?.status?.replaceAll('_', ' ').toLowerCase() ?? 'not available for this older run'}</li>
            </ol>
            <p className="mt-3 text-[11px] text-text-muted">Recovered inputs pause for QC approval before fitting. The teaching fixture runs directly for regression testing. Shrinkage uses the recorded DESeq2 normal prior; the teaching slides show apeglm.</p>
          </div>

          <div className="grid gap-2 sm:grid-cols-4 lg:grid-cols-8">
            <Metric label="Genes input" value={number(summary.genes_input, 0)} />
            <Metric label="Genes tested" value={number(summary.genes_kept, 0)} />
            <Metric label="Samples" value={number(summary.samples, 0)} />
            <Metric label="DEGs" value={number(summary.significant, 0)} />
            <Metric label="Up" value={number(summary.up, 0)} />
            <Metric label="Down" value={number(summary.down, 0)} />
            <Metric label="PC1" value={`${number(summary.pca_percent_variance.PC1)}%`} />
            <Metric label="PC2" value={`${number(summary.pca_percent_variance.PC2)}%`} />
          </div>

          <div className="grid gap-2 sm:grid-cols-4">
            <Metric label="Design" value={summary.design} />
            <Metric label="Contrast" value={`${summary.test_level} vs ${summary.reference_level}`} />
            <Metric label={summary.input_kind === 'salmon' ? 'Normalization factor summary' : 'Size factors'} note={summary.input_kind === 'salmon' ? 'Geometric means of gene-specific normalization factors; full offsets retained in the fitted RDS.' : undefined} value={`${number(summary.size_factor_min, 3)}–${number(summary.size_factor_max, 3)}`} />
            <Metric label="Threshold" value={`padj<${summary.alpha}, |LFC|>${summary.lfc_threshold}`} note={`LFC shrinkage: ${summary.lfc_shrinkage}`} />
          </div>

          <div className="rounded-xl border border-glass-border bg-surface-0 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-accent-cyan">Experimental-design gate</p>
                <h3 className="mt-1 text-sm font-semibold text-text-primary">Replication, confounding and model identifiability</h3>
                <p className="mt-1 text-[11px] leading-5 text-text-muted">This gate is evaluated before DESeq2 fitting. Technical repeats are not counted as biological replication merely because they occupy separate matrix columns.</p>
              </div>
              <span className={`rounded border px-2.5 py-1 font-mono text-[10px] ${summary.design_full_rank === true ? 'border-good/25 bg-good/5 text-good' : summary.design_full_rank === false ? 'border-error/25 bg-error/10 text-error' : 'border-glass-border bg-surface-1 text-text-muted'}`}>
                {summary.design_full_rank === true ? 'FULL RANK' : summary.design_full_rank === false ? 'NOT FULL RANK' : 'NOT EVALUATED'}
              </span>
            </div>
            <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
              <Metric label="Compared samples" value={Object.entries(summary.replicate_counts ?? {}).map(([group, n]) => `${group}: ${n}`).join(' · ') || '—'} />
              <Metric label="Design rank" value={summary.design_rank === undefined ? '—' : `${summary.design_rank}/${summary.design_columns}`} />
              <Metric label="Library-size spread" value={summary.library_size_fold_range === undefined ? '—' : `${number(summary.library_size_fold_range, 2)}×`} />
              <Metric label="Size-factor vs library r" value={number(summary.size_factor_library_correlation, 3)} note="A value below 1 can reflect composition correction." />
              <Metric label="Experimental units" value={summary.experimental_unit_status ?? 'NOT_DECLARED'} />
            </div>
            <div className="mt-3 rounded-lg border border-glass-border bg-surface-1 p-3 text-[10px] leading-5 text-text-muted">
              Recorded technical variables: {stringList(summary.technical_covariates_detected).join(', ') || 'none declared'}.
              {stringList(summary.technical_covariates_in_model).length > 0 && <> Modelled: {stringList(summary.technical_covariates_in_model).join(', ')}.</>}
            </div>
            {stringList(summary.design_warnings).length > 0 && (
              <div className="mt-3 rounded-lg border border-warn/25 bg-warn/5 p-3 text-[10px] leading-5 text-warn">
                {stringList(summary.design_warnings).join(' ')}
              </div>
            )}
          </div>

          <div className="space-y-4">
            <div className="flex items-center gap-2"><ChartScatter className="text-accent-cyan" /><h3 className="text-sm font-semibold text-text-primary">QC before differential testing</h3></div>
            <p className="text-xs leading-5 text-text-muted">R computes these QC matrices before fitting the DESeq2 model. For recovered inputs, inference follows explicit checkpoint approval. Inspect outliers, batch patterns and sample identity before interpreting the gene calls.</p>
            <div className="grid gap-4 xl:grid-cols-2">
              <FigureCard title="PCA on variance-stabilized counts" subtitle="Sample-level QC generated in R with DESeq2 VST. Inspect grouping and outliers before interpreting differential expression." image={pca} data={pcaData} onExpand={setExpanded} />
              <FigureCard title="Sample-to-sample distance" subtitle="ComplexHeatmap generated from the exact VST distance matrix. The downloadable TSV is the matrix plotted here." image={distance} data={distanceData} onExpand={setExpanded} />
            </div>
          </div>

          <RnaSeqResultTables key={displayedResult.run_id} result={displayedResult} />

          <div className="space-y-4">
            <div className="flex items-center gap-2"><ChartScatter className="text-accent-cyan" /><h3 className="text-sm font-semibold text-text-primary">Differential expression evidence</h3></div>
            <div className="grid gap-4 xl:grid-cols-2">
              <FigureCard title="DESeq2 MA plot" subtitle="Effect size versus mean abundance from the fitted negative-binomial model. Dashed lines mark the declared fold-change threshold." image={ma} data={resultsTable} onExpand={setExpanded} />
              <FigureCard title="Volcano plot" subtitle="log2 fold change versus adjusted-p-value evidence. Calls use the predeclared padj and fold-change criteria shown above." image={volcano} data={artifact(displayedResult, 'volcano_plot_data.tsv') ?? resultsTable} onExpand={setExpanded} />
              <FigureCard title="Dispersion fit" subtitle="DESeq2 gene-wise dispersion estimates and the fitted mean-dispersion trend. Check this model diagnostic alongside the gene calls." image={dispersion} onExpand={setExpanded} />
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center gap-2"><GridFour className="text-accent-cyan" /><h3 className="text-sm font-semibold text-text-primary">Expression heatmap</h3></div>
            <FigureCard title={heatmapTitle} subtitle={heatmapSubtitle} image={heatmap} data={heatmapData ?? heatmapSelection} onExpand={setExpanded} />
          </div>

          <div className="space-y-4 rounded-xl border border-glass-border bg-surface-0 p-4">
            <h3 className="text-sm font-semibold text-text-primary">10. Functional enrichment · {enrichment?.database ?? 'GO'}</h3>
            <p className="text-xs leading-5 text-text-secondary">{enrichment?.message ?? 'This saved run has no enrichment. Use the recovery options below to generate it.'}</p>
            <p className="text-[11px] leading-5 text-text-muted">{enrichment?.method ?? 'GO over-representation with BH correction across terms and directions'}. Background: {enrichment?.background ?? 'Uniquely mapped, GO-annotated genes with non-missing DESeq2 adjusted p-values'}. Terms contain 10–500 background genes.</p>
            {enrichment?.coverage_warning && <p role="status" className="text-xs text-amber-500">{enrichment.coverage_warning}</p>}
            {!!enrichment?.direction_conflicts && <p className="text-xs text-amber-500">{enrichment.direction_conflicts} mapped genes had conflicting up/down calls and were excluded from both ORA query sets.</p>}
            {enrichment?.interpretation_note && <p className="text-xs text-text-muted">{enrichment.interpretation_note}</p>}
            {enrichment && <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
              <Metric label="Organism / IDs" value={`${enrichment.organism} / ${enrichment.gene_id_type ?? 'unresolved'}`} />
              <Metric label="Mapped input rows" value={`${enrichment.genes_uniquely_mapped ?? '—'} / ${enrichment.genes_eligible ?? '—'}`} />
              <Metric label="Alias recoveries" value={String(enrichment.aliases_recovered ?? '—')} />
              <Metric label="Annotated coverage" value={enrichment.annotation_coverage == null ? '—' : `${number(100 * enrichment.annotation_coverage)}%`} />
              <Metric label="Background genes" value={String(enrichment.background_genes ?? '—')} />
              <Metric label="Unmapped / ambiguous" value={`${enrichment.genes_unmapped ?? '—'} / ${enrichment.genes_ambiguous ?? '—'}`} />
              <Metric label="Term tests" value={String(enrichment.terms_tested ?? '—')} />
              <Metric label="Significant terms" value={String(enrichment.significant_terms ?? '—')} />
            </div>}
            {enrichmentPlot && <FigureCard title="Functional enrichment" subtitle="Top 20 significant term-direction tests ranked by BH adjusted p-value. Full results, mapping audit, background and annotation release metadata are in the reproducibility bundle." image={enrichmentPlot} data={enrichmentTable} onExpand={setExpanded} />}
            {enrichmentTable && <a href={enrichmentTable.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-xs text-accent-cyan"><DownloadSimple /> Download significant terms</a>}
          </div>

          <EnrichmentRecovery key={displayedResult.run_id} result={displayedResult} onResult={next => {
            if (baseResult) setRecovered({ sourceId: baseResult.run_id, result: next });
          }} />

          <div className="rounded-xl border border-glass-border bg-surface-0 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-sm font-semibold text-text-primary">Complete reproducibility bundle</h3><p className="mt-1 text-[11px] leading-5 text-text-muted">Normalized counts, size factors, PCA coordinates, distance matrix, all-gene results, significant-gene table, plotted heatmap matrix, gene-selection evidence, SVG/PDF/300-dpi PNG figures and provenance.</p></div>{displayedResult.manifest_url && <a href={displayedResult.manifest_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-[10px] text-text-secondary"><DownloadSimple /> Manifest</a>}</div>
            <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">{displayedResult.artifacts.map(item => <button type="button" key={item.name} onClick={() => downloadRemote(item)} className="flex items-center justify-between gap-3 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-left text-[10px] text-text-secondary"><span className="truncate font-mono">{item.name}</span><span className="shrink-0 text-text-muted">{number(item.bytes / 1024)} KB</span></button>)}</div>
          </div>
        </>
      )}

      {expanded && (
        <div className="fixed inset-4 z-50 overflow-auto rounded-2xl border border-glass-border bg-surface-0 p-4 shadow-2xl">
          <div className="mb-3 flex items-center justify-between"><div><p className="text-xs font-semibold text-text-primary">{expanded.name}</p><p className="text-[10px] text-text-muted">Native R-generated artifact</p></div><button onClick={() => setExpanded(null)} className="inline-flex items-center gap-1 rounded-lg border border-glass-border px-3 py-2 text-xs text-text-secondary"><X /> Close</button></div>
          <div className="rounded-xl bg-white p-4"><img src={expanded.url} alt={expanded.name} className="mx-auto min-h-[70vh] max-h-[85vh] w-full object-contain" /></div>
        </div>
      )}
    </section>
  );
}

'use client';

import { useState } from 'react';
import {
  ArrowsOut,
  ChartScatter,
  CircleNotch,
  DownloadSimple,
  FileArrowUp,
  Flask,
  GridFour,
  ShieldCheck,
  Table,
  Warning,
  X,
} from '@phosphor-icons/react';

import { CriticalButton } from '@/components/ui';
import {
  runCerSalsDemo,
  runRnaSeqExpression,
  type RnaSeqArtifact,
  type RnaSeqExpressionResult,
} from '@/lib/rnaseqExpressionApi';

function number(value: number, digits = 2) {
  return Number.isFinite(value) ? value.toLocaleString(undefined, { maximumFractionDigits: digits }) : '—';
}

function artifact(result: RnaSeqExpressionResult | null, name: string) {
  return result?.artifacts.find(item => item.name === name) ?? null;
}

function downloadText(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/tab-separated-values;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
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
        <div className="bg-white p-3"><img src={image.url} alt={title} className="mx-auto max-h-[520px] w-full object-contain" /></div>
      ) : (
        <div className="p-6 text-xs text-text-muted">This figure was not emitted by the analysis. BioNexus does not synthesize a replacement.</div>
      )}
    </article>
  );
}

export function RnaSeqExpressionWorkspace() {
  const [counts, setCounts] = useState<File | null>(null);
  const [metadata, setMetadata] = useState<File | null>(null);
  const [conditionColumn, setConditionColumn] = useState('condition');
  const [referenceLevel, setReferenceLevel] = useState('healthy');
  const [testLevel, setTestLevel] = useState('SALS');
  const [covariates, setCovariates] = useState('');
  const [minSamples, setMinSamples] = useState(2);
  const [lfcThreshold, setLfcThreshold] = useState(1);
  const [running, setRunning] = useState<'demo' | 'upload' | null>(null);
  const [result, setResult] = useState<RnaSeqExpressionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<RnaSeqArtifact | null>(null);

  const runDemo = async () => {
    setRunning('demo'); setError(null);
    try { setResult(await runCerSalsDemo()); }
    catch (caught: unknown) { setError(caught instanceof Error ? caught.message : 'The DESeq2 demo failed.'); }
    finally { setRunning(null); }
  };

  const runUpload = async () => {
    if (!counts || !metadata) { setError('Choose both a raw integer count matrix and a metadata TSV first.'); return; }
    setRunning('upload'); setError(null);
    try {
      setResult(await runRnaSeqExpression({
        counts,
        metadata,
        conditionColumn,
        referenceLevel,
        testLevel,
        covariates,
        alpha: 0.05,
        lfcThreshold,
        minCount: 10,
        minSamples,
        topHeatmapGenes: 40,
      }));
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'DESeq2 analysis failed.');
    } finally { setRunning(null); }
  };

  const summary = result?.summary;
  const pca = artifact(result, 'pca.svg');
  const pcaData = artifact(result, 'pca_coordinates.tsv');
  const distance = artifact(result, 'sample_distance_heatmap.svg');
  const distanceData = artifact(result, 'sample_distance_matrix.tsv');
  const ma = artifact(result, 'ma_plot.svg');
  const volcano = artifact(result, 'volcano.svg');
  const resultsTable = artifact(result, 'deseq2_all_results.tsv');
  const degTable = artifact(result, 'deseq2_significant.tsv');
  const heatmap = artifact(result, 'expression_heatmap.svg');
  const heatmapData = artifact(result, 'heatmap_matrix_zscore.tsv');
  const heatmapSelection = artifact(result, 'heatmap_gene_selection.tsv');
  const heatmapTitle = summary?.expression_heatmap_basis === 'significant_DE_genes'
    ? 'Top differential genes'
    : 'Top variable genes (QC)';
  const heatmapSubtitle = summary?.expression_heatmap_basis === 'significant_DE_genes'
    ? 'ComplexHeatmap generated from row-z-scored VST values for significant genes ranked by adjusted p-value. The exact plotted matrix and selection evidence are downloadable.'
    : 'ComplexHeatmap generated from the highest-variance VST genes because fewer than two genes met the declared DEG thresholds. This is a QC/exploratory view, not a list of differential-expression calls.';

  return (
    <section className="space-y-5">
      <div className="overflow-hidden rounded-xl border border-glass-border bg-surface-0">
        <div className="border-b border-glass-border p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-accent-cyan">Real statistical execution</p>
              <h3 className="mt-1 text-base font-semibold text-text-primary">Count matrix → DESeq2 → publication figures</h3>
              <p className="mt-1 text-xs leading-5 text-text-muted">Raw counts and sample metadata are processed by R/DESeq2. PCA and heatmaps are generated in R from the exact transformed matrices, then stored with the tables that produced them.</p>
            </div>
            <CriticalButton onClick={runDemo} disabled={Boolean(running)} className="px-4 py-2 text-xs disabled:opacity-50">{running === 'demo' ? <CircleNotch className="animate-spin" /> : <Flask />} {running === 'demo' ? 'Running DESeq2…' : 'Run SALS DESeq2 demo'}</CriticalButton>
          </div>
          <div className="mt-4 rounded-lg border border-accent-cyan/20 bg-accent-cyan/5 p-3 text-[11px] leading-5 text-text-secondary"><ShieldCheck className="mr-2 inline h-4 w-4 text-accent-cyan" />The bundled demonstration is a deterministic every-100th-gene execution fixture from the user-supplied cerebellum count matrix. It preserves all 18 samples and their real counts, but it is not a substitute for full-study inference; upload the full matrix below to reproduce the complete practical. Healthy is the reference, SALS is the test level, and the practical pre-filter is ≥10 counts in ≥8 samples.</div>
        </div>

        <div className="grid gap-px bg-glass-border lg:grid-cols-2">
          <div className="bg-surface-0 p-5">
            <div className="flex items-center gap-2"><FileArrowUp className="text-accent-cyan" /><h4 className="text-sm font-semibold text-text-primary">Your raw count matrix</h4></div>
            <p className="mt-1 text-[11px] leading-5 text-text-muted">TSV: first column is the gene identifier; remaining columns are samples. Values must be non-negative raw integers.</p>
            <input type="file" accept=".tsv,.txt,text/tab-separated-values,text/plain" onChange={event => setCounts(event.target.files?.[0] ?? null)} className="mt-3 block w-full text-xs text-text-secondary file:mr-3 file:rounded-lg file:border file:border-glass-border file:bg-surface-1 file:px-3 file:py-2 file:text-xs file:text-text-primary" />
            {counts && <p className="mt-2 font-mono text-[10px] text-text-muted">{counts.name}</p>}
          </div>
          <div className="bg-surface-0 p-5">
            <div className="flex items-center gap-2"><Table className="text-accent-cyan" /><h4 className="text-sm font-semibold text-text-primary">Sample metadata</h4></div>
            <p className="mt-1 text-[11px] leading-5 text-text-muted">TSV must contain <code>sample</code> and the condition column. Extra recorded covariates can be included in the model.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <input type="file" accept=".tsv,.txt,text/tab-separated-values,text/plain" onChange={event => setMetadata(event.target.files?.[0] ?? null)} className="block min-w-0 flex-1 text-xs text-text-secondary file:mr-3 file:rounded-lg file:border file:border-glass-border file:bg-surface-1 file:px-3 file:py-2 file:text-xs file:text-text-primary" />
              <button type="button" onClick={() => downloadText('rnaseq_metadata_template.tsv', 'sample\tcondition\nSample_1\thealthy\nSample_2\tSALS\n')} className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-[10px] text-text-secondary"><DownloadSimple /> Template</button>
            </div>
            {metadata && <p className="mt-2 font-mono text-[10px] text-text-muted">{metadata.name}</p>}
          </div>
        </div>

        <div className="border-t border-glass-border p-5">
          <div className="grid gap-3 md:grid-cols-3 lg:grid-cols-6">
            <label className="text-[10px] text-text-muted">Condition column<input value={conditionColumn} onChange={e => setConditionColumn(e.target.value)} className="mt-1 w-full rounded-lg border border-glass-border bg-surface-1 px-2 py-2 text-xs text-text-primary" /></label>
            <label className="text-[10px] text-text-muted">Reference<input value={referenceLevel} onChange={e => setReferenceLevel(e.target.value)} className="mt-1 w-full rounded-lg border border-glass-border bg-surface-1 px-2 py-2 text-xs text-text-primary" /></label>
            <label className="text-[10px] text-text-muted">Test level<input value={testLevel} onChange={e => setTestLevel(e.target.value)} className="mt-1 w-full rounded-lg border border-glass-border bg-surface-1 px-2 py-2 text-xs text-text-primary" /></label>
            <label className="text-[10px] text-text-muted">Covariates<input placeholder="batch,sex" value={covariates} onChange={e => setCovariates(e.target.value)} className="mt-1 w-full rounded-lg border border-glass-border bg-surface-1 px-2 py-2 text-xs text-text-primary" /></label>
            <label className="text-[10px] text-text-muted">Min samples<input type="number" min={1} value={minSamples} onChange={e => setMinSamples(Math.max(1, Number(e.target.value)))} className="mt-1 w-full rounded-lg border border-glass-border bg-surface-1 px-2 py-2 text-xs text-text-primary" /></label>
            <label className="text-[10px] text-text-muted">|log2FC|<input type="number" min={0} step={0.1} value={lfcThreshold} onChange={e => setLfcThreshold(Math.max(0, Number(e.target.value)))} className="mt-1 w-full rounded-lg border border-glass-border bg-surface-1 px-2 py-2 text-xs text-text-primary" /></label>
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3"><p className="text-[10px] leading-4 text-text-muted">DESeq2 input is always raw counts. PCA/sample distances use blind VST for QC before inference. The condition term is placed last after any declared covariates.</p><CriticalButton disabled={!counts || !metadata || Boolean(running)} onClick={runUpload} className="px-4 py-2 text-xs disabled:opacity-40">{running === 'upload' ? <CircleNotch className="animate-spin" /> : <ChartScatter />} {running === 'upload' ? 'Running R…' : 'Run uploaded matrix'}</CriticalButton></div>
        </div>
      </div>

      {error && <div className="rounded-xl border border-error/25 bg-error/10 p-4 text-sm text-error"><Warning className="mr-2 inline h-4 w-4" />{error}</div>}

      {summary && result && (
        <>
          <div className="rounded-xl border border-good/20 bg-good/5 p-4 text-[11px] leading-5 text-text-secondary"><ShieldCheck className="mr-2 inline h-4 w-4 text-good" />DESeq2 completed. These values are read from the emitted R artifacts; no result card below is populated from placeholder data.</div>

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
            <Metric label="Size factors" value={`${number(summary.size_factor_min, 3)}–${number(summary.size_factor_max, 3)}`} />
            <Metric label="Threshold" value={`padj<${summary.alpha}, |LFC|>${summary.lfc_threshold}`} note={`LFC shrinkage: ${summary.lfc_shrinkage}`} />
          </div>

          <div className="space-y-4">
            <div className="flex items-center gap-2"><ChartScatter className="text-accent-cyan" /><h3 className="text-sm font-semibold text-text-primary">QC before differential testing</h3></div>
            <div className="grid gap-4 xl:grid-cols-2">
              <FigureCard title="PCA on variance-stabilized counts" subtitle="Sample-level QC generated in R with DESeq2 VST. Inspect grouping and outliers before interpreting differential expression." image={pca} data={pcaData} onExpand={setExpanded} />
              <FigureCard title="Sample-to-sample distance" subtitle="ComplexHeatmap generated from the exact VST distance matrix. The downloadable TSV is the matrix plotted here." image={distance} data={distanceData} onExpand={setExpanded} />
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center gap-2"><ChartScatter className="text-accent-cyan" /><h3 className="text-sm font-semibold text-text-primary">Differential expression evidence</h3></div>
            <div className="grid gap-4 xl:grid-cols-2">
              <FigureCard title="DESeq2 MA plot" subtitle="Effect size versus mean abundance from the fitted negative-binomial model. Dashed lines mark the declared fold-change threshold." image={ma} data={resultsTable} onExpand={setExpanded} />
              <FigureCard title="Volcano plot" subtitle="log2 fold change versus adjusted-p-value evidence. Calls use the predeclared padj and fold-change criteria shown above." image={volcano} data={degTable} onExpand={setExpanded} />
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center gap-2"><GridFour className="text-accent-cyan" /><h3 className="text-sm font-semibold text-text-primary">Expression heatmap</h3></div>
            <FigureCard title={heatmapTitle} subtitle={heatmapSubtitle} image={heatmap} data={heatmapData ?? heatmapSelection} onExpand={setExpanded} />
          </div>

          <div className="rounded-xl border border-glass-border bg-surface-0 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-sm font-semibold text-text-primary">Complete reproducibility bundle</h3><p className="mt-1 text-[11px] leading-5 text-text-muted">Normalized counts, size factors, PCA coordinates, distance matrix, all-gene results, significant-gene table, plotted heatmap matrix, gene-selection evidence, SVG/PDF/300-dpi PNG figures and provenance.</p></div>{result.manifest_url && <a href={result.manifest_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-[10px] text-text-secondary"><DownloadSimple /> Manifest</a>}</div>
            <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">{result.artifacts.map(item => <button type="button" key={item.name} onClick={() => downloadRemote(item)} className="flex items-center justify-between gap-3 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-left text-[10px] text-text-secondary"><span className="truncate font-mono">{item.name}</span><span className="shrink-0 text-text-muted">{number(item.bytes / 1024)} KB</span></button>)}</div>
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

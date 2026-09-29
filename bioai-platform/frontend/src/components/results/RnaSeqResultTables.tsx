'use client';

import { useEffect, useMemo, useState } from 'react';
import { DownloadSimple } from '@phosphor-icons/react';
import type { RnaSeqArtifact, RnaSeqExpressionResult } from '@/lib/rnaseqExpressionApi';

type Row = Record<string, string>;
type Preview = { rows: Row[]; truncated: boolean };

async function readTsvPreview(url: string, limit: number, signal: AbortSignal): Promise<Preview> {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`Artifact request failed (${response.status}).`);
  const reader = response.body?.getReader();
  if (!reader) throw new Error('The browser could not stream this table. Download the TSV instead.');
  const decoder = new TextDecoder();
  const lines: string[] = [];
  let pending = '';
  let bytes = 0;
  try {
    while (lines.length < limit + 2) {
      const { value, done } = await reader.read();
      if (done) {
        pending += decoder.decode();
        if (pending) lines.push(pending.replace(/\r$/, ''));
        break;
      }
      bytes += value.byteLength;
      if (bytes > 1024 * 1024) throw new Error('Table preview exceeded 1 MB. Download the TSV instead.');
      pending += decoder.decode(value, { stream: true });
      const parts = pending.split('\n');
      pending = parts.pop() ?? '';
      lines.push(...parts.map(line => line.replace(/\r$/, '')));
    }
  } finally {
    await reader.cancel().catch(() => undefined);
  }
  const [headerLine, ...dataLines] = lines;
  if (!headerLine) throw new Error('The result table has no header.');
  const headers = headerLine.split('\t');
  const rows = dataLines.filter(Boolean).slice(0, limit).map(line => {
    const values = line.split('\t');
    return Object.fromEntries(headers.map((header, index) => [header, values[index] ?? '']));
  });
  return { rows, truncated: dataLines.filter(Boolean).length > limit || lines.length >= limit + 2 };
}

function downloadLink(item: RnaSeqArtifact | undefined, label: string) {
  return item && <a href={item.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-accent-cyan"><DownloadSimple /> {label}</a>;
}

export function RnaSeqResultTables({ result }: { result: RnaSeqExpressionResult }) {
  const { deg, all, libraries, factors, pca } = useMemo(() => {
    const get = (name: string) => result.artifacts.find(item => item.name === name);
    return { deg: get('deseq2_significant.tsv'), all: get('deseq2_all_results.tsv'), libraries: get('library_sizes.tsv'), factors: get('size_factors.tsv'), pca: get('pca_coordinates.tsv') };
  }, [result.artifacts]);
  const [genePreview, setGenePreview] = useState<Preview | null>(null);
  const [sampleRows, setSampleRows] = useState<Row[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const [genes, libraryTable, factorTable, pcaTable] = await Promise.all([
          deg ? readTsvPreview(deg.url, 50, controller.signal) : null,
          libraries ? readTsvPreview(libraries.url, 500, controller.signal) : null,
          factors ? readTsvPreview(factors.url, 500, controller.signal) : null,
          pca ? readTsvPreview(pca.url, 500, controller.signal) : null,
        ]);
        if (controller.signal.aborted) return;
        setGenePreview(genes);
        const factorBySample = new Map(factorTable?.rows.map(row => [row.sample, row.size_factor]));
        const pcaBySample = new Map(pcaTable?.rows.map(row => [row.sample, row]));
        setSampleRows((libraryTable?.rows ?? []).map(row => ({
          ...row, size_factor: factorBySample.get(row.sample) ?? '',
          PC1: pcaBySample.get(row.sample)?.PC1 ?? '', PC2: pcaBySample.get(row.sample)?.PC2 ?? '',
        })));
      } catch (caught) {
        if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : 'Could not load result tables.');
      }
    }
    void load();
    return () => controller.abort();
  }, [deg, libraries, factors, pca]);

  return <div className="space-y-4">
    <section className="rounded-xl border border-glass-border bg-surface-0 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-sm font-semibold text-text-primary">Sample QC and normalization</h3><p className="mt-1 text-xs text-text-muted">Library totals, DESeq2 size factors and exact PCA coordinates emitted by R. Each sample is listed even when plot labels overlap.</p></div><div className="flex flex-wrap gap-3">{downloadLink(libraries, 'Library sizes')}{downloadLink(factors, 'Size factors')}{downloadLink(pca, 'PCA coordinates')}</div></div>
      {Number(result.summary.library_size_fold_range) > 10 && <p className="mt-3 rounded border border-warn/25 bg-warn/5 p-3 text-xs leading-5 text-warn">Library count totals differ by {Number(result.summary.library_size_fold_range).toLocaleString(undefined, { maximumFractionDigits: 1 })}×. Review low-depth samples, detection rates and source QC before interpreting PCA separation or DEG calls. This is a QC warning, not an automatic exclusion.</p>}
      {sampleRows.length > 0 ? <div className="mt-3 max-h-80 overflow-auto rounded border border-glass-border"><table className="w-full text-left text-xs"><thead className="sticky top-0 bg-surface-1 text-text-muted"><tr><th className="px-3 py-2">Sample</th><th className="px-3 py-2">Condition</th><th className="px-3 py-2 text-right">Library counts</th><th className="px-3 py-2 text-right">Size factor</th><th className="px-3 py-2 text-right">PC1</th><th className="px-3 py-2 text-right">PC2</th></tr></thead><tbody className="divide-y divide-glass-border">{sampleRows.map(row => <tr key={row.sample}><td className="px-3 py-2 font-mono text-text-primary">{row.sample}</td><td className="px-3 py-2">{row.condition}</td><td className="px-3 py-2 text-right font-mono">{Number(row.total_counts).toLocaleString()}</td><td className="px-3 py-2 text-right font-mono">{row.size_factor}</td><td className="px-3 py-2 text-right font-mono">{row.PC1 || '—'}</td><td className="px-3 py-2 text-right font-mono">{row.PC2 || '—'}</td></tr>)}</tbody></table></div> : <p className="mt-3 text-xs text-text-muted">{error ?? 'Loading sample evidence…'}</p>}
    </section>
    <section className="rounded-xl border border-glass-border bg-surface-0 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-sm font-semibold text-text-primary">Differentially expressed genes</h3><p className="mt-1 text-xs text-text-muted">Ordered by adjusted p-value. Calls require padj &lt; {result.summary.alpha} and |log2FC| &gt; {result.summary.lfc_threshold}; open the full tables for all rows and precision.</p></div><div className="flex gap-3">{downloadLink(deg, 'Full DEG TSV')}{downloadLink(all, 'All genes TSV')}</div></div>
      {genePreview?.rows.length ? <><div className="mt-3 max-h-96 overflow-auto rounded border border-glass-border"><table className="w-full text-left text-xs"><thead className="sticky top-0 bg-surface-1 text-text-muted"><tr><th className="px-3 py-2">Gene</th><th className="px-3 py-2 text-right">Mean normalized count</th><th className="px-3 py-2 text-right">log2FC</th><th className="px-3 py-2 text-right">padj</th><th className="px-3 py-2">Direction</th></tr></thead><tbody className="divide-y divide-glass-border">{genePreview.rows.map(row => <tr key={row.gene}><td className="px-3 py-2 font-mono text-text-primary">{row.gene}</td><td className="px-3 py-2 text-right font-mono">{row.baseMean}</td><td className="px-3 py-2 text-right font-mono">{row.log2FoldChange}</td><td className="px-3 py-2 text-right font-mono">{row.padj}</td><td className="px-3 py-2">{row.direction}</td></tr>)}</tbody></table></div><p className="mt-2 text-xs text-text-muted">Showing the first {genePreview.rows.length} of {result.summary.significant.toLocaleString()} calls. Download the TSV for every gene and full precision.</p></> : <p className="mt-3 text-xs text-text-muted">{error ?? (genePreview ? 'No genes met both declared thresholds. Inspect the PCA and the all-gene table.' : 'Loading gene evidence…')}</p>}
    </section>
  </div>;
}

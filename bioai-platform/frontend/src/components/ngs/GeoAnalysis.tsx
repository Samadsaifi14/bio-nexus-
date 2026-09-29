'use client';

import { useCallback, useEffect, useState } from 'react';
import { ArrowRight, CircleNotch, DownloadSimple, Warning } from '@phosphor-icons/react';
import type { GeoRecord } from '@/lib/api';
import { prepareGeoCounts, type GeoCountColumn, type GeoCountPreview } from '@/lib/geoCounts';
import { runRnaSeqExpression, type RnaSeqExpressionResult } from '@/lib/rnaseqExpressionApi';

function download(name: string, content: Blob) {
  const url = URL.createObjectURL(content);
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = name; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function metadataFile(record: GeoRecord, columns: GeoCountColumn[]): File {
  const clean = (value: string) => value.replace(/[\t\r\n]+/g, ' ').trim();
  const rows = ['sample\tcondition\tgeo_accession\tgeo_title', ...columns.map(item =>
    `${clean(item.name)}\t${clean(item.condition)}\t${item.sample}\t${clean(item.title)}`)];
  return new File([rows.join('\n') + '\n'], `${record.accession}_metadata.tsv`, { type: 'text/tab-separated-values' });
}

export function GeoAnalysis({ record, onResult }: { record: GeoRecord; onResult: (result: RnaSeqExpressionResult) => void }) {
  const candidates = record.files.filter(item => /count/i.test(item.name)
    && /\.(csv|tsv|txt)(\.gz)?$/i.test(item.name)
    && !/(fpkm|tpm|rpkm|normalized|normalised|log2?|vst|rlog)/i.test(item.name));
  const [preview, setPreview] = useState<GeoCountPreview | null>(null);
  const [columns, setColumns] = useState<GeoCountColumn[]>([]);
  const [reference, setReference] = useState('');
  const [test, setTest] = useState('');
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');

  const prepare = useCallback(async (filename: string) => {
    setLoading(true); setError(''); setPreview(null);
    try {
      const input = await prepareGeoCounts(record, filename);
      setPreview(input);
      setColumns(input.columns);
      const groups = [...new Set(input.columns.map(item => item.condition).filter(Boolean))];
      setReference(groups.includes('sensitive') ? 'sensitive' : groups[0] ?? '');
      setTest(groups.includes('resistant') ? 'resistant' : groups[1] ?? '');
    } catch (caught: unknown) { setError(caught instanceof Error ? caught.message : 'The matrix could not be prepared.'); }
    finally { setLoading(false); }
  }, [record, setLoading, setError, setPreview, setColumns, setReference, setTest]);

  const onlyCandidate = candidates.length === 1 ? candidates[0].name : null;
  useEffect(() => {
    if (!onlyCandidate) return;
    const timer = window.setTimeout(() => { void prepare(onlyCandidate); }, 0);
    return () => window.clearTimeout(timer);
  }, [onlyCandidate, prepare]);

  const groups = [...new Set(columns.map(item => item.condition.trim()).filter(Boolean))];
  const counts = Object.fromEntries(groups.map(group => [group, columns.filter(item => item.condition.trim() === group).length]));
  const ready = preview && columns.length >= 4 && columns.every(item => item.sample && item.condition.trim())
    && new Set(columns.map(item => item.sample)).size === columns.length
    && reference !== test && (counts[reference] ?? 0) >= 2 && (counts[test] ?? 0) >= 2;

  const run = async () => {
    if (!preview || !ready) return;
    setRunning(true); setError('');
    try {
      const result = await runRnaSeqExpression({
        counts: preview.counts, metadata: metadataFile(record, columns),
        conditionColumn: 'condition', referenceLevel: reference, testLevel: test,
        minSamples: 0, topHeatmapGenes: 40,
      });
      onResult(result);
    } catch (caught: unknown) {
      const response = caught as { response?: { data?: { detail?: string } }; message?: string };
      setError(response.response?.data?.detail || response.message || 'R analysis could not be completed.');
    } finally { setRunning(false); }
  };

  return <div className="rounded-xl border border-glass-border bg-surface-1 p-4 sm:p-5">
    <p className="font-mono text-[10px] uppercase tracking-widest text-accent-cyan">From GEO counts to R figures</p>
    <h4 className="mt-1 text-sm font-semibold text-text-primary">Analyze published raw counts</h4>
    <p className="mt-1 text-xs leading-5 text-text-muted">BioNexus fetches the published matrix, validates integer counts, matches its columns to GEO samples, then runs DESeq2 and the existing PCA, heatmap, MA and volcano figures. Review the groups before statistical analysis.</p>

    {candidates.length ? <div className="mt-4 flex flex-wrap gap-2">{candidates.map(file => <button key={file.url} type="button" disabled={loading || running} onClick={() => prepare(file.name)} className="rounded-lg border border-glass-border bg-surface-0 px-3 py-2 text-xs text-text-secondary hover:text-text-primary disabled:opacity-50">{loading && candidates.length === 1 ? <CircleNotch className="mr-1 inline animate-spin" /> : null}{file.name}</button>)}</div>
      : <p className="mt-3 text-xs text-text-muted">No plain-text raw count matrix is listed for this series. FASTQ, single-cell, array or normalized-only files need an assay-specific workflow; no DESeq2 result is inferred from their metadata.</p>}

    {preview && <div className="mt-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-xs text-text-secondary"><strong className="text-text-primary">{preview.genes.toLocaleString()} genes · {columns.length} columns</strong><br />{preview.filename}</p><div className="flex gap-2"><button type="button" onClick={() => download(preview.counts.name, preview.counts)} className="inline-flex items-center gap-1 rounded-lg border border-glass-border px-3 py-2 text-xs text-text-secondary"><DownloadSimple /> Counts TSV</button><button type="button" onClick={() => download(`${record.accession}_metadata.tsv`, metadataFile(record, columns))} className="inline-flex items-center gap-1 rounded-lg border border-glass-border px-3 py-2 text-xs text-text-secondary"><DownloadSimple /> Metadata TSV</button></div></div>
      <div className="max-h-80 overflow-auto rounded-lg border border-glass-border"><table className="w-full min-w-[650px] text-left text-xs"><thead className="sticky top-0 bg-surface-0 text-text-muted"><tr><th className="px-3 py-2">Matrix column</th><th className="px-3 py-2">GEO sample</th><th className="px-3 py-2">Condition</th></tr></thead><tbody className="divide-y divide-glass-border">{columns.map((item, index) => <tr key={`${item.name}-${index}`}><td className="max-w-56 truncate px-3 py-2 font-mono text-text-primary" title={item.name}>{item.name}</td><td className="px-3 py-2"><select aria-label={`GEO sample for ${item.name}`} value={item.sample} onChange={event => setColumns(current => current.map((row, i) => i === index ? { ...row, sample: event.target.value, title: record.samples.find(sample => sample.accession === event.target.value)?.title ?? '' } : row))} className="w-full rounded border border-glass-border bg-surface-0 p-2 text-text-secondary"><option value="">Choose sample</option>{record.samples.map(sample => <option key={sample.accession} value={sample.accession}>{sample.accession} · {sample.title}</option>)}</select></td><td className="px-3 py-2"><input aria-label={`Condition for ${item.name}`} value={item.condition} onChange={event => setColumns(current => current.map((row, i) => i === index ? { ...row, condition: event.target.value } : row))} className="w-full rounded border border-glass-border bg-surface-0 p-2 text-text-primary" placeholder="Group" /></td></tr>)}</tbody></table></div>
      <p className="text-[11px] leading-5 text-text-muted">Suggested groups come from GEO sample titles; verify them against the study design. Matching sample IDs and at least two independent biological samples per compared group are required. Raw read QC cannot be inferred from the processed matrix.</p>
      <div className="flex flex-wrap items-end gap-3"><label className="text-[11px] text-text-muted">Reference group<select value={reference} onChange={event => setReference(event.target.value)} className="mt-1 block rounded-lg border border-glass-border bg-surface-0 px-3 py-2 text-xs text-text-primary"><option value="">Choose</option>{groups.map(group => <option key={group} value={group}>{group} ({counts[group]})</option>)}</select></label><label className="text-[11px] text-text-muted">Comparison group<select value={test} onChange={event => setTest(event.target.value)} className="mt-1 block rounded-lg border border-glass-border bg-surface-0 px-3 py-2 text-xs text-text-primary"><option value="">Choose</option>{groups.map(group => <option key={group} value={group}>{group} ({counts[group]})</option>)}</select></label><button type="button" onClick={run} disabled={!ready || running} className="inline-flex items-center gap-2 rounded-lg bg-accent-cyan/15 px-4 py-2 text-xs font-semibold text-text-primary hover:bg-accent-cyan/25 disabled:opacity-40">{running ? <CircleNotch className="animate-spin" /> : <ArrowRight />}{running ? 'Running R / DESeq2…' : 'Generate figures with R'}</button></div>
    </div>}
    {error && <p role="alert" className="mt-4 flex items-start gap-2 text-xs text-error"><Warning className="mt-0.5 shrink-0" />{error}</p>}
  </div>;
}

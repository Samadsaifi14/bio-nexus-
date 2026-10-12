'use client';

import { useMemo } from 'react';
import { DownloadSimple, FileText, Table, Dna } from '@phosphor-icons/react';

function downloadText(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function VcfPreview({ text }: { text: string }) {
  const lines = useMemo(() => text.split(/\r?\n/).filter(Boolean), [text]);
  const header = lines.find(l => l.startsWith('#CHROM'))?.replace(/^#/, '').split('\t') ?? ['CHROM','POS','ID','REF','ALT','QUAL','FILTER','INFO'];
  const data = lines.filter(l => !l.startsWith('#')).slice(0, 20).map(l => l.split('\t'));
  if (!data.length) return <div className="rounded-lg border border-glass-border bg-surface-1 p-4 text-xs text-text-muted">No variant records were emitted for this run.</div>;
  return <div className="overflow-hidden rounded-xl border border-glass-border">
    <div className="overflow-x-auto">
      <table className="min-w-full text-[11px]">
        <thead className="bg-surface-1 text-text-muted"><tr>{header.slice(0,8).map(h=><th key={h} className="whitespace-nowrap px-3 py-2 text-left font-semibold">{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-glass-border">{data.map((r,i)=><tr key={i} className="hover:bg-surface-1/60">{r.slice(0,8).map((v,j)=><td key={j} className={`px-3 py-2 font-mono text-text-secondary ${j === 7 ? 'max-w-80 truncate' : 'whitespace-nowrap'}`} title={v}>{v || '—'}</td>)}</tr>)}</tbody>
      </table>
    </div>
    <div className="border-t border-glass-border bg-surface-1 px-3 py-2 text-[10px] text-text-muted">Showing the first {data.length} VCF records. Download the VCF for the complete file.</div>
  </div>;
}

function SamPreview({ text }: { text: string }) {
  const data = useMemo(() => text.split(/\r?\n/).filter(l => l && !l.startsWith('@')).slice(0, 20).map(l => l.split('\t')), [text]);
  const heads = ['Read name','Flag','Reference','Position','MAPQ','CIGAR'];
  if (!data.length) return <div className="rounded-lg border border-glass-border bg-surface-1 p-4 text-xs text-text-muted">No alignment records were emitted for this run.</div>;
  return <div className="overflow-hidden rounded-xl border border-glass-border">
    <div className="overflow-x-auto">
      <table className="min-w-full table-fixed text-[11px]">
        <colgroup><col className="w-[38%]"/><col className="w-[9%]"/><col className="w-[14%]"/><col className="w-[14%]"/><col className="w-[10%]"/><col className="w-[15%]"/></colgroup>
        <thead className="bg-surface-1 text-text-muted"><tr>{heads.map(h=><th key={h} className="px-3 py-2 text-left font-semibold">{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-glass-border">{data.map((r,i)=><tr key={i} className="hover:bg-surface-1/60">{r.slice(0,6).map((v,j)=><td key={j} className="overflow-hidden text-ellipsis whitespace-nowrap px-3 py-2 font-mono text-text-secondary" title={v}>{v || '—'}</td>)}</tr>)}</tbody>
      </table>
    </div>
    <div className="border-t border-glass-border bg-surface-1 px-3 py-2 text-[10px] text-text-muted">Showing the first {data.length} SAM alignment records. Sequence and quality columns are intentionally hidden here to keep the preview readable; the downloaded SAM retains every field.</div>
  </div>;
}

export default function NgsArtifactPanel({ vcf = '', sam = '', pipeline }: { vcf?: string; sam?: string; pipeline: unknown }) {
  const artifacts = [
    ...(vcf ? [{ name: 'Variant calls', filename: 'bionexus-variants.vcf', mime: 'text/plain', content: vcf, description: 'Complete variant call file for downstream review and annotation.', icon: <Dna/> }] : []),
    ...(sam ? [{ name: 'Alignments', filename: 'bionexus-alignments.sam', mime: 'text/plain', content: sam, description: 'Complete alignment file with all SAM fields preserved.', icon: <Table/> }] : []),
    { name: 'Pipeline report', filename: 'bionexus-pipeline-report.json', mime: 'application/json', content: JSON.stringify(pipeline, null, 2), description: 'Machine-readable audit trail of stages, QC decisions and provenance.', icon: <FileText/> },
  ];

  return <div className="space-y-6">
    <div>
      <h3 className="text-sm font-semibold text-text-primary">Analysis files</h3>
      <p className="mt-1 text-xs leading-5 text-text-muted">The tables below are readable previews. Downloaded artifacts contain the complete scientific records.</p>
    </div>
    <div className="grid gap-3 md:grid-cols-3">{artifacts.map(a => <button key={a.filename} onClick={() => downloadText(a.filename, a.content, a.mime)} className="rounded-xl border border-glass-border bg-surface-1 p-4 text-left transition hover:border-accent-cyan/35"><div className="flex items-center justify-between"><div className="flex items-center gap-2 text-sm font-semibold text-text-primary">{a.icon}{a.name}</div><DownloadSimple className="text-accent-cyan"/></div><p className="mt-2 text-[11px] leading-4 text-text-muted">{a.description}</p><p className="mt-3 font-mono text-[10px] text-accent-cyan">Download complete file</p></button>)}</div>
    {vcf && <section><h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-muted">Variant records</h3><VcfPreview text={vcf}/></section>}
    {sam && <section><h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-muted">Alignment records</h3><SamPreview text={sam}/></section>}
    <details className="rounded-xl border border-glass-border"><summary className="cursor-pointer px-4 py-3 text-xs font-medium text-text-secondary">Advanced machine-readable report</summary><div className="border-t border-glass-border p-3 text-[11px] text-text-muted">This JSON is intended for reproducibility, automation and debugging, not as the primary result view.</div><pre className="max-h-80 overflow-auto border-t border-glass-border bg-surface-1 p-4 text-[10px] leading-5 text-text-muted">{JSON.stringify(pipeline, null, 2)}</pre></details>
  </div>;
}

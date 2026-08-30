'use client';

import { useMemo } from 'react';
import { DownloadSimple, FileText, Table, Dna } from '@phosphor-icons/react';

function downloadText(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
}

function VcfPreview({ text }: { text: string }) {
  const lines = useMemo(() => text.split(/\r?\n/).filter(Boolean), [text]);
  const header = lines.find(l => l.startsWith('#CHROM'))?.replace(/^#/, '').split('\t') ?? ['CHROM','POS','ID','REF','ALT','QUAL','FILTER','INFO'];
  const data = lines.filter(l => !l.startsWith('#')).slice(0, 25).map(l => l.split('\t'));
  if (!data.length) return <p className="text-xs text-text-muted">No variant records were emitted for this run.</p>;
  return <div className="overflow-x-auto rounded-lg border border-glass-border"><table className="min-w-full text-[11px]"><thead className="bg-surface-1 text-text-muted"><tr>{header.slice(0,8).map(h=><th key={h} className="px-2 py-2 text-left">{h}</th>)}</tr></thead><tbody className="divide-y divide-glass-border">{data.map((r,i)=><tr key={i}>{r.slice(0,8).map((v,j)=><td key={j} className="px-2 py-2 font-mono text-text-secondary">{v}</td>)}</tr>)}</tbody></table></div>;
}

function SamPreview({ text }: { text: string }) {
  const data = useMemo(() => text.split(/\r?\n/).filter(l => l && !l.startsWith('@')).slice(0, 25).map(l => l.split('\t')), [text]);
  const heads = ['QNAME','FLAG','RNAME','POS','MAPQ','CIGAR'];
  if (!data.length) return <p className="text-xs text-text-muted">No alignment records were emitted for this run.</p>;
  return <div className="overflow-x-auto rounded-lg border border-glass-border"><table className="min-w-full text-[11px]"><thead className="bg-surface-1 text-text-muted"><tr>{heads.map(h=><th key={h} className="px-2 py-2 text-left">{h}</th>)}</tr></thead><tbody className="divide-y divide-glass-border">{data.map((r,i)=><tr key={i}>{r.slice(0,6).map((v,j)=><td key={j} className="px-2 py-2 font-mono text-text-secondary">{v}</td>)}</tr>)}</tbody></table></div>;
}

export default function NgsArtifactPanel({ vcf = '', sam = '', pipeline }: { vcf?: string; sam?: string; pipeline: unknown }) {
  const artifacts = [
    ...(vcf ? [{ name: 'Variant calls', filename: 'bionexus-variants.vcf', mime: 'text/plain', content: vcf, description: 'VCF records from the variant-calling stage.', icon: <Dna/> }] : []),
    ...(sam ? [{ name: 'Alignments', filename: 'bionexus-alignments.sam', mime: 'text/plain', content: sam, description: 'SAM records used by downstream QC and genome visualization.', icon: <Table/> }] : []),
    { name: 'Pipeline report', filename: 'bionexus-pipeline-report.json', mime: 'application/json', content: JSON.stringify(pipeline, null, 2), description: 'Machine-readable audit trail with stages, QC, decisions and provenance.', icon: <FileText/> },
  ];
  return <div className="space-y-5">
    <div className="grid gap-3 md:grid-cols-3">{artifacts.map(a => <button key={a.filename} onClick={() => downloadText(a.filename, a.content, a.mime)} className="rounded-xl border border-glass-border bg-surface-1 p-4 text-left transition hover:border-accent-cyan/35"><div className="flex items-center justify-between"><div className="flex items-center gap-2 text-sm font-semibold text-text-primary">{a.icon}{a.name}</div><DownloadSimple className="text-accent-cyan"/></div><p className="mt-2 text-[11px] leading-4 text-text-muted">{a.description}</p><p className="mt-3 font-mono text-[10px] text-accent-cyan">Download file</p></button>)}</div>
    {vcf && <section><h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-muted">Variant table preview</h3><VcfPreview text={vcf}/></section>}
    {sam && <section><h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-muted">Alignment table preview</h3><SamPreview text={sam}/></section>}
    <details className="rounded-xl border border-glass-border"><summary className="cursor-pointer px-4 py-3 text-xs font-medium text-text-secondary">Advanced: machine-readable JSON</summary><pre className="max-h-80 overflow-auto border-t border-glass-border bg-surface-1 p-4 text-[10px] leading-5 text-text-muted">{JSON.stringify(pipeline, null, 2)}</pre></details>
  </div>;
}

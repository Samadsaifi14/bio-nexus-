'use client';

import { useState } from 'react';
import { Copy, Check } from '@phosphor-icons/react';

type UnknownRecord = Record<string, unknown>;

function titleCase(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function Scalar({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === '') return <span className="text-text-muted">Not reported</span>;
  if (typeof value === 'boolean') return <span>{value ? 'Yes' : 'No'}</span>;
  return <span>{String(value)}</span>;
}

function MetadataRows({ data }: { data: UnknownRecord }) {
  return <div className="divide-y divide-glass-border">{Object.entries(data).map(([key, value]) => {
    if (Array.isArray(value) || (value && typeof value === 'object')) return null;
    return <div key={key} className="grid gap-1 px-4 py-2.5 text-xs sm:grid-cols-[180px_1fr] sm:gap-4"><span className="text-text-muted">{titleCase(key)}</span><span className="break-words font-mono text-text-primary"><Scalar value={value}/></span></div>;
  })}</div>;
}

function ToolTable({ tools }: { tools: unknown[] }) {
  const rows = tools.filter((t): t is UnknownRecord => Boolean(t) && typeof t === 'object');
  if (!rows.length) return null;
  return <section className="space-y-2"><h4 className="text-xs font-semibold uppercase tracking-wider text-text-muted">Tools and versions</h4><div className="overflow-x-auto rounded-xl border border-glass-border"><table className="min-w-full text-xs"><thead className="bg-surface-1 text-text-muted"><tr><th className="px-3 py-2 text-left">Stage</th><th className="px-3 py-2 text-left">Tool</th><th className="px-3 py-2 text-left">Version</th></tr></thead><tbody className="divide-y divide-glass-border">{rows.map((tool, i)=><tr key={`${String(tool.stage)}-${i}`}><td className="whitespace-nowrap px-3 py-2 text-text-secondary">{titleCase(String(tool.stage ?? 'stage'))}</td><td className="px-3 py-2 font-mono text-text-primary">{String(tool.name ?? 'Not reported')}</td><td className="whitespace-nowrap px-3 py-2 font-mono text-text-secondary">{String(tool.version ?? 'Not reported')}</td></tr>)}</tbody></table></div></section>;
}

function InputTable({ inputs }: { inputs: unknown[] }) {
  const rows = inputs.filter((t): t is UnknownRecord => Boolean(t) && typeof t === 'object');
  if (!rows.length) return null;
  return <section className="space-y-2"><h4 className="text-xs font-semibold uppercase tracking-wider text-text-muted">Input files</h4><div className="overflow-hidden rounded-xl border border-glass-border"><div className="divide-y divide-glass-border">{rows.map((input, i) => {
    const checksum = input.checksum && typeof input.checksum === 'object' ? input.checksum as UnknownRecord : null;
    return <div key={i} className="grid gap-2 px-4 py-3 text-xs md:grid-cols-[1fr_100px_1fr]"><span className="font-mono text-text-primary">{String(input.name ?? 'Unnamed input')}</span><span className="uppercase text-text-muted">{String(checksum?.algorithm ?? 'checksum')}</span><span className="break-all font-mono text-text-secondary">{String(checksum?.value ?? 'Not reported')}</span></div>;
  })}</div></div></section>;
}

function ReferencePanel({ reference }: { reference: UnknownRecord }) {
  const artifacts = Array.isArray(reference.artifacts) ? reference.artifacts.filter((a): a is UnknownRecord => Boolean(a) && typeof a === 'object') : [];
  const scalar = Object.fromEntries(Object.entries(reference).filter(([k, v]) => k !== 'artifacts' && !Array.isArray(v) && !(v && typeof v === 'object')));
  return <section className="space-y-2"><h4 className="text-xs font-semibold uppercase tracking-wider text-text-muted">Reference</h4><div className="overflow-hidden rounded-xl border border-glass-border"><MetadataRows data={scalar}/>{artifacts.length > 0 && <div className="border-t border-glass-border p-4"><div className="mb-2 text-[11px] font-medium text-text-muted">Reference resources</div><div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{artifacts.map((a,i)=><div key={i} className="flex items-center justify-between rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-[11px]"><span className="text-text-secondary">{String(a.name ?? 'Artifact')}</span><span className={a.present ? 'text-good' : 'text-text-muted'}>{a.present ? 'Available' : 'Not bundled'}</span></div>)}</div></div>}</div></section>;
}

export function ProvenancePanel({ provenance }: { provenance?: Record<string, unknown> | null }) {
  if (!provenance || Object.keys(provenance).length === 0) return <p className="text-sm text-text-muted">This run did not emit provenance metadata.</p>;

  const schemaVersion = provenance.schema_version;
  const pipeline = provenance.pipeline && typeof provenance.pipeline === 'object' ? provenance.pipeline as UnknownRecord : null;
  const analysis = provenance.analysis && typeof provenance.analysis === 'object' ? provenance.analysis as UnknownRecord : null;
  const reference = provenance.reference && typeof provenance.reference === 'object' ? provenance.reference as UnknownRecord : null;
  const inputs = Array.isArray(provenance.inputs) ? provenance.inputs : [];
  const tools = Array.isArray(provenance.tools) ? provenance.tools : [];

  return <div className="space-y-6">
    <div><h3 className="text-sm font-semibold text-text-primary">Reproducibility and methods</h3><p className="mt-1 text-xs leading-5 text-text-muted">Human-readable provenance for this analysis. Machine-readable provenance remains available in the downloaded pipeline report.</p></div>
    <div className="overflow-hidden rounded-xl border border-glass-border"><div className="grid gap-px bg-glass-border md:grid-cols-3"><div className="bg-surface-1 p-4"><div className="text-[10px] uppercase tracking-wider text-text-muted">Schema version</div><div className="mt-1 font-mono text-sm text-text-primary"><Scalar value={schemaVersion}/></div></div><div className="bg-surface-1 p-4"><div className="text-[10px] uppercase tracking-wider text-text-muted">Pipeline</div><div className="mt-1 font-mono text-sm text-text-primary"><Scalar value={pipeline?.name}/></div></div><div className="bg-surface-1 p-4"><div className="text-[10px] uppercase tracking-wider text-text-muted">Pipeline version</div><div className="mt-1 font-mono text-sm text-text-primary"><Scalar value={pipeline?.version}/></div></div></div>{analysis && <MetadataRows data={analysis}/>}</div>
    <InputTable inputs={inputs}/>
    {reference && <ReferencePanel reference={reference}/>} 
    <ToolTable tools={tools}/>
  </div>;
}

export function RawEvidence({ value, label = 'Raw result payload' }: { value: unknown; label?: string }) {
  const [copied, setCopied] = useState(false);
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  const copy = async () => { await navigator.clipboard.writeText(text); setCopied(true); window.setTimeout(() => setCopied(false), 1500); };
  return <div><div className="mb-2 flex items-center justify-between"><p className="text-xs font-medium text-text-secondary">{label}</p><button onClick={copy} className="inline-flex items-center gap-1 rounded border border-glass-border px-2 py-1 text-[10px] text-text-muted hover:text-text-primary">{copied ? <Check /> : <Copy />}{copied ? 'Copied' : 'Copy'}</button></div><pre className="max-h-[520px] overflow-auto rounded-xl border border-glass-border bg-surface-1 p-4 text-[11px] leading-5 text-text-secondary">{text}</pre></div>;
}

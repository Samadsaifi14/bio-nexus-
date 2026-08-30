'use client';

import { useState } from 'react';
import { Copy, Check } from '@phosphor-icons/react';
import { ProvenanceTable, type ProvenanceEntry } from './ScientificResultsWorkspace';

export function ProvenancePanel({ provenance }: { provenance?: Record<string, unknown> | null }) {
  if (!provenance || Object.keys(provenance).length === 0) return <p className="text-sm text-text-muted">This run did not emit provenance metadata.</p>;
  const entries: ProvenanceEntry[] = Object.entries(provenance).map(([label, value]) => ({ label: label.replaceAll('_', ' '), value: typeof value === 'object' ? JSON.stringify(value) : String(value ?? '—') }));
  return <div><p className="mb-3 text-xs leading-5 text-text-muted">Reproducibility metadata emitted by the analysis engine. Tool versions, reference/database releases and parameters should be retained here whenever the backend provides them.</p><ProvenanceTable entries={entries} /></div>;
}

export function RawEvidence({ value, label = 'Raw result payload' }: { value: unknown; label?: string }) {
  const [copied, setCopied] = useState(false);
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  const copy = async () => { await navigator.clipboard.writeText(text); setCopied(true); window.setTimeout(() => setCopied(false), 1500); };
  return <div><div className="mb-2 flex items-center justify-between"><p className="text-xs font-medium text-text-secondary">{label}</p><button onClick={copy} className="inline-flex items-center gap-1 rounded border border-glass-border px-2 py-1 text-[10px] text-text-muted hover:text-text-primary">{copied ? <Check /> : <Copy />}{copied ? 'Copied' : 'Copy'}</button></div><pre className="max-h-[520px] overflow-auto rounded-xl border border-glass-border bg-surface-1 p-4 text-[11px] leading-5 text-text-secondary">{text}</pre></div>;
}

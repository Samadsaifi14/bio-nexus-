'use client';

import { useState, type ReactNode } from 'react';
import { CheckCircle, Warning, XCircle, Flask, Database, FileText, Code, Brain } from '@phosphor-icons/react';

export type ScientificStatus = 'PASS' | 'WARN' | 'FAIL' | 'INFO';
export type ScientificMetric = { label: string; value: ReactNode; detail?: string; status?: ScientificStatus };
export type ProvenanceEntry = { label: string; value: ReactNode };

const tabs = [
  ['overview', 'Overview'], ['qc', 'QC'], ['results', 'Results'], ['raw', 'Raw'], ['methods', 'Methods'], ['ai', 'AI interpretation'],
] as const;

type TabId = typeof tabs[number][0];

const statusStyle: Record<ScientificStatus, string> = {
  PASS: 'border-good/30 bg-good/8 text-good',
  WARN: 'border-warn/30 bg-warn/8 text-warn',
  FAIL: 'border-error/30 bg-error/8 text-error',
  INFO: 'border-glass-border bg-surface-1 text-text-secondary',
};

function StatusIcon({ status }: { status: ScientificStatus }) {
  if (status === 'PASS') return <CheckCircle className="h-4 w-4" weight="fill" />;
  if (status === 'WARN') return <Warning className="h-4 w-4" weight="fill" />;
  if (status === 'FAIL') return <XCircle className="h-4 w-4" weight="fill" />;
  return <Flask className="h-4 w-4" />;
}

export function MetricGrid({ metrics }: { metrics: ScientificMetric[] }) {
  return <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-glass-border bg-glass-border md:grid-cols-4">
    {metrics.map((metric) => <div key={metric.label} className="bg-surface-1 p-3.5">
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.08em] text-text-muted">
        {metric.status && <span className={statusStyle[metric.status].split(' ').at(-1)}><StatusIcon status={metric.status} /></span>}
        {metric.label}
      </div>
      <div className="mt-1 font-mono text-sm font-semibold text-text-primary">{metric.value ?? '—'}</div>
      {metric.detail && <p className="mt-1 text-[11px] leading-4 text-text-muted">{metric.detail}</p>}
    </div>)}
  </div>;
}

export function ProvenanceTable({ entries }: { entries: ProvenanceEntry[] }) {
  return <div className="overflow-hidden rounded-xl border border-glass-border">
    {entries.map((entry, index) => <div key={entry.label} className={`grid grid-cols-[150px_1fr] gap-4 px-4 py-2.5 text-xs ${index ? 'border-t border-glass-border' : ''}`}>
      <span className="text-text-muted">{entry.label}</span>
      <span className="break-all font-mono text-text-primary">{entry.value ?? '—'}</span>
    </div>)}
  </div>;
}

export default function ScientificResultsWorkspace({
  title, subtitle, status = 'INFO', statusLabel, metadata = [], metrics = [], overview, qc, results, raw, methods, ai,
}: {
  title: string; subtitle?: string; status?: ScientificStatus; statusLabel?: string; metadata?: ProvenanceEntry[]; metrics?: ScientificMetric[];
  overview?: ReactNode; qc?: ReactNode; results?: ReactNode; raw?: ReactNode; methods?: ReactNode; ai?: ReactNode;
}) {
  const [active, setActive] = useState<TabId>('overview');
  const content: Record<TabId, ReactNode> = { overview, qc, results, raw, methods, ai };
  const icons: Record<TabId, ReactNode> = { overview: <Flask />, qc: <CheckCircle />, results: <Database />, raw: <Code />, methods: <FileText />, ai: <Brain /> };

  return <section className="overflow-hidden rounded-2xl border border-glass-border bg-surface-0">
    <header className="border-b border-glass-border px-5 py-4">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-start">
        <div><h2 className="text-lg font-semibold text-text-primary">{title}</h2>{subtitle && <p className="mt-1 text-xs text-text-muted">{subtitle}</p>}</div>
        <span className={`inline-flex w-fit items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] font-semibold ${statusStyle[status]}`}><StatusIcon status={status} />{statusLabel ?? status}</span>
      </div>
      {metadata.length > 0 && <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[11px] text-text-muted">{metadata.slice(0, 6).map((item) => <span key={item.label}><b className="font-medium text-text-secondary">{item.label}:</b> {item.value}</span>)}</div>}
    </header>
    {metrics.length > 0 && <div className="p-4 pb-0"><MetricGrid metrics={metrics} /></div>}
    <nav className="mt-4 flex gap-1 overflow-x-auto border-y border-glass-border bg-surface-1 px-3 py-1.5" aria-label="Scientific result sections">
      {tabs.map(([id, label]) => <button key={id} onClick={() => setActive(id)} className={`flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-2 text-xs font-medium transition ${active === id ? 'bg-surface-0 text-text-primary ring-1 ring-glass-border' : 'text-text-muted hover:text-text-primary'}`}><span className="h-3.5 w-3.5">{icons[id]}</span>{label}</button>)}
    </nav>
    <div className="min-h-52 p-5">{content[active] ?? <p className="text-sm text-text-muted">No data was emitted for this section.</p>}</div>
  </section>;
}

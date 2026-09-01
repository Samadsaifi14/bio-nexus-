'use client';

import { CheckCircle, Warning, XCircle, Info } from '@phosphor-icons/react';

type Metric = { name?: string; value?: number | string | null; status?: string; expected?: string | null; detail?: string | null };
type Stage = { step?: string; evidence_level?: string; inputs?: string[]; outputs?: string[]; qc?: { status?: string; decision?: string; metrics?: Metric[] } | null; decision?: string };

const evidenceLabel = (level?: string) => level === 'MEASURED' ? 'Measured' : level === 'INFERRED' ? 'Inferred' : level === 'SURROGATE' ? 'Surrogate' : 'Computed from input';

const statusClass = (status?: string) => status === 'PASS' ? 'text-good bg-good/10' : status === 'WARN' ? 'text-warn bg-warn/10' : status === 'FAIL' ? 'text-error bg-error/10' : 'text-text-muted bg-surface-1';

function Icon({ status }: { status?: string }) {
  if (status === 'PASS') return <CheckCircle weight="fill" />;
  if (status === 'WARN') return <Warning weight="fill" />;
  if (status === 'FAIL') return <XCircle weight="fill" />;
  return <Info />;
}

export default function StageEvidenceTable({ stages = [] }: { stages?: Stage[] }) {
  if (!Array.isArray(stages) || !stages.length) return <div className="rounded-xl border border-glass-border bg-surface-1 p-4 text-sm text-text-muted">No QC stages were returned for this run.</div>;
  return <div className="overflow-x-auto rounded-xl border border-glass-border">
    <table className="w-full min-w-[860px] text-left text-xs">
      <thead className="bg-surface-1 text-[10px] uppercase tracking-[0.08em] text-text-muted"><tr><th className="px-3 py-2.5">Analysis step</th><th className="px-3 py-2.5">Evidence</th><th className="px-3 py-2.5">QC</th><th className="px-3 py-2.5">Observed metrics</th><th className="px-3 py-2.5">Artifacts</th><th className="px-3 py-2.5">Decision</th></tr></thead>
      <tbody className="divide-y divide-glass-border">{stages.map((stage, index) => {
        const metrics = Array.isArray(stage.qc?.metrics) ? stage.qc!.metrics! : [];
        const outputs = Array.isArray(stage.outputs) ? stage.outputs : [];
        return <tr key={`${stage.step ?? 'stage'}-${index}`} className="align-top hover:bg-surface-1/60">
          <td className="px-3 py-3 font-medium text-text-primary"><span className="mr-2 font-mono text-text-muted">{String(index + 1).padStart(2, '0')}</span>{stage.step ?? 'Unnamed stage'}</td>
          <td className="px-3 py-3"><span className="rounded border border-glass-border bg-surface-1 px-2 py-1 text-[10px] font-medium text-text-secondary">{evidenceLabel(stage.evidence_level)}</span></td>
          <td className="px-3 py-3"><span className={`inline-flex items-center gap-1 rounded px-2 py-1 font-semibold ${statusClass(stage.qc?.status)}`}><span className="h-3 w-3"><Icon status={stage.qc?.status} /></span>{stage.qc?.status ?? 'NOT REPORTED'}</span></td>
          <td className="px-3 py-3"><div className="flex max-w-lg flex-wrap gap-1">{metrics.length ? metrics.slice(0, 8).map((metric, mIndex) => <span title={[metric.expected, metric.detail].filter(Boolean).join(' · ')} key={`${metric.name ?? 'metric'}-${mIndex}`} className={`rounded border border-glass-border px-1.5 py-0.5 font-mono ${statusClass(metric.status)}`}>{metric.name ?? 'metric'}: {metric.value ?? '—'}</span>) : <span className="text-text-muted">No metrics reported</span>}</div></td>
          <td className="px-3 py-3 text-text-muted"><div className="max-w-52 truncate" title={outputs.join(', ')}>{outputs.length ? outputs.join(', ') : 'Not reported'}</div></td>
          <td className="px-3 py-3 font-mono text-text-secondary">{stage.decision ?? stage.qc?.decision ?? '—'}</td>
        </tr>;
      })}</tbody>
    </table>
  </div>;
}

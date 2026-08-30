'use client';

import { CheckCircle, Warning, XCircle } from '@phosphor-icons/react';

type Metric = { name: string; value: number | null; status: string; expected: string | null; detail: string | null };
type Stage = { step: string; tool: string; version: string; inputs: string[]; outputs: string[]; qc: { status: string; decision: string; metrics: Metric[] } | null; decision: string };

const statusClass = (status?: string) => status === 'PASS' ? 'text-good bg-good/8' : status === 'WARN' ? 'text-warn bg-warn/8' : status === 'FAIL' ? 'text-error bg-error/8' : 'text-text-muted bg-surface-1';

function Icon({ status }: { status?: string }) {
  if (status === 'PASS') return <CheckCircle weight="fill" />;
  if (status === 'WARN') return <Warning weight="fill" />;
  return <XCircle weight="fill" />;
}

export default function StageEvidenceTable({ stages }: { stages: Stage[] }) {
  return <div className="overflow-x-auto rounded-xl border border-glass-border">
    <table className="w-full min-w-[820px] text-left text-xs">
      <thead className="bg-surface-1 text-[10px] uppercase tracking-[0.08em] text-text-muted"><tr><th className="px-3 py-2.5">Stage</th><th className="px-3 py-2.5">Tool</th><th className="px-3 py-2.5">QC</th><th className="px-3 py-2.5">Key metrics</th><th className="px-3 py-2.5">Artifacts</th><th className="px-3 py-2.5">Decision</th></tr></thead>
      <tbody className="divide-y divide-glass-border">
        {stages.map((stage, index) => <tr key={`${stage.step}-${index}`} className="align-top hover:bg-surface-1/60">
          <td className="px-3 py-3 font-medium text-text-primary"><span className="mr-2 font-mono text-text-muted">{String(index + 1).padStart(2, '0')}</span>{stage.step}</td>
          <td className="px-3 py-3"><div className="font-mono text-text-primary">{stage.tool}</div><div className="mt-0.5 text-[10px] text-text-muted">{stage.version || 'version not reported'}</div></td>
          <td className="px-3 py-3"><span className={`inline-flex items-center gap-1 rounded px-2 py-1 font-semibold ${statusClass(stage.qc?.status)}`}><span className="h-3 w-3"><Icon status={stage.qc?.status} /></span>{stage.qc?.status ?? '—'}</span></td>
          <td className="px-3 py-3"><div className="flex max-w-md flex-wrap gap-1">{stage.qc?.metrics?.slice(0, 6).map((metric) => <span title={[metric.expected, metric.detail].filter(Boolean).join(' · ')} key={metric.name} className={`rounded border border-glass-border px-1.5 py-0.5 font-mono ${statusClass(metric.status)}`}>{metric.name}: {metric.value ?? '—'}</span>)}</div></td>
          <td className="px-3 py-3 text-text-muted"><div className="max-w-48 truncate" title={stage.outputs.join(', ')}>{stage.outputs.length ? stage.outputs.join(', ') : '—'}</div></td>
          <td className="px-3 py-3 font-mono text-text-secondary">{stage.decision}</td>
        </tr>)}
      </tbody>
    </table>
  </div>;
}

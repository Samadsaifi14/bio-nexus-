'use client';

import { CheckCircle, Warning, XCircle, ShieldCheck } from '@phosphor-icons/react';

type Metric = { name?: string; value?: number | string | boolean | null; status?: string; expected?: string | null; detail?: string | null };
type Stage = { step?: string; qc?: { status?: string; metrics?: Metric[] } | null; decision?: string };

function humanize(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatMetric(metric: Metric) {
  const value = metric.value === null || metric.value === undefined ? 'not reported' : String(metric.value);
  const expected = metric.expected ? `; expected ${metric.expected}` : '';
  return `${humanize(metric.name || 'metric')}: ${value}${expected}`;
}

export default function NgsEvidenceInterpretation({
  stages,
  pipelineStatus,
  warnings = [],
  integrityErrors = [],
  demonstration = false,
}: {
  stages: Stage[];
  pipelineStatus: string;
  warnings?: string[];
  integrityErrors?: string[];
  demonstration?: boolean;
}) {
  const failedStages = stages.filter((s) => s.qc?.status === 'FAIL');
  const warnedStages = stages.filter((s) => s.qc?.status === 'WARN');
  const flaggedMetrics = stages.flatMap((stage) =>
    stage.step === 'final_gate' ? [] :
    (stage.qc?.metrics || [])
      .filter((metric) => metric.status === 'WARN' || metric.status === 'FAIL')
      .map((metric) => ({ stage: stage.step || 'unknown stage', metric })),
  );
  const uniqueWarnings = [...new Set(warnings.filter(Boolean))];
  const ready = pipelineStatus === 'ANALYSIS_READY' || pipelineStatus === 'PASS';
  const readyWithWarnings = pipelineStatus === 'ANALYSIS_READY_WITH_WARNINGS' || pipelineStatus === 'WARN';
  const blocked = pipelineStatus === 'NOT_ANALYSIS_READY' || pipelineStatus === 'FAIL' || integrityErrors.length > 0;

  const headline = blocked
    ? 'Result requires review before interpretation'
    : readyWithWarnings
      ? 'Analysis completed with evidence-backed warnings'
      : ready
        ? 'Analysis passed the configured readiness gate'
        : 'Analysis completed with an unrecognized readiness state';

  return <div className="space-y-5">
    <div className={`rounded-xl border p-4 ${blocked ? 'border-error/25 bg-error/7' : readyWithWarnings ? 'border-warn/25 bg-warn/7' : 'border-good/25 bg-good/7'}`}>
      <div className="flex items-start gap-3">
        {blocked ? <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-error" weight="fill"/> : readyWithWarnings ? <Warning className="mt-0.5 h-5 w-5 shrink-0 text-warn" weight="fill"/> : <CheckCircle className="mt-0.5 h-5 w-5 shrink-0 text-good" weight="fill"/>}
        <div><h3 className="text-sm font-semibold text-text-primary">{headline}</h3><p className="mt-1 text-xs leading-5 text-text-secondary">This interpretation is generated deterministically from the emitted QC statuses, metric values, decisions and warnings. It does not invent biological findings or infer values that are absent from the run.</p></div>
      </div>
    </div>

    <div className="grid gap-3 md:grid-cols-3">
      <div className="rounded-xl border border-glass-border bg-surface-1 p-4"><p className="text-[10px] uppercase tracking-wider text-text-muted">Failed stages</p><p className="mt-1 font-mono text-lg font-semibold text-text-primary">{failedStages.length}</p></div>
      <div className="rounded-xl border border-glass-border bg-surface-1 p-4"><p className="text-[10px] uppercase tracking-wider text-text-muted">Warning stages</p><p className="mt-1 font-mono text-lg font-semibold text-text-primary">{warnedStages.length}</p></div>
      <div className="rounded-xl border border-glass-border bg-surface-1 p-4"><p className="text-[10px] uppercase tracking-wider text-text-muted">Evidence gaps / flags</p><p className="mt-1 font-mono text-lg font-semibold text-text-primary">{flaggedMetrics.length}</p></div>
    </div>

    {integrityErrors.length > 0 && <section><h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-error">Integrity blockers</h4><div className="space-y-2">{[...new Set(integrityErrors)].map((item) => <div key={item} className="rounded-lg border border-error/20 bg-error/5 px-3 py-2 text-xs text-text-secondary">{item}</div>)}</div></section>}

    {flaggedMetrics.length > 0 ? <section><h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-muted">Evidence requiring attention</h4><div className="overflow-hidden rounded-xl border border-glass-border">{flaggedMetrics.map(({ stage, metric }, index) => <div key={`${stage}-${metric.name}-${index}`} className={`grid gap-1 px-4 py-3 text-xs md:grid-cols-[170px_1fr] ${index ? 'border-t border-glass-border' : ''}`}><span className="font-medium text-text-primary">{humanize(stage)}</span><span className={metric.status === 'FAIL' ? 'text-error' : 'text-warn'}>{formatMetric(metric)}{metric.detail ? ` — ${metric.detail}` : ''}</span></div>)}</div></section> : <div className="rounded-xl border border-good/20 bg-good/5 p-4 text-xs text-text-secondary">No WARN or FAIL metrics were emitted by the evaluated stages.</div>}

    {uniqueWarnings.length > 0 && <section><h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-muted">Pipeline warnings</h4><div className="space-y-2">{uniqueWarnings.map((warning) => <div key={warning} className="rounded-lg border border-warn/20 bg-warn/5 px-3 py-2 text-xs text-text-secondary">{warning}</div>)}</div></section>}

    {demonstration && <div className="flex items-start gap-2 rounded-xl border border-info/20 bg-info/5 p-4 text-xs leading-5 text-text-secondary"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-info"/><span>Synthetic demonstration data can validate execution, rendering and QC logic, but it must not be used to make biological, diagnostic or clinical conclusions.</span></div>}
  </div>;
}

'use client';

import { ArrowRight, CheckCircle, Circle, Warning, XCircle } from '@phosphor-icons/react';
import type { Ngs2Stage } from '@/lib/api';

type Status = 'PASS' | 'WARN' | 'FAIL' | 'NA';

function statusOf(stage: Ngs2Stage): Status {
  const data = stage.data && typeof stage.data === 'object' && !Array.isArray(stage.data)
    ? stage.data as Record<string, unknown>
    : {};
  if (data.status === 'NOT_EVALUATED' || data.status === 'NOT_EXECUTED_IN_PREVIEW' || data.unevaluated) return 'NA';
  if (stage.qc?.status === 'PASS' || stage.qc?.status === 'WARN' || stage.qc?.status === 'FAIL') return stage.qc.status;
  return 'NA';
}

function statusClass(status: Status) {
  if (status === 'PASS') return 'border-good/30 bg-good/5 text-good';
  if (status === 'WARN') return 'border-warn/30 bg-warn/5 text-warn';
  if (status === 'FAIL') return 'border-error/30 bg-error/5 text-error';
  return 'border-glass-border bg-surface-1 text-text-muted';
}

function StatusIcon({ status }: { status: Status }) {
  if (status === 'PASS') return <CheckCircle weight="fill" />;
  if (status === 'WARN') return <Warning weight="fill" />;
  if (status === 'FAIL') return <XCircle weight="fill" />;
  return <Circle />;
}

export default function NgsRunDiagram({ stages }: { stages: Ngs2Stage[] }) {
  if (!stages.length) return null;

  return (
    <section className="rounded-xl border border-glass-border bg-surface-0 p-4" aria-label="NGS run evidence diagram">
      <div className="mb-4">
        <p className="text-sm font-semibold text-text-primary">Run evidence diagram</p>
        <p className="mt-1 text-[11px] leading-4 text-text-muted">
          This diagram is generated from the stages actually returned by the run. It is a provenance/status view, not an invented biological result.
        </p>
      </div>
      <div className="overflow-x-auto pb-2">
        <div className="flex min-w-max items-stretch gap-2">
          {stages.map((stage, index) => {
            const status = statusOf(stage);
            return (
              <div key={`${stage.step}-${index}`} className="flex items-center gap-2">
                <div className="w-44 rounded-lg border border-glass-border bg-surface-1 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className={`inline-flex h-6 w-6 items-center justify-center rounded-full border text-[11px] ${statusClass(status)}`}>
                      <StatusIcon status={status} />
                    </span>
                    <span className="font-mono text-[9px] text-text-muted">{status}</span>
                  </div>
                  <p className="mt-2 text-xs font-medium capitalize text-text-primary">{stage.step.replaceAll('_', ' ')}</p>
                  <p className="mt-1 truncate text-[10px] text-text-muted" title={`${stage.tool || 'unknown tool'} ${stage.version || ''}`}>
                    {stage.tool || 'Tool not recorded'}{stage.version ? ` · ${stage.version}` : ''}
                  </p>
                  <p className="mt-2 text-[9px] uppercase tracking-[0.08em] text-text-muted">{stage.evidence_level || 'Evidence not labelled'}</p>
                </div>
                {index < stages.length - 1 && <ArrowRight className="h-4 w-4 shrink-0 text-text-muted" />}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

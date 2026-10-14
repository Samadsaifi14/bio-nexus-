'use client';

import { explainRnaSeqResult } from '@/lib/rnaseqInterpretation';
import { safeInterpretationHref } from '@/lib/interpretationStream';
import type { RnaSeqExpressionResult } from '@/lib/rnaseqExpressionApi';

export function RnaSeqInterpretation({ result }: { result: RnaSeqExpressionResult }) {
  const report = explainRnaSeqResult(result);
  return <section className="space-y-4 rounded-xl border border-glass-border bg-surface-0 p-5">
    <div><h3 className="text-sm font-semibold text-text-primary">{report.title}</h3>
      <p className="mt-1 text-xs leading-5 text-text-muted">Deterministic explanation of this saved run. Available without an AI provider; no statistics are recalculated.</p></div>
    <div className="space-y-4">{report.statements.map(statement => <article key={statement.title}>
      <h4 className="text-xs font-semibold text-text-primary">{statement.title}</h4>
      <p className="mt-1 text-xs leading-6 text-text-secondary">{statement.text}</p>
      <div className="mt-2 flex flex-wrap gap-3 text-[11px]">{statement.artifacts.map(name => {
        const entry = result.artifacts.find(item => item.name === name);
        const href = entry ? safeInterpretationHref(entry.url) : null;
        return href ? <a key={name} href={href} target="_blank" rel="noopener noreferrer" className="text-accent-cyan underline">{name}</a> : null;
      })}</div>
    </article>)}</div>
    <details className="rounded-lg border border-glass-border p-3"><summary className="cursor-pointer text-xs font-semibold">Interpretation limits and review flags</summary>
      <ul className="mt-3 list-disc space-y-2 pl-5 text-xs leading-5 text-text-secondary">{report.caveats.map(value => <li key={value}>{value}</li>)}</ul>
    </details>
    <p className="text-[11px] text-text-muted">Run: <span className="font-mono">{result.run_id}</span></p>
  </section>;
}

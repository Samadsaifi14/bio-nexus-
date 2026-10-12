'use client';

import type { NgsPortableBenchmark } from '@/lib/api';

interface NgsPortableBenchmarkCardProps {
  report: NgsPortableBenchmark;
}

export function NgsPortableBenchmarkCard({ report }: NgsPortableBenchmarkCardProps) {
  const call = report.expected_call;
  return <section className="data-card overflow-hidden">
    <div className="flex flex-col gap-3 border-b border-glass-border p-5 sm:flex-row sm:items-start sm:justify-between">
      <div><div className="flex items-center gap-2"><h2 className="text-sm font-semibold text-text-primary">Portable NGS positive control</h2><span className="rounded border border-good/20 bg-good/10 px-2 py-0.5 font-mono text-[9px] text-good">{report.status}</span></div><p className="mt-1 text-xs leading-5 text-text-muted">{report.biological_scope}. This measures workflow consistency, not real-sample or full-pipeline accuracy.</p></div>
      <span className="font-mono text-[10px] text-text-muted">{report.benchmark}</span>
    </div>
    <div className="grid gap-px bg-glass-border md:grid-cols-4"><div className="bg-surface-0 p-4"><div className="text-[10px] uppercase tracking-wider text-text-muted">Expected call</div><div className="mt-1 font-mono text-xs text-text-primary">{call.chrom}:{call.pos} {call.ref}&gt;{call.alt}</div></div><div className="bg-surface-0 p-4"><div className="text-[10px] uppercase tracking-wider text-text-muted">Genotype</div><div className="mt-1 font-mono text-xs text-text-primary">{call.genotype} · DP {call.depth} · AD {call.allelic_depth}</div></div><div className="bg-surface-0 p-4"><div className="text-[10px] uppercase tracking-wider text-text-muted">Output parity</div><div className="mt-1 font-mono text-xs text-good">{report.workflow_output_parity ? 'EXACT MATCH' : 'MISMATCH'}</div></div><div className="bg-surface-0 p-4"><div className="text-[10px] uppercase tracking-wider text-text-muted">Normalized SHA-256</div><div className="mt-1 truncate font-mono text-xs text-text-primary" title={report.reports[0]?.normalized_sha256}>{report.reports[0]?.normalized_sha256.slice(0, 12)}…</div></div></div>
    <div className="overflow-x-auto"><table className="min-w-full text-xs"><thead className="bg-surface-1 text-text-muted"><tr><th className="px-4 py-2 text-left">Execution</th><th className="px-4 py-2 text-left">Evidence</th><th className="px-4 py-2 text-right">TP</th><th className="px-4 py-2 text-right">FP</th><th className="px-4 py-2 text-right">FN</th><th className="px-4 py-2 text-right">Precision</th><th className="px-4 py-2 text-right">Recall</th><th className="px-4 py-2 text-right">F1</th></tr></thead><tbody className="divide-y divide-glass-border">{report.reports.map(row => <tr key={row.orchestrator}><td className="px-4 py-3 font-medium text-text-primary">{row.orchestrator}</td><td className="px-4 py-3 font-mono text-[10px] text-text-muted">{row.execution.replaceAll('_', ' ')}</td><td className="px-4 py-3 text-right font-mono">{row.tp}</td><td className="px-4 py-3 text-right font-mono">{row.fp}</td><td className="px-4 py-3 text-right font-mono">{row.fn}</td><td className="px-4 py-3 text-right font-mono">{row.precision.toFixed(3)}</td><td className="px-4 py-3 text-right font-mono">{row.recall.toFixed(3)}</td><td className="px-4 py-3 text-right font-mono text-good">{row.f1.toFixed(3)}</td></tr>)}</tbody></table></div>
    <div className="border-t border-warn/15 bg-warn/5 px-5 py-3 text-[11px] leading-5 text-text-muted">Galaxy wrapper lint passed, but the local Galaxy server test did not complete because dependency downloads were interrupted. The Galaxy row represents execution of the wrapper command without a Galaxy server. It must not be presented as public Galaxy parity.</div>
  </section>;
}

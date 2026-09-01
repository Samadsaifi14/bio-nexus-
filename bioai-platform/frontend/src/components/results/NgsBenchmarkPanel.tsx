'use client';

import type { Ngs2BenchmarkComparison } from '@/lib/api';

interface NgsBenchmarkPanelProps {
  claim?: string;
  summary?: string;
  sameOrBetterSupported?: boolean;
  comparisons?: Ngs2BenchmarkComparison[];
  analysisGrade?: string;
  researchReady?: boolean;
  requirements?: Array<{ id: string; label: string; detail: string; status: string }>;
  inputSampling?: { mode: string; record_cap_per_file: number; truncated_files: string[]; all_records_processed: boolean };
}

export function NgsBenchmarkPanel({ claim, summary, sameOrBetterSupported = false, comparisons = [], analysisGrade, researchReady = false, requirements = [], inputSampling }: NgsBenchmarkPanelProps) {
  return <div className="space-y-4">
    <div className="rounded-xl border border-warn/25 bg-warn/5 p-4">
      <div className="text-xs font-semibold text-text-primary">Accuracy claim: {sameOrBetterSupported ? 'supported for this benchmark' : 'not established'}</div>
      <p className="mt-1 text-xs leading-5 text-text-secondary">{summary || 'No truth-set comparison was reported.'}</p>
      <p className="mt-2 font-mono text-[10px] text-text-muted">{claim || 'NO_ACCURACY_CLAIM'}</p>
      <div className="mt-3 flex flex-wrap gap-2"><span className="rounded border border-warn/25 px-2 py-1 font-mono text-[10px] text-warn">{analysisGrade?.replaceAll('_', ' ') || 'GRADE NOT REPORTED'}</span><span className="rounded border border-glass-border px-2 py-1 font-mono text-[10px] text-text-muted">{researchReady ? 'RESEARCH READY' : 'NOT RESEARCH READY'}</span></div>
    </div>
    {inputSampling && <div className="rounded-xl border border-glass-border bg-surface-1 p-4"><h3 className="text-xs font-semibold text-text-primary">Input processing scope</h3><p className="mt-1 text-xs text-text-secondary">{inputSampling.all_records_processed ? 'All records in the supplied files were processed.' : `Only the first ${inputSampling.record_cap_per_file.toLocaleString()} records per FASTQ were processed.`}</p>{inputSampling.truncated_files.length > 0 && <p className="mt-2 break-words font-mono text-[10px] text-warn">Truncated: {inputSampling.truncated_files.join(', ')}</p>}</div>}
    {requirements.length > 0 && <div className="overflow-hidden rounded-xl border border-glass-border"><div className="border-b border-glass-border bg-surface-1 px-4 py-3"><h3 className="text-sm font-semibold text-text-primary">Production-readiness gaps</h3><p className="mt-1 text-[11px] leading-5 text-text-muted">These items must be evidenced before this workflow can be compared with nf-core/sarek or used for research conclusions.</p></div><div className="divide-y divide-glass-border">{requirements.map(item => <div key={item.id} className="grid gap-2 p-4 sm:grid-cols-[1fr_100px]"><div><div className="text-xs font-medium text-text-primary">{item.label}</div><p className="mt-1 text-[11px] leading-5 text-text-muted">{item.detail}</p></div><span className="h-fit rounded border border-error/20 bg-error/5 px-2 py-1 text-center font-mono text-[10px] text-error">{item.status}</span></div>)}</div></div>}
    <div className="overflow-hidden rounded-xl border border-glass-border">
      <div className="border-b border-glass-border bg-surface-1 px-4 py-3"><h3 className="text-sm font-semibold text-text-primary">Independent benchmark sources</h3><p className="mt-1 text-[11px] leading-5 text-text-muted">A listed source is not a completed comparison. Scores appear only after the matching truth data and confident regions are evaluated.</p></div>
      <div className="divide-y divide-glass-border">{comparisons.map(item => <div key={item.id} className="grid gap-3 p-4 md:grid-cols-[1fr_140px]">
        <div><a href={item.url} target="_blank" rel="noreferrer" className="text-xs font-semibold text-accent-cyan hover:underline">{item.source}</a><p className="mt-1 text-xs text-text-secondary">{item.scope}</p><p className="mt-1 text-[11px] leading-5 text-text-muted">{item.comparison_method}</p><p className="mt-2 text-[11px] text-text-muted">{item.reason}</p></div>
        <div className="md:text-right"><span className={`inline-flex rounded border px-2 py-1 font-mono text-[10px] ${item.status === 'EVALUATED' ? 'border-good/25 bg-good/10 text-good' : 'border-glass-border bg-surface-1 text-text-muted'}`}>{item.status.replaceAll('_', ' ')}</span>{item.metrics && <pre className="mt-2 text-[10px] text-text-secondary">{JSON.stringify(item.metrics, null, 2)}</pre>}</div>
      </div>)}</div>
    </div>
  </div>;
}

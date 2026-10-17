'use client';
import { useEffect, useState } from 'react';
import { longApi } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';

type Monitor = { run_id: string; execution_state: string; process_evidence: {
  state: string; message?: string; observed_process_records?: number; states?: Record<string, number>;
  trace_sha256?: string; incomplete_last_record?: boolean; claim?: string;
  tasks?: { task_id: string; name: string; state: string; exit_code: number | null; duration?: string; peak_rss?: string }[];
} };

export function ProductionTracePanel({ runId }: { runId: string }) {
  const [saved, setSaved] = useState<Monitor | null>(null);
  const [error, setError] = useState('');
  const monitor = saved?.run_id === runId ? saved : null;
  useEffect(() => {
    if (!runId) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function refresh() {
      let terminal = false;
      try {
        const response = await longApi.get<Monitor>(`/api/ngs/v2/production/runs/${encodeURIComponent(runId)}/execution-monitor`, { signal: controller.signal, timeout: 15000 });
        if (!active) return;
        setSaved(response.data); setError('');
        terminal = ['SUCCEEDED', 'FAILED'].includes(response.data.execution_state);
      } catch (caught) { if (active) setError(extractErrorMessage(caught, 'Could not refresh process evidence; retrying')); }
      if (active && !terminal) timer = setTimeout(refresh, 5000);
    }
    void refresh();
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, [runId]);
  if (!runId) return null;
  const evidence = monitor?.process_evidence;
  return <section className="rounded border border-glass-border p-4 space-y-3" aria-live="polite">
    <h3 className="text-sm font-semibold">Nextflow process evidence</h3>
    {error && <p className="text-xs text-error">{error}</p>}
    {!monitor && <p className="text-xs text-text-muted">Retrieving recorded process status…</p>}
    {evidence && <>
      <p className="text-xs text-text-secondary">{evidence.message || evidence.claim}</p>
      {evidence.states && <p className="text-xs">{evidence.observed_process_records} process records · {evidence.states.COMPLETED} completed · {evidence.states.CACHED} cached · {evidence.states.FAILED} failed</p>}
      {!!evidence.tasks?.length && <div className="overflow-auto"><table className="w-full text-left text-xs">
        <thead><tr><th scope="col">Process</th><th scope="col">State</th><th scope="col">Exit</th><th scope="col">Duration</th><th scope="col">Peak memory</th></tr></thead>
        <tbody>{evidence.tasks.slice(0, 200).map((task, index) => <tr key={`${task.task_id}-${index}`}><td className="py-2 pr-3">{task.name}</td><td>{task.state}</td><td>{task.exit_code ?? '—'}</td><td>{task.duration ?? '—'}</td><td>{task.peak_rss ?? '—'}</td></tr>)}</tbody>
      </table>{evidence.tasks.length > 200 && <p className="text-xs text-text-muted">Showing the first 200 records. The export contains all observed records.</p>}</div>}
      {evidence.incomplete_last_record && <p className="text-xs text-text-muted">The worker is writing a trace row; it will appear after the row is complete.</p>}
      <button type="button" className="text-xs underline" onClick={() => {
        const url = URL.createObjectURL(new Blob([JSON.stringify(monitor, null, 2)], { type: 'application/json' }));
        const anchor = document.createElement('a'); anchor.href = url; anchor.download = `nextflow-process-evidence-${runId}.json`; anchor.click(); URL.revokeObjectURL(url);
      }}>Export observed process evidence</button>
    </>}
  </section>;
}

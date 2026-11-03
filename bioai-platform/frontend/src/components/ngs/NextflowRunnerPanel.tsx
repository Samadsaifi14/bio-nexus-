'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  ArrowSquareOut,
  CheckCircle,
  CircleNotch,
  DownloadSimple,
  Play,
  WarningCircle,
  XCircle,
} from '@phosphor-icons/react';

import {
  downloadNextflowArtifact,
  evidenceFileUrl,
  getNextflowArtifacts,
  getNextflowCapabilities,
  getNextflowEvidence,
  getNextflowRun,
  submitNextflowRun,
  type NextflowArtifact,
  type NextflowArtifactManifest,
  type NextflowCapabilities,
  type NextflowEvidence,
  type NextflowRun,
} from '@/lib/ngsNextflowApi';

const TERMINAL = ['SUCCEEDED', 'FAILED'];

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : 'Could not complete the request. Please retry.';
}

function formatBytes(value: number | null): string {
  if (value === null || value === undefined) return '—';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value?: string): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toISOString().replace('T', ' ').replace('.000Z', ' UTC');
}

function StateIcon({ state }: { state: string }) {
  if (state === 'SUCCEEDED') return <CheckCircle className="text-accent-green" aria-hidden />;
  if (state === 'FAILED') return <XCircle className="text-error" aria-hidden />;
  if (state === 'RUNNING' || state === 'SUBMITTED') return <CircleNotch className="animate-spin text-accent-cyan" aria-hidden />;
  return <WarningCircle className="text-warn" aria-hidden />;
}

export default function NextflowRunnerPanel() {
  const [capabilities, setCapabilities] = useState<NextflowCapabilities | null>(null);
  const [evidence, setEvidence] = useState<NextflowEvidence | null>(null);
  const [loadError, setLoadError] = useState('');
  const [fixture, setFixture] = useState('tiny-positive-control');
  const [minQual, setMinQual] = useState(20);
  const [minDp, setMinDp] = useState(10);
  const [threads, setThreads] = useState(1);
  const [runId, setRunId] = useState('');
  const [run, setRun] = useState<NextflowRun | null>(null);
  const [artifacts, setArtifacts] = useState<NextflowArtifactManifest | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [pollError, setPollError] = useState('');

  useEffect(() => {
    let active = true;
    Promise.allSettled([getNextflowCapabilities(), getNextflowEvidence()]).then(([capability, committed]) => {
      if (!active) return;
      if (capability.status === 'fulfilled') setCapabilities(capability.value);
      else setLoadError(messageOf(capability.reason));
      if (committed.status === 'fulfilled') setEvidence(committed.value);
      else setLoadError(messageOf(committed.reason));
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!runId) return;
    let active = true;
    let terminal = false;
    let inFlight = false;
    const refresh = async () => {
      if (terminal || inFlight) return;
      inFlight = true;
      try {
        const next = await getNextflowRun(runId);
        if (!active) return;
        setRun(next);
        setPollError('');
        if (TERMINAL.includes(next.state)) {
          terminal = true;
          const manifest = await getNextflowArtifacts(runId);
          if (active) setArtifacts(manifest);
        }
      } catch (caught) {
        if (active) setPollError(messageOf(caught));
      } finally {
        inFlight = false;
      }
    };
    void refresh();
    const timer = window.setInterval(refresh, 2000);
    return () => { active = false; window.clearInterval(timer); };
  }, [runId]);

  const selectedFixture = capabilities?.fixtures.find(item => item.id === fixture);
  const running = Boolean(runId && (!run || !TERMINAL.includes(run.state)));
  const callsRows = useMemo(() => {
    const text = evidence?.inline?.['calls.tsv'];
    if (!text) return [];
    return text.trim().split('\n').slice(1).map(line => line.split('\t'));
  }, [evidence]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setRunId('');
    setRun(null);
    setArtifacts(null);
    try {
      const submitted = await submitNextflowRun({
        fixture,
        min_qual: minQual,
        min_dp: minDp,
        threads,
        sample_name: selectedFixture?.id,
      });
      setRunId(submitted.run_id);
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  async function download(artifactId: string, filename: string) {
    try {
      await downloadNextflowArtifact(runId, artifactId, filename);
    } catch (caught) {
      setError(messageOf(caught));
    }
  }

  return (
    <section className="scientific-page mx-auto max-w-7xl space-y-6 pb-12">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold">Nextflow NGS runner</h2>
          <span className="rounded-full border border-glass-border px-3 py-1 text-xs text-text-secondary">
            Real DSL2 workflow · 7 processes
          </span>
        </div>
        <p className="max-w-4xl text-sm leading-6 text-text-secondary">
          Reference indexing, BAM preparation, bcftools variant calling, quality filtering, run metrics and
          truth concordance are executed by <code>nextflow run</code> inside a Docker tool image. A run is
          labelled as a Nextflow execution only after Nextflow exits successfully and writes its trace.
        </p>
      </div>

      {loadError && <p role="alert" className="data-card p-4 text-sm text-error">{loadError}</p>}

      <div className="data-card space-y-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold">Run the workflow</h3>
            <p className="mt-1 text-xs leading-5 text-text-secondary">
              The only exposed input is the committed synthetic positive control, so a run is reproducible.
              No exploratory Python fallback is used.
            </p>
          </div>
          {capabilities && (
            <span
              className={`rounded-full border px-3 py-1 text-xs ${
                capabilities.executor.available
                  ? 'border-accent-green/40 text-accent-green'
                  : 'border-warn/40 text-warn'
              }`}
            >
              {capabilities.executor.available ? 'Docker executor ready' : 'Docker executor unavailable'}
            </span>
          )}
        </div>

        {!capabilities && !loadError && <p className="text-sm text-text-muted">Checking execution capabilities…</p>}

        {capabilities && !capabilities.executor.available && (
          <div className="rounded-lg border border-warn/30 bg-surface-1 p-4">
            <p role="status" className="flex items-start gap-2 text-sm text-warn">
              <WarningCircle className="mt-0.5 shrink-0" aria-hidden />
              {capabilities.executor.reason}
            </p>
            <p className="mt-2 text-xs text-text-muted">
              This deployment refuses to submit rather than pretending a workflow ran. The committed evidence
              below comes from a real execution on a Docker-capable workstation.
            </p>
            <ul className="mt-2 list-disc pl-5 text-xs text-text-secondary">
              {capabilities.executor.requirements.map(item => <li key={item}>{item}</li>)}
            </ul>
          </div>
        )}

        {capabilities?.executor.available && (
          <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <label className="text-xs text-text-secondary">
              Input fixture
              <select
                value={fixture}
                onChange={event => setFixture(event.target.value)}
                className="scientific-select mt-1 w-full"
              >
                {capabilities.fixtures.map(item => (
                  <option key={item.id} value={item.id}>{item.label}</option>
                ))}
              </select>
            </label>
            <label className="text-xs text-text-secondary">
              Minimum QUAL
              <input
                type="number" min={0} max={1000} value={minQual}
                onChange={event => setMinQual(Number(event.target.value))}
                className="mt-1 w-full rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-sm text-text-primary"
              />
            </label>
            <label className="text-xs text-text-secondary">
              Minimum FORMAT/DP
              <input
                type="number" min={0} max={10000} value={minDp}
                onChange={event => setMinDp(Number(event.target.value))}
                className="mt-1 w-full rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-sm text-text-primary"
              />
            </label>
            <label className="text-xs text-text-secondary">
              Threads
              <input
                type="number" min={1} max={8} value={threads}
                onChange={event => setThreads(Number(event.target.value))}
                className="mt-1 w-full rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-sm text-text-primary"
              />
            </label>
            <div className="sm:col-span-2 lg:col-span-4 flex flex-wrap items-center gap-3">
              <button disabled={busy || running} className="btn-primary inline-flex items-center gap-2 disabled:opacity-40">
                {busy || running ? <CircleNotch className="animate-spin" aria-hidden /> : <Play aria-hidden />}
                {busy ? 'Submitting…' : running ? 'Workflow running…' : 'Run Nextflow workflow'}
              </button>
              {selectedFixture && (
                <span className="text-xs text-text-muted">
                  Expected: {selectedFixture.expected_snp} · {selectedFixture.classification.replaceAll('_', ' ').toLowerCase()}
                </span>
              )}
              {capabilities.engine.version && (
                <span className="text-xs text-text-muted">
                  Nextflow {capabilities.engine.version} · samtools {capabilities.engine.tool_versions.samtools ?? '—'} · bcftools {capabilities.engine.tool_versions.bcftools ?? '—'}
                </span>
              )}
            </div>
          </form>
        )}

        {error && <p role="alert" className="text-sm text-error">{error}</p>}
      </div>

      {runId && (
        <div className="data-card space-y-4 p-5" aria-live="polite">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              {run && <StateIcon state={run.state} />}
              <h3 className="text-sm font-semibold">Run {runId.slice(0, 8)}</h3>
              <span className="rounded-full border border-glass-border px-2 py-0.5 text-xs">{run?.state ?? 'SUBMITTED'}</span>
              {run?.nextflow_executed && (
                <span className="rounded-full border border-accent-green/40 px-2 py-0.5 text-xs text-accent-green">
                  Nextflow trace verified
                </span>
              )}
            </div>
            <span className="font-mono text-xs text-text-muted">{runId}</span>
          </div>
          <p className="text-xs leading-5 text-text-secondary">
            {run?.state === 'SUCCEEDED'
              ? 'Nextflow completed every process. Artifacts are read from the run directory below.'
              : run?.state === 'FAILED'
                ? 'The workflow failed. The exit status and available logs are retained.'
                : 'The workflow is executing in Docker. Status is read from the durable run record; no simulated progress is shown.'}
          </p>
          {run && (
            <dl className="grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
              <div><dt className="text-text-muted">Workflow revision</dt><dd className="font-mono">{run.revision}</dd></div>
              <div><dt className="text-text-muted">Engine</dt><dd>{run.engine} {run.engine_version ?? '—'}</dd></div>
              <div><dt className="text-text-muted">Image</dt><dd className="break-all font-mono">{run.container_image}</dd></div>
              <div><dt className="text-text-muted">Command SHA-256</dt><dd className="break-all font-mono">{run.command_sha256.slice(0, 24)}…</dd></div>
            </dl>
          )}
          {run?.message && <p role="alert" className="text-sm text-error">{run.message}</p>}
          {pollError && <p role="alert" className="text-sm text-error">{pollError} The job is retained; polling will retry.</p>}
          {run?.processes && run.processes.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-text-muted">
                  <tr><th className="py-1 pr-4">Process</th><th className="py-1 pr-4">Status</th><th className="py-1 pr-4">Exit</th><th className="py-1">Real time</th></tr>
                </thead>
                <tbody>
                  {run.processes.map(process => (
                    <tr key={`${process.task_id}-${process.name}`} className="border-t border-glass-border">
                      <td className="py-1 pr-4">{process.name}</td>
                      <td className="py-1 pr-4">{process.status}</td>
                      <td className="py-1 pr-4">{process.exit}</td>
                      <td className="py-1">{process.realtime}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {artifacts && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold">Artifacts</h4>
              <ul className="grid gap-2 sm:grid-cols-2">
                {artifacts.artifacts.filter(item => item.present).map(item => (
                  <li key={item.id} className="flex items-center justify-between gap-3 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs">
                    <span>
                      {item.label}
                      <span className="ml-2 text-text-muted">{formatBytes(item.bytes)}</span>
                      {item.sha256 && <span className="block font-mono text-[10px] text-text-muted">{item.sha256.slice(0, 24)}…</span>}
                    </span>
                    <button
                      type="button"
                      onClick={() => void download(item.id, item.path.split('/').pop() ?? item.id)}
                      className="inline-flex items-center gap-1 text-accent-cyan"
                    >
                      <DownloadSimple aria-hidden /> Download
                    </button>
                  </li>
                ))}
              </ul>
              {!artifacts.required_complete && artifacts.missing_required.length > 0 && (
                <p className="text-xs text-warn">Missing required artifacts: {artifacts.missing_required.join(', ')}</p>
              )}
              <p className="text-xs text-text-muted">{artifacts.claim}</p>
            </div>
          )}
        </div>
      )}

      <div className="data-card space-y-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">Committed evidence · real executed run</h3>
            <p className="mt-1 text-xs leading-5 text-text-secondary">
              These artifacts were produced by an actual <code>nextflow run</code> and are packaged with the
              backend. They remain viewable on deployments where Docker is unavailable.
            </p>
          </div>
          {evidence?.available && (
            <span className="rounded-full border border-accent-green/40 px-3 py-1 text-xs text-accent-green">
              {evidence.execution.state} · exit {evidence.execution.exit_code}
            </span>
          )}
        </div>

        {!evidence && !loadError && <p className="text-sm text-text-muted">Loading committed evidence…</p>}
        {evidence && !evidence.available && <p className="text-sm text-warn">{evidence.reason}</p>}

        {evidence?.available && (
          <>
            <dl className="grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
              <div><dt className="text-text-muted">Executed</dt><dd>{formatDate(evidence.generated_at)}</dd></div>
              <div><dt className="text-text-muted">Engine</dt><dd>{evidence.execution.engine} {evidence.execution.engine_version}</dd></div>
              <div><dt className="text-text-muted">Tool versions</dt><dd>samtools {evidence.tool_versions.samtools} · bcftools {evidence.tool_versions.bcftools}</dd></div>
              <div><dt className="text-text-muted">Workflow revision</dt><dd className="font-mono">{evidence.revision}</dd></div>
              <div className="sm:col-span-2 lg:col-span-4">
                <dt className="text-text-muted">Image / command</dt>
                <dd className="break-all font-mono">{evidence.execution.container_digest}</dd>
                <dd className="break-all font-mono">command sha256 {evidence.execution.command_sha256}</dd>
                {evidence.execution.command && (
                  <details className="mt-1">
                    <summary className="cursor-pointer text-text-secondary">Executed container command</summary>
                    <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-all text-[10px] text-text-muted">
                      {evidence.execution.command.join(' ')}
                    </pre>
                  </details>
                )}
              </div>
            </dl>

            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {[
                ['Called variants', evidence.result.called_variants],
                ['Mean depth', evidence.result.mean_depth],
                ['Mapped reads', evidence.result.mapped_reads],
                ['TP / FP / FN', `${evidence.result.tp} / ${evidence.result.fp} / ${evidence.result.fn}`],
                ['F1', evidence.result.f1.toFixed(3)],
                ['Expected', evidence.fixture.expected_snp],
              ].map(([label, value]) => (
                <div key={String(label)} className="rounded-lg border border-glass-border bg-surface-1 p-3">
                  <p className="text-[10px] uppercase tracking-wide text-text-muted">{label}</p>
                  <p className="mt-1 text-sm font-semibold">{value}</p>
                </div>
              ))}
            </div>

            {callsRows.length > 0 && (
              <div>
                <h4 className="mb-2 text-xs font-semibold">Filtered calls</h4>
                <div className="overflow-x-auto rounded-lg border border-glass-border">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-surface-1 text-text-muted">
                      <tr>{['CHROM', 'POS', 'REF', 'ALT', 'GT', 'DP', 'AD'].map(header => <th key={header} className="px-3 py-2">{header}</th>)}</tr>
                    </thead>
                    <tbody>
                      {callsRows.map((row, index) => (
                        <tr key={`${row[0]}-${row[1]}-${index}`} className="border-t border-glass-border">
                          {row.map((cell, cellIndex) => <td key={cellIndex} className="px-3 py-2 font-mono">{cell}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div>
              <h4 className="mb-2 text-xs font-semibold">Artifacts</h4>
              <ul className="grid gap-2 sm:grid-cols-2">
                {Object.entries(evidence.files).map(([name, file]) => (
                  <li key={name} className="flex items-center justify-between gap-3 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs">
                    <span>
                      {file.label}
                      <span className="ml-2 text-text-muted">{formatBytes(file.bytes)}</span>
                      <span className="block font-mono text-[10px] text-text-muted">sha256 {file.sha256.slice(0, 24)}…</span>
                    </span>
                    <a href={evidenceFileUrl(name)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent-cyan">
                      Open <ArrowSquareOut aria-hidden />
                    </a>
                  </li>
                ))}
              </ul>
            </div>

            {evidence.processes?.length > 0 && (
              <details>
                <summary className="cursor-pointer text-xs font-semibold">Nextflow process trace ({evidence.processes.length})</summary>
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="text-text-muted"><tr><th className="py-1 pr-4">Process</th><th className="py-1 pr-4">Status</th><th className="py-1 pr-4">Exit</th><th className="py-1">Real time</th></tr></thead>
                    <tbody>
                      {evidence.processes.map(process => (
                        <tr key={`${process.task_id}-${process.name}`} className="border-t border-glass-border">
                          <td className="py-1 pr-4">{process.name}</td>
                          <td className="py-1 pr-4">{process.status}</td>
                          <td className="py-1 pr-4">{process.exit}</td>
                          <td className="py-1">{process.realtime}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}

            <p className="text-xs leading-5 text-text-muted">{evidence.claim}</p>
          </>
        )}
      </div>
    </section>
  );
}

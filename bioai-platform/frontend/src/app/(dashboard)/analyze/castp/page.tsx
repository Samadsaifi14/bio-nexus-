'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  Atom,
  CheckCircle,
  CircleNotch as LoaderCircle,
  Database,
  Dna,
  Warning as WarningIcon,
  XCircle,
} from '@phosphor-icons/react';

import { AIResultSummary } from '@/components/results/AIResultSummary';
import { DockingViewer } from '@/components/DockingViewer';
import { BackButton, CriticalButton, FlatInput, FlatTextarea, PageHeader } from '@/components/ui';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import { fadeUp } from '@/lib/animations';
import { longApi } from '@/lib/api';
import { consumeParam, continueAnalysis, getAnalysisHandoff } from '@/lib/cross-link';
import { isScientificResult, type ScientificResult } from '@/types/scientific-result';

type MethodChoice = 'castp' | 'fpocket' | 'sasa_heuristic';
type InputMode = 'identifier' | 'sequence' | 'pdb_text';

type ChainGap = { start: number; end: number; count: number };
type Chain = { id: string; residue_count: number; sequence: string; gaps: ChainGap[] };
type PocketResidue = {
  chain: string;
  residue_number: number;
  residue_name: string;
  one: string;
  label: string;
  coordinate_present: boolean;
};
type Pocket = {
  id: number;
  area_sa: number;
  volume_sa: number;
  score?: number | null;
  druggability_score?: number | null;
  alpha_spheres?: number | null;
  num_residues: number;
  residues: string[];
  centroid: number[];
  radius: number;
  method_metrics?: Record<string, unknown>;
  residue_details?: PocketResidue[];
  gap_ranges?: Array<{ chain: string; gaps: ChainGap[] }>;
  chain_spans?: Array<{ chain: string; min: number; max: number; count: number }>;
};
type PipelineStep = { step: string; status: string; detail: string };
type PocketResults = Record<string, unknown> & {
  pdb_id: string;
  probe_radius: number;
  total_residues: number;
  pockets: Pocket[];
  sequence_source: string;
  structure_source: string;
  structure_pdb: string;
  pipeline: PipelineStep[];
  uniprot?: {
    accession: string;
    name: string;
    organism: string;
    gene_names: string[];
    sequence_length: number;
  } | null;
  chains: Chain[];
};

const METHODS: Array<{ value: MethodChoice; title: string; detail: string }> = [
  {
    value: 'castp',
    title: 'CASTp',
    detail: 'CASTp-specific results only. If genuine CASTp execution/retrieval is unavailable, the run fails rather than substituting fpocket values.',
  },
  {
    value: 'fpocket',
    title: 'fpocket',
    detail: 'Local fpocket output including its own score, druggability score, volume, alpha spheres and lining residues when emitted.',
  },
  {
    value: 'sasa_heuristic',
    title: 'BioNexus exploratory SASA heuristic',
    detail: 'Exploratory geometric estimate. This is explicitly not CASTp or fpocket output.',
  },
];

function statusTone(status: ScientificResult['status']): string {
  if (status === 'VALID') return 'border-good/25 bg-good/5 text-good';
  if (status === 'DEGRADED' || status === 'NOT_EVALUATED') return 'border-warn/25 bg-warn/5 text-warn';
  return 'border-error/25 bg-error/5 text-error';
}

function ResultViewer({ result }: { result: ScientificResult<PocketResults> }) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!result.results.structure_pdb) {
      setObjectUrl(null);
      return;
    }
    const url = URL.createObjectURL(new Blob([result.results.structure_pdb], { type: 'text/plain' }));
    setObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [result.results.structure_pdb]);

  const canView = Boolean(objectUrl || (result.results.pdb_id && result.results.pdb_id !== 'predicted' && result.results.pdb_id !== 'custom'));
  if (!canView) return null;

  return (
    <div className="data-card overflow-hidden p-1">
      <DockingViewer
        pdbId={objectUrl ? 'custom' : result.results.pdb_id}
        pdbUrl={objectUrl || undefined}
        pdbUrlFormat={objectUrl ? 'pdb' : undefined}
        ligandPdb=""
        height={430}
        chains={result.results.chains?.map((chain) => ({ id: chain.id, residue_count: chain.residue_count })) || []}
      />
    </div>
  );
}

export default function PocketAnalysisPage() {
  const audit = useAuditTrail();
  const router = useRouter();
  const [method, setMethod] = useState<MethodChoice>('fpocket');
  const [inputMode, setInputMode] = useState<InputMode>('identifier');
  const [input, setInput] = useState('');
  const [probeRadius, setProbeRadius] = useState(1.4);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ScientificResult<PocketResults> | null>(null);

  const selectedMethod = useMemo(() => METHODS.find((item) => item.value === method)!, [method]);

  useEffect(() => {
    const handoff = getAnalysisHandoff();
    const carried = consumeParam('castp_pdb_id') || handoff?.pdbId || handoff?.resolvedAccession || null;
    if (carried) {
      setInputMode('identifier');
      setInput(carried);
    }
  }, []);

  const continueToDocking = (pocket: Pocket) => {
    const handoff = getAnalysisHandoff();
    const emitted = result?.results.pdb_id;
    const receptor = emitted && emitted !== 'predicted' && emitted !== 'custom'
      ? emitted
      : handoff?.pdbId || (inputMode === 'identifier' ? input.trim() : null);
    if (!receptor) return;
    continueAnalysis(
      router,
      { sourceTool: 'castp', pdbId: receptor },
      '/analyze/docking',
      {
        docking_pdb_id: receptor,
        docking_centroid: JSON.stringify(pocket.centroid),
      },
    );
  };

  const run = async () => {
    if (!input.trim()) return;
    const summary = `${method}:${inputMode}:${input.trim().slice(0, 60)}`;
    setRunning(true);
    setError(null);
    setResult(null);
    audit.emitStarted('pocket_analysis', selectedMethod.title, summary);
    try {
      const payload: Record<string, unknown> = { method, probe_radius: probeRadius, pdb_id: '', sequence: '', pdb_text: '' };
      if (inputMode === 'identifier') payload.pdb_id = input.trim();
      if (inputMode === 'sequence') payload.sequence = input.trim();
      if (inputMode === 'pdb_text') payload.pdb_text = input.trim();
      const response = await longApi.post('/api/castp/analyze', payload);
      if (!isScientificResult(response.data)) throw new Error('Pocket backend did not emit a valid ScientificResult');
      const scientific = response.data as ScientificResult<PocketResults>;
      setResult(scientific);
      if (scientific.status === 'FAILED') {
        audit.emitFailed('pocket_analysis', selectedMethod.title, summary, String(scientific.validation.reason || 'Scientific method failed'));
      } else {
        audit.emitSuccess('pocket_analysis', selectedMethod.title, summary, scientific.output_sha256);
      }
    } catch (cause: unknown) {
      const typed = cause as { response?: { data?: { detail?: string } }; message?: string };
      const message = typed.response?.data?.detail || typed.message || 'Pocket analysis failed';
      setError(message);
      audit.emitFailed('pocket_analysis', selectedMethod.title, summary, message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="max-w-6xl">
      <BackButton />
      <PageHeader
        title="Pocket & Cavity Analysis"
        subtitle="CASTp, fpocket and BioNexus exploratory geometry are separate scientific methods with separate provenance. Values are never silently substituted between them."
      />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card mb-6 space-y-5 p-5">
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">Method</p>
          <div className="grid gap-3 md:grid-cols-3">
            {METHODS.map((item) => (
              <button
                key={item.value}
                onClick={() => { setMethod(item.value); setResult(null); setError(null); }}
                className={`rounded-xl border p-4 text-left transition ${method === item.value ? 'border-accent-cyan/45 bg-accent-cyan/10' : 'border-glass-border bg-surface-1 hover:border-glass-border-strong'}`}
              >
                <p className="text-sm font-semibold text-text-primary">{item.title}</p>
                <p className="mt-1.5 text-xs leading-5 text-text-secondary">{item.detail}</p>
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          {([
            ['identifier', 'PDB / UniProt / gene'],
            ['sequence', 'Protein sequence'],
            ['pdb_text', 'PDB text'],
          ] as Array<[InputMode, string]>).map(([value, label]) => (
            <button key={value} onClick={() => { setInputMode(value); setInput(''); setResult(null); }} className={`rounded-lg border px-3 py-2 text-xs ${inputMode === value ? 'border-accent-cyan/40 bg-accent-cyan/10 text-accent-cyan' : 'border-glass-border bg-surface-1 text-text-secondary'}`}>
              {label}
            </button>
          ))}
        </div>

        {inputMode === 'identifier' ? (
          <FlatInput value={input} onChange={(event) => setInput(event.target.value)} placeholder="Example: 1CRN, P68871 or TP53" className="w-full" />
        ) : (
          <FlatTextarea value={input} onChange={(event) => setInput(event.target.value)} placeholder={inputMode === 'sequence' ? 'Paste amino-acid sequence…' : 'Paste PDB text…'} className="h-44 w-full font-mono text-xs" />
        )}

        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-text-muted">
            Probe radius (Å)
            <input type="number" min={0.1} max={5} step={0.1} value={probeRadius} onChange={(event) => setProbeRadius(Number(event.target.value) || 1.4)} className="mt-1 block w-32 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-sm text-text-primary" />
          </label>
          <div className="flex-1" />
          <CriticalButton onClick={run} disabled={running || !input.trim()}>
            {running ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Atom className="h-4 w-4" />}
            {running ? 'Running method…' : `Run ${selectedMethod.title}`}
          </CriticalButton>
        </div>
      </motion.div>

      {error && (
        <div className="mb-6 flex gap-2 rounded-xl border border-error/25 bg-error/5 p-4 text-sm text-error">
          <XCircle className="mt-0.5 h-4 w-4 flex-none" /> {error}
        </div>
      )}

      {result && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-4">
          <div className={`rounded-xl border p-5 ${statusTone(result.status)}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex gap-3">
                {result.status === 'VALID' ? <CheckCircle className="mt-0.5 h-5 w-5" /> : result.status === 'FAILED' ? <XCircle className="mt-0.5 h-5 w-5" /> : <WarningIcon className="mt-0.5 h-5 w-5" />}
                <div>
                  <p className="text-sm font-semibold">{result.status} — {result.method}</p>
                  <p className="mt-1 text-xs text-text-secondary">Engine/version: {result.engine} · {result.engine_version}</p>
                </div>
              </div>
              <span className="rounded-lg border border-current/20 px-2.5 py-1 text-xs">{result.evidence_class}</span>
            </div>
            {result.validation.reason && <p className="mt-3 text-xs">{String(result.validation.reason)}</p>}
          </div>

          {result.method.includes('heuristic') && (
            <div className="rounded-xl border border-warn/25 bg-warn/5 p-4 text-xs text-warn">
              Exploratory geometric estimate — not CASTp/fpocket output. Do not cite these area/volume estimates as values produced by either external method.
            </div>
          )}

          <div className="data-card p-5">
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <Database className="h-4 w-4 text-accent-cyan" />
              <p className="text-sm font-semibold text-text-primary">Structure and provenance</p>
            </div>
            <div className="grid gap-3 md:grid-cols-4">
              {[
                ['Structure', result.results.pdb_id],
                ['Structure source', result.results.structure_source],
                ['Sequence source', result.results.sequence_source],
                ['Residues', result.results.total_residues],
              ].map(([label, value]) => (
                <div key={String(label)} className="rounded-xl bg-surface-1 p-3"><p className="text-xs text-text-muted">{label}</p><p className="mt-1 break-words text-sm text-text-primary">{String(value ?? '—')}</p></div>
              ))}
            </div>
            <div className="mt-4 space-y-2">
              {result.results.pipeline?.map((step, index) => (
                <div key={`${step.step}-${index}`} className="flex gap-3 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs">
                  <span className={step.status === 'ok' ? 'text-good' : step.status === 'skip' ? 'text-text-muted' : 'text-error'}>{step.status.toUpperCase()}</span>
                  <span className="font-medium text-text-primary">{step.step}</span>
                  <span className="text-text-secondary">{step.detail}</span>
                </div>
              ))}
            </div>
          </div>

          {result.status !== 'FAILED' && <ResultViewer result={result} />}

          <div className="data-card p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-text-primary">Method-specific pockets</h3>
                <p className="mt-1 text-xs text-text-muted">{result.results.pockets.length} pocket(s) emitted by {result.method}.</p>
              </div>
            </div>

            {result.results.pockets.length === 0 ? (
              <p className="text-sm text-text-secondary">No pocket result was emitted. This is not interpreted as a negative biological finding.</p>
            ) : (
              <div className="overflow-auto">
                <table className="w-full min-w-[900px] text-xs">
                  <thead className="bg-surface-1 text-text-muted">
                    <tr>
                      {['Pocket', 'Area / estimate', 'Volume / estimate', 'fpocket score', 'Druggability', 'Alpha spheres', 'Residues', 'Centroid', 'Continue'].map((heading) => <th key={heading} className="px-3 py-2 text-left font-medium">{heading}</th>)}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-glass-border">
                    {result.results.pockets.map((pocket) => (
                      <tr key={pocket.id}>
                        <td className="px-3 py-3 font-mono text-text-primary">{pocket.id}</td>
                        <td className="px-3 py-3 font-mono text-text-secondary">{pocket.area_sa}</td>
                        <td className="px-3 py-3 font-mono text-text-secondary">{pocket.volume_sa}</td>
                        <td className="px-3 py-3 font-mono text-text-secondary">{pocket.score ?? '—'}</td>
                        <td className="px-3 py-3 font-mono text-text-secondary">{pocket.druggability_score ?? '—'}</td>
                        <td className="px-3 py-3 font-mono text-text-secondary">{pocket.alpha_spheres ?? '—'}</td>
                        <td className="px-3 py-3 text-text-secondary">{pocket.num_residues}</td>
                        <td className="px-3 py-3 font-mono text-text-secondary">{pocket.centroid?.join(', ') || '—'}</td>
                        <td className="px-3 py-3">
                          <button
                            type="button"
                            onClick={() => continueToDocking(pocket)}
                            className="rounded-lg border border-glass-border px-2.5 py-1.5 text-[11px] font-medium text-accent-cyan hover:border-accent-cyan/40"
                          >
                            Use for docking
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {result.results.pockets.some((pocket) => (pocket.residue_details?.length || pocket.residues?.length)) && (
            <div className="data-card p-5">
              <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-primary"><Dna className="h-4 w-4 text-accent-cyan" /> Pocket-lining residues</h3>
              <div className="space-y-3">
                {result.results.pockets.map((pocket) => {
                  const labels = pocket.residue_details?.map((residue) => residue.label) || pocket.residues || [];
                  if (!labels.length) return null;
                  return <div key={pocket.id}><p className="mb-1 text-xs font-medium text-text-muted">Pocket {pocket.id}</p><p className="break-words font-mono text-xs leading-5 text-text-secondary">{labels.join(' · ')}</p></div>;
                })}
              </div>
            </div>
          )}

          <div className="data-card grid gap-3 p-5 text-xs md:grid-cols-2">
            <div><p className="text-text-muted">Input SHA-256</p><p className="break-all font-mono text-text-secondary">{result.input_sha256}</p></div>
            <div><p className="text-text-muted">Output SHA-256</p><p className="break-all font-mono text-text-secondary">{result.output_sha256}</p></div>
          </div>

          <AIResultSummary toolName="pocket_analysis" result={result as unknown as Record<string, unknown>} />
        </motion.div>
      )}
    </div>
  );
}

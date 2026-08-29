'use client';

import { Fragment, useState } from 'react';
import { motion } from 'framer-motion';
import {
  CircleNotch as LoaderCircle,
  MagnifyingGlass as Search,
  Funnel as Filter,
  Dna,
  FloppyDisk as Database,
  GitBranch as Branch,
  Atom,
  CheckCircle as Check,
  XCircle as X,
  ArrowRight,
} from '@phosphor-icons/react';
import { fadeUp, stagger } from '@/lib/animations';
import { runCastp, type CastpResult, type CastpPipelineStep } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import { DockingViewer } from '@/components/DockingViewer';
import { BackButton, PageHeader, CriticalButton, FlatInput } from '@/components/ui';
import { AIResultSummary } from '@/components/results/AIResultSummary';

const STEP_META: Record<string, { label: string; icon: typeof Database }> = {
  pdb: { label: 'PDB Search', icon: Database },
  sequence: { label: 'Sequence Input', icon: Dna },
  uniprot: { label: 'UniProt Mapping', icon: Branch },
  structure: { label: 'Structure', icon: Atom },
  input: { label: 'Structure Input', icon: Database },
};

function PipelineView({ pipeline }: { pipeline: CastpPipelineStep[] }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {pipeline.map((step, i) => {
        const meta = STEP_META[step.step] ?? { label: step.step, icon: Database };
        const Icon = meta.icon;
        const ok = step.status === 'ok';
        return (
          <div key={i} className="flex items-center gap-1.5">
            {i > 0 && <ArrowRight className="w-3 h-3 text-text-muted/40" />}
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs ${
                ok
                  ? 'bg-accent-cyan/10 border-accent-cyan/25 text-accent-cyan'
                  : step.status === 'skip'
                  ? 'bg-surface-1 border-glass-border text-text-muted'
                  : 'bg-error/10 border-error/25 text-error'
              }`}
              title={step.detail}
            >
              <Icon className="w-3.5 h-3.5" />
              <span className="font-medium whitespace-nowrap">{meta.label}</span>
              {ok ? (
                <Check className="w-3 h-3" />
              ) : step.status === 'skip' ? (
                <span className="opacity-60">skip</span>
              ) : (
                <X className="w-3 h-3" />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function CastpPage() {
  const [identifier, setIdentifier] = useState('');
  const [probeRadius, setProbeRadius] = useState(1.4);
  const [result, setResult] = useState<CastpResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showResidues, setShowResidues] = useState<number | null>(null);
  const [viewerUrl, setViewerUrl] = useState<string | undefined>(undefined);
  const audit = useAuditTrail();

  const handleAnalyze = async () => {
    if (!identifier.trim()) return;
    const label = identifier.trim().toUpperCase();
    audit.emitStarted('castp_analyze', 'CASTp', label);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await runCastp(identifier.trim(), probeRadius);
      setResult(res);
      setViewerUrl(undefined);
      // Modeled / uploaded structures ship their PDB text — show via Blob URL.
      if (res.structure_pdb) {
        const blob = new Blob([res.structure_pdb], { type: 'text/plain' });
        setViewerUrl(URL.createObjectURL(blob));
      }
      audit.emitSuccess('castp_analyze', 'CASTp', label, `${res.pockets.length} pockets`);
    } catch (err: unknown) {
      const msg = extractErrorMessage(err, 'Analysis failed');
      audit.emitFailed('castp_analyze', 'CASTp', label, msg);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl">
      <BackButton />
      <PageHeader
        title="CASTp Pocket Analysis"
        subtitle="Resolves any identifier — PDB ID, UniProt accession, gene name, or raw sequence — through PDB search, UniProt mapping, and ESMFold modeling before running CASTp pocket detection."
      />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-6">
        <div className="flex gap-3">
          <FlatInput
            type="text"
            value={identifier}
            onChange={(e) => { setIdentifier(e.target.value); setResult(null); setError(null); }}
            onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
            placeholder="PDB ID, UniProt accession, gene name, or sequence (e.g. 1TIM, P04637, TP53, ...)"
            className="flex-1"
          />
          <CriticalButton onClick={handleAnalyze} disabled={loading || !identifier.trim()}>
            {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            {loading ? 'Resolving & Analyzing...' : 'Analyze'}
          </CriticalButton>
        </div>

        <div className="flex flex-wrap items-center gap-2 mt-3 text-xs text-text-muted">
          <span>Try:</span>
          {['1TIM', '4HHB', 'P04637', 'TP53'].map((id) => (
            <button
              key={id}
              onClick={() => { setIdentifier(id); setError(null); setResult(null); }}
              className="text-accent-cyan hover:text-accent-cyan/80 underline"
            >
              {id}
            </button>
          ))}
        </div>

        <div className="mt-4">
          <label className="block text-xs text-text-muted mb-2">
            Probe radius: {probeRadius.toFixed(1)} Å
          </label>
          <input
            type="range"
            min={0.5}
            max={5.0}
            step={0.1}
            value={probeRadius}
            onChange={(e) => setProbeRadius(parseFloat(e.target.value))}
            className="w-full h-1.5 bg-surface-1 rounded-lg appearance-none cursor-pointer accent-accent-cyan"
          />
          <div className="flex justify-between text-[10px] text-text-muted mt-1">
            <span>0.5</span>
            <span>Standard (1.4)</span>
            <span>5.0</span>
          </div>
        </div>
      </motion.div>

      {error && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-4 border border-error/20 mb-4">
          <p className="text-sm text-error">{error}</p>
        </motion.div>
      )}

      {result && (
        <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-4">
          <AIResultSummary toolName="castp" result={result as unknown as Record<string, unknown>} />

          {result.pipeline && result.pipeline.length > 0 && (
            <motion.div variants={fadeUp} className="data-card p-4">
              <h3 className="font-semibold text-text-primary mb-3 text-sm">Resolution Pipeline</h3>
              <PipelineView pipeline={result.pipeline} />
              {result.uniprot && (
                <div className="mt-3 pt-3 border-t border-glass-border text-xs text-text-muted">
                  <span className="font-medium text-text-secondary">Resolved to:</span>{' '}
                  <span className="font-mono text-accent-cyan">{result.uniprot.accession}</span>
                  {result.uniprot.name && <span> — {result.uniprot.name}</span>}
                  {result.uniprot.organism && <span> · {result.uniprot.organism}</span>}
                  {result.uniprot.gene_names?.length > 0 && (
                    <span> · genes: {result.uniprot.gene_names.join(', ')}</span>
                  )}
                  {result.uniprot.sequence_length > 0 && <span> · {result.uniprot.sequence_length} aa</span>}
                </div>
              )}
            </motion.div>
          )}

          <motion.div variants={fadeUp} className="data-card p-5">
            <h3 className="font-semibold text-text-primary mb-1">Structure Viewer</h3>
            <p className="text-xs text-text-muted mb-4">
              {result.pdb_id.toUpperCase()} · {result.total_residues} residues · {result.pockets.length} pockets detected
              {result.structure_source && (
                <span className="ml-2 px-1.5 py-0.5 bg-accent-cyan/10 text-accent-cyan rounded text-[10px]">
                  {result.structure_source === 'model_esmfold'
                    ? 'ESMFold modeled'
                    : result.structure_source === 'uniprot_pdb'
                    ? 'UniProt-linked PDB'
                    : result.structure_source === 'pdb'
                    ? 'RCSB PDB'
                    : 'Uploaded structure'}
                </span>
              )}
            </p>
            <DockingViewer
              pdbId={viewerUrl ? 'predicted' : result.pdb_id}
              pdbUrl={viewerUrl}
              ligandPdb=""
            />
          </motion.div>

          <motion.div variants={fadeUp} className="data-card p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-text-primary">Detected Pockets</h3>
              <span className="text-xs text-text-muted bg-surface-1 px-2 py-1 rounded">
                <Filter className="w-3 h-3 inline mr-1" />
                {result.pockets.length} total
              </span>
            </div>

            {result.pockets.length === 0 ? (
              <p className="text-sm text-text-muted">No significant pockets detected with this probe radius.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-glass-border text-text-muted text-left text-xs">
                      <th className="pb-2 font-medium">#</th>
                      <th className="pb-2 font-medium">SA Area (Å²)</th>
                      <th className="pb-2 font-medium">SA Volume (Å³)</th>
                      <th className="pb-2 font-medium">Residues</th>
                      <th className="pb-2 font-medium">Radius (Å)</th>
                      <th className="pb-2 font-medium"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.pockets.map((p) => (
                      <Fragment key={p.id}>
                        <tr>
                          <td className="py-2 text-accent-cyan font-mono">{p.id}</td>
                          <td className="py-2">{p.area_sa.toLocaleString()}</td>
                          <td className="py-2">{p.volume_sa.toLocaleString()}</td>
                          <td className="py-2 font-mono text-xs">{p.num_residues}</td>
                          <td className="py-2">{p.radius.toFixed(1)}</td>
                          <td className="py-2">
                            <button
                              onClick={() => setShowResidues(showResidues === p.id ? null : p.id)}
                              className="text-xs text-accent-cyan hover:underline"
                            >
                              {showResidues === p.id ? 'Hide' : 'Show residues'}
                            </button>
                          </td>
                        </tr>
                        {showResidues === p.id && (
                          <tr key={`${p.id}-res`}>
                            <td colSpan={6} className="py-2 px-3 bg-surface-0">
                              <div className="flex flex-wrap gap-1">
                                {p.residues.map((r) => (
                                  <span key={r} className="text-[10px] font-mono bg-surface-1 px-1.5 py-0.5 rounded text-text-secondary">
                                    {r}
                                  </span>
                                ))}
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </div>
  );
}

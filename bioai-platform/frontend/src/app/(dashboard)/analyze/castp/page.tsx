'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
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
  CaretDown as ChevronDown,
  Target,
  LinkSimple as Link,
  SpinnerGap as Spinner,
} from '@phosphor-icons/react';
import { fadeUp, stagger } from '@/lib/animations';
import {
  runCastp,
  type CastpResult,
  type CastpPipelineStep,
  type CastpPocket,
  type CastpActiveSiteResidue,
  type CastpChain,
} from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import { DockingViewer } from '@/components/DockingViewer';
import { BackButton, PageHeader, CriticalButton, FlatInput } from '@/components/ui';
import { AIResultSummary } from '@/components/results/AIResultSummary';
import { setPrefill } from '@/lib/cross-link';

/* ------------------------------------------------------------------ */
/* Workflow stepper — mirrors the CASTp site's guided flow.            */
/* ------------------------------------------------------------------ */
const WORKFLOW_STEPS = [
  'Select protein',
  'Search structure in PDB',
  'Open CASTp',
  'Enter PDB ID / Submit structure',
  'Run pocket & cavity analysis',
  'Obtain pockets (1, 2, 3...)',
  'Check area & volume',
  'Identify pocket lining residues',
  'Compare with known active-site residues',
  'Select probable binding pocket',
  'Use for molecular docking',
];

function WorkflowStepper({ progress }: { progress: number }) {
  // progress = highest completed step index (-1 if none). Steps <= progress are done;
  // the step right after is current.
  return (
    <div className="flex flex-wrap gap-1.5">
      {WORKFLOW_STEPS.map((label, i) => {
        const done = i < progress;
        const current = i === progress;
        const pending = i > progress;
        return (
          <div
            key={label}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[11px] font-medium transition-colors ${
              done
                ? 'bg-good/10 border-good/25 text-good'
                : current
                ? 'bg-accent-cyan/15 border-accent-cyan/40 text-accent-cyan'
                : pending
                ? 'bg-surface-1 border-glass-border text-text-muted/60'
                : 'bg-surface-1 border-glass-border text-text-muted'
            }`}
          >
            <span className="font-mono text-[10px] opacity-70">{i + 1}</span>
            <span>{label}</span>
            {done ? (
              <Check className="w-3 h-3" />
            ) : current ? (
              <Spinner className="w-3 h-3 animate-spin" />
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Resolution pipeline (identifier → structure)                        */
/* ------------------------------------------------------------------ */
const STEP_META: Record<string, { label: string; icon: typeof Database }> = {
  pdb: { label: 'PDB Search', icon: Database },
  sequence: { label: 'Sequence Input', icon: Dna },
  uniprot: { label: 'UniProt Mapping', icon: Branch },
  structure: { label: 'Structure', icon: Atom },
  input: { label: 'Structure Input', icon: Database },
  compare: { label: 'Active-site (M-CSA)', icon: Target },
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

/* ------------------------------------------------------------------ */
/* Chains view (structure chains + coordinate gaps)                    */
/* ------------------------------------------------------------------ */
function ChainsView({ chains }: { chains: CastpChain[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  return (
    <div className="space-y-2">
      {chains.map((chain) => {
        const open = expanded === chain.id;
        const gapTotals = chain.gaps.reduce((s, g) => s + g.count, 0);
        return (
          <div key={chain.id} className="border border-glass-border rounded-lg overflow-hidden">
            <button
              onClick={() => setExpanded(open ? null : chain.id)}
              className="w-full flex items-center justify-between px-3 py-2 text-sm hover:bg-surface-1 transition-colors"
            >
              <div className="flex items-center gap-2">
                <span className="font-mono text-accent-cyan bg-accent-cyan/10 px-1.5 py-0.5 rounded text-xs">
                  Chain {chain.id}
                </span>
                <span className="text-text-secondary text-xs">{chain.residue_count} residues</span>
                {gapTotals > 0 && (
                  <span className="text-[10px] text-warn bg-warn/10 px-1.5 py-0.5 rounded">
                    {gapTotals} coordinate gap{gapTotals > 1 ? 's' : ''}
                  </span>
                )}
              </div>
              <ChevronDown className={`w-3.5 h-3.5 text-text-muted transition-transform ${open ? 'rotate-180' : ''}`} />
            </button>
            {open && (
              <div className="px-3 pb-3">
                <p className="text-[11px] text-text-muted mb-1">
                  Sequence ({chain.sequence.length} aa, 1-letter):
                </p>
                <div className="flex flex-wrap gap-0.5 font-mono text-[10px] leading-4">
                  {chain.sequence.split('').map((ch, i) => (
                    <span key={i} className={`px-0.5 rounded ${ch === 'X' ? 'bg-error/20 text-error' : 'text-text-secondary'}`}>
                      {ch}
                    </span>
                  ))}
                </div>
                {chain.gaps.length > 0 && (
                  <div className="mt-2">
                    <p className="text-[11px] text-warn mb-1">Missing residues (no coordinates):</p>
                    <div className="flex flex-wrap gap-1">
                      {chain.gaps.map((g, i) => (
                        <span key={i} className="text-[10px] font-mono bg-warn/10 text-warn px-1.5 py-0.5 rounded">
                          {g.start}–{g.end} ({g.count})
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Pocket lining residues with gap markers                             */
/* ------------------------------------------------------------------ */
function PocketLining({ pocket, activeSites }: { pocket: CastpPocket; activeSites: CastpActiveSiteResidue[] }) {
  const activeKeys = new Set(
    activeSites.map((a) => `${a.chain}:${a.residue_number}`),
  );
  const hitKeys = new Set(
    pocket.active_site_hits.map((a) => `${a.chain}:${a.residue_number}`),
  );

  const byChain = new Map<string, CastpPocket['residue_details']>();
  for (const r of pocket.residue_details) {
    if (!byChain.has(r.chain)) byChain.set(r.chain, []);
    byChain.get(r.chain)!.push(r);
  }
  const chainOrder = pocket.chain_spans.map((c) => c.chain);

  return (
    <div className="space-y-3">
      {chainOrder.map((chainId) => {
        const residues = (byChain.get(chainId) || []).slice().sort((a, b) => a.residue_number - b.residue_number);
        if (residues.length === 0) return null;
        const chunks: { type: 'res' | 'gap'; label?: string; r?: CastpPocket['residue_details'][0] }[] = [];
        residues.forEach((r, i) => {
          if (i === 0) {
            chunks.push({ type: 'res', r });
          } else {
            const prev = residues[i - 1];
            if (r.residue_number > prev.residue_number + 1) {
              chunks.push({ type: 'gap', label: `${prev.residue_number + 1}–${r.residue_number - 1}` });
            }
            chunks.push({ type: 'res', r });
          }
        });
        return (
          <div key={chainId}>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[11px] font-semibold text-text-muted">Chain {chainId}</span>
              <span className="text-[10px] text-text-muted">{residues.length} lining residues</span>
            </div>
            <div className="flex flex-wrap items-center gap-1">
              {chunks.map((c, i) =>
                c.type === 'gap' ? (
                  <span key={i} className="text-[10px] text-warn/80 font-mono bg-warn/8 px-1.5 py-0.5 rounded border border-dashed border-warn/30">
                    gap {c.label}
                  </span>
                ) : c.r ? (
                  <span
                    key={i}
                    title={`${c.r.chain}${c.r.residue_number} ${c.r.residue_name}`}
                    className={`text-[10px] font-mono px-1 py-0.5 rounded border ${
                      hitKeys.has(`${c.r.chain}:${c.r.residue_number}`)
                        ? 'bg-good/15 border-good/40 text-good'
                        : activeKeys.has(`${c.r.chain}:${c.r.residue_number}`)
                        ? 'bg-warn/15 border-warn/40 text-warn'
                        : 'bg-surface-1 border-glass-border text-text-secondary'
                    }`}
                  >
                    {c.r.one}
                    <span className="opacity-60 text-[9px] ml-0.5">{c.r.residue_number}</span>
                  </span>
                ) : null,
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */
export default function CastpPage() {
  const router = useRouter();
  const [identifier, setIdentifier] = useState('');
  const [probeRadius, setProbeRadius] = useState(1.4);
  const [result, setResult] = useState<CastpResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showResidues, setShowResidues] = useState<number | null>(null);
  const [viewerUrl, setViewerUrl] = useState<string | undefined>(undefined);
  const [selectedPocket, setSelectedPocket] = useState<number | null>(null);
  const [docking, setDocking] = useState(false);
  const audit = useAuditTrail();

  const handleAnalyze = async () => {
    if (!identifier.trim()) return;
    const label = identifier.trim().toUpperCase();
    audit.emitStarted('castp_analyze', 'CASTp', label);
    setLoading(true);
    setError(null);
    setResult(null);
    setSelectedPocket(null);
    try {
      const res = await runCastp(identifier.trim(), probeRadius);
      setResult(res);
      setViewerUrl(undefined);
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

  const handleUseForDocking = (pocket: CastpPocket) => {
    setDocking(true);
    // Pass the PDB and the selected pocket centroid as the Vina box center.
    setPrefill(router, 'docking_pdb_id', identifier.trim().toUpperCase(), '/analyze/docking');
    setPrefill(router, 'docking_centroid', JSON.stringify(pocket.centroid), '/analyze/docking');
    // router.push already happens inside setPrefill; reset busy state before nav.
    setDocking(false);
  };

  const workflowProgress = result ? 6 : -1; // marks through "Obtain pockets" once data is back

  return (
    <div className="max-w-4xl">
      <BackButton />
      <PageHeader
        title="CASTp Pocket & Cavity Analysis"
        subtitle="Resolves any identifier — PDB ID, UniProt accession, gene name, or raw sequence — through PDB search, UniProt mapping, and ESMFold modeling, then runs the CASTp pocket workflow."
      />

      {/* Workflow stepper */}
      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-4 mb-6">
        <h3 className="font-semibold text-text-primary mb-3 text-sm">Guided Workflow</h3>
        <WorkflowStepper progress={result ? workflowProgress : -1} />
      </motion.div>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-6">
        {/* Select protein (step 1) */}
        <p className="text-[11px] text-text-muted mb-2 uppercase tracking-wide">1 · Select protein</p>
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
            {loading ? 'Searching...' : 'Search'}
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

          {/* Structure resolution pipeline (steps 2–5) */}
          {result.pipeline && result.pipeline.length > 0 && (
            <motion.div variants={fadeUp} className="data-card p-4">
              <h3 className="font-semibold text-text-primary mb-3 text-sm">Structure Resolution (PDB → UniProt → Model)</h3>
              <PipelineView pipeline={result.pipeline} />
              {result.uniprot && (
                <div className="mt-3 pt-3 border-t border-glass-border text-xs text-text-muted">
                  <span className="font-medium text-text-secondary">Resolved to:</span>{' '}
                  <span className="font-mono text-accent-cyan">{result.uniprot.accession}</span>
                  {result.uniprot.name && <span> — {result.uniprot.name}</span>}
                  {result.uniprot.organism && <span> · {result.uniprot.organism}</span>}
                  {result.uniprot.gene_names?.length > 0 && <span> · genes: {result.uniprot.gene_names.join(', ')}</span>}
                  {result.uniprot.sequence_length > 0 && <span> · {result.uniprot.sequence_length} aa</span>}
                </div>
              )}
            </motion.div>
          )}

          {/* Structure viewer */}
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
            <DockingViewer pdbId={viewerUrl ? 'predicted' : result.pdb_id} pdbUrl={viewerUrl} ligandPdb="" />
          </motion.div>

          {/* Chains + gaps */}
          {result.chains && result.chains.length > 0 && (
            <motion.div variants={fadeUp} className="data-card p-5">
              <h3 className="font-semibold text-text-primary mb-3">Structure Chains & Gaps</h3>
              <ChainsView chains={result.chains} />
            </motion.div>
          )}

          {/* Known active-site residues (M-CSA) */}
          {result.active_sites && result.active_sites.length > 0 && (
            <motion.div variants={fadeUp} className="data-card p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-text-primary">Known Active-Site Residues (M-CSA)</h3>
                <Target className="w-4 h-4 text-warn" />
              </div>
              <div className="flex flex-wrap gap-1.5">
                {result.active_sites.map((a, i) => (
                  <span
                    key={i}
                    title={a.role}
                    className="text-[11px] font-mono bg-warn/10 border border-warn/25 text-warn px-2 py-1 rounded"
                  >
                    {a.chain}{a.residue_number} {a.residue_name}
                  </span>
                ))}
              </div>
              <p className="text-[11px] text-text-muted mt-2">
                Catalytic residues from the Mechanism & Catalytic Site Atlas, mapped onto the loaded structure.
              </p>
            </motion.div>
          )}

          {/* Pockets */}
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
              <div className="space-y-4">
                {result.pockets.map((pocket) => {
                  const open = showResidues === pocket.id;
                  const isSelected = selectedPocket === pocket.id;
                  return (
                    <div key={pocket.id} className="border border-glass-border rounded-lg overflow-hidden">
                      <div className={`p-3 ${isSelected ? 'bg-accent-cyan/5' : ''}`}>
                        <div className="flex items-center justify-between gap-3 flex-wrap">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-mono text-accent-cyan">{pocket.id}</span>
                            {isSelected && (
                              <span className="text-[10px] bg-accent-cyan/15 text-accent-cyan px-1.5 py-0.5 rounded font-medium">
                                Probable binding pocket
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 flex-wrap">
                            {pocket.active_site_hits.length > 0 && (
                              <span className="text-[10px] bg-good/10 text-good px-1.5 py-0.5 rounded">
                                {pocket.active_site_hits.length} active-site match{pocket.active_site_hits.length > 1 ? 'es' : ''}
                              </span>
                            )}
                            <button
                              onClick={() => setShowResidues(open ? null : pocket.id)}
                              className="text-xs text-accent-cyan hover:underline flex items-center gap-1"
                            >
                              {open ? 'Hide lining residues' : 'Show lining residues'}
                              <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
                            </button>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3 text-xs">
                          <div>
                            <div className="text-text-muted text-[10px] uppercase">Area (Å²)</div>
                            <div className="font-mono text-text-primary mt-0.5">{pocket.area_sa.toLocaleString()}</div>
                          </div>
                          <div>
                            <div className="text-text-muted text-[10px] uppercase">Volume (Å³)</div>
                            <div className="font-mono text-text-primary mt-0.5">{pocket.volume_sa.toLocaleString()}</div>
                          </div>
                          <div>
                            <div className="text-text-muted text-[10px] uppercase">Lining residues</div>
                            <div className="font-mono text-text-primary mt-0.5">{pocket.num_residues}</div>
                          </div>
                          <div>
                            <div className="text-text-muted text-[10px] uppercase">Radius (Å)</div>
                            <div className="font-mono text-text-primary mt-0.5">{pocket.radius.toFixed(1)}</div>
                          </div>
                        </div>

                        {pocket.chain_spans.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-3">
                            {pocket.chain_spans.map((s) => (
                              <span key={s.chain} className="text-[10px] font-mono bg-surface-1 px-1.5 py-0.5 rounded text-text-muted">
                                Chain {s.chain}: {s.min}–{s.max} ({s.count} res)
                              </span>
                            ))}
                          </div>
                        )}

                        {open && (
                          <div className="mt-4 pt-3 border-t border-glass-border">
                            <PocketLining pocket={pocket} activeSites={result.active_sites || []} />
                            {pocket.gap_ranges.length > 0 && (
                              <div className="mt-3 text-[11px] text-warn">
                                {pocket.gap_ranges.flatMap((pg) => pg.gaps).length} gaps in the lining sequence across{' '}
                                {pocket.gap_ranges.length} chain{pocket.gap_ranges.length > 1 ? 's' : ''}.
                              </div>
                            )}
                          </div>
                        )}

                        {/* Steps 10-11: select probable binding pocket, use for docking */}
                        <div className="flex items-center gap-2 mt-3 pt-3 border-t border-glass-border flex-wrap">
                          <button
                            onClick={() => setSelectedPocket(isSelected ? null : pocket.id)}
                            className={`text-xs px-3 py-1.5 rounded-lg border font-medium transition-colors flex items-center gap-1.5 ${
                              isSelected
                                ? 'bg-accent-cyan/15 border-accent-cyan/40 text-accent-cyan'
                                : 'bg-surface-1 border-glass-border text-text-secondary hover:text-text-primary'
                            }`}
                          >
                            <Target className="w-3.5 h-3.5" />
                            {isSelected ? 'Selected as binding pocket' : 'Select as binding pocket'}
                          </button>
                          <CriticalButton
                            onClick={() => handleUseForDocking(pocket)}
                            disabled={docking}
                            className="text-xs px-3 py-1.5 flex items-center gap-1.5 disabled:opacity-50"
                          >
                            {docking ? <LoaderCircle className="w-3.5 h-3.5 animate-spin" /> : <Link className="w-3.5 h-3.5" />}
                            Use for molecular docking
                          </CriticalButton>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </div>
  );
}

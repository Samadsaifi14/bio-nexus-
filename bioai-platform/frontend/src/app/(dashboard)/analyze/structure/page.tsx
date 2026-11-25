'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { CircleNotch as LoaderCircle, ArrowSquareOut as ExternalLink, Dna, TestTube as FlaskConical, Brain, Pulse as Activity } from '@phosphor-icons/react';
import { fadeUp } from '@/lib/animations';
import { fetchStructure, getStructureInventory, inspectPdbChainIntegrity } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import type { StructureResult, StructureChainInspection } from '@/lib/api';
import { DockingViewer } from '@/components/DockingViewer';
import { AIResultSummary } from '@/components/results/AIResultSummary';
import { BackButton, PageHeader, CriticalButton, FlatInput } from '@/components/ui';
import { consumeParam, getAnalysisHandoff, setPrefill } from '@/lib/cross-link';

function parseHighlightParam(raw: string | null): { start: number; end: number } | undefined {
  if (!raw) return undefined;
  const m = raw.match(/^(\d+)-(\d+)$/);
  if (!m) return undefined;
  const start = Number(m[1]);
  const end = Number(m[2]);
  if (!Number.isFinite(start) || !Number.isFinite(end) || start < 1 || end < start) return undefined;
  return { start, end };
}

export default function StructurePage() {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<StructureResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inventory, setInventory] = useState<{ chains: Array<{ id: string; residue_count: number }>; ligands: Array<{ id: string; chain: string; residue_count: number }> } | null>(null);
  const [linkHighlight, setLinkHighlight] = useState<{ acc: string; range: { start: number; end: number } } | null>(null);
  const [inspection, setInspection] = useState<StructureChainInspection | null>(null);
  const [inspectionLoading, setInspectionLoading] = useState(false);
  const [inspectionError, setInspectionError] = useState<string | null>(null);
  const audit = useAuditTrail();

  const runSearch = async (input: string) => {
    if (!input.trim()) return;
    const inputSummary = `query:${input.trim()}`;
    audit.emitStarted('structure_fetch', 'AlphaFold/PDB', inputSummary);
    setLoading(true);
    setError(null);
    setResult(null);
    setInventory(null);
    setInspection(null);
    setInspectionLoading(false);
    setInspectionError(null);
    try {
      const res = await fetchStructure(input.trim());
      setResult(res);
      if (res.pdb_id) {
        getStructureInventory(res.pdb_id).then(setInventory).catch(() => setInventory(null));
        setInspectionLoading(true);
        inspectPdbChainIntegrity(res.pdb_id)
          .then((report) => { setInspection(report); setInspectionError(null); })
          .catch((inspectionErr: unknown) => setInspectionError(extractErrorMessage(inspectionErr, 'PDB identifiers could not be resolved')))
          .finally(() => setInspectionLoading(false));
      }
      audit.emitSuccess('structure_fetch', 'AlphaFold/PDB', inputSummary, `pdb:${res?.pdb_id ?? ''}`);
    } catch (err: unknown) {
      const errMsg = extractErrorMessage(err, 'Structure not found');
      audit.emitFailed('structure_fetch', 'AlphaFold/PDB', inputSummary, errMsg);
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => runSearch(query);

  const handleInspectChain = async () => {
    if (!pdbId) return;
    setInspectionLoading(true);
    setInspectionError(null);
    try {
      const report = await inspectPdbChainIntegrity(pdbId);
      setInspection(report);
    } catch (err: unknown) {
      setInspectionError(extractErrorMessage(err, 'Could not inspect this PDB entry'));
    } finally {
      setInspectionLoading(false);
    }
  };

  useEffect(() => {
    const handoff = getAnalysisHandoff();
    const stored = consumeParam('structure_query')
      || handoff?.resolvedAccession
      || handoff?.pdbId
      || null;
    if (stored) {
      setQuery(stored);
      void runSearch(stored);
      return;
    }
    const params = new URLSearchParams(window.location.search);
    const uniprotParam = params.get('uniprot');
    if (uniprotParam) {
      const range = parseHighlightParam(params.get('highlight'));
      setQuery(uniprotParam);
      if (range) setLinkHighlight({ acc: uniprotParam, range });
      void runSearch(uniprotParam);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const pdbId = result?.pdb_id || result?.pdb_url?.match(/view\/(\w+)\.pdb$/)?.[1] || '';

  // AlphaFold results don't carry a PDB id — render them by file URL instead.
  const viewerUrl = result?.source === 'alphafold' ? result.cif_url || result.pdb_url : undefined;
  const viewerUrlFormat = result?.source === 'alphafold' ? (result.cif_url ? 'cif' : 'pdb') : undefined;

  const highlightApplied =
    linkHighlight &&
    result &&
    (result.uniprot_accession?.toUpperCase() === linkHighlight.acc.toUpperCase() ||
      query.trim().toUpperCase() === linkHighlight.acc.toUpperCase())
      ? linkHighlight.range
      : undefined;

  return (
    <div className="max-w-3xl">
      <BackButton />

      <PageHeader title="Structure Viewer" subtitle="Fetch 3D structures from PDB or AlphaFold by PDB ID or UniProt accession." />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-6">
        <div className="flex gap-3">
          <FlatInput
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setResult(null); setError(null); setInventory(null); setLinkHighlight(null); setInspection(null); setInspectionError(null); }}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="e.g. 1TIM, P04637, 4HHB"
            className="flex-1"
          />
          <CriticalButton onClick={handleSearch} disabled={loading || !query.trim()}>
            {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Dna className="w-4 h-4" />}
            Fetch
          </CriticalButton>
        </div>
        <div className="flex gap-3 mt-3">
          <button onClick={() => { setQuery('1TIM'); setError(null); setResult(null); }} className="text-xs text-accent-cyan hover:text-accent-cyan/80 underline">1TIM (triosephosphate isomerase)</button>
          <button onClick={() => { setQuery('4HHB'); setError(null); setResult(null); }} className="text-xs text-accent-cyan hover:text-accent-cyan/80 underline">4HHB (hemoglobin)</button>
          <button onClick={() => { setQuery('P04637'); setError(null); setResult(null); }} className="text-xs text-accent-cyan hover:text-accent-cyan/80 underline">P04637 (p53, UniProt)</button>
        </div>
      </motion.div>

      {loading && (
        <div className="data-card p-4 mb-4" role="status" aria-live="polite">
          <p className="text-sm font-medium text-text-primary">Resolving structure identifier</p>
          <p className="text-xs text-text-muted mt-1">
            Query: <span className="font-mono text-text-secondary">{query.trim().toUpperCase()}</span>
            {' '}· Checking RCSB PDB and AlphaFold sources
          </p>
        </div>
      )}

      {error && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-4 border border-error/20">
          <p className="text-sm text-error">{error}</p>
          {linkHighlight && (
            <div className="mt-2 text-xs text-text-muted">
              Couldn&apos;t find a structure for{' '}
              <code className="font-mono text-text-secondary">{linkHighlight.acc}</code>. AlphaFold and PDB may not
              cover this accession. Search with a UniProt accession (e.g. P04637) or a PDB ID (e.g. 1TIM) to continue,
              then use the motif scanner&apos;s highlight again.
            </div>
          )}
        </motion.div>
      )}

      {result && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-4">
          <AIResultSummary toolName="structure" result={result as unknown as Record<string, unknown>} />
          <section className="data-card p-4" aria-label="Resolved structure identifiers">
            <h3 className="text-sm font-semibold text-text-primary mb-3">Resolved identifiers</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <p className="text-[11px] uppercase tracking-wide text-text-muted">RCSB PDB ID</p>
                {pdbId ? (
                  <a className="font-mono text-sm text-accent-cyan hover:underline" href={`https://www.rcsb.org/structure/${pdbId}`} target="_blank" rel="noopener noreferrer">{pdbId} ↗</a>
                ) : <p className="text-sm text-text-secondary">Not applicable to this AlphaFold model</p>}
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-wide text-text-muted">UniProt accession(s)</p>
                {inspectionLoading ? (
                  <p className="text-sm text-text-secondary">Resolving UniProt mappings…</p>
                ) : inspection?.chain_uniprot?.length ? (
                  <div className="flex flex-wrap gap-2 mt-1">
                    {inspection.chain_uniprot.flatMap((mapping) => mapping.accessions.map((accession) => (
                      <div key={`${mapping.chain}-${accession}`} className="flex items-center gap-2 flex-wrap">
                        <a className="font-mono text-sm text-accent-cyan hover:underline" href={`https://www.uniprot.org/uniprotkb/${accession}`} target="_blank" rel="noopener noreferrer">
                          {accession} <span className="text-text-muted text-xs">(chain {mapping.chain})</span>
                        </a>
                        <button type="button" onClick={() => router.push(`/analyze/swissmodel?accession=${encodeURIComponent(accession)}&chain=${encodeURIComponent(mapping.chain)}&pdb_id=${encodeURIComponent(pdbId)}`)} className="text-[11px] rounded-md border border-accent-cyan/30 px-2 py-1 text-accent-cyan hover:bg-accent-cyan/10">
                          Open in SWISS-MODEL
                        </button>
                      </div>
                    )))}
                  </div>
                ) : result.uniprot_accession ? (
                  <a className="font-mono text-sm text-accent-cyan hover:underline" href={`https://www.uniprot.org/uniprotkb/${result.uniprot_accession}`} target="_blank" rel="noopener noreferrer">{result.uniprot_accession} ↗</a>
                ) : <p className="text-sm text-text-secondary">{inspectionError || 'No UniProt mapping reported for this entry'}</p>}
              </div>
            </div>
            {pdbId && (
              <div className="flex flex-wrap gap-3 mt-3 text-xs">
                <a className="text-accent-cyan hover:underline" href={`https://www.rcsb.org/structure/${pdbId}`} target="_blank" rel="noopener noreferrer">Open RCSB entry ↗</a>
                <a className="text-accent-cyan hover:underline" href={`https://www.ebi.ac.uk/pdbe/entry/pdb/${pdbId.toLowerCase()}`} target="_blank" rel="noopener noreferrer">Open PDBe entry ↗</a>
              </div>
            )}
          </section>
          <div className="data-card p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-semibold text-text-primary">{result.title || result.pdb_id || result.uniprot_accession}</h3>
                <p className="text-xs text-text-muted mt-1">
                  Source: {result.source === 'pdb' ? 'PDB' : 'AlphaFold'}
                  {result.method ? ` · ${result.method}` : ''}
                  {result.resolution ? ` · ${result.resolution}Å` : ''}
                  {result.confidence ? ` · pLDDT: ${result.confidence}` : ''}
                </p>
              </div>
              {result.pdb_url && (
                <a href={result.pdb_url} target="_blank" rel="noopener noreferrer" className="text-xs text-accent-cyan hover:underline flex items-center gap-1">
                  Download PDB <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
            {pdbId || viewerUrl ? (
              <DockingViewer
                pdbId={pdbId}
                pdbUrl={viewerUrl}
                pdbUrlFormat={viewerUrlFormat}
                ligandPdb=""
                chains={inventory?.chains}
                ligands={inventory?.ligands}
                highlightRange={highlightApplied}
              />
            ) : (
              <div className="w-full h-96 rounded-xl bg-surface-0 flex items-center justify-center">
                <p className="text-sm text-text-muted">3D view not available</p>
              </div>
            )}
            {highlightApplied && (
              <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-accent-amber/30 bg-accent-amber/5 px-3 py-2 text-xs text-text-secondary">
                <span className="text-accent-amber">Highlighted residues {highlightApplied.start}–{highlightApplied.end}</span>
                <button onClick={() => setLinkHighlight(null)} className="text-text-muted hover:text-text-primary underline">Clear highlight</button>
              </div>
            )}
          </div>

          {pdbId && (
            <section className="data-card p-5 space-y-3" aria-label="Chain integrity inspection">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-text-primary">Chain integrity check</h3>
                  <p className="text-xs text-text-muted mt-1">Checks deposited missing-residue records and Cα–Cα discontinuities.</p>
                </div>
                <CriticalButton onClick={handleInspectChain} disabled={inspectionLoading}>
                  {inspectionLoading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Activity className="w-4 h-4" />}
                  {inspectionLoading ? 'Checking…' : 'Check chain gaps'}
                </CriticalButton>
              </div>
              {inspectionError && <p className="text-sm text-error">{inspectionError}</p>}
              {inspection && (
                <div className="space-y-4">
                  <div className={inspection.chain_health.is_broken
                    ? "rounded-lg border border-error/30 bg-error/5 p-3"
                    : "rounded-lg border border-accent-cyan/20 bg-accent-cyan/5 p-3"}>
                    <p className="text-sm font-medium text-text-primary">
                      {inspection.chain_health.is_broken ? 'Potential chain discontinuity detected' : 'No chain gaps detected by these checks'}
                    </p>
                    <p className="text-xs text-text-muted mt-1">
                      {inspection.chain_health.total_residues.toLocaleString()} observed protein residues across {inspection.chain_health.chains.length} chains ·
                      {' '}{inspection.chain_health.missing_residue_count} REMARK 465 missing residues ·
                      {' '}{inspection.chain_health.chain_break_count} Cα distance breaks
                    </p>
                  </div>
                  {inspection.chain_health.missing_ranges.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-text-primary mb-1">Deposited missing-residue records</p>
                      <p className="text-xs text-text-muted break-words">{inspection.chain_health.missing_ranges.join(', ')}</p>
                    </div>
                  )}
                  {inspection.chain_health.chain_breaks.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-text-primary mb-1">Cα–Cα discontinuities (threshold: 4.2 Å)</p>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs text-left">
                          <thead><tr className="text-text-muted"><th className="py-1 pr-3">Chain</th><th className="py-1 pr-3">From residue</th><th className="py-1 pr-3">To residue</th><th className="py-1">Distance</th></tr></thead>
                          <tbody>{inspection.chain_health.chain_breaks.map((gap, index) => (
                            <tr key={`${gap.chain}-${gap.from_resnum}-${gap.to_resnum}-${index}`} className="border-t border-glass-border text-text-secondary">
                              <td className="py-1 pr-3">{gap.chain}</td><td className="py-1 pr-3">{gap.from_resnum}</td><td className="py-1 pr-3">{gap.to_resnum}</td><td className="py-1">{gap.distance.toFixed(2)} Å</td>
                            </tr>
                          ))}</tbody>
                        </table>
                      </div>
                    </div>
                  )}
                  <div>
                    <p className="text-xs font-semibold text-text-primary mb-2">Chain → UniProt mapping</p>
                    {inspection.chain_uniprot.length === 0 ? (
                      <p className="text-xs text-text-muted">No UniProt mapping was returned by PDBe SIFTS for this entry. This does not mean the protein has no UniProt record.</p>
                    ) : inspection.chain_uniprot.map((mapping) => (
                      <div key={mapping.chain} className="mb-3 rounded-lg border border-glass-border p-3">
                        <p className="text-xs text-text-secondary mb-2">Chain {mapping.chain}</p>
                        <div className="flex flex-wrap gap-2">
                          {mapping.accessions.map((accession) => (
                            <div key={accession} className="w-full space-y-2">
                              <p className="text-sm font-mono text-text-primary">{accession}</p>
                              <div className="flex flex-wrap gap-3 text-xs">
                                <a className="text-accent-cyan hover:underline" href={`https://www.uniprot.org/uniprotkb/${accession}`} target="_blank" rel="noopener noreferrer">UniProt record ↗</a>
                                <a className="text-accent-cyan hover:underline" href={`https://alphafold.ebi.ac.uk/entry/${accession}`} target="_blank" rel="noopener noreferrer">AlphaFold DB ↗</a>
                                <a className="text-accent-cyan hover:underline" href={`https://swissmodel.expasy.org/repository/uniprot/${accession}`} target="_blank" rel="noopener noreferrer">SWISS-MODEL ↗</a>
                                <button className="text-accent-cyan hover:underline" onClick={() => { setQuery(accession); void runSearch(accession); }}>Fetch by UniProt ID</button>
                              </div>
                              {(inspection.alternative_structures[accession] || []).length > 0 && (
                                <div className="text-xs text-text-muted">
                                  Alternative experimental PDB entries: {(inspection.alternative_structures[accession] || []).map((entry) => (
                                    <a key={entry.pdb_id} className="ml-2 text-accent-cyan hover:underline" href={entry.url} target="_blank" rel="noopener noreferrer">{entry.pdb_id}</a>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                  <p className="text-[11px] text-text-muted">Method note: this report uses PDB REMARK 465 annotations and observed Cα–Cα distances greater than 4.2 Å. It is a chain-continuity screen, not a complete wwPDB validation or proof that the biological protein is complete.</p>
                  <div className="flex flex-wrap gap-3 text-xs">
                    <a className="text-accent-cyan hover:underline" href={inspection.sources.rcsb} target="_blank" rel="noopener noreferrer">RCSB entry ↗</a>
                    <a className="text-accent-cyan hover:underline" href={inspection.sources.pdbe} target="_blank" rel="noopener noreferrer">PDBe entry ↗</a>
                  </div>
                </div>
              )}
            </section>
          )}

          {pdbId && inspection?.chain_health.is_broken && (
            <p className="text-xs text-text-muted">
              Whole-entry preparation keeps the PDB ID as one job and inspects all deposited chains. The current SWISS-MODEL integration does not yet perform validated multichain reconstruction, so this action must not be interpreted as a completed whole-complex model.
            </p>
          )}
          <div className="glass-card p-4 flex flex-wrap gap-2">
            <span className="text-xs text-text-muted self-center mr-2">Open in:</span>
            {pdbId && inspection?.chain_health.is_broken && (
              <button
                onClick={() => setPrefill(router, 'structure_prep_pdb_id', pdbId, '/analyze/structure-prep')}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-accent-amber/30 bg-accent-amber/5 hover:bg-accent-amber/10 transition"
                title="Run one preparation job against the complete deposited PDB entry"
              >
                <Activity className="w-3 h-3" /> Prepare whole PDB entry
              </button>
            )}
            {pdbId && (
              <>
                <button onClick={() => setPrefill(router, 'docking_pdb_id', pdbId, '/analyze/docking')}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-glass-border bg-surface-1 hover:bg-surface-2 hover:text-accent-cyan transition">
                  <FlaskConical className="w-3 h-3" /> Docking
                </button>
                <button onClick={() => setPrefill(router, 'md_pdb_id', pdbId, '/analyze/md')}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-glass-border bg-surface-1 hover:bg-surface-2 hover:text-accent-cyan transition">
                  <Activity className="w-3 h-3" /> MD Simulation
                </button>
                <button onClick={() => setPrefill(router, 'function_pdb_id', pdbId, '/analyze/function')}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-glass-border bg-surface-1 hover:bg-surface-2 hover:text-accent-cyan transition">
                  <Brain className="w-3 h-3" /> Function Evidence
                </button>
              </>
            )}
            {result?.uniprot_accession && (
              <button onClick={() => setPrefill(router, 'domains_accession', result.uniprot_accession!, '/analyze/domains')}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-glass-border bg-surface-1 hover:bg-surface-2 hover:text-accent-cyan transition">
                <Dna className="w-3 h-3" /> Domains
              </button>
            )}
          </div>
        </motion.div>
      )}
    </div>
  );
}

'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { LoaderCircle, ExternalLink, Dna, FlaskConical, Brain, Activity } from 'lucide-react';
import { fadeUp } from '@/lib/animations';
import { fetchStructure, getStructureInventory } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import type { StructureResult } from '@/lib/api';
import { DockingViewer } from '@/components/DockingViewer';
import { BackButton, PageHeader, CriticalButton, FlatInput } from '@/components/ui';

export default function StructurePage() {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<StructureResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inventory, setInventory] = useState<{ chains: Array<{ id: string; residue_count: number }>; ligands: Array<{ id: string; chain: string; residue_count: number }> } | null>(null);
  const audit = useAuditTrail();

  useEffect(() => {
    const stored = sessionStorage.getItem('structure_query');
    if (stored) {
      sessionStorage.removeItem('structure_query');
      setQuery(stored);
      setTimeout(() => handleSearch(), 100);
    }
  }, []);

  const handleSearch = async () => {
    if (!query.trim()) return;
    const inputSummary = `query:${query.trim()}`;
    audit.emitStarted('structure_fetch', 'AlphaFold/PDB', inputSummary);
    setLoading(true);
    setError(null);
    setResult(null);
    setInventory(null);
    try {
      const res = await fetchStructure(query.trim());
      setResult(res);
      if (res.pdb_id) {
        getStructureInventory(res.pdb_id).then(setInventory).catch(() => setInventory(null));
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

  const pdbId = result?.pdb_id || result?.pdb_url?.match(/view\/(\w+)\.pdb$/)?.[1] || '';

  return (
    <div className="max-w-3xl">
      <BackButton />

      <PageHeader title="Structure Viewer" subtitle="Fetch 3D structures from PDB or AlphaFold by PDB ID or UniProt accession." />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-6">
        <div className="flex gap-3">
          <FlatInput
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
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

      {error && <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-4 border border-error/20"><p className="text-sm text-error">{error}</p></motion.div>}

      {result && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-4">
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
            {pdbId ? (
              <DockingViewer pdbId={pdbId} ligandPdb="" chains={inventory?.chains} ligands={inventory?.ligands} />
            ) : (
              <div className="w-full h-96 rounded-xl bg-surface-0 flex items-center justify-center">
                <p className="text-sm text-text-muted">3D view not available</p>
              </div>
            )}
          </div>

          <div className="glass-card p-4 flex flex-wrap gap-2">
            <span className="text-xs text-text-muted self-center mr-2">Open in:</span>
            {pdbId && (
              <>
                <button onClick={() => { sessionStorage.setItem('docking_pdb_id', pdbId); router.push('/analyze/docking'); }}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-glass-border bg-surface-1 hover:bg-surface-2 hover:text-accent-cyan transition">
                  <FlaskConical className="w-3 h-3" /> Docking
                </button>
                <button onClick={() => { sessionStorage.setItem('md_pdb_id', pdbId); router.push('/analyze/md'); }}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-glass-border bg-surface-1 hover:bg-surface-2 hover:text-accent-cyan transition">
                  <Activity className="w-3 h-3" /> MD Simulation
                </button>
                <button onClick={() => { sessionStorage.setItem('function_pdb_id', pdbId); router.push('/analyze/function'); }}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-glass-border bg-surface-1 hover:bg-surface-2 hover:text-accent-cyan transition">
                  <Brain className="w-3 h-3" /> Function Prediction
                </button>
              </>
            )}
            {result?.uniprot_accession && (
              <button onClick={() => { sessionStorage.setItem('domains_accession', result.uniprot_accession!); router.push('/analyze/domains'); }}
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

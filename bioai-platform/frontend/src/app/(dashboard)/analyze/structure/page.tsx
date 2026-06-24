'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { ArrowLeft, LoaderCircle, ExternalLink, Dna } from 'lucide-react';
import { fadeUp } from '@/lib/animations';
import { fetchStructure } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import type { StructureResult } from '@/lib/api';
import StructureViewer from '@/components/StructureViewer';

export default function StructurePage() {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<StructureResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetchStructure(query.trim());
      setResult(res);
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Structure not found'));
    } finally {
      setLoading(false);
    }
  };

  const pdbId = result?.pdb_id || result?.pdb_url?.match(/view\/(\w+)\.pdb$/)?.[1] || '';

  return (
    <div className="max-w-3xl">
      <button onClick={() => router.push('/analyze')} className="flex items-center gap-1 text-sm text-text-muted hover:text-text-primary mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Choose a different operation
      </button>

      <motion.div variants={fadeUp} initial="hidden" animate="show" className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary mb-1">Structure Viewer</h1>
        <p className="text-sm text-text-secondary">Fetch 3D structures from PDB or AlphaFold by PDB ID or UniProt accession.</p>
      </motion.div>

      <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-5 mb-6">
        <div className="flex gap-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="e.g. 1TIM, P04637, 4HHB"
            className="flex-1 px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm"
          />
          <button onClick={handleSearch} disabled={loading || !query.trim()} className="btn-primary px-6 py-3 flex items-center gap-2 disabled:opacity-50">
            {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Dna className="w-4 h-4" />}
            Fetch
          </button>
        </div>
        <div className="flex gap-3 mt-3">
          <button onClick={() => { setQuery('1TIM'); setError(null); setResult(null); }} className="text-xs text-accent-cyan hover:text-accent-cyan/80 underline">1TIM (triosephosphate isomerase)</button>
          <button onClick={() => { setQuery('4HHB'); setError(null); setResult(null); }} className="text-xs text-accent-cyan hover:text-accent-cyan/80 underline">4HHB (hemoglobin)</button>
          <button onClick={() => { setQuery('P04637'); setError(null); setResult(null); }} className="text-xs text-accent-cyan hover:text-accent-cyan/80 underline">P04637 (p53, UniProt)</button>
        </div>
      </motion.div>

      {error && <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-4 border border-error/20"><p className="text-sm text-error">{error}</p></motion.div>}

      {result && (
        <motion.div variants={fadeUp} initial="hidden" animate="show" className="space-y-4">
          <div className="glass-card p-5">
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
              <StructureViewer pdbId={pdbId} />
            ) : (
              <div className="w-full h-96 rounded-xl bg-surface-0 flex items-center justify-center">
                <p className="text-sm text-text-muted">3D view not available</p>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </div>
  );
}

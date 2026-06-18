'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { ArrowLeft, LoaderCircle, ExternalLink, GitBranch } from 'lucide-react';
import { fadeUp } from '@/lib/animations';
import { searchPathways } from '@/lib/api';
import type { PathwayResult } from '@/lib/api';

export default function PathwayPage() {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PathwayResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const res = await searchPathways(query.trim());
      setResults(res.results);
    } catch {
      setError('Pathway search failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <button onClick={() => router.push('/analyze')} className="flex items-center gap-1 text-sm text-text-muted hover:text-text-primary mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Choose a different operation
      </button>

      <motion.div variants={fadeUp} initial="hidden" animate="show" className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary mb-1">Pathway Analysis</h1>
        <p className="text-sm text-text-secondary">Map your genes or proteins to biological pathways from Reactome.</p>
      </motion.div>

      <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-5 mb-6">
        <div className="flex gap-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="e.g. TP53, BRCA1, EGFR"
            className="flex-1 px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm"
          />
          <button onClick={handleSearch} disabled={loading || !query.trim()} className="btn-primary px-6 py-3 flex items-center gap-2 disabled:opacity-50">
            {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <GitBranch className="w-4 h-4" />}
            Search
          </button>
        </div>
      </motion.div>

      {error && <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-4 border border-error/20"><p className="text-sm text-error">{error}</p></motion.div>}

      {results && (
        <motion.div variants={fadeUp} initial="hidden" animate="show" className="space-y-3">
          <p className="text-xs text-text-muted mb-2">{results.length} pathway{results.length !== 1 ? 's' : ''} found</p>
          {results.length === 0 ? (
            <div className="glass-card p-6 text-center"><p className="text-sm text-text-secondary">No pathways found</p></div>
          ) : (
            results.map((p) => (
              <a key={p.pathway_id} href={p.url} target="_blank" rel="noopener noreferrer" className="glass-card p-4 flex items-center justify-between hover:bg-surface-2 transition cursor-pointer">
                <div>
                  <p className="text-sm font-medium text-text-primary">{p.name}</p>
                  <p className="text-xs text-text-muted mt-0.5">{p.pathway_id} · {p.species}</p>
                </div>
                <ExternalLink className="w-4 h-4 text-text-muted shrink-0" />
              </a>
            ))
          )}
        </motion.div>
      )}
    </div>
  );
}

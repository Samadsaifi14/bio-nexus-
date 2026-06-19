'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, LoaderCircle, ExternalLink, GitBranch, ChevronDown, ChevronRight, Dna } from 'lucide-react';
import { fadeUp } from '@/lib/animations';
import { searchPathways, searchKEGGPathways, runEnrichment } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import type { PathwayResult, KEGGPathwayResult, EnrichmentResult } from '@/lib/api';
import PathwayDiagram from '@/components/results/PathwayDiagram';

type Tab = 'reactome' | 'kegg' | 'enrichment';

export default function PathwayPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>('reactome');
  const [query, setQuery] = useState('');
  const [reactomeResults, setReactomeResults] = useState<PathwayResult[] | null>(null);
  const [keggResults, setKeggResults] = useState<KEGGPathwayResult[] | null>(null);
  const [enrichmentResult, setEnrichmentResult] = useState<EnrichmentResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedDiagram, setExpandedDiagram] = useState<string | null>(null);
  const [expandedKEGG, setExpandedKEGG] = useState<string | null>(null);
  const [geneInput, setGeneInput] = useState('');

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setExpandedDiagram(null);
    try {
      if (tab === 'reactome') {
        setKeggResults(null);
        setEnrichmentResult(null);
        const res = await searchPathways(query.trim());
        setReactomeResults(res.results);
      } else if (tab === 'kegg') {
        setReactomeResults(null);
        setEnrichmentResult(null);
        const res = await searchKEGGPathways(query.trim());
        setKeggResults(res.results);
      }
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Search failed'));
    } finally {
      setLoading(false);
    }
  }, [query, tab]);

  const handleEnrichment = useCallback(async () => {
    const ids = geneInput.trim().split(/[\n,]+/).map(s => s.trim()).filter(Boolean);
    if (ids.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const res = await runEnrichment(ids);
      setEnrichmentResult(res);
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Enrichment analysis failed'));
    } finally {
      setLoading(false);
    }
  }, [geneInput]);

  return (
    <div className="max-w-3xl">
      <button onClick={() => router.push('/analyze')} className="flex items-center gap-1 text-sm text-text-muted hover:text-text-primary mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Choose a different operation
      </button>

      <motion.div variants={fadeUp} initial="hidden" animate="show" className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary mb-1">Pathway Analysis</h1>
        <p className="text-sm text-text-secondary">Map your genes or proteins to biological pathways from Reactome and KEGG, or run pathway enrichment analysis.</p>
      </motion.div>

      <div className="flex gap-1 mb-6 border-b border-glass-border">
        {(['reactome', 'kegg', 'enrichment'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => { setTab(t); setError(null); }}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition -mb-px ${
              tab === t
                ? 'border-accent-cyan text-accent-cyan'
                : 'border-transparent text-text-muted hover:text-text-primary'
            }`}
          >
            {t === 'reactome' ? 'Reactome' : t === 'kegg' ? 'KEGG' : 'Enrichment'}
          </button>
        ))}
      </div>

      {tab !== 'enrichment' && (
        <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-5 mb-6">
          <div className="flex gap-3">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder={tab === 'reactome' ? 'e.g. TP53, BRCA1, EGFR' : 'e.g. TP53, BRCA1'}
              className="flex-1 px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm"
            />
            <button onClick={handleSearch} disabled={loading || !query.trim()} className="btn-primary px-6 py-3 flex items-center gap-2 disabled:opacity-50">
              {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <GitBranch className="w-4 h-4" />}
              Search
            </button>
          </div>
          <div className="flex gap-3 mt-3">
            <button onClick={() => { setQuery('TP53'); setError(null); }} className="text-xs text-accent-cyan hover:text-accent-cyan/80 underline">TP53 (p53)</button>
            <button onClick={() => { setQuery('BRCA1'); setError(null); }} className="text-xs text-accent-cyan hover:text-accent-cyan/80 underline">BRCA1</button>
            <button onClick={() => { setQuery('EGFR'); setError(null); }} className="text-xs text-accent-cyan hover:text-accent-cyan/80 underline">EGFR</button>
          </div>
        </motion.div>
      )}

      {tab === 'enrichment' && (
        <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-5 mb-6">
          <p className="text-sm text-text-secondary mb-3">Paste gene or protein identifiers (one per line or comma-separated) to find over-represented pathways.</p>
          <textarea
            value={geneInput}
            onChange={(e) => setGeneInput(e.target.value)}
            placeholder={`TP53\nBRCA1\nEGFR\nMYC\nPTEN`}
            rows={6}
            className="w-full px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm resize-none mb-3"
          />
          <button onClick={handleEnrichment} disabled={loading || !geneInput.trim()} className="btn-primary px-6 py-3 flex items-center gap-2 disabled:opacity-50">
            {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Dna className="w-4 h-4" />}
            Analyze
          </button>
        </motion.div>
      )}

      {error && <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-4 border border-error/20"><p className="text-sm text-error">{error}</p></motion.div>}

      {tab === 'reactome' && reactomeResults && (
        <motion.div variants={fadeUp} initial="hidden" animate="show" className="space-y-3">
          <p className="text-xs text-text-muted mb-2">{reactomeResults.length} pathway{reactomeResults.length !== 1 ? 's' : ''} found</p>
          {reactomeResults.length === 0 ? (
            <div className="glass-card p-6 text-center"><p className="text-sm text-text-secondary">No pathways found</p></div>
          ) : (
            reactomeResults.map((p) => (
              <div key={p.pathway_id} className="glass-card overflow-hidden">
                <button
                  onClick={() => setExpandedDiagram(expandedDiagram === p.pathway_id ? null : p.pathway_id)}
                  className="w-full p-4 flex items-center justify-between hover:bg-surface-2 transition cursor-pointer text-left"
                >
                  <div>
                    <p className="text-sm font-medium text-text-primary">{p.name}</p>
                    <p className="text-xs text-text-muted mt-0.5">{p.pathway_id} · {p.species}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <a href={p.url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} className="text-text-muted hover:text-accent-cyan transition">
                      <ExternalLink className="w-4 h-4" />
                    </a>
                    {expandedDiagram === p.pathway_id ? <ChevronDown className="w-4 h-4 text-text-muted" /> : <ChevronRight className="w-4 h-4 text-text-muted" />}
                  </div>
                </button>
                <AnimatePresence>
                  {expandedDiagram === p.pathway_id && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3 }}
                      className="overflow-hidden border-t border-glass-border"
                    >
                      <div className="p-4">
                        <PathwayDiagram stId={p.pathway_id} geneName={query} />
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ))
          )}
        </motion.div>
      )}

      {tab === 'kegg' && keggResults && (
        <motion.div variants={fadeUp} initial="hidden" animate="show" className="space-y-3">
          <p className="text-xs text-text-muted mb-2">{keggResults.length} pathway{keggResults.length !== 1 ? 's' : ''} found</p>
          {keggResults.length === 0 ? (
            <div className="glass-card p-6 text-center"><p className="text-sm text-text-secondary">No pathways found</p></div>
          ) : (
            keggResults.map((p) => (
              <div key={p.pathway_id} className="glass-card overflow-hidden">
                <button
                  onClick={() => setExpandedKEGG(expandedKEGG === p.pathway_id ? null : p.pathway_id)}
                  className="w-full p-4 flex items-center justify-between hover:bg-surface-2 transition cursor-pointer text-left"
                >
                  <div className="flex items-center gap-3">
                    <img src={p.image_url} alt="" className="w-16 h-12 object-contain rounded border border-glass-border shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-text-primary">{p.name}</p>
                      <p className="text-xs text-text-muted mt-0.5">{p.pathway_id} · {p.organism}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <a href={p.url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} className="text-text-muted hover:text-accent-cyan transition">
                      <ExternalLink className="w-4 h-4" />
                    </a>
                    {expandedKEGG === p.pathway_id ? <ChevronDown className="w-4 h-4 text-text-muted" /> : <ChevronRight className="w-4 h-4 text-text-muted" />}
                  </div>
                </button>
                <AnimatePresence>
                  {expandedKEGG === p.pathway_id && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3 }}
                      className="overflow-hidden border-t border-glass-border"
                    >
                      <div className="p-4 flex justify-center">
                        <img src={p.image_url} alt={p.name} className="max-w-full rounded border border-glass-border" />
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ))
          )}
        </motion.div>
      )}

      {tab === 'enrichment' && enrichmentResult && (
        <motion.div variants={fadeUp} initial="hidden" animate="show" className="space-y-3">
          <p className="text-xs text-text-muted mb-2">{enrichmentResult.pathways.length} enriched pathway{enrichmentResult.pathways.length !== 1 ? 's' : ''} found</p>
          {enrichmentResult.pathways.length === 0 ? (
            <div className="glass-card p-6 text-center"><p className="text-sm text-text-secondary">No significantly enriched pathways found</p></div>
          ) : (
            enrichmentResult.pathways.map((pw) => (
              <div key={pw.stId} className="glass-card overflow-hidden">
                <button
                  onClick={() => setExpandedDiagram(expandedDiagram === pw.stId ? null : pw.stId)}
                  className="w-full p-4 flex items-center justify-between hover:bg-surface-2 transition cursor-pointer text-left"
                >
                  <div>
                    <p className="text-sm font-medium text-text-primary">{pw.name}</p>
                    <p className="text-xs text-text-muted mt-0.5">
                      {pw.stId} · {pw.species} · {pw.entitiesFound}/{pw.entitiesTotal} genes · FDR {pw.entitiesFDR.toExponential(2)}
                    </p>
                  </div>
                  {expandedDiagram === pw.stId ? <ChevronDown className="w-4 h-4 text-text-muted" /> : <ChevronRight className="w-4 h-4 text-text-muted" />}
                </button>
                <AnimatePresence>
                  {expandedDiagram === pw.stId && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3 }}
                      className="overflow-hidden border-t border-glass-border"
                    >
                      <div className="p-4">
                        <PathwayDiagram stId={pw.stId} />
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ))
          )}
        </motion.div>
      )}
    </div>
  );
}
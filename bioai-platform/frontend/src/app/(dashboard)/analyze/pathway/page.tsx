'use client';

import { useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CircleNotch as LoaderCircle, ArrowSquareOut as ExternalLink, GitBranch, CaretDown as ChevronDown, CaretRight as ChevronRight, Dna } from '@phosphor-icons/react';
import { fadeUp } from '@/lib/animations';
import { searchPathways, searchKEGGPathways, runEnrichment } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import type { PathwayResult, KEGGPathwayResult, EnrichmentResult } from '@/lib/api';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import PathwayDiagram from '@/components/results/PathwayDiagram';
import { BackButton, PageHeader, ClaySegmented, CriticalButton, FlatInput, FlatTextarea } from '@/components/ui';

type Tab = 'reactome' | 'kegg' | 'enrichment';

export default function PathwayPage() {
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
  const audit = useAuditTrail();

  useEffect(() => {
    const stored = sessionStorage.getItem('pathway_query');
    if (stored) {
      sessionStorage.removeItem('pathway_query');
      setQuery(stored);
    }
  }, []);

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;
    const inputSummary = `tab:${tab},query:${query.trim()}`;
    audit.emitStarted('pathway_search', 'Pathway', inputSummary);
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
      audit.emitSuccess('pathway_search', 'Pathway', inputSummary, `tab:${tab}`);
    } catch (err: unknown) {
      const errMsg = extractErrorMessage(err, 'Search failed');
      audit.emitFailed('pathway_search', 'Pathway', inputSummary, errMsg);
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  }, [query, tab, audit]);

  const handleEnrichment = useCallback(async () => {
    const ids = geneInput.trim().split(/[\n,]+/).map(s => s.trim()).filter(Boolean);
    if (ids.length === 0) return;
    const inputSummary = `genes:${ids.length}`;
    audit.emitStarted('pathway_enrichment', 'Pathway', inputSummary);
    setLoading(true);
    setError(null);
    try {
      const res = await runEnrichment(ids);
      setEnrichmentResult(res);
      audit.emitSuccess('pathway_enrichment', 'Pathway', inputSummary, `hits:${res?.pathways?.length ?? 0}`);
    } catch (err: unknown) {
      const errMsg = extractErrorMessage(err, 'Enrichment analysis failed');
      audit.emitFailed('pathway_enrichment', 'Pathway', inputSummary, errMsg);
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  }, [geneInput, audit]);

  return (
    <div className="max-w-3xl">
      <BackButton />

      <PageHeader title="Pathway Analysis" subtitle="Map your genes or proteins to biological pathways from Reactome and KEGG, or run pathway enrichment analysis." />

      <ClaySegmented
        className="mb-6"
        options={[
          { value: 'reactome', label: 'Reactome' },
          { value: 'kegg', label: 'KEGG' },
          { value: 'enrichment', label: 'Enrichment' },
        ]}
        value={tab}
        onChange={(t) => { setTab(t); setError(null); }}
      />

      {tab !== 'enrichment' && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-6">
          <div className="flex gap-3">
            <FlatInput
              type="text"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setReactomeResults(null); setKeggResults(null); setError(null); }}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder={tab === 'reactome' ? 'e.g. TP53, BRCA1, EGFR' : 'e.g. TP53, BRCA1'}
              className="flex-1"
            />
            <CriticalButton onClick={handleSearch} disabled={loading || !query.trim()}>
              {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <GitBranch className="w-4 h-4" />}
              Search
            </CriticalButton>
          </div>
          <div className="flex gap-3 mt-3">
            <button onClick={() => { setQuery('TP53'); setError(null); }} className="text-xs text-accent-cyan hover:text-accent-cyan/80 underline">TP53 (p53)</button>
            <button onClick={() => { setQuery('BRCA1'); setError(null); }} className="text-xs text-accent-cyan hover:text-accent-cyan/80 underline">BRCA1</button>
            <button onClick={() => { setQuery('EGFR'); setError(null); }} className="text-xs text-accent-cyan hover:text-accent-cyan/80 underline">EGFR</button>
          </div>
        </motion.div>
      )}

      {tab === 'enrichment' && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-6">
          <p className="text-sm text-text-secondary mb-3">Paste gene or protein identifiers (one per line or comma-separated) to find over-represented pathways.</p>
          <FlatTextarea
            value={geneInput}
            onChange={(e) => { setGeneInput(e.target.value); setEnrichmentResult(null); setError(null); }}
            placeholder={`TP53\nBRCA1\nEGFR\nMYC\nPTEN`}
            rows={6}
            className="w-full mb-3"
          />
          <CriticalButton onClick={handleEnrichment} disabled={loading || !geneInput.trim()}>
            {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Dna className="w-4 h-4" />}
            Analyze
          </CriticalButton>
        </motion.div>
      )}

      {error && <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-4 border border-error/20"><p className="text-sm text-error">{error}</p></motion.div>}

      {tab === 'reactome' && reactomeResults && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-3">
          <p className="text-xs text-text-muted mb-2">{reactomeResults.length} pathway{reactomeResults.length !== 1 ? 's' : ''} found</p>
          {reactomeResults.length === 0 ? (
            <div className="glass-card p-6 text-center"><p className="text-sm text-text-secondary">No pathways found</p></div>
          ) : (
            reactomeResults.map((p) => (
              <div key={p.pathway_id} className="data-card overflow-hidden">
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
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-3">
          <p className="text-xs text-text-muted mb-2">{keggResults.length} pathway{keggResults.length !== 1 ? 's' : ''} found</p>
          {keggResults.length === 0 ? (
            <div className="glass-card p-6 text-center"><p className="text-sm text-text-secondary">No pathways found</p></div>
          ) : (
            keggResults.map((p) => (
              <div key={p.pathway_id} className="data-card overflow-hidden">
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
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-3">
          <p className="text-xs text-text-muted mb-2">{enrichmentResult.pathways.length} enriched pathway{enrichmentResult.pathways.length !== 1 ? 's' : ''} found</p>
          {enrichmentResult.pathways.length === 0 ? (
            <div className="glass-card p-6 text-center"><p className="text-sm text-text-secondary">No significantly enriched pathways found</p></div>
          ) : (
            enrichmentResult.pathways.map((pw) => (
              <div key={pw.stId} className="data-card overflow-hidden">
                <button
                  onClick={() => setExpandedDiagram(expandedDiagram === pw.stId ? null : pw.stId)}
                  className="w-full p-4 flex items-center justify-between hover:bg-surface-2 transition cursor-pointer text-left"
                >
                  <div>
                    <p className="text-sm font-medium text-text-primary">{pw.name}</p>
                    <p className="text-xs text-text-muted mt-0.5">
                      {pw.stId} · {pw.species} · {pw.entitiesFound}/{pw.entitiesTotal} genes · gene ratio {pw.geneRatio ? pw.geneRatio.toFixed(3) : '—'} · p {pw.entitiesPValue ? pw.entitiesPValue.toExponential(2) : '—'} · FDR {pw.entitiesFDR.toExponential(2)}
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
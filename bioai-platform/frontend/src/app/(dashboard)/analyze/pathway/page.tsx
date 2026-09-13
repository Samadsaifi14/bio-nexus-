'use client';

import { useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CircleNotch as LoaderCircle, ArrowSquareOut as ExternalLink, GitBranch, CaretDown as ChevronDown, CaretRight as ChevronRight, Dna, DownloadSimple as Download } from '@phosphor-icons/react';
import { fadeUp } from '@/lib/animations';
import { searchPathways, searchKEGGPathways, runEnrichment } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import type { PathwayResult, KEGGPathwayResult, EnrichmentResult } from '@/lib/api';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import PathwayDiagram from '@/components/results/PathwayDiagram';
import { PathwayEnrichmentPlots } from '@/components/results/PathwayEnrichmentPlots';
import { ReferenceComparisonWorkbench } from '@/components/results/ReferenceComparisonWorkbench';
import { BackButton, PageHeader, ClaySegmented, CriticalButton, FlatInput, FlatTextarea } from '@/components/ui';
import { AIResultSummary } from '@/components/results/AIResultSummary';
import { consumeParam } from '@/lib/cross-link';
import { downloadJson, downloadTsv } from '@/lib/export-utils';

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
    const stored = consumeParam('pathway_query');
    if (stored) setQuery(stored);
  }, []);

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;
    const inputSummary = `tab:${tab},query:${query.trim()}`;
    audit.emitStarted('pathway_search', 'Pathway', inputSummary);
    setLoading(true); setError(null); setExpandedDiagram(null);
    try {
      if (tab === 'reactome') {
        setKeggResults(null); setEnrichmentResult(null);
        const res = await searchPathways(query.trim());
        setReactomeResults(res.results);
      } else if (tab === 'kegg') {
        setReactomeResults(null); setEnrichmentResult(null);
        const res = await searchKEGGPathways(query.trim());
        setKeggResults(res.results);
      }
      audit.emitSuccess('pathway_search', 'Pathway', inputSummary, `tab:${tab}`);
    } catch (err: unknown) {
      const errMsg = extractErrorMessage(err, 'Search failed');
      audit.emitFailed('pathway_search', 'Pathway', inputSummary, errMsg); setError(errMsg);
    } finally { setLoading(false); }
  }, [query, tab, audit]);

  const handleEnrichment = useCallback(async () => {
    const ids = geneInput.trim().split(/[\n,]+/).map(s => s.trim()).filter(Boolean);
    if (ids.length === 0) return;
    const inputSummary = `genes:${ids.length}`;
    audit.emitStarted('pathway_enrichment', 'Pathway', inputSummary);
    setLoading(true); setError(null);
    try {
      const res = await runEnrichment(ids);
      setEnrichmentResult(res);
      audit.emitSuccess('pathway_enrichment', 'Pathway', inputSummary, `hits:${res?.pathways?.length ?? 0}`);
    } catch (err: unknown) {
      const errMsg = extractErrorMessage(err, 'Enrichment analysis failed');
      audit.emitFailed('pathway_enrichment', 'Pathway', inputSummary, errMsg); setError(errMsg);
    } finally { setLoading(false); }
  }, [geneInput, audit]);

  return (
    <div className="max-w-5xl">
      <BackButton />
      <PageHeader title="Pathway Analysis" subtitle="Map genes or proteins to Reactome/KEGG and inspect enrichment with explicit p-value, FDR, gene-ratio plots and independent reference comparison." />

      <ClaySegmented className="mb-6" options={[{ value: 'reactome', label: 'Reactome' }, { value: 'kegg', label: 'KEGG' }, { value: 'enrichment', label: 'Enrichment' }]} value={tab} onChange={(t) => { setTab(t); setError(null); }} />

      {tab !== 'enrichment' && <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-6">
        <div className="flex gap-3"><FlatInput type="text" value={query} onChange={(e) => { setQuery(e.target.value); setReactomeResults(null); setKeggResults(null); setError(null); }} onKeyDown={(e) => e.key === 'Enter' && handleSearch()} placeholder={tab === 'reactome' ? 'e.g. TP53, BRCA1, EGFR' : 'e.g. TP53, BRCA1'} className="flex-1" /><CriticalButton onClick={handleSearch} disabled={loading || !query.trim()}>{loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <GitBranch className="w-4 h-4" />} Search</CriticalButton></div>
        <div className="flex gap-3 mt-3">{['TP53','BRCA1','EGFR'].map(g => <button key={g} onClick={() => { setQuery(g); setError(null); }} className="text-xs text-accent-cyan hover:text-accent-cyan/80 underline">{g}</button>)}</div>
      </motion.div>}

      {tab === 'enrichment' && <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-6">
        <p className="text-sm text-text-secondary mb-3">Paste identifiers (one per line or comma-separated). BioNexus preserves the returned stable pathway IDs, p-values, FDR and gene ratios as plot source data.</p>
        <FlatTextarea value={geneInput} onChange={(e) => { setGeneInput(e.target.value); setEnrichmentResult(null); setError(null); }} placeholder={`TP53\nBRCA1\nEGFR\nMYC\nPTEN`} rows={6} className="w-full mb-3" />
        <CriticalButton onClick={handleEnrichment} disabled={loading || !geneInput.trim()}>{loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Dna className="w-4 h-4" />} Analyze</CriticalButton>
      </motion.div>}

      {error && <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-4 border border-error/20"><p className="text-sm text-error">{error}</p></motion.div>}

      {tab === 'reactome' && reactomeResults && <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-3">
        <AIResultSummary toolName="pathway" result={{ query, results: reactomeResults } as unknown as Record<string, unknown>} />
        <div className="flex items-center justify-between gap-2"><p className="text-xs text-text-muted">{reactomeResults.length} pathway{reactomeResults.length !== 1 ? 's' : ''} found</p><button onClick={() => downloadJson({ query, source: 'Reactome', results: reactomeResults }, 'reactome-pathways.json')} className="btn-ghost flex items-center gap-1 px-2 py-1 text-xs"><Download className="h-3.5 w-3.5" /> JSON</button></div>
        {reactomeResults.length === 0 ? <div className="glass-card p-6 text-center"><p className="text-sm text-text-secondary">No pathways found</p></div> : reactomeResults.map((p) => <div key={p.pathway_id} className="data-card overflow-hidden"><button onClick={() => setExpandedDiagram(expandedDiagram === p.pathway_id ? null : p.pathway_id)} className="w-full p-4 flex items-center justify-between hover:bg-surface-2 transition cursor-pointer text-left"><div><p className="text-sm font-medium text-text-primary">{p.name}</p><p className="text-xs text-text-muted mt-0.5">{p.pathway_id} · {p.species}</p></div><div className="flex items-center gap-2"><a href={p.url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} className="text-text-muted hover:text-accent-cyan transition"><ExternalLink className="w-4 h-4" /></a>{expandedDiagram === p.pathway_id ? <ChevronDown className="w-4 h-4 text-text-muted" /> : <ChevronRight className="w-4 h-4 text-text-muted" />}</div></button><AnimatePresence>{expandedDiagram === p.pathway_id && <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden border-t border-glass-border"><div className="p-4"><PathwayDiagram stId={p.pathway_id} geneName={query} /></div></motion.div>}</AnimatePresence></div>)}
      </motion.div>}

      {tab === 'kegg' && keggResults && <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-3">
        <AIResultSummary toolName="pathway" result={{ query, results: keggResults } as unknown as Record<string, unknown>} />
        <div className="flex items-center justify-between"><p className="text-xs text-text-muted">{keggResults.length} pathway{keggResults.length !== 1 ? 's' : ''} found</p><button onClick={() => downloadJson({ query, source: 'KEGG', results: keggResults }, 'kegg-pathways.json')} className="btn-ghost flex items-center gap-1 px-2 py-1 text-xs"><Download className="h-3.5 w-3.5" /> JSON</button></div>
        {keggResults.length === 0 ? <div className="glass-card p-6 text-center"><p className="text-sm text-text-secondary">No pathways found</p></div> : keggResults.map((p) => <div key={p.pathway_id} className="data-card overflow-hidden"><button onClick={() => setExpandedKEGG(expandedKEGG === p.pathway_id ? null : p.pathway_id)} className="w-full p-4 flex items-center justify-between hover:bg-surface-2 transition cursor-pointer text-left"><div className="flex items-center gap-3"><img src={p.image_url} alt="" className="w-16 h-12 object-contain rounded border border-glass-border shrink-0" /><div><p className="text-sm font-medium text-text-primary">{p.name}</p><p className="text-xs text-text-muted mt-0.5">{p.pathway_id} · {p.organism}</p></div></div><div className="flex items-center gap-2"><a href={p.url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} className="text-text-muted hover:text-accent-cyan transition"><ExternalLink className="w-4 h-4" /></a>{expandedKEGG === p.pathway_id ? <ChevronDown className="w-4 h-4 text-text-muted" /> : <ChevronRight className="w-4 h-4 text-text-muted" />}</div></button><AnimatePresence>{expandedKEGG === p.pathway_id && <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden border-t border-glass-border"><div className="p-4 flex justify-center"><img src={p.image_url} alt={p.name} className="max-w-full rounded border border-glass-border" /></div></motion.div>}</AnimatePresence></div>)}
      </motion.div>}

      {tab === 'enrichment' && enrichmentResult && <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-4">
        <AIResultSummary toolName="pathway_enrichment" result={enrichmentResult as unknown as Record<string, unknown>} />
        <div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs text-text-muted">{enrichmentResult.pathways.length} enriched pathway{enrichmentResult.pathways.length !== 1 ? 's' : ''} found</p><div className="flex gap-2"><button onClick={() => downloadJson(enrichmentResult, 'reactome-enrichment.json')} className="btn-ghost flex items-center gap-1 px-2 py-1 text-xs"><Download className="h-3.5 w-3.5" /> JSON</button><button onClick={() => downloadTsv(['stable_id','name','species','entities_found','entities_total','gene_ratio','p_value','fdr'], enrichmentResult.pathways.map(p => [p.stId,p.name,p.species,String(p.entitiesFound),String(p.entitiesTotal),String(p.geneRatio ?? ''),String(p.entitiesPValue ?? ''),String(p.entitiesFDR ?? '')]), 'reactome-enrichment.tsv')} className="btn-ghost flex items-center gap-1 px-2 py-1 text-xs"><Download className="h-3.5 w-3.5" /> TSV</button></div></div>
        <PathwayEnrichmentPlots result={enrichmentResult} />
        {enrichmentResult.pathways.length === 0 ? <div className="glass-card p-6 text-center"><p className="text-sm text-text-secondary">No significantly enriched pathways found</p></div> : enrichmentResult.pathways.map((pw) => <div key={pw.stId} className="data-card overflow-hidden"><button onClick={() => setExpandedDiagram(expandedDiagram === pw.stId ? null : pw.stId)} className="w-full p-4 flex items-center justify-between hover:bg-surface-2 transition cursor-pointer text-left"><div><p className="text-sm font-medium text-text-primary">{pw.name}</p><p className="text-xs text-text-muted mt-0.5">{pw.stId} · {pw.species} · {pw.entitiesFound}/{pw.entitiesTotal} genes · gene ratio {pw.geneRatio ? pw.geneRatio.toFixed(3) : '—'} · p {pw.entitiesPValue ? pw.entitiesPValue.toExponential(2) : '—'} · FDR {pw.entitiesFDR.toExponential(2)}</p></div>{expandedDiagram === pw.stId ? <ChevronDown className="w-4 h-4 text-text-muted" /> : <ChevronRight className="w-4 h-4 text-text-muted" />}</button><AnimatePresence>{expandedDiagram === pw.stId && <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden border-t border-glass-border"><div className="p-4"><PathwayDiagram stId={pw.stId} /></div></motion.div>}</AnimatePresence></div>)}
        <ReferenceComparisonWorkbench analysisType="pathway" bionexusResult={enrichmentResult as unknown as Record<string, unknown>} title="Compare this enrichment result with the Reactome Analysis Service" defaultTopN={Math.min(25, enrichmentResult.pathways.length || 10)} />
      </motion.div>}
    </div>
  );
}

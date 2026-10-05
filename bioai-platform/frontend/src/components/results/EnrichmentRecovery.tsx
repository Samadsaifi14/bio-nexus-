'use client';

import { useState } from 'react';
import { rerunRnaSeqEnrichment, type RnaSeqExpressionResult } from '@/lib/rnaseqExpressionApi';

export function EnrichmentRecovery({ result, onResult }: { result: RnaSeqExpressionResult; onResult: (value: RnaSeqExpressionResult) => void }) {
  const e = result.summary.enrichment;
  const [organism, setOrganism] = useState(e?.organism === 'mouse' ? 'mouse' : e?.organism === 'human' ? 'human' : 'auto');
  const [customOrganism, setCustomOrganism] = useState('');
  const [database, setDatabase] = useState('GO');
  const [method, setMethod] = useState('ora');
  const [idType, setIdType] = useState('auto');
  const [aliases, setAliases] = useState(true);
  const [databaseLabel, setDatabaseLabel] = useState('');
  const [namespace, setNamespace] = useState('');
  const [gmt, setGmt] = useState<File | null>(null);
  const [mapping, setMapping] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const custom = database === 'CUSTOM';
  const field = 'mt-1 w-full rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-xs text-text-primary';
  const run = async () => {
    setBusy(true); setError('');
    try {
      const next = await rerunRnaSeqEnrichment(result.run_id, { organism: custom ? customOrganism : organism,
        database, method, idType, aliases, databaseLabel, namespace, gmt: custom ? gmt : null, mapping: custom ? mapping : null });
      onResult(next);
    } catch (caught: unknown) {
      const detail = (caught as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : caught instanceof Error ? caught.message : 'Enrichment could not complete.');
    } finally { setBusy(false); }
  };
  return <details className="rounded-lg border border-glass-border p-4" open={!!e && ['NEEDS_ORGANISM', 'NO_MAPPED_BACKGROUND', 'UNAVAILABLE', 'ID_SPECIES_MISMATCH', 'ERROR'].includes(e.status)}>
    <summary className="cursor-pointer text-sm font-medium text-text-primary">Recovery and alternative analyses</summary>
    <p className="mt-3 text-xs leading-5 text-text-secondary">Rerun enrichment from this saved DESeq2 result. Each choice creates a new record with the original results linked, the selected method and annotation files retained. No gene lists are sent to another service.</p>
    <div className="mt-4 grid gap-4 sm:grid-cols-2">
      <label className="text-xs text-text-muted">Gene-set database<select className={field} value={database} onChange={e => setDatabase(e.target.value)}>
        <option value="GO">GO · all ontologies</option><option value="GO:BP">GO · biological process</option>
        <option value="GO:MF">GO · molecular function</option><option value="GO:CC">GO · cellular component</option>
        <option value="CUSTOM">Custom GMT · Reactome or other sets</option></select></label>
      <label className="text-xs text-text-muted">Statistical method<select className={field} value={method} onChange={e => setMethod(e.target.value)}>
        <option value="ora">Over-representation · thresholded DEGs</option><option value="ranked_wilcoxon">Ranked Wilcoxon · all eligible genes</option></select></label>
      {!custom && <><label className="text-xs text-text-muted">Documented organism<select className={field} value={organism} onChange={e => setOrganism(e.target.value)}>
        <option value="auto">Infer from species-specific Ensembl IDs</option><option value="human">Human</option><option value="mouse">Mouse</option></select></label>
      <label className="text-xs text-text-muted">Gene identifier type<select className={field} value={idType} onChange={e => setIdType(e.target.value)}>
        <option value="auto">Detect each ID · mixed types allowed</option><option value="SYMBOL">Gene symbol</option><option value="ENSEMBL">Ensembl gene</option>
        <option value="ENSEMBLTRANS">Ensembl transcript</option><option value="ENTREZID">Entrez gene ID</option></select></label></>}
      {custom && <><label className="text-xs text-text-muted">Organism matching the GMT<input className={field} value={customOrganism} onChange={e => setCustomOrganism(e.target.value)} placeholder="e.g. Homo sapiens" maxLength={200} /></label>
        <label className="text-xs text-text-muted">Database source and release<input className={field} value={databaseLabel} onChange={e => setDatabaseLabel(e.target.value)} placeholder="Database name, release, source URL" maxLength={200} /></label>
        <label className="text-xs text-text-muted">GMT identifier namespace<input className={field} value={namespace} onChange={e => setNamespace(e.target.value)} placeholder="e.g. Entrez gene IDs or locus tags" maxLength={200} /></label>
        <label className="text-xs text-text-muted">Gene sets · GMT, up to 10 MB<input className={field} type="file" accept=".gmt,.txt" onChange={e => setGmt(e.target.files?.[0] ?? null)} /></label>
        <label className="text-xs text-text-muted">Optional ID mapping · TSV, up to 10 MB<input className={field} type="file" accept=".tsv,.txt" onChange={e => setMapping(e.target.files?.[0] ?? null)} /></label></>}
    </div>
    {!custom && <label className="mt-4 flex items-center gap-2 text-xs text-text-secondary"><input type="checkbox" checked={aliases} onChange={e => setAliases(e.target.checked)} />Recover unambiguous aliases after official symbol matching</label>}
    <p className="mt-3 text-xs leading-5 text-text-muted">{custom ? 'Use species-matched GMT rows: term ID, description, then gene IDs, separated by tabs. IDs match exactly and remain case-sensitive. Optional mapping TSV headers: source_id and target_id. Ambiguous mappings are excluded. Organism and database release are your declarations.' : 'Versioned Ensembl IDs are normalized. Symbols are case-sensitive; ambiguous aliases remain excluded. Unknown sample identities or treatment groups must be reviewed in sample metadata.'}</p>
    {method === 'ranked_wilcoxon' && <p className="mt-3 text-xs leading-5 text-text-secondary">This exploratory competitive test compares signed Wald statistics inside each set with the remaining annotated genes. It uses BH correction across both directions; duplicate target IDs use their median statistic. Gene correlation is not modeled. It is not GSEA.</p>}
    <p className="mt-3 text-xs leading-5 text-text-muted">No significant terms is a valid outcome. Record alternative analyses as sensitivity checks; do not choose a database or method only because it produces significance.</p>
    {error && <p role="alert" className="mt-3 text-xs text-red-400">{error}</p>}
    <button type="button" disabled={busy || (custom && (!gmt || !customOrganism.trim() || !databaseLabel.trim() || !namespace.trim()))} onClick={run}
      className="mt-4 rounded-lg border border-glass-border bg-surface-1 px-4 py-2 text-xs font-medium text-text-primary disabled:opacity-50">{busy ? 'Running enrichment…' : 'Run enrichment with these options'}</button>
  </details>;
}

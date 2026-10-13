'use client';
import { useState } from 'react';
import { longApi } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import { downloadJson, downloadTsv } from '@/lib/export-utils';
import { CriticalButton, FlatInput, FlatTextarea } from '@/components/ui';

type Row = { term_id: string; overlap: string[]; overlap_size: number; term_size: number; p_value: number; adjusted_p_value: number; fold_enrichment: number };
type Result = { results: Row[]; tested_terms: number; excluded_empty_terms: number; annotation_note: string; source_provenance: Record<string,string>; background_sha256: string; annotation_sha256: string };
const split = (value: string) => value.split(/[\n,\s]+/).map(x => x.trim()).filter(Boolean);

export default function CustomGeneSetEnrichment() {
  const [query, setQuery] = useState('');
  const [background, setBackground] = useState('');
  const [annotation, setAnnotation] = useState('');
  const [meta, setMeta] = useState({ source: '', release: '', organism: '', identifier_namespace: '' });
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const invalidate = () => { setResult(null); setError(''); };
  async function analyze() {
    setLoading(true); setError(''); setResult(null);
    try {
      const gene_sets: Record<string,string[]> = Object.create(null);
      for (const [index, line] of annotation.trim().split('\n').entries()) {
        const fields = line.replace(/\r$/, '').split('\t');
        if (fields.length < 3 || !fields[0].trim()) throw new Error(`GMT line ${index+1}: require term ID, description and at least one identifier separated by tabs.`);
        const term = fields[0].trim();
        if (Object.prototype.hasOwnProperty.call(gene_sets, term)) throw new Error(`Duplicate GMT term: ${term}`);
        gene_sets[term] = fields.slice(2).map(x=>x.trim()).filter(Boolean);
      }
      const response = await longApi.post<Result>('/api/pathways/enrichment/gene-sets', { identifiers: split(query), background: split(background), gene_sets, ...meta });
      setResult(response.data);
    } catch (err) { setError(extractErrorMessage(err, 'Gene-set enrichment failed')); }
    finally { setLoading(false); }
  }
  return <div className="data-card p-5 mb-6 space-y-4">
    <h2 className="text-base font-medium">Custom annotation enrichment</h2>
    <p className="text-sm text-text-secondary">Test selected genes against all genes eligible for selection in your experiment. Upload a GMT annotation from a declared database release. Identifier matching is exact; use the same species and identifier namespace throughout.</p>
    <label className="block text-sm">Selected identifiers<FlatTextarea value={query} onChange={e=>{setQuery(e.target.value);invalidate();}} rows={3} className="w-full mt-1" /></label>
    <label className="block text-sm">Experimental background<FlatTextarea value={background} onChange={e=>{setBackground(e.target.value);invalidate();}} rows={4} className="w-full mt-1" /></label>
    <p className="text-xs text-text-muted">For differential expression, use all genes that passed the statistical testing filter, including nonsignificant genes. Each selected gene must belong to this background.</p>
    <label className="block text-sm">GMT file<input type="file" accept=".gmt,.txt" className="block mt-1" onChange={async e=>{
      invalidate(); const file=e.target.files?.[0]; if (!file) return;
      if(file.size>20_000_000){setError('GMT upload exceeds 20 MB');return;}
      try {setAnnotation(await file.text());} catch {setError('Could not read annotation file');}
    }} /></label>
    <label className="block text-sm">GMT annotation (term ID, description, identifiers; tab-separated)<FlatTextarea value={annotation} onChange={e=>{setAnnotation(e.target.value);invalidate();}} rows={4} className="w-full mt-1" placeholder={'GO:0000001\tdescription\tGENE1\tGENE2'} /></label>
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">{(Object.keys(meta) as Array<keyof typeof meta>).map(key=><label key={key} className="text-sm">{{source:'Database source',release:'Database release',organism:'Organism',identifier_namespace:'Identifier namespace'}[key]}<FlatInput className="w-full mt-1" value={meta[key]} onChange={e=>{setMeta({...meta,[key]:e.target.value});invalidate();}} /></label>)}</div>
    <CriticalButton onClick={analyze} disabled={loading || !query.trim() || !background.trim() || !annotation.trim() || Object.values(meta).some(v=>!v.trim())}>{loading?'Analyzing…':'Run exact-background enrichment'}</CriticalButton>
    {error && <p role="alert" className="text-sm text-error">{error}</p>}
    {result && <div className="space-y-3">
      <p className="text-sm">Hypergeometric over-representation · Benjamini–Hochberg correction · {result.tested_terms} tested terms · {result.excluded_empty_terms} terms outside background excluded.</p>
      <p className="text-xs text-text-muted">{result.annotation_note}</p>
      <div className="flex gap-3"><button className="btn-ghost text-xs" onClick={()=>downloadJson(result,'custom-enrichment-evidence.json')}>Download evidence JSON</button><button className="btn-ghost text-xs" onClick={()=>downloadTsv(['Term','Overlap','Term size','p','BH adjusted p','Fold enrichment','Matched genes'],result.results.map(r=>[r.term_id,String(r.overlap_size),String(r.term_size),String(r.p_value),String(r.adjusted_p_value),String(r.fold_enrichment),r.overlap.join(',')]),'custom-enrichment-all.tsv')}>Download all terms</button></div>
      <p className="text-xs text-text-muted">First {Math.min(50,result.results.length)} of {result.results.length} tested terms shown. Downloads contain every term and input digests.</p>
      <div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr>{['Term','Overlap','p','BH adjusted p','Fold enrichment'].map(h=><th className="p-2 text-left" key={h}>{h}</th>)}</tr></thead><tbody>{result.results.slice(0,50).map(r=><tr key={r.term_id}><td className="p-2">{r.term_id}</td><td>{r.overlap_size}/{r.term_size}</td><td>{r.p_value.toExponential(3)}</td><td>{r.adjusted_p_value.toExponential(3)}</td><td>{r.fold_enrichment.toFixed(3)}</td></tr>)}</tbody></table></div>
    </div>}
  </div>;
}

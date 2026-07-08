'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Search, ArrowLeft, LoaderCircle, Globe, Dna, Beaker, ChevronRight, ExternalLink, BookOpen, Download } from 'lucide-react';
import { fadeUp } from '@/lib/animations';
import { searchUniprot, getUniprotDetail, fetchUniprotCds } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import type { UniprotSummary } from '@/types/pipeline';
import { downloadJson, downloadTsv } from '@/lib/export-utils';

type SearchResult = {
  accession: string;
  name: string;
  gene_names: string[];
  organism: string;
  length: number;
};

export default function UniprotLookupPage() {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [detail, setDetail] = useState<UniprotSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cdsResult, setCdsResult] = useState<{ accession: string; sequence: string; length: number } | null>(null);
  const [cdsLoading, setCdsLoading] = useState<string | null>(null);
  const [cdsError, setCdsError] = useState<string | null>(null);
  const audit = useAuditTrail();

  const handleSearch = async () => {
    if (!query.trim()) return;
    const inputSummary = `query:${query.trim()}`;
    audit.emitStarted('uniprot_search', 'UniProt', inputSummary);
    setLoading(true);
    setError(null);
    setResults(null);
    setDetail(null);
    try {
      const res = await searchUniprot(query.trim());
      setResults(res.results);
      audit.emitSuccess('uniprot_search', 'UniProt', inputSummary, `count:${res.results?.length ?? 0}`);
    } catch (err: unknown) {
      const errMsg = extractErrorMessage(err, 'Search failed');
      audit.emitFailed('uniprot_search', 'UniProt', inputSummary, errMsg);
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = async (accession: string) => {
    const inputSummary = `accession:${accession}`;
    audit.emitStarted('uniprot_fetch', 'UniProt', inputSummary);
    setDetailLoading(true);
    setError(null);
    setDetail(null);
    try {
      const res = await getUniprotDetail(accession);
      setDetail(res);
      audit.emitSuccess('uniprot_fetch', 'UniProt', inputSummary, `name:${res?.full_name ?? ''}`);
    } catch (err: unknown) {
      const errMsg = extractErrorMessage(err, 'Failed to fetch details');
      audit.emitFailed('uniprot_fetch', 'UniProt', inputSummary, errMsg);
      setError(errMsg);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleSendToBlast = (accession: string, seq: string) => {
    sessionStorage.setItem('blast_sequence', `>${accession}\n${seq}`);
    router.push('/analyze/blast');
  };

  const handleFetchCds = async (emblAcc: string) => {
    if (!detail) return;
    setCdsLoading(emblAcc);
    setCdsResult(null);
    setCdsError(null);
    try {
      const res = await fetchUniprotCds(detail.accession, emblAcc);
      setCdsResult({ accession: emblAcc, sequence: res.sequence, length: res.length });
    } catch {
      setCdsError('Failed to fetch CDS sequence');
    } finally {
      setCdsLoading(null);
    }
  };

  return (
    <div className="max-w-3xl">
      <button
        onClick={() => router.push('/analyze')}
        className="flex items-center gap-1 text-sm text-text-muted hover:text-text-primary mb-6 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Choose a different operation
      </button>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary mb-1">UniProt Lookup</h1>
        <p className="text-sm text-text-secondary">
          Search by gene name, protein name, or keyword to retrieve comprehensive annotations.
        </p>
      </motion.div>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-5 mb-6">
        <div className="flex gap-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="e.g. p53, BRCA1, TP53 human, kinase"
            className="flex-1 px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm"
          />
          <button
            onClick={handleSearch}
            disabled={loading || !query.trim()}
            className="btn-primary px-6 py-3 flex items-center gap-2 disabled:opacity-50"
          >
            {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            Search
          </button>
        </div>
      </motion.div>

      {error && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-4 border border-error/20">
          <p className="text-sm text-error">{error}</p>
        </motion.div>
      )}

      {results && !detail && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-3">
          <p className="text-xs text-text-muted mb-2">{results.length} result{results.length !== 1 ? 's' : ''}</p>
          {results.length === 0 ? (
            <div className="glass-card p-6 text-center">
              <p className="text-sm text-text-secondary">No results found</p>
            </div>
          ) : (
            results.map((r) => (
              <button
                key={r.accession}
                onClick={() => handleSelect(r.accession)}
                className="glass-card p-4 w-full text-left hover:bg-surface-2 transition cursor-pointer"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <code className="text-sm font-mono text-accent-cyan">{r.accession}</code>
                      <span className="badge bg-accent-cyan/10 text-accent-cyan text-[10px]">{r.length} aa</span>
                    </div>
                    <p className="text-sm text-text-primary line-clamp-1">{r.name}</p>
                    {r.gene_names.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-1.5">
                        {r.gene_names.map((g) => (
                          <span key={g} className="text-[10px] font-mono text-accent-purple bg-accent-purple/10 px-1.5 py-0.5 rounded">{g}</span>
                        ))}
                      </div>
                    )}
                    <p className="text-xs text-text-muted mt-1">{r.organism}</p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-text-muted shrink-0 mt-1" />
                </div>
              </button>
            ))
          )}
        </motion.div>
      )}

      {detailLoading && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-8 text-center">
          <LoaderCircle className="w-6 h-6 animate-spin text-accent-cyan mx-auto mb-3" />
          <p className="text-sm text-text-secondary">Loading UniProt entry...</p>
        </motion.div>
      )}

      {detail && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-4">
          <div className="glass-card divide-y divide-glass-border">
            <div className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <code className="text-lg font-mono font-bold text-accent-cyan">{detail.accession}</code>
                    <Globe className="w-4 h-4 text-accent-cyan/60" />
                  </div>
                  <h2 className="text-lg font-semibold text-text-primary">{detail.full_name}</h2>
                  <p className="text-sm text-text-muted mt-1">{detail.organism}</p>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-text-primary">{detail.sequence_length}</div>
                  <div className="text-xs text-text-muted">residues</div>
                </div>
              </div>

              {detail.gene_names.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs font-medium text-text-muted uppercase tracking-wider mb-1.5">Gene Names</p>
                  <div className="flex flex-wrap gap-2">
                    {detail.gene_names.map((g) => (
                      <span key={g} className="badge bg-accent-purple/10 text-accent-purple">{g}</span>
                    ))}
                  </div>
                </div>
              )}

              {detail.functions.length > 0 && (
                <div className="mb-4">
                  <p className="text-xs font-medium text-text-muted uppercase tracking-wider mb-1.5">Functions</p>
                  {detail.functions.map((f, i) => (
                    <p key={i} className="text-sm text-text-secondary mb-1 leading-relaxed">{f}</p>
                  ))}
                </div>
              )}
            </div>

            {detail.keywords.length > 0 && (
              <div className="px-6 py-4">
                <p className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Keywords</p>
                <div className="flex flex-wrap gap-1.5">
                  {detail.keywords.map((kw) => (
                    <span key={kw} className="text-xs bg-surface-2 text-text-secondary px-2 py-0.5 rounded-full">{kw}</span>
                  ))}
                </div>
              </div>
            )}

            {detail.subcellular_locations.length > 0 && (
              <div className="px-6 py-4">
                <p className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Subcellular Locations</p>
                {detail.subcellular_locations.map((loc, i) => (
                  <p key={i} className="text-sm text-text-secondary">{loc}</p>
                ))}
              </div>
            )}

            {detail.go_terms.length > 0 && (
              <div className="px-6 py-4">
                <p className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">GO Terms</p>
                <div className="flex flex-wrap gap-1.5">
                  {detail.go_terms.map((go) => (
                    <span key={go} className="text-xs font-mono text-accent-amber bg-accent-amber/10 px-2 py-0.5 rounded-full">{go}</span>
                  ))}
                </div>
              </div>
            )}

            {detail.features.length > 0 && (
              <div className="px-6 py-4">
                <p className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Features</p>
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {detail.features.slice(0, 20).map((f, i) => (
                    <div key={i} className="flex items-center gap-3 text-sm py-0.5">
                      <span className="badge bg-surface-2 text-text-secondary text-[10px]">{f.type}</span>
                      <span className="text-text-secondary truncate">{f.description}</span>
                      {f.begin && f.end && (
                        <span className="text-xs text-text-muted ml-auto shrink-0">{f.begin}–{f.end}</span>
                      )}
                    </div>
                  ))}
                  {detail.features.length > 20 && (
                    <p className="text-xs text-text-muted mt-1">+{detail.features.length - 20} more features</p>
                  )}
                </div>
              </div>
            )}

            {detail.pdb_ids.length > 0 && (
              <div className="px-6 py-4">
                <p className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">PDB Structures</p>
                <div className="flex flex-wrap gap-2">
                  {detail.pdb_ids.map((pdb) => (
                    <a
                      key={pdb}
                      href={`https://www.rcsb.org/structure/${pdb}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="badge bg-accent-cyan/10 text-accent-cyan hover:bg-accent-cyan/20 transition flex items-center gap-1"
                    >
                      {pdb}
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  ))}
                </div>
              </div>
            )}

            {detail.cds_accessions && detail.cds_accessions.length > 0 && (
              <div className="px-6 py-4">
                <p className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Coding Sequence (CDS) Accessions</p>
                <div className="space-y-2">
                  {detail.cds_accessions.map((cds) => (
                    <div key={cds.accession} className="flex items-center justify-between bg-surface-1 rounded-xl p-3 border border-glass-border">
                      <div className="flex items-center gap-2">
                        <Dna className="w-4 h-4 text-accent-cyan" />
                        <code className="text-sm font-mono text-accent-cyan">{cds.accession}</code>
                        <span className="text-xs text-text-muted">({cds.database})</span>
                      </div>
                      <button
                        onClick={() => handleFetchCds(cds.accession)}
                        disabled={cdsLoading === cds.accession}
                        className="btn-ghost text-xs px-2 py-1 flex items-center gap-1"
                      >
                        {cdsLoading === cds.accession ? (
                          <LoaderCircle className="w-3 h-3 animate-spin" />
                        ) : (
                          <Dna className="w-3 h-3" />
                        )}
                        {cdsLoading === cds.accession ? 'Fetching...' : 'Fetch CDS'}
                      </button>
                    </div>
                  ))}
                </div>
                {cdsError && (
                  <p className="mt-2 text-xs text-error">{cdsError}</p>
                )}
                {cdsResult && (
                  <div className="mt-3 bg-surface-1 rounded-xl p-4 border border-accent-cyan/20">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-xs font-medium text-accent-cyan">{cdsResult.accession} — {cdsResult.length} bp</p>
                      <button onClick={() => {
                        const a = document.createElement('a');
                        a.download = `${cdsResult.accession}.fasta`;
                        a.href = 'data:text/fasta;charset=utf-8,' + encodeURIComponent(`>${cdsResult.accession}\n${cdsResult.sequence}`);
                        a.click();
                      }} className="btn-ghost text-xs px-2 py-1 flex items-center gap-1">
                        <Download className="w-3 h-3" /> FASTA
                      </button>
                    </div>
                    <pre className="font-mono text-xs text-text-secondary break-all whitespace-pre-wrap max-h-24 overflow-auto">
                      {cdsResult.sequence}
                    </pre>
                  </div>
                )}
              </div>
            )}

            {detail.sequence && (
              <div className="px-6 py-4">
                <p className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Sequence</p>
                <pre className="font-mono text-xs text-text-secondary bg-surface-0 rounded-xl p-4 max-h-32 overflow-auto break-all whitespace-pre-wrap">
                  {detail.sequence}
                </pre>
              </div>
            )}

            <div className="px-6 py-4 flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <a
                  href={`https://www.uniprot.org/uniprotkb/${detail.accession}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-text-muted hover:text-accent-cyan transition flex items-center gap-1"
                >
                  <BookOpen className="w-3 h-3" />
                  View on UniProt
                  <ExternalLink className="w-3 h-3" />
                </a>
                <button onClick={() => downloadJson(detail, `uniprot-${detail.accession}.json`)}
                  className="btn-ghost text-xs px-2 py-1 flex items-center gap-1">
                  <Download className="w-3 h-3" /> JSON
                </button>
                <button onClick={() => {
                  const headers = ["Accession", "Gene", "Organism", "Length", "Function", "Keywords", "Subcellular Location"];
                  const rows = [[
                    detail.accession,
                    detail.gene_names.join("; "),
                    detail.organism,
                    String(detail.sequence_length),
                    detail.functions.join("; ").replace(/"/g, '""'),
                    detail.keywords.join("; "),
                    detail.subcellular_locations.join("; "),
                  ]];
                  downloadTsv(headers, rows, `uniprot-${detail.accession}.tsv`);
                }} className="btn-ghost text-xs px-2 py-1 flex items-center gap-1">
                  <Download className="w-3 h-3" /> CSV
                </button>
              </div>
              <button
                onClick={() => handleSendToBlast(detail.accession, detail.sequence)}
                className="btn-primary py-2 px-4 text-sm flex items-center gap-2"
              >
                <Beaker className="w-4 h-4" />
                Analyze with BLAST
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}

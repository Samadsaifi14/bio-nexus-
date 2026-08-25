'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { MagnifyingGlass as Search, Dna, CircleNotch as LoaderCircle, CheckCircle, WarningCircle as AlertCircle, BookOpen, ArrowRight, Flask as Beaker } from '@phosphor-icons/react';
import { fadeUp, stagger } from '@/lib/animations';
import { fetchSequence, validateSequence, searchSequences } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import type { SequenceResult, SequenceValidation, SequenceSearchResult } from '@/types/pipeline';
import { setPrefill } from '@/lib/cross-link';

type InputMode = 'accession' | 'sequence' | 'name';

export function SequenceRetrieval() {
  const router = useRouter();
  const [mode, setMode] = useState<InputMode>('accession');
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SequenceResult | null>(null);
  const [validation, setValidation] = useState<SequenceValidation | null>(null);
  const [searchResults, setSearchResults] = useState<SequenceSearchResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleSearch = async () => {
    if (!input.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setValidation(null);
    setSearchResults(null);

    try {
      if (mode === 'accession') {
        const res = await fetchSequence(input.trim());
        if (res.error) {
          setError(res.error);
        } else {
          setResult(res);
        }
      } else if (mode === 'sequence') {
        const res = await validateSequence(input);
        setValidation(res);
      } else if (mode === 'name') {
        const res = await searchSequences(input.trim());
        if (res.error) {
          setError(res.error);
        } else {
          setSearchResults(res.results);
        }
      }
    } catch (err: unknown) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleSelectAccession = async (accession: string) => {
    setInput(accession);
    setMode('accession');
    setLoading(true);
    setError(null);
    setSearchResults(null);
    try {
      const res = await fetchSequence(accession);
      if (res.error) setError(res.error);
      else setResult(res);
    } catch (err: unknown) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const copySequence = () => {
    if (result?.sequence) {
      navigator.clipboard.writeText(result.sequence);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const seqTypeColor = (type?: string) => {
    switch (type) {
      case 'protein': return 'text-molecule-protein bg-molecule-protein/10';
      case 'dna': return 'text-molecule-dna bg-molecule-dna/10';
      case 'rna': return 'text-molecule-rna bg-molecule-rna/10';
      default: return 'text-text-muted bg-surface-0';
    }
  };

  return (
    <motion.div initial={{ y: 24 }} animate="show" variants={stagger} className="space-y-6">
      <motion.div variants={fadeUp} className="bg-surface-0 rounded-2xl border border-glass-border p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-1">Sequence Retrieval</h2>
        <p className="text-sm text-text-muted mb-6">
          Look up a sequence by accession number, paste raw sequence data, or search by gene/protein name
        </p>

        <div className="flex gap-2 mb-6">
          {([
            { id: 'accession' as const, label: 'Accession' },
            { id: 'name' as const, label: 'Gene / Protein Name' },
            { id: 'sequence' as const, label: 'Raw Sequence' },
          ]).map((m) => (
            <button
              key={m.id}
              onClick={() => { setMode(m.id); setResult(null); setValidation(null); setSearchResults(null); setError(null); }}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition ${
                mode === m.id ? 'bg-accent-cyan text-void' : 'bg-surface-0 text-text-muted hover:bg-surface-2'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        <div className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => { setInput(e.target.value); setResult(null); setValidation(null); setSearchResults(null); setError(null); }}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder={
              mode === 'accession' ? 'e.g. NP_000509.1, P04637, 1TIM' :
              mode === 'name' ? 'e.g. p53, BRCA1, TP53 human' :
              'Paste FASTA or raw sequence...'
            }
            className="flex-1 px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan focus:ring-2 focus:ring-accent-cyan/20 outline-none transition text-sm"
          />
          <button
            onClick={handleSearch}
            disabled={loading || !input.trim()}
            className="px-6 py-3 bg-accent-cyan text-void font-medium rounded-xl hover:bg-accent-hover transition disabled:opacity-50 flex items-center gap-2"
          >
            {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>
      </motion.div>

      {error && (
        <motion.div variants={fadeUp} className="bg-error-dim border border-error/20 rounded-2xl p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-error mt-0.5 shrink-0" />
          <p className="text-sm text-error">{error}</p>
        </motion.div>
      )}

      {validation && mode === 'sequence' && (
        <motion.div variants={fadeUp} className="bg-surface-0 rounded-2xl border border-glass-border p-6">
          <div className="flex items-center gap-3 mb-4">
            {validation.valid ? (
              <CheckCircle className="w-5 h-5 text-accent-cyan" />
            ) : (
              <AlertCircle className="w-5 h-5 text-error" />
            )}
            <h3 className="font-semibold text-text-primary">
              {validation.valid ? 'Valid Sequence' : 'Invalid Sequence'}
            </h3>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="p-3 bg-surface-0 rounded-xl">
              <div className="text-xs text-text-muted mb-1">Type</div>
              <div className="text-sm font-medium text-text-primary">
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${seqTypeColor(validation.sequence_type)}`}>
                  {validation.sequence_type}
                </span>
              </div>
            </div>
            <div className="p-3 bg-surface-0 rounded-xl">
              <div className="text-xs text-text-muted mb-1">Length</div>
              <div className="text-sm font-medium text-text-primary">{validation.length.toLocaleString()} residues</div>
            </div>
            <div className="p-3 bg-surface-0 rounded-xl">
              <div className="text-xs text-text-muted mb-1">Format</div>
              <div className="text-sm font-medium text-text-primary">{validation.format}</div>
            </div>
          </div>
          {validation.issues.length > 0 && (
            <div className="mt-4 p-3 bg-error-dim rounded-xl">
              <p className="text-xs text-error font-medium mb-1">Issues</p>
              {validation.issues.map((issue, i) => (
                <p key={i} className="text-sm text-error">{issue}</p>
              ))}
            </div>
          )}
        </motion.div>
      )}

      {searchResults && mode === 'name' && (
        <motion.div variants={fadeUp} className="bg-surface-0 rounded-2xl border border-glass-border p-6">
          <h3 className="font-semibold text-text-primary mb-4">Search Results ({searchResults.length})</h3>
          {searchResults.length === 0 ? (
            <p className="text-sm text-text-muted">No results found</p>
          ) : (
            <motion.div animate="show" variants={stagger} className="space-y-2">
              {searchResults.map((r, i) => (
                <motion.div key={i} variants={fadeUp}>
                  <button
                    onClick={() => handleSelectAccession(r.accession)}
                    className="w-full text-left p-4 rounded-xl border border-glass-border hover:border-accent-cyan/30 hover:bg-accent-cyan/10 transition"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <code className="text-sm font-mono text-accent-cyan">{r.accession}</code>
                          <ArrowRight className="w-3 h-3 text-text-muted" />
                        </div>
                        <p className="text-sm text-text-secondary mt-1 line-clamp-1">{r.title}</p>
                      </div>
                      <div className="text-right text-xs text-text-muted">
                        <div>{r.organism}</div>
                        <div>{r.length} aa</div>
                      </div>
                    </div>
                  </button>
                </motion.div>
              ))}
            </motion.div>
          )}
        </motion.div>
      )}

      {result && mode === 'accession' && (
        <motion.div variants={fadeUp} className="bg-surface-0 rounded-2xl border border-glass-border divide-y divide-glass-border">
          <div className="p-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <code className="text-lg font-mono font-bold text-accent-cyan">{result.accession}</code>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${seqTypeColor(result.sequence_type)}`}>
                    {result.sequence_type}
                  </span>
                  <span className="text-xs bg-surface-0 text-text-muted px-2 py-0.5 rounded-full">{result.db_source}</span>
                </div>
                <p className="text-sm text-text-secondary">{result.description}</p>
                {result.organism && (
                  <p className="text-xs text-text-muted mt-1">{result.organism}</p>
                )}
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold text-text-primary">{result.length.toLocaleString()}</div>
                <div className="text-xs text-text-muted">residues</div>
              </div>
            </div>

            <div className="bg-surface-0 rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-text-muted">Sequence</span>
                <button
                  onClick={copySequence}
                  className="text-xs text-accent-cyan hover:text-accent-cyan font-medium"
                >
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
              <pre className="font-mono text-xs text-text-secondary overflow-auto max-h-32 break-all whitespace-pre-wrap">
                {result.sequence}
              </pre>
            </div>
          </div>

          {(result.gene_names && result.gene_names.length > 0) && (
            <div className="px-6 py-4">
              <h4 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Gene Names</h4>
              <div className="flex flex-wrap gap-2">
                {result.gene_names.map((g, i) => (
                  <span key={i} className="px-2 py-1 bg-surface-0 text-text-secondary rounded-lg text-xs font-mono">{g}</span>
                ))}
              </div>
            </div>
          )}

          {result.functions && result.functions.length > 0 && (
            <div className="px-6 py-4">
              <h4 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Functions</h4>
              {result.functions.map((f, i) => (
                <p key={i} className="text-sm text-text-secondary mb-1">{f}</p>
              ))}
            </div>
          )}

          {result.pdb_ids && result.pdb_ids.length > 0 && (
            <div className="px-6 py-4">
              <h4 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">PDB Structures</h4>
              <div className="flex flex-wrap gap-2">
                {result.pdb_ids.map((pdb, i) => (
                  <a
                    key={i}
                    href={`https://www.rcsb.org/structure/${pdb}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-2 py-1 bg-info/10 text-info rounded-lg text-xs font-mono hover:bg-info/10"
                  >
                    {pdb}
                  </a>
                ))}
              </div>
            </div>
          )}

          {result.features && result.features.length > 0 && (
            <div className="px-6 py-4">
              <h4 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Features</h4>
              <div className="space-y-1">
                {result.features.slice(0, 10).map((f, i) => (
                  <div key={i} className="flex items-center gap-3 text-sm">
                    <span className="px-2 py-0.5 bg-surface-0 text-text-muted rounded text-xs font-mono">{f.type}</span>
                    <span className="text-text-secondary">{f.description}</span>
                    {f.begin && f.end && (
                      <span className="text-xs text-text-muted ml-auto">{f.begin}-{f.end}</span>
                    )}
                  </div>
                ))}
                {result.features.length > 10 && (
                  <p className="text-xs text-text-muted mt-1">+{result.features.length - 10} more features</p>
                )}
              </div>
            </div>
          )}

          <div className="px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-text-muted">
              <BookOpen className="w-3 h-3" />
              <span>Source: {result.db_source} {result.from_cache && '(cached)'}</span>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={() => setPrefill(router, 'blast_sequence', `>${result.accession}\n${result.sequence}`, '/analyze/blast')}
                className="flex items-center gap-2 px-4 py-2 bg-accent-cyan text-void text-sm font-medium rounded-xl hover:bg-accent-hover transition"
              >
                <Beaker className="w-4 h-4" />
                Analyze with BLAST
              </button>
              {(result.sequence_type === 'dna' || result.sequence_type === 'rna') && (
                <>
                  <button
                    onClick={() => setPrefill(router, 'primer_sequence', result.sequence, '/analyze/primers')}
                    className="flex items-center gap-2 px-4 py-2 border border-accent-purple/40 text-accent-purple text-sm font-medium rounded-xl hover:bg-accent-purple/10 transition"
                  >
                    <Dna className="w-4 h-4" />
                    Design Primers
                  </button>
                  <button
                    onClick={() => setPrefill(router, 'cds_sequence', result.sequence, '/analyze/tools')}
                    className="flex items-center gap-2 px-4 py-2 border border-accent-amber/40 text-accent-amber text-sm font-medium rounded-xl hover:bg-accent-amber/10 transition"
                  >
                    <Dna className="w-4 h-4" />
                    Translate CDS
                  </button>
                </>
              )}
            </div>
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}

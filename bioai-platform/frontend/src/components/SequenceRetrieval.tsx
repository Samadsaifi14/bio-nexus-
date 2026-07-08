'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { Search, Dna, LoaderCircle, CheckCircle, AlertCircle, BookOpen, ArrowRight, Beaker } from 'lucide-react';
import { fadeUp, stagger } from '@/lib/animations';
import { fetchSequence, validateSequence, searchSequences } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import type { SequenceResult, SequenceValidation, SequenceSearchResult } from '@/types/pipeline';

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
      case 'protein': return 'text-blue-600 bg-blue-50';
      case 'dna': return 'text-purple-600 bg-purple-50';
      case 'rna': return 'text-orange-600 bg-orange-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  return (
    <motion.div initial={{ y: 24 }} animate="show" variants={stagger} className="space-y-6">
      <motion.div variants={fadeUp} className="bg-white rounded-2xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Sequence Retrieval</h2>
        <p className="text-sm text-gray-500 mb-6">
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
                mode === m.id ? 'bg-teal-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
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
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder={
              mode === 'accession' ? 'e.g. NP_000509.1, P04637, 1TIM' :
              mode === 'name' ? 'e.g. p53, BRCA1, TP53 human' :
              'Paste FASTA or raw sequence...'
            }
            className="flex-1 px-4 py-3 rounded-xl border border-gray-300 focus:border-teal-500 focus:ring-2 focus:ring-teal-200 outline-none transition text-sm"
          />
          <button
            onClick={handleSearch}
            disabled={loading || !input.trim()}
            className="px-6 py-3 bg-teal-600 text-white font-medium rounded-xl hover:bg-teal-700 transition disabled:opacity-50 flex items-center gap-2"
          >
            {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>
      </motion.div>

      {error && (
        <motion.div variants={fadeUp} className="bg-red-50 border border-red-200 rounded-2xl p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 shrink-0" />
          <p className="text-sm text-red-700">{error}</p>
        </motion.div>
      )}

      {validation && mode === 'sequence' && (
        <motion.div variants={fadeUp} className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="flex items-center gap-3 mb-4">
            {validation.valid ? (
              <CheckCircle className="w-5 h-5 text-teal-500" />
            ) : (
              <AlertCircle className="w-5 h-5 text-red-500" />
            )}
            <h3 className="font-semibold text-gray-900">
              {validation.valid ? 'Valid Sequence' : 'Invalid Sequence'}
            </h3>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="p-3 bg-gray-50 rounded-xl">
              <div className="text-xs text-gray-500 mb-1">Type</div>
              <div className="text-sm font-medium text-gray-900">
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${seqTypeColor(validation.sequence_type)}`}>
                  {validation.sequence_type}
                </span>
              </div>
            </div>
            <div className="p-3 bg-gray-50 rounded-xl">
              <div className="text-xs text-gray-500 mb-1">Length</div>
              <div className="text-sm font-medium text-gray-900">{validation.length.toLocaleString()} residues</div>
            </div>
            <div className="p-3 bg-gray-50 rounded-xl">
              <div className="text-xs text-gray-500 mb-1">Format</div>
              <div className="text-sm font-medium text-gray-900">{validation.format}</div>
            </div>
          </div>
          {validation.issues.length > 0 && (
            <div className="mt-4 p-3 bg-red-50 rounded-xl">
              <p className="text-xs text-red-600 font-medium mb-1">Issues</p>
              {validation.issues.map((issue, i) => (
                <p key={i} className="text-sm text-red-700">{issue}</p>
              ))}
            </div>
          )}
        </motion.div>
      )}

      {searchResults && mode === 'name' && (
        <motion.div variants={fadeUp} className="bg-white rounded-2xl border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-900 mb-4">Search Results ({searchResults.length})</h3>
          {searchResults.length === 0 ? (
            <p className="text-sm text-gray-500">No results found</p>
          ) : (
            <motion.div animate="show" variants={stagger} className="space-y-2">
              {searchResults.map((r, i) => (
                <motion.div key={i} variants={fadeUp}>
                  <button
                    onClick={() => handleSelectAccession(r.accession)}
                    className="w-full text-left p-4 rounded-xl border border-gray-200 hover:border-teal-300 hover:bg-teal-50 transition"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <code className="text-sm font-mono text-teal-700">{r.accession}</code>
                          <ArrowRight className="w-3 h-3 text-gray-300" />
                        </div>
                        <p className="text-sm text-gray-700 mt-1 line-clamp-1">{r.title}</p>
                      </div>
                      <div className="text-right text-xs text-gray-500">
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
        <motion.div variants={fadeUp} className="bg-white rounded-2xl border border-gray-200 divide-y divide-gray-100">
          <div className="p-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <code className="text-lg font-mono font-bold text-teal-700">{result.accession}</code>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${seqTypeColor(result.sequence_type)}`}>
                    {result.sequence_type}
                  </span>
                  <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{result.db_source}</span>
                </div>
                <p className="text-sm text-gray-700">{result.description}</p>
                {result.organism && (
                  <p className="text-xs text-gray-500 mt-1">{result.organism}</p>
                )}
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold text-gray-900">{result.length.toLocaleString()}</div>
                <div className="text-xs text-gray-500">residues</div>
              </div>
            </div>

            <div className="bg-gray-50 rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-gray-500">Sequence</span>
                <button
                  onClick={copySequence}
                  className="text-xs text-teal-600 hover:text-teal-700 font-medium"
                >
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
              <pre className="font-mono text-xs text-gray-700 overflow-auto max-h-32 break-all whitespace-pre-wrap">
                {result.sequence}
              </pre>
            </div>
          </div>

          {(result.gene_names && result.gene_names.length > 0) && (
            <div className="px-6 py-4">
              <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Gene Names</h4>
              <div className="flex flex-wrap gap-2">
                {result.gene_names.map((g, i) => (
                  <span key={i} className="px-2 py-1 bg-gray-100 text-gray-700 rounded-lg text-xs font-mono">{g}</span>
                ))}
              </div>
            </div>
          )}

          {result.functions && result.functions.length > 0 && (
            <div className="px-6 py-4">
              <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Functions</h4>
              {result.functions.map((f, i) => (
                <p key={i} className="text-sm text-gray-700 mb-1">{f}</p>
              ))}
            </div>
          )}

          {result.pdb_ids && result.pdb_ids.length > 0 && (
            <div className="px-6 py-4">
              <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">PDB Structures</h4>
              <div className="flex flex-wrap gap-2">
                {result.pdb_ids.map((pdb, i) => (
                  <a
                    key={i}
                    href={`https://www.rcsb.org/structure/${pdb}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-2 py-1 bg-blue-50 text-blue-700 rounded-lg text-xs font-mono hover:bg-blue-100"
                  >
                    {pdb}
                  </a>
                ))}
              </div>
            </div>
          )}

          {result.features && result.features.length > 0 && (
            <div className="px-6 py-4">
              <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Features</h4>
              <div className="space-y-1">
                {result.features.slice(0, 10).map((f, i) => (
                  <div key={i} className="flex items-center gap-3 text-sm">
                    <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs font-mono">{f.type}</span>
                    <span className="text-gray-700">{f.description}</span>
                    {f.begin && f.end && (
                      <span className="text-xs text-gray-400 ml-auto">{f.begin}-{f.end}</span>
                    )}
                  </div>
                ))}
                {result.features.length > 10 && (
                  <p className="text-xs text-gray-400 mt-1">+{result.features.length - 10} more features</p>
                )}
              </div>
            </div>
          )}

          <div className="px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-gray-400">
              <BookOpen className="w-3 h-3" />
              <span>Source: {result.db_source} {result.from_cache && '(cached)'}</span>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={() => {
                  sessionStorage.setItem('blast_sequence', `>${result.accession}\n${result.sequence}`);
                  router.push('/analyze/blast');
                }}
                className="flex items-center gap-2 px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-xl hover:bg-teal-700 transition"
              >
                <Beaker className="w-4 h-4" />
                Analyze with BLAST
              </button>
              {(result.sequence_type === 'dna' || result.sequence_type === 'rna') && (
                <>
                  <button
                    onClick={() => {
                      sessionStorage.setItem('primer_sequence', result.sequence);
                      router.push('/analyze/primers');
                    }}
                    className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-xl hover:bg-purple-700 transition"
                  >
                    <Dna className="w-4 h-4" />
                    Design Primers
                  </button>
                  <button
                    onClick={() => {
                      sessionStorage.setItem('cds_sequence', result.sequence);
                      router.push('/analyze/tools');
                    }}
                    className="flex items-center gap-2 px-4 py-2 bg-amber-600 text-white text-sm font-medium rounded-xl hover:bg-amber-700 transition"
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

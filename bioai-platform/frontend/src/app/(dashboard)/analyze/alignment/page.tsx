'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { ArrowLeft, LoaderCircle, ChevronRight } from 'lucide-react';
import { fadeUp } from '@/lib/animations';
import { runAlignment } from '@/lib/api';
import type { AlignmentResult } from '@/lib/api';

const SAMPLE_PAIR = `>Protein_A
MEEPQSDPSVEPPLSQETFSDLWKLLPENN
>Protein_B
MEEPQSDPSVEPPLSQETFSDLWKLLPENN`;

export default function AlignmentPage() {
  const router = useRouter();
  const [input, setInput] = useState('');
  const [stype, setStype] = useState('protein');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AlignmentResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!input.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await runAlignment(input, stype);
      setResult(res);
    } catch {
      setError('Alignment failed — check your sequences and try again.');
    } finally {
      setLoading(false);
    }
  };

  const parseFasta = (fasta: string) => {
    const lines = fasta.split('\n');
    const entries: { header: string; seq: string }[] = [];
    let current: { header: string; seq: string } | null = null;
    for (const line of lines) {
      if (line.startsWith('>')) {
        if (current) entries.push(current);
        current = { header: line.slice(1).trim(), seq: '' };
      } else if (current) {
        current.seq += line.trim();
      }
    }
    if (current) entries.push(current);
    return entries;
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

      <motion.div variants={fadeUp} initial="hidden" animate="show" className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary mb-1">Pairwise Alignment</h1>
        <p className="text-sm text-text-secondary">
          Align two or more protein or DNA sequences using Clustal Omega.
        </p>
      </motion.div>

      <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-5 mb-6 space-y-4">
        <div className="flex gap-2">
          {(['protein', 'dna'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setStype(t)}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition ${
                stype === t ? 'btn-primary' : 'glass-card text-text-secondary'
              }`}
            >
              {t === 'protein' ? 'Protein' : 'DNA'}
            </button>
          ))}
        </div>

        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={`Paste 2+ sequences in FASTA format...\n\nExample:\n>Protein_A\nMEEPQSDPSVEPPLSQETFSDLWKLLPENN\n>Protein_B\nMEEPQSDPSVEPPLSQETFSDLWKLLPENN`}
          className="w-full h-48 px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition font-mono text-sm resize-none bg-surface-1 text-text-primary"
        />

        <div className="flex gap-3">
          <button
            onClick={() => setInput(SAMPLE_PAIR)}
            className="text-sm text-accent-cyan hover:text-accent-cyan/80 underline"
          >
            Load sample
          </button>
          <div className="flex-1" />
          <button
            onClick={handleSubmit}
            disabled={loading || !input.trim()}
            className="btn-primary px-6 py-2.5 flex items-center gap-2 text-sm disabled:opacity-50"
          >
            {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : null}
            {loading ? 'Aligning...' : 'Align'}
          </button>
        </div>
      </motion.div>

      {error && (
        <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-4 border border-error/20">
          <p className="text-sm text-error">{error}</p>
        </motion.div>
      )}

      {loading && !result && (
        <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-8 text-center">
          <LoaderCircle className="w-6 h-6 animate-spin text-accent-cyan mx-auto mb-3" />
          <p className="text-sm text-text-secondary">Running Clustal Omega on EBI servers...</p>
        </motion.div>
      )}

      {result && (
        <motion.div variants={fadeUp} initial="hidden" animate="show" className="space-y-4">
          <div className="glass-card p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3">Alignment (FASTA)</h3>
            <pre className="font-mono text-xs text-text-secondary bg-surface-0 rounded-xl p-4 max-h-80 overflow-auto whitespace-pre-wrap break-all">
              {result.aln_fasta}
            </pre>
          </div>

          {result.phylotree && (
            <div className="glass-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3">Phylogenetic Tree (Newick)</h3>
              <pre className="font-mono text-xs text-text-secondary bg-surface-0 rounded-xl p-4 max-h-40 overflow-auto whitespace-pre-wrap break-all">
                {result.phylotree}
              </pre>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}

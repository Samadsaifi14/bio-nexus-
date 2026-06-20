'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { ArrowLeft, LoaderCircle } from 'lucide-react';
import { fadeUp } from '@/lib/animations';
import { runAlignment } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import type { AlignmentResult } from '@/lib/api';
import { PhyloTreeViewer } from '@/components/phylo/PhyloTreeViewer';
import { ConservationTrack } from '@/components/alignment/ConservationTrack';

function parseAlignedFasta(fasta: string): string[] {
  const seqs: string[] = [];
  let current = '';
  for (const line of fasta.split('\n')) {
    if (line.startsWith('>')) {
      if (current) seqs.push(current);
      current = '';
    } else if (current !== undefined) {
      current += line.trim();
    }
  }
  if (current) seqs.push(current);
  return seqs;
}

const SAMPLE_PROTEIN = `>p53_human
MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYQGSYGFRLGFLHSGTAKSVTCTYSPALNKMFCQLAKTCPVQLWVDSTPPPGTRVRAMAIYKQSQHMTEVVRRCPHHERCSDSDGLAPPQHLIRVEGNLRVEYLDDRNTFRHSVVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRNSFEVRVCACPGRDRRTEEENLRKKGEPHHELPPGSTKRALPNNTSSSPQPKKKPLDGEYFTLQIRGRERFEMFRELNEALELKDAQAGKEPGGSRAHSSHLKSKKGQSTSRHKKLMFKTEGPDSD
>p53_mouse
MEEPQSDPSIEPPLSQETFSDLWKLLPENNVLSPLPSQAVDDLMLSPDDLAQWFTEDPGPDEAPRMSEAAPPAAPAPAAPTPAAPAPAPSWPLSSFVPSQKTYQGNYGFHLGFLQSGTAKSVMCTYSPPLNKLFCQLAKTCPVQLWVSATPPAGSRVRAMAIYKKSQHMTEVVRRCPHHERCSDSSDGLAPPQHLIRVEGNLRAEYLDDRNTFRHSIVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRDSFEVRVCACPGRDRRTEEENFKKKEPCPEPPPGSTRALGSTSTSSPTPKKKPLDGEYFTLKIRGRERFEMFRELNEALELKDAHATEEPFGGSRAHSSHLKSKKGQSTSRHKKFKKTADPSS`;
const SAMPLE_DNA = `>seq_human
AGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCT
>seq_chimp
AGCTAGCTAGCTAGCTAGCCAGCTAGCTAGCT`;

function parseFasta(text: string): { headers: string[]; sequences: string[] } {
  const lines = text.split('\n');
  const headers: string[] = [];
  const sequences: string[] = [];
  let currentHeader = '';
  let currentSeq = '';
  for (const line of lines) {
    if (line.startsWith('>')) {
      if (currentHeader) {
        headers.push(currentHeader);
        sequences.push(currentSeq);
      }
      currentHeader = line.slice(1).trim();
      currentSeq = '';
    } else if (currentHeader) {
      currentSeq += line.trim();
    }
  }
  if (currentHeader) {
    headers.push(currentHeader);
    sequences.push(currentSeq);
  }
  return { headers, sequences };
}

function validateFasta(text: string): string | null {
  if (!text.trim()) return 'Enter sequences in FASTA format';
  const { headers, sequences } = parseFasta(text);
  if (headers.length < 2) return 'Provide at least 2 sequences in FASTA format (each starting with >)';
  const uniqueSeqs = new Set(sequences.map(s => s.toUpperCase().replace(/[^A-Z]/g, '')));
  if (uniqueSeqs.size < 2) return 'Sequences are identical — provide different sequences for alignment';
  for (let i = 0; i < sequences.length; i++) {
    const clean = sequences[i].replace(/[^A-Za-z]/g, '');
    if (clean.length < 4) return `Sequence "${headers[i]}" is too short (min 4 residues)`;
  }
  return null;
}

export default function AlignmentPage() {
  const router = useRouter();
  const [input, setInput] = useState('');
  const [stype, setStype] = useState('protein');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AlignmentResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    const validationError = validateFasta(input);
    if (validationError) {
      setError(validationError);
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await runAlignment(input, stype);
      setResult(res);
    } catch (err: unknown) {
      setError(extractErrorMessage(err, 'Alignment failed'));
    } finally {
      setLoading(false);
    }
  };

  const handleSample = () => {
    setInput(stype === 'protein' ? SAMPLE_PROTEIN : SAMPLE_DNA);
    setError(null);
    setResult(null);
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
        <h1 className="text-2xl font-bold text-text-primary mb-1">Multiple Sequence Alignment</h1>
        <p className="text-sm text-text-secondary">
          Align two or more protein or DNA sequences using Clustal Omega.
        </p>
      </motion.div>

      <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-5 mb-6 space-y-4">
        <div className="flex gap-2">
          {(['protein', 'dna'] as const).map((t) => (
            <button
              key={t}
              onClick={() => { setStype(t); setError(null); setResult(null); }}
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
          placeholder={`Paste 2+ sequences in FASTA format...\n\n>sequence_1\nMEEPQSDPSVEPPLSQETFSDLWKLLPENN\n>sequence_2\nMEEPQSDPSIEPPLSQETFSDLWKLLPENN`}
          className="w-full h-48 px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition font-mono text-sm resize-none bg-surface-1 text-text-primary"
        />

        <div className="flex gap-3">
          <button
            onClick={handleSample}
            className="text-sm text-accent-cyan hover:text-accent-cyan/80 underline"
          >
            Load sample {stype === 'protein' ? 'p53 (human vs mouse)' : 'DNA sequences'}
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

      {result && (() => {
        const alignedSeqs = parseAlignedFasta(result.aln_fasta);
        return (
          <motion.div variants={fadeUp} initial="hidden" animate="show" className="space-y-4">
            <div className="glass-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3">Alignment (FASTA)</h3>
              <pre className="font-mono text-xs text-text-secondary bg-surface-0 rounded-xl p-4 max-h-80 overflow-auto whitespace-pre-wrap break-all">
                {result.aln_fasta}
              </pre>
            </div>

            {result.phylotree && (
              <div className="glass-card p-5">
                <PhyloTreeViewer newick={result.phylotree} />
              </div>
            )}

            {alignedSeqs.length >= 2 && (
              <div className="glass-card p-5">
                <ConservationTrack alignedSeqs={alignedSeqs} />
              </div>
            )}
          </motion.div>
        );
      })()}
    </div>
  );
}

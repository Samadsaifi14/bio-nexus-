'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { CircleNotch as LoaderCircle } from '@phosphor-icons/react';
import { fadeUp } from '@/lib/animations';
import { runAlignment, type AlignmentMethod } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import type { AlignmentResult } from '@/lib/api';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import PhyloTreeViewer from '@/components/phylo/PhyloTreeViewer';
import { ConservationTrack } from '@/components/alignment/ConservationTrack';
import { BackButton, CriticalButton, ClaySegmented, FlatTextarea, PageHeader } from '@/components/ui';

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

const METHOD_LABELS: Record<AlignmentMethod, string> = {
  clustalo: 'Clustal Omega',
  muscle: 'MUSCLE',
  kalign: 'Kalign',
  mafft: 'MAFFT',
  tcoffee: 'T-Coffee',
};

const METHOD_OPTIONS = (Object.entries(METHOD_LABELS) as [AlignmentMethod, string][]).map(([value, label]) => ({ value, label }));

export default function AlignmentPage() {
  const [input, setInput] = useState('');
  const [stype, setStype] = useState('protein');
  const [method, setMethod] = useState<AlignmentMethod>('clustalo');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AlignmentResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const audit = useAuditTrail();

  const handleSubmit = async () => {
    const validationError = validateFasta(input);
    if (validationError) {
      setError(validationError);
      return;
    }
    const seqCount = parseFasta(input).headers.length;
    const inputSummary = `type:${stype},seqs:${seqCount}`;
    audit.emitStarted('alignment_run', METHOD_LABELS[method], inputSummary);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await runAlignment(input, stype, method);
      setResult(res);
      audit.emitSuccess('alignment_run', METHOD_LABELS[method], inputSummary, `job_id:${res?.job_id ?? ''},stype:${res?.stype ?? ''}`);
    } catch (err: unknown) {
      const errMsg = extractErrorMessage(err, 'Alignment failed');
      audit.emitFailed('alignment_run', METHOD_LABELS[method], inputSummary, errMsg);
      setError(errMsg);
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
      <BackButton />

      <PageHeader
        title="Multiple Sequence Alignment"
        subtitle="Align two or more protein or DNA sequences with a choice of EBI methods."
      />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-6 space-y-4">
        <ClaySegmented
          options={[
            { value: 'protein', label: 'Protein' },
            { value: 'dna', label: 'DNA' },
          ] as { value: string; label: string }[]}
          value={stype}
          onChange={(v) => { setStype(v); setError(null); setResult(null); }}
        />

        <ClaySegmented
          options={METHOD_OPTIONS as { value: string; label: string }[]}
          value={method}
          onChange={(v) => { setMethod(v as AlignmentMethod); setError(null); setResult(null); }}
        />

        <FlatTextarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={`Paste 2+ sequences in FASTA format...\n\n>sequence_1\nMEEPQSDPSVEPPLSQETFSDLWKLLPENN\n>sequence_2\nMEEPQSDPSIEPPLSQETFSDLWKLLPENN`}
          className="w-full h-48 font-mono text-sm text-text-primary"
        />

        <div className="flex gap-3">
          <button
            onClick={handleSample}
            className="text-sm text-accent-cyan hover:text-accent-cyan/80 underline"
          >
            Load sample {stype === 'protein' ? 'p53 (human vs mouse)' : 'DNA sequences'}
          </button>
          <div className="flex-1" />
          <CriticalButton onClick={handleSubmit} disabled={loading || !input.trim()}>
            {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : null}
            {loading ? 'Aligning...' : 'Align'}
          </CriticalButton>
        </div>
      </motion.div>

      {error && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-4 border border-error/20">
          <p className="text-sm text-error">{error}</p>
        </motion.div>
      )}

      {loading && !result && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-8 text-center">
          <LoaderCircle className="w-6 h-6 animate-spin text-accent-cyan mx-auto mb-3" />
          <p className="text-sm text-text-secondary">Running {METHOD_LABELS[method]} on EBI servers...</p>
        </motion.div>
      )}

      {result && (() => {
        const alignedSeqs = parseAlignedFasta(result.aln_fasta);
        return (
          <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-4">
          <div className="data-card p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3">Alignment (FASTA) — {METHOD_LABELS[result.method as AlignmentMethod] ?? result.method ?? 'Clustal Omega'}</h3>
              <pre className="font-mono text-xs text-text-secondary bg-surface-0 rounded-xl p-4 max-h-80 overflow-auto whitespace-pre-wrap break-all">
                {result.aln_fasta}
              </pre>
            </div>

            {result.phylotree && (
              <div className="data-card p-5">
                <PhyloTreeViewer newick={result.phylotree} />
              </div>
            )}

            {alignedSeqs.length >= 2 && (
              <div className="data-card p-5">
                <ConservationTrack alignedSeqs={alignedSeqs} />
              </div>
            )}
          </motion.div>
        );
      })()}
    </div>
  );
}

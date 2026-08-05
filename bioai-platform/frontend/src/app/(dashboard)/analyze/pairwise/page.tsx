'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowsLeftRight as ArrowSwap, CircleNotch as LoaderCircle } from '@phosphor-icons/react';
import { fadeUp } from '@/lib/animations';
import { runPairwiseAlignment } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import { BackButton, CriticalButton, ClaySegmented, FlatTextarea, PageHeader } from '@/components/ui';
import { PairwiseResultDisplay } from '@/components/alignment/PairwiseResultDisplay';
import type { PairwiseAlignResult } from '@/types/pipeline';

type AlignMode = 'global' | 'local';
type Matrix = 'blosum62' | 'pam250';

function getStoredAlignMode(): AlignMode {
  if (typeof window === 'undefined') return 'global';
  return sessionStorage.getItem('blast_align_mode') === 'local' ? 'local' : 'global';
}

function stripFastaHeader(text: string): string {
  return text.split('\n').filter(l => !l.startsWith('>')).join('\n');
}

function cleanLength(text: string): number {
  return stripFastaHeader(text).replace(/[^A-Za-z]/g, '').length;
}

const SAMPLES: [string, string] = [
  `>p53_human
MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYQGSYGFRLGFLHSGTAKSVTCTYSPALNKMFCQLAKTCPVQLWVDSTPPPGTRVRAMAIYKQSQHMTEVVRRCPHHERCSDSDGLAPPQHLIRVEGNLRVEYLDDRNTFRHSVVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRNSFEVRVCACPGRDRRTEEENLRKKGEPHHELPPGSTKRALPNNTSSSPQPKKKPLDGEYFTLQIRGRERFEMFRELNEALELKDAQAGKEPGGSRAHSSHLKSKKGQSTSRHKKLMFKTEGPDSD`,
  `>p53_mouse
MEEPQSDPSIEPPLSQETFSDLWKLLPENNVLSPLPSQAVDDLMLSPDDLAQWFTEDPGPDEAPRMSEAAPPAAPAPAAPTPAAPAPAPSWPLSSFVPSQKTYQGNYGFHLGFLQSGTAKSVMCTYSPPLNKLFCQLAKTCPVQLWVSATPPAGSRVRAMAIYKKSQHMTEVVRRCPHHERCSDSSDGLAPPQHLIRVEGNLRAEYLDDRNTFRHSIVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRDSFEVRVCACPGRDRRTEEENFKKKEPCPEPPPGSTRALGSTSTSSPTPKKKPLDGEYFTLKIRGRERFEMFRELNEALELKDAHATEEPFGGSRAHSSHLKSKKGQSTSRHKKFKKTADPSS`,
];

export default function PairwiseAlignPage() {
  const [seqA, setSeqA] = useState('');
  const [seqB, setSeqB] = useState('');
  const [mode, setMode] = useState<AlignMode>(getStoredAlignMode);
  const [matrix, setMatrix] = useState<Matrix>('blosum62');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PairwiseAlignResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const audit = useAuditTrail();

  const lenA = cleanLength(seqA);
  const lenB = cleanLength(seqB);
  const canRun = lenA >= 2 && lenB >= 2 && !loading;

  const handleModeChange = (m: AlignMode) => {
    setMode(m);
    sessionStorage.setItem('blast_align_mode', m);
  };

  const handleRun = async () => {
    if (!canRun) return;
    setLoading(true);
    setError(null);
    setResult(null);
    const summary = `lenA:${lenA},lenB:${lenB},mode:${mode},matrix:${matrix}`;
    audit.emitStarted('pairwise_alignment', 'Pairwise Alignment', summary);
    try {
      const res = await runPairwiseAlignment({
        query_sequence: seqA,
        subject_sequence: seqB,
        mode,
        matrix,
      });
      setResult(res);
      audit.emitSuccess('pairwise_alignment', 'Pairwise Alignment', summary, `identity:${res.pct_identity}%`);
    } catch (err: unknown) {
      const errMsg = extractErrorMessage(err, 'Pairwise alignment failed');
      setError(errMsg);
      audit.emitFailed('pairwise_alignment', 'Pairwise Alignment', summary, errMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <BackButton />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show">
        <PageHeader
          title="Pairwise Alignment"
          subtitle="Align two sequences directly — Needleman-Wunsch (global) or Smith-Waterman (local), with BLOSUM62 or PAM250 scoring."
        />
      </motion.div>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-6">
        <div className="data-card p-5 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="text-xs font-mono text-text-muted">SAMPLE</span>
              <button
                type="button"
                onClick={() => { setSeqA(SAMPLES[0]); setSeqB(SAMPLES[1]); setResult(null); }}
                className="text-sm text-accent-cyan hover:text-accent-cyan/80 underline"
              >
                Load p53 human vs mouse
              </button>
            </div>
            <button
              type="button"
              onClick={() => { setSeqA(seqB); setSeqB(seqA); setResult(null); }}
              disabled={!seqA && !seqB}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-glass-border text-xs text-text-secondary hover:text-accent-cyan hover:border-accent-cyan/40 transition disabled:opacity-40"
            >
              <ArrowSwap className="w-3.5 h-3.5" />
              Swap
            </button>
          </div>

          <div>
            <label className="text-xs font-medium text-text-secondary block mb-1.5">
              Sequence A <span className="text-text-muted">— query</span>
            </label>
            <FlatTextarea
              value={seqA}
              onChange={(e) => { setSeqA(e.target.value); setResult(null); }}
              placeholder="Paste FASTA or raw sequence A..."
              className="w-full h-32 text-sm"
            />
            <p className="text-[11px] text-text-muted mt-1">{lenA > 0 ? `${lenA} residues` : ''}</p>
          </div>

          <div>
            <label className="text-xs font-medium text-text-secondary block mb-1.5">
              Sequence B <span className="text-text-muted">— subject</span>
            </label>
            <FlatTextarea
              value={seqB}
              onChange={(e) => { setSeqB(e.target.value); setResult(null); }}
              placeholder="Paste FASTA or raw sequence B..."
              className="w-full h-32 text-sm"
            />
            <p className="text-[11px] text-text-muted mt-1">{lenB > 0 ? `${lenB} residues` : ''}</p>
          </div>
        </div>

        <div className="glass p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 border border-glass-border">
          <div>
            <p className="text-sm font-medium text-text-primary">Alignment mode</p>
            <p className="text-xs text-text-muted mt-0.5">
              {mode === 'global'
                ? 'Global: Needleman-Wunsch — aligns the entire query against the full subject, including divergent tails.'
                : 'Local: Smith-Waterman — finds the single best matching region between the two sequences.'}
            </p>
          </div>
          <div className="flex items-center gap-4">
            <label className="text-xs text-text-secondary flex items-center gap-2">
              Matrix
              <select
                value={matrix}
                onChange={(e) => { setMatrix(e.target.value as Matrix); setResult(null); }}
                className="px-2.5 py-1.5 rounded-lg border border-glass-border bg-surface-1 text-sm text-text-primary"
              >
                <option value="blosum62">BLOSUM62</option>
                <option value="pam250">PAM250</option>
              </select>
            </label>
            <ClaySegmented
              options={[
                { value: 'global', label: 'Global (NW)' },
                { value: 'local', label: 'Local (SW)' },
              ]}
              value={mode}
              onChange={handleModeChange}
            />
          </div>
        </div>

        <div className="flex justify-end">
          <CriticalButton onClick={handleRun} disabled={!canRun}>
            {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : null}
            {loading ? 'Aligning...' : 'Align sequences'}
          </CriticalButton>
        </div>

        {error && (
          <div className="rounded-lg bg-error/10 border border-error/30 px-4 py-3 text-sm text-error">
            <strong>Alignment failed:</strong> {error}
          </div>
        )}

        {result && !loading && (
          <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="mt-8">
            <PairwiseResultDisplay
              result={result}
              queryLabel="Sequence A"
              subjectLabel="Sequence B"
            />
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}

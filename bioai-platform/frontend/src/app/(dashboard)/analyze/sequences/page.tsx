'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { CircleNotch as LoaderCircle } from '@phosphor-icons/react';
import { fadeUp } from '@/lib/animations';
import { analyzeSequence } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import { BackButton, CriticalButton, ClaySegmented, FlatTextarea, PageHeader } from '@/components/ui';
import { SequenceUtilitiesView } from '@/components/sequences/SequenceUtilitiesView';
import type { SequenceUtilitiesResult } from '@/types/pipeline';

type SeqType = 'auto' | 'dna' | 'rna' | 'protein';

const SAMPLE_DNA = '>probe\nAGCTAGCGGATCCGAATTCGATCGTACGATCGATCGTACGATGACGTAGCTAGCATCGATCGTAGCTAGCG';
const SAMPLE_PROTEIN = '>p53_1_70\nMEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPAA';

function cleanLength(seq: string): number {
  return seq.replace(/[^A-Za-z]/g, '').length;
}

export default function SequenceUtilitiesPage() {
  const [sequence, setSequence] = useState('');
  const [seqType, setSeqType] = useState<SeqType>('auto');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SequenceUtilitiesResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const audit = useAuditTrail();

  const canRun = cleanLength(sequence) >= 1 && !loading;

  const handleRun = async () => {
    if (!canRun) return;
    setLoading(true);
    setError(null);
    setResult(null);
    const summary = `len:${cleanLength(sequence)},type:${seqType}`;
    audit.emitStarted('sequence_utilities', 'Sequence Utilities', summary);
    try {
      const res = await analyzeSequence({ sequence, seq_type: seqType });
      setResult(res);
      audit.emitSuccess('sequence_utilities', 'Sequence Utilities', summary, `type:${res.sequence_type},length:${res.length}`);
    } catch (err: unknown) {
      const errMsg = extractErrorMessage(err, 'Sequence analysis failed');
      setError(errMsg);
      audit.emitFailed('sequence_utilities', 'Sequence Utilities', summary, errMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <BackButton />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show">
        <PageHeader
          title="Sequence Utilities"
          subtitle="GC content, reverse complement, molecular weight, six-frame translation with best-ORF detection, amino-acid composition and restriction-enzyme site scanning — all computed instantly."
        />
      </motion.div>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-6">
        <div className="data-card p-5 space-y-4">
          <FlatTextarea
            value={sequence}
            onChange={e => setSequence(e.target.value)}
            placeholder="Paste DNA, RNA or protein sequence (raw or FASTA)..."
            className="w-full h-40 text-sm"
          />
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <ClaySegmented
              options={[
                { value: 'auto', label: 'Auto-detect' },
                { value: 'dna', label: 'DNA' },
                { value: 'rna', label: 'RNA' },
                { value: 'protein', label: 'Protein' },
              ]}
              value={seqType}
              onChange={setSeqType}
            />
            <div className="flex gap-2">
              <button
                onClick={() => setSequence(SAMPLE_DNA)}
                className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition"
              >
                Load DNA sample
              </button>
              <button
                onClick={() => setSequence(SAMPLE_PROTEIN)}
                className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition"
              >
                Load protein sample
              </button>
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <CriticalButton onClick={handleRun} disabled={!canRun}>
            {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : null}
            {loading ? 'Analyzing...' : 'Analyze sequence'}
          </CriticalButton>
        </div>

        {error && (
          <div className="rounded-lg bg-error/10 border border-error/30 px-4 py-3 text-sm text-error">
            <strong>Analysis failed:</strong> {error}
          </div>
        )}

        {result && !loading && (
          <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="mt-8">
            <SequenceUtilitiesView result={result} />
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}

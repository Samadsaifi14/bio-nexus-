'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { motion } from 'framer-motion';
import { CircleNotch as LoaderCircle, Rocket as Send } from '@phosphor-icons/react';
import { fadeUp, stagger } from '@/lib/animations';
import { predictStructure, getPredictionStatus, type PredictionResult } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import { DockingViewer } from '@/components/DockingViewer';
import { BackButton, PageHeader, CriticalButton, FlatInput } from '@/components/ui';

function PredictResultDisplay({ pdb, result, seqLen }: { pdb: string; result: PredictionResult; seqLen: number }) {
  const pdbUrl = useMemo(() => {
    const blob = new Blob([pdb], { type: 'text/plain' });
    return URL.createObjectURL(blob);
  }, [pdb]);

  useEffect(() => {
    return () => URL.revokeObjectURL(pdbUrl);
  }, [pdbUrl]);

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-4">
      <motion.div variants={fadeUp} className="data-card p-5">
        <h3 className="font-semibold text-text-primary mb-1">Predicted Structure</h3>
        <div className="flex flex-wrap gap-4 text-xs text-text-muted mb-4">
          {result.mean_plddt != null && (
            <span>Mean pLDDT: <span className="text-accent-cyan font-mono">{result.mean_plddt.toFixed(1)}</span></span>
          )}
          {result.ptm != null && (
            <span>pTM: <span className="text-accent-cyan font-mono">{result.ptm.toFixed(3)}</span></span>
          )}
          <span>{seqLen} residues</span>
        </div>
        <DockingViewer pdbId="" pdbUrl={pdbUrl} pdbUrlFormat="pdb" ligandPdb="" />
      </motion.div>

      <motion.div variants={fadeUp} className="data-card p-4">
        <h4 className="text-sm font-semibold text-text-primary mb-2">Download</h4>
        <button
          onClick={() => {
            const a = document.createElement('a');
            a.href = pdbUrl;
            a.download = 'esmfold_prediction.pdb';
            a.click();
          }}
          className="text-xs text-accent-cyan hover:underline"
        >
          Download PDB file
        </button>
      </motion.div>
    </motion.div>
  );
}

const EXAMPLES = [
  { label: 'Villin headpiece (35 res)', seq: 'MDYKDDDDKLEIRELHEEAAKEFAKEIAAALPAAEA' },
  { label: 'Trp-cage (20 res)', seq: 'NLYIQWLKDGGPSSGRPPPS' },
];

export default function PredictStructurePage() {
  const [sequence, setSequence] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const audit = useAuditTrail();
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const cleanSeq = sequence.replace(/[^A-Za-z]/g, '').toUpperCase();
  const seqLen = cleanSeq.length;

  const handleSubmit = async () => {
    if (!cleanSeq || seqLen < 10) return;
    audit.emitStarted('structure_predict', 'ESMFold', `len:${seqLen}`);
    setLoading(true);
    setError(null);
    setResult(null);
    setProgress(0);
    try {
      const res = await predictStructure(cleanSeq, jobTitle || `ESMFold ${seqLen} res`);
      setJobId(res.job_id);
      setProgress(10);
    } catch (err: unknown) {
      const msg = extractErrorMessage(err, 'Prediction failed');
      audit.emitFailed('structure_predict', 'ESMFold', `len:${seqLen}`, msg);
      setError(msg);
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!jobId) return;
    let elapsed = 0;
    pollRef.current = setInterval(async () => {
      elapsed += 2;
      setProgress(Math.min(10 + (elapsed / 120) * 80, 90));
      try {
        const res = await getPredictionStatus(jobId);
        if (res.status === 'complete') {
          if (pollRef.current) clearInterval(pollRef.current);
          setResult(res);
          setLoading(false);
          setProgress(100);
          audit.emitSuccess('structure_predict', 'ESMFold', `len:${seqLen}`, `plddt:${res.mean_plddt}`);
        } else if (res.status === 'failed') {
          if (pollRef.current) clearInterval(pollRef.current);
          setError(res.error || 'Prediction failed');
          setLoading(false);
          audit.emitFailed('structure_predict', 'ESMFold', `len:${seqLen}`, res.error || 'unknown');
        }
      } catch {
        // keep polling
      }
    }, 2000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [jobId, seqLen, audit]);

  return (
    <div className="max-w-4xl">
      <BackButton />
      <PageHeader
        title="Structure Prediction"
        subtitle="Predict 3D protein structure from sequence using ESMFold (Facebook AI). No templates or MSA required."
      />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-6">
        <div className="mb-3">
          <FlatInput
            type="text"
            value={jobTitle}
            onChange={(e) => setJobTitle(e.target.value)}
            placeholder="Job title (optional)"
            className="w-full mb-3"
          />
          <textarea
            value={sequence}
            onChange={(e) => { setSequence(e.target.value); setResult(null); setError(null); }}
            placeholder="Paste protein sequence (10–768 residues, A-Z only)"
            rows={5}
            className="w-full bg-surface-0 border border-glass-border rounded-lg px-4 py-3 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-cyan/50 font-mono resize-y"
          />
          <div className="flex items-center justify-between mt-2">
            <span className={`text-xs ${seqLen > 768 ? 'text-error' : seqLen >= 10 ? 'text-accent-green' : 'text-text-muted'}`}>
              {seqLen} / 768 residues
            </span>
            {seqLen > 0 && seqLen < 10 && (
              <span className="text-xs text-error">Minimum 10 residues</span>
            )}
          </div>
        </div>

        <div className="flex gap-3 mb-3">
          {EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              onClick={() => { setSequence(ex.seq); setError(null); setResult(null); }}
              className="text-xs text-accent-cyan hover:text-accent-cyan/80 underline"
            >
              {ex.label}
            </button>
          ))}
        </div>

        <CriticalButton onClick={handleSubmit} disabled={loading || seqLen < 10 || seqLen > 768}>
          {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          Predict Structure
        </CriticalButton>

        {loading && jobId && (
          <div className="mt-4">
            <div className="w-full bg-surface-1 rounded-full h-1.5">
              <div
                className="bg-accent-cyan h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-xs text-text-muted mt-2">
              Predicting... ESMFold typically takes 30–120 seconds for small proteins.
            </p>
          </div>
        )}
      </motion.div>

      {error && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-4 border border-error/20 mb-4">
          <p className="text-sm text-error">{error}</p>
        </motion.div>
      )}

      {result && result.pdb && (
        <PredictResultDisplay pdb={result.pdb} result={result} seqLen={seqLen} />
      )}
    </div>
  );
}

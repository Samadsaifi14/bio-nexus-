'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { motion } from 'framer-motion';
import { CircleNotch as LoaderCircle, CheckCircle as Check, Warning as AlertTriangle, XCircle as X, Funnel, Dna } from '@phosphor-icons/react';
import { fadeUp, stagger } from '@/lib/animations';
import { extractErrorMessage } from '@/lib/errors';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import { DockingViewer } from '@/components/DockingViewer';
import { AIResultSummary } from '@/components/results/AIResultSummary';
import { BackButton, PageHeader, CriticalButton, FlatInput } from '@/components/ui';
import { runStructurePrep, runStructurePrepSequence, getStructurePrepStatus, type StructurePrepResult } from '@/lib/api';

type PipelineStatus = StructurePrepResult;
type InputMode = 'pdb_id' | 'sequence';

const STEP_LABELS: Record<string, string> = {
  fetching: 'Fetching structure',
  predicting_structure: 'Predicting structure (ESMFold)',
  analyzing: 'Detecting chain health',
  repairing: 'SWISS-MODEL repair',
  cleaning: 'PyMOL cleanup',
  running_fpocket: 'fpocket (local)',
  running_castp: 'CASTp (remote)',
  complete: 'Complete',
};

function StatusBadge({ step, target }: { step: string; target: string }) {
  const steps = Object.keys(STEP_LABELS);
  const currentIdx = steps.indexOf(step);
  const targetIdx = steps.indexOf(target);

  if (step === 'complete' || currentIdx > targetIdx) {
    return <Check className="w-4 h-4 text-accent-green" />;
  }
  if (currentIdx === targetIdx) {
    return <LoaderCircle className="w-4 h-4 text-accent-cyan animate-spin" />;
  }
  return <div className="w-4 h-4 rounded-full border border-glass-border" />;
}

export default function StructurePrepPage() {
  const [mode, setMode] = useState<InputMode>('pdb_id');
  const [pdbId, setPdbId] = useState('');
  const [sequence, setSequence] = useState('');
  const [probeRadius, setProbeRadius] = useState(1.4);
  const [result, setResult] = useState<PipelineStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const audit = useAuditTrail();
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const cleanSeq = sequence.replace(/[^A-Za-z]/g, '').toUpperCase();

  const pdbUrl = useMemo(() => {
    if (!result?.cleaned_pdb) return null;
    const blob = new Blob([result.cleaned_pdb], { type: 'text/plain' });
    return URL.createObjectURL(blob);
  }, [result?.cleaned_pdb]);

  useEffect(() => () => { if (pdbUrl) URL.revokeObjectURL(pdbUrl); }, [pdbUrl]);

  const canSubmit = mode === 'pdb_id' ? pdbId.trim().length > 0 : cleanSeq.length >= 10;

  const handleRun = async () => {
    const label = mode === 'pdb_id' ? `pdb:${pdbId.trim().toUpperCase()}` : `seq:${cleanSeq.length}aa`;
    audit.emitStarted('structure_prep', 'Pipeline', label);
    setLoading(true);
    setError(null);
    setResult(null);
    setProgress(0);
    try {
      const res = mode === 'pdb_id'
        ? await runStructurePrep(pdbId.trim().toUpperCase(), probeRadius)
        : await runStructurePrepSequence(cleanSeq, probeRadius);
      pollForResults(res.job_id);
    } catch (err: unknown) {
      const msg = extractErrorMessage(err, 'Pipeline failed');
      audit.emitFailed('structure_prep', 'Pipeline', label, msg);
      setError(msg);
      setLoading(false);
    }
  };

  const pollForResults = (jobId: string) => {
    let elapsed = 0;
    pollRef.current = setInterval(async () => {
      elapsed += 2;
      setProgress(Math.min(10 + (elapsed / 180) * 80, 90));
      try {
        const data = await getStructurePrepStatus(jobId);
        if (data.status === 'complete') {
          if (pollRef.current) clearInterval(pollRef.current);
          setResult(data);
          setLoading(false);
          setProgress(100);
          audit.emitSuccess('structure_prep', 'Pipeline', `job:${jobId}`, `${data.fpocket_pockets.length} fpocket + ${data.castp_pockets.length} castp pockets`);
        } else if (data.status === 'failed') {
          if (pollRef.current) clearInterval(pollRef.current);
          setError(data.error || 'Pipeline failed');
          setLoading(false);
          audit.emitFailed('structure_prep', 'Pipeline', `job:${jobId}`, data.error || 'unknown');
        } else {
          setResult(data);
        }
      } catch {
        // keep polling
      }
    }, 2000);
  };

  return (
    <div className="max-w-4xl">
      <BackButton />
      <PageHeader
        title="Structure Preparation Pipeline"
        subtitle="Fetch or predict structure → detect broken chains → SWISS-MODEL repair → PyMOL cleanup → fpocket + CASTp pocket detection."
      />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-6">
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => { setMode('pdb_id'); setError(null); setResult(null); }}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              mode === 'pdb_id'
                ? 'bg-accent-cyan/20 text-accent-cyan border border-accent-cyan/30'
                : 'bg-surface-1 text-text-muted hover:text-text-secondary border border-transparent'
            }`}
          >
            PDB ID
          </button>
          <button
            onClick={() => { setMode('sequence'); setError(null); setResult(null); }}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              mode === 'sequence'
                ? 'bg-accent-cyan/20 text-accent-cyan border border-accent-cyan/30'
                : 'bg-surface-1 text-text-muted hover:text-text-secondary border border-transparent'
            }`}
          >
            <Dna className="w-3 h-3 inline mr-1" />
            Amino Acid Sequence
          </button>
        </div>

        {mode === 'pdb_id' ? (
          <div className="flex gap-3">
            <FlatInput
              type="text"
              value={pdbId}
              onChange={(e) => { setPdbId(e.target.value); setResult(null); setError(null); }}
              onKeyDown={(e) => e.key === 'Enter' && handleRun()}
              placeholder="PDB ID (e.g. 1TIM, 4HHB, 1FME)"
              className="flex-1"
            />
            <CriticalButton onClick={handleRun} disabled={loading || !pdbId.trim()}>
              {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Funnel className="w-4 h-4" />}
              Run Pipeline
            </CriticalButton>
          </div>
        ) : (
          <div>
            <textarea
              value={sequence}
              onChange={(e) => { setSequence(e.target.value); setResult(null); setError(null); }}
              placeholder="Paste amino acid sequence (10–768 residues)"
              rows={4}
              className="w-full bg-surface-0 border border-glass-border rounded-lg p-3 text-sm font-mono text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-cyan/50 resize-none"
            />
            <div className="flex items-center justify-between mt-2">
              <span className={`text-xs ${cleanSeq.length > 768 ? 'text-error' : cleanSeq.length >= 10 ? 'text-accent-green' : 'text-text-muted'}`}>
                {cleanSeq.length} / 768 residues
              </span>
              <CriticalButton onClick={handleRun} disabled={loading || cleanSeq.length < 10}>
                {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Funnel className="w-4 h-4" />}
                {loading ? 'Running...' : 'Predict & Run Pipeline'}
              </CriticalButton>
            </div>
            <p className="text-[10px] text-text-muted mt-2">
              ESMFold predicts the 3D structure, then the full preparation pipeline runs automatically.
            </p>
          </div>
        )}

        <div className="mt-4">
          <label className="block text-xs text-text-muted mb-2">Probe radius: {probeRadius.toFixed(1)} Å</label>
          <input
            type="range" min={0.5} max={5.0} step={0.1} value={probeRadius}
            onChange={(e) => setProbeRadius(parseFloat(e.target.value))}
            className="w-full h-1.5 bg-surface-1 rounded-lg appearance-none cursor-pointer accent-accent-cyan"
          />
        </div>

        {mode === 'pdb_id' && (
          <div className="flex gap-3 mt-3">
            {['1TIM', '4HHB', '1FME', '1BNA'].map((id) => (
              <button key={id} onClick={() => { setPdbId(id); setError(null); setResult(null); }}
                className="text-xs text-accent-cyan hover:text-accent-cyan/80 underline">{id}</button>
            ))}
          </div>
        )}
      </motion.div>

      {loading && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-6">
          <div className="w-full bg-surface-1 rounded-full h-1.5 mb-4">
            <div className="bg-accent-cyan h-1.5 rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
          </div>
          <div className="space-y-2">
            {Object.entries(STEP_LABELS).filter(([k]) => k !== 'complete').map(([key, label]) => (
              <div key={key} className="flex items-center gap-3">
                <StatusBadge step={result?.step || 'fetching'} target={key} />
                <span className={`text-sm ${result?.step === key ? 'text-accent-cyan' : 'text-text-muted'}`}>{label}</span>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {error && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-4 border border-error/20 mb-4">
          <p className="text-sm text-error">{error}</p>
        </motion.div>
      )}

      {result && result.status === 'complete' && (
        <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-4">
          <AIResultSummary toolName="structure_prep" result={result as unknown as Record<string, unknown>} />
          {result.chain_health && (
            <motion.div variants={fadeUp} className="data-card p-5">
              <div className="flex items-center gap-3 mb-3">
                {result.chain_health.is_broken ? (
                  <AlertTriangle className="w-5 h-5 text-warn" />
                ) : (
                  <Check className="w-5 h-5 text-accent-green" />
                )}
                <h3 className="font-semibold text-text-primary">
                  {result.chain_health.is_broken ? 'Broken Chains Detected' : 'Structure Intact'}
                </h3>
              </div>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-text-muted text-xs">Chains</span>
                  <p className="font-mono">{result.chain_health.chains.join(', ')}</p>
                </div>
                <div>
                  <span className="text-text-muted text-xs">Total residues</span>
                  <p className="font-mono">{result.chain_health.total_residues}</p>
                </div>
                <div>
                  <span className="text-text-muted text-xs">Missing residues</span>
                  <p className="font-mono">{result.chain_health.missing_residue_count}</p>
                </div>
              </div>
              {result.chain_health.chain_breaks.length > 0 && (
                <div className="mt-3 text-xs text-text-muted">
                  Chain breaks: {result.chain_health.chain_breaks.map((b) => (
                    <span key={`${b.chain}-${b.from_resnum}`} className="font-mono text-warn">
                      {b.chain}:{b.from_resnum}-{b.to_resnum} ({b.distance}Å){' '}
                    </span>
                  ))}
                </div>
              )}
            </motion.div>
          )}

          {pdbUrl && (
            <motion.div variants={fadeUp} className="data-card p-5">
              <h3 className="font-semibold text-text-primary mb-4">Cleaned Structure</h3>
              <DockingViewer pdbId="" pdbUrl={pdbUrl} pdbUrlFormat="pdb" ligandPdb="" />
            </motion.div>
          )}

          <motion.div variants={fadeUp} className="data-card p-5">
            <h3 className="font-semibold text-text-primary mb-4">Pocket Detection Results</h3>

            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-medium text-text-primary">fpocket (local)</h4>
                <span className="text-xs text-text-muted bg-surface-1 px-2 py-0.5 rounded">{result.fpocket_pockets.length} pockets</span>
              </div>
              {result.fpocket_pockets.length === 0 ? (
                <p className="text-xs text-text-muted">No pockets detected</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-glass-border text-text-muted text-left">
                        <th className="pb-1 font-medium">#</th>
                        <th className="pb-1 font-medium">Druggability</th>
                        <th className="pb-1 font-medium">Volume (³)</th>
                        <th className="pb-1 font-medium">Area (²)</th>
                        <th className="pb-1 font-medium">Residues</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.fpocket_pockets.map((p) => (
                        <tr key={p.id} className="border-b border-glass-border/50">
                          <td className="py-1 text-accent-cyan font-mono">{p.id}</td>
                          <td className="py-1 font-mono">{p.druggability_score.toFixed(3)}</td>
                          <td className="py-1">{p.volume.toFixed(1)}</td>
                          <td className="py-1">{p.area.toFixed(1)}</td>
                          <td className="py-1">{p.num_residues}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-medium text-text-primary">CASTp (remote)</h4>
                <span className="text-xs text-text-muted bg-surface-1 px-2 py-0.5 rounded">{result.castp_pockets.length} pockets</span>
              </div>
              {result.castp_pockets.length === 0 ? (
                <p className="text-xs text-text-muted">No pockets returned</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-glass-border text-text-muted text-left">
                        <th className="pb-1 font-medium">#</th>
                        <th className="pb-1 font-medium">SA Area (²)</th>
                        <th className="pb-1 font-medium">SA Volume (³)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.castp_pockets.map((p) => (
                        <tr key={p.id} className="border-b border-glass-border/50">
                          <td className="py-1 text-accent-cyan font-mono">{p.id}</td>
                          <td className="py-1">{p.area_sa}</td>
                          <td className="py-1">{p.volume_sa}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </div>
  );
}

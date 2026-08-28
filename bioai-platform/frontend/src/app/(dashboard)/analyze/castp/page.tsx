'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { CircleNotch as LoaderCircle, MagnifyingGlass as Search, Funnel as Filter, Dna } from '@phosphor-icons/react';
import { fadeUp, stagger } from '@/lib/animations';
import { runCastp, runCastpSequence, type CastpResult } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import { DockingViewer } from '@/components/DockingViewer';
import { BackButton, PageHeader, CriticalButton, FlatInput } from '@/components/ui';
import { AIResultSummary } from '@/components/results/AIResultSummary';

type InputMode = 'pdb_id' | 'sequence';

export default function CastpPage() {
  const [mode, setMode] = useState<InputMode>('pdb_id');
  const [pdbId, setPdbId] = useState('');
  const [sequence, setSequence] = useState('');
  const [probeRadius, setProbeRadius] = useState(1.4);
  const [result, setResult] = useState<CastpResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showResidues, setShowResidues] = useState<number | null>(null);
  const audit = useAuditTrail();

  const canSubmit = mode === 'pdb_id' ? pdbId.trim().length > 0 : sequence.trim().length >= 10;

  const handleAnalyze = async () => {
    if (mode === 'pdb_id' && !pdbId.trim()) return;
    if (mode === 'sequence' && sequence.trim().length < 10) return;

    const label = mode === 'pdb_id' ? `pdb:${pdbId.trim().toUpperCase()}` : `seq:${sequence.trim().length}aa`;
    audit.emitStarted('castp_analyze', 'CASTp', label);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = mode === 'pdb_id'
        ? await runCastp(pdbId.trim().toUpperCase(), probeRadius)
        : await runCastpSequence(sequence.trim(), probeRadius);
      setResult(res);
      audit.emitSuccess('castp_analyze', 'CASTp', label, `${res.pockets.length} pockets`);
    } catch (err: unknown) {
      const msg = extractErrorMessage(err, 'Analysis failed');
      audit.emitFailed('castp_analyze', 'CASTp', label, msg);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl">
      <BackButton />
      <PageHeader
        title="CASTp Pocket Analysis"
        subtitle="Identify binding pockets and cavities in protein structures. Accepts PDB IDs or raw amino acid sequences (auto-predicted via ESMFold)."
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
              onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
              placeholder="PDB ID (e.g. 1TIM, 4HHB, 1FME)"
              className="flex-1"
            />
            <CriticalButton onClick={handleAnalyze} disabled={loading || !pdbId.trim()}>
              {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              Analyze
            </CriticalButton>
          </div>
        ) : (
          <div>
            <textarea
              value={sequence}
              onChange={(e) => { setSequence(e.target.value); setResult(null); setError(null); }}
              placeholder="Paste amino acid sequence (10–768 residues, e.g. MVSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICTTGKLPVPWPTL..."
              rows={4}
              className="w-full bg-surface-0 border border-glass-border rounded-lg p-3 text-sm font-mono text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-cyan/50 resize-none"
            />
            <div className="flex items-center justify-between mt-2">
              <span className="text-xs text-text-muted">
                {sequence.trim().length > 0 ? `${sequence.trim().replace(/[\s\n]/g, '').length} residues` : 'Min 10 residues'}
              </span>
              <CriticalButton onClick={handleAnalyze} disabled={loading || sequence.trim().length < 10}>
                {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                {loading ? 'Predicting & Analyzing...' : 'Predict Structure & Analyze'}
              </CriticalButton>
            </div>
            <p className="text-[10px] text-text-muted mt-2">
              Sequence mode: ESMFold predicts the 3D structure, then CASTp identifies pockets. Takes ~15–60s.
            </p>
          </div>
        )}

        <div className="mt-4">
          <label className="block text-xs text-text-muted mb-2">
            Probe radius: {probeRadius.toFixed(1)} Å
          </label>
          <input
            type="range"
            min={0.5}
            max={5.0}
            step={0.1}
            value={probeRadius}
            onChange={(e) => setProbeRadius(parseFloat(e.target.value))}
            className="w-full h-1.5 bg-surface-1 rounded-lg appearance-none cursor-pointer accent-accent-cyan"
          />
          <div className="flex justify-between text-[10px] text-text-muted mt-1">
            <span>0.5</span>
            <span>Standard (1.4)</span>
            <span>5.0</span>
          </div>
        </div>

        {mode === 'pdb_id' && (
          <div className="flex gap-3 mt-3">
            {['1TIM', '4HHB', '1FME'].map((id) => (
              <button
                key={id}
                onClick={() => { setPdbId(id); setError(null); setResult(null); }}
                className="text-xs text-accent-cyan hover:text-accent-cyan/80 underline"
              >
                {id}
              </button>
            ))}
          </div>
        )}
      </motion.div>

      {error && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-4 border border-error/20 mb-4">
          <p className="text-sm text-error">{error}</p>
        </motion.div>
      )}

      {result && (
        <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-4">
          <AIResultSummary toolName="castp" result={result as unknown as Record<string, unknown>} />
          <motion.div variants={fadeUp} className="data-card p-5">
            <h3 className="font-semibold text-text-primary mb-1">Structure Viewer</h3>
            <p className="text-xs text-text-muted mb-4">
              {result.pdb_id.toUpperCase()} · {result.total_residues} residues · {result.pockets.length} pockets detected
              {result.sequence_source && (
                <span className="ml-2 px-1.5 py-0.5 bg-accent-cyan/10 text-accent-cyan rounded text-[10px]">
                  {result.sequence_source === 'sequence_esmfold' ? 'ESMFold predicted' : result.sequence_source}
                </span>
              )}
            </p>
            <DockingViewer pdbId={result.pdb_id} ligandPdb="" />
          </motion.div>

          <motion.div variants={fadeUp} className="data-card p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-text-primary">Detected Pockets</h3>
              <span className="text-xs text-text-muted bg-surface-1 px-2 py-1 rounded">
                <Filter className="w-3 h-3 inline mr-1" />
                {result.pockets.length} total
              </span>
            </div>

            {result.pockets.length === 0 ? (
              <p className="text-sm text-text-muted">No significant pockets detected with this probe radius.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-glass-border text-text-muted text-left text-xs">
                      <th className="pb-2 font-medium">#</th>
                      <th className="pb-2 font-medium">SA Area (Å²)</th>
                      <th className="pb-2 font-medium">SA Volume (Å³)</th>
                      <th className="pb-2 font-medium">Residues</th>
                      <th className="pb-2 font-medium">Radius (Å)</th>
                      <th className="pb-2 font-medium"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.pockets.map((p) => (
                      <>
                        <tr key={p.id} className="border-b border-glass-border/50 hover:bg-surface-1 transition-colors">
                          <td className="py-2 text-accent-cyan font-mono">{p.id}</td>
                          <td className="py-2">{p.area_sa.toLocaleString()}</td>
                          <td className="py-2">{p.volume_sa.toLocaleString()}</td>
                          <td className="py-2 font-mono text-xs">{p.num_residues}</td>
                          <td className="py-2">{p.radius.toFixed(1)}</td>
                          <td className="py-2">
                            <button
                              onClick={() => setShowResidues(showResidues === p.id ? null : p.id)}
                              className="text-xs text-accent-cyan hover:underline"
                            >
                              {showResidues === p.id ? 'Hide' : 'Show residues'}
                            </button>
                          </td>
                        </tr>
                        {showResidues === p.id && (
                          <tr key={`${p.id}-res`}>
                            <td colSpan={6} className="py-2 px-3 bg-surface-0">
                              <div className="flex flex-wrap gap-1">
                                {p.residues.map((r) => (
                                  <span key={r} className="text-[10px] font-mono bg-surface-1 px-1.5 py-0.5 rounded text-text-secondary">
                                    {r}
                                  </span>
                                ))}
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </div>
  );
}

'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { ArrowLeft, LoaderCircle, FlaskConical, CheckCircle, XCircle, AlertTriangle, Hexagon } from 'lucide-react';
import { fadeUp } from '@/lib/animations';
import { runDocking, getDockingStatus } from '@/lib/api';
import type { DockingResult } from '@/lib/api';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import { DockingViewer } from '@/components/DockingViewer';
import { InteractionPanel } from '@/components/InteractionPanel';

const PDB_EXAMPLES = ['1TIM', '4HHB', '1A42', '2XAB'];
const SMILES_EXAMPLES = [
  { label: 'Aspirin', value: 'CC(=O)Oc1ccccc1C(=O)O' },
  { label: 'Caffeine', value: 'CN1C=NC2=C1C(=O)N(C(=O)N2C)C' },
  { label: 'Ibuprofen', value: 'CC(C)Cc1ccc(cc1)C(C)C(=O)O' },
];

function affinityColor(affinity: number | null): string {
  if (affinity === null) return 'text-text-muted';
  if (affinity <= -8) return 'text-green-400';
  if (affinity <= -5) return 'text-amber-400';
  return 'text-red-400';
}

export default function DockingPage() {
  const router = useRouter();
  const searchParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
  const [pdbId, setPdbId] = useState(searchParams?.get('pdb_id') || '');
  const [pdbUrl, setPdbUrl] = useState(searchParams?.get('pdb_url') || '');
  const [smiles, setSmiles] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);
  const audit = useAuditTrail();
  const [result, setResult] = useState<DockingResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

  const startDocking = async () => {
    const hasPdbId = pdbId.trim().length > 0;
    const hasPdbUrl = pdbUrl.trim().length > 0;
    if ((!hasPdbId && !hasPdbUrl) || !smiles.trim()) return;
    const inputSummary = hasPdbId ? `pdb:${pdbId.trim().toUpperCase()}` : `url:${pdbUrl.trim().slice(0, 60)}`;
    audit.emitStarted('docking_run', 'AutoDock Vina', inputSummary);
    setLoading(true);
    setError(null);
    setResult(null);
    setJobId(null);
    try {
      const { job_id } = await runDocking(pdbId.trim().toUpperCase(), smiles.trim(), pdbUrl.trim() || undefined);
      setJobId(job_id);
      setPolling(true);
      audit.emitSuccess('docking_run', 'AutoDock Vina', inputSummary, `job_id:${job_id}`);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Failed to start docking';
      audit.emitFailed('docking_run', 'AutoDock Vina', inputSummary, errMsg);
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  const poll = useCallback(async () => {
    if (!jobId) return;
    try {
      const status = await getDockingStatus(jobId);
      setResult(status);
      if (status.status === 'complete' || status.status === 'failed') {
        setPolling(false);
      }
    } catch {
      setPolling(false);
      setError('Failed to check docking status');
    }
  }, [jobId]);

  useEffect(() => {
    if (!polling) return;
    const interval = setInterval(poll, 3000);
    return () => clearInterval(interval);
  }, [polling, poll]);

  useEffect(() => {
    if (jobId) poll();
  }, [jobId, poll]);

  const statusIcon = () => {
    if (!result) return null;
    if (result.status === 'complete') return <CheckCircle className="w-5 h-5 text-green-400" />;
    if (result.status === 'failed') return <XCircle className="w-5 h-5 text-red-400" />;
    return <LoaderCircle className="w-5 h-5 text-accent-cyan animate-spin" />;
  };

  const bestPose = result?.result?.poses?.length
    ? result.result.poses.reduce((a, b) => (a.affinity !== null && (b.affinity === null || a.affinity < b.affinity) ? a : b))
    : null;

  const bestLigandPdb = (() => {
    if (!result?.result?.ligand_pdb) return '';
    return result.result.ligand_pdb;
  })();

  return (
    <div className="max-w-3xl">
      <button onClick={() => router.push('/analyze')} className="flex items-center gap-1 text-sm text-text-muted hover:text-text-primary mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Choose a different operation
      </button>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary mb-1">Molecular Docking</h1>
        <p className="text-sm text-text-secondary">Dock a small molecule (SMILES) into a protein structure (PDB ID) using AutoDock Vina. CPU-based, runs entirely on our server. Expect 1–5 min for completion.</p>
      </motion.div>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-5 mb-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-text-primary mb-1.5">PDB ID</label>
          <input
            type="text"
            value={pdbId}
            onChange={(e) => setPdbId(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === 'Enter' && startDocking()}
            placeholder="e.g. 1TIM"
            className="w-full px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm font-mono bg-surface-1 text-text-primary"
          />
          <div className="flex gap-2 mt-2 flex-wrap">
            <span className="text-xs text-text-muted">Examples:</span>
            {PDB_EXAMPLES.map((pdb) => (
              <button
                key={pdb}
                onClick={() => setPdbId(pdb)}
                className="px-2 py-1 text-xs rounded bg-accent-cyan/10 text-accent-cyan hover:bg-accent-cyan/20 transition font-mono"
              >
                {pdb}
              </button>
            ))}
          </div>
        </div>

        {pdbUrl && (
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">PDB URL (from AlphaFold)</label>
            <input
              type="text"
              value={pdbUrl}
              readOnly
              className="w-full px-4 py-3 rounded-xl border border-accent-cyan/40 text-sm font-mono bg-surface-1 text-accent-cyan"
            />
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-text-primary mb-1.5">Ligand SMILES</label>
          <input
            type="text"
            value={smiles}
            onChange={(e) => setSmiles(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && startDocking()}
            placeholder="e.g. CC(=O)Oc1ccccc1C(=O)O"
            className="w-full px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm font-mono bg-surface-1 text-text-primary"
          />
          <div className="flex gap-2 mt-2 flex-wrap">
            <span className="text-xs text-text-muted">Examples:</span>
            {SMILES_EXAMPLES.map((ex) => (
              <button
                key={ex.label}
                onClick={() => setSmiles(ex.value)}
                className="px-2 py-1 text-xs rounded bg-accent-cyan/10 text-accent-cyan hover:bg-accent-cyan/20 transition"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>

        <button onClick={startDocking} disabled={loading || (!pdbId.trim() && !pdbUrl.trim()) || !smiles.trim() || polling}
          className="btn-primary w-full py-3 flex items-center justify-center gap-2 disabled:opacity-50">
          {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <FlaskConical className="w-4 h-4" />}
          {loading ? 'Starting...' : polling ? 'Running...' : 'Run Docking'}
        </button>
      </motion.div>

      {error && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-4 mb-6 border border-red-400/20">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-400">{error}</p>
          </div>
        </motion.div>
      )}

      {result && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-4">
          <div className="glass-card p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                {statusIcon()}
                <span className="text-sm font-medium text-text-primary capitalize">{result.status}</span>
              </div>
              <span className="text-xs text-text-muted font-mono">{result.result?.pdb_id} + {result.result?.smiles?.slice(0, 20)}...</span>
            </div>

            {result.status === 'failed' && result.error && (
              <div className="p-3 rounded-lg bg-red-400/5 border border-red-400/20 mt-3">
                <pre className="text-xs text-red-400 whitespace-pre-wrap font-mono">{result.error}</pre>
              </div>
            )}
          </div>

          {result.result?.poses && result.result.poses.length > 0 && (
            <div className="glass-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3">Docking Results</h3>

              <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-xs text-text-muted">Best Affinity</p>
                  <p className={`text-lg font-bold font-mono ${affinityColor(bestPose?.affinity ?? null)}`}>
                    {bestPose?.affinity?.toFixed(2) ?? '—'} <span className="text-xs font-normal">kcal/mol</span>
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-surface-1">
                  <p className="text-xs text-text-muted">Poses Generated</p>
                  <p className="text-lg font-bold text-text-primary font-mono">{result.result.num_poses}</p>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-text-muted uppercase border-b border-glass-border">
                      <th className="text-left py-2 pr-4">Pose</th>
                      <th className="text-left py-2 pr-4">Atoms</th>
                      <th className="text-left py-2 pr-4">Affinity (kcal/mol)</th>
                      <th className="text-left py-2">Interactions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-glass-border">
                    {result.result.poses.map((pose) => {
                      const pi = result.result?.pose_interactions?.find((p: { model: number }) => p.model === pose.model);
                      return (
                        <tr key={pose.model} className="text-text-primary">
                          <td className="py-2 pr-4 font-mono">{pose.model}</td>
                          <td className="py-2 pr-4 font-mono">{pose.atoms}</td>
                          <td className={`py-2 pr-4 font-mono ${affinityColor(pose.affinity)}`}>
                            {pose.affinity !== null ? pose.affinity.toFixed(2) : '—'}
                          </td>
                          <td className="py-2 font-mono text-xs text-text-muted">
                            {pi ? `${pi.hbonds}H / ${pi.hydrophobic}HP / ${pi.pi_stacking}π` : '—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {result.result?.interactions && (
            <InteractionPanel interactions={result.result.interactions} />
          )}

          {result.result?.box_center && (
            <div className="glass-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3">Binding Site Search Box</h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-xs text-text-muted mb-1">Center (x, y, z)</p>
                  <p className="text-text-primary font-mono">
                    {result.result.box_center.x.toFixed(2)}, {result.result.box_center.y.toFixed(2)}, {result.result.box_center.z.toFixed(2)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-text-muted mb-1">Size (x, y, z)</p>
                  <p className="text-text-primary font-mono">
                    {result.result.box_size.x}Å, {result.result.box_size.y}Å, {result.result.box_size.z}Å
                  </p>
                </div>
              </div>
            </div>
          )}

          {result.result?.pdb_id && bestLigandPdb && (
            <div className="glass-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                <Hexagon className="w-4 h-4 text-accent-cyan" />
                Structure — Best Pose
              </h3>
              <DockingViewer pdbId={result.result.pdb_id} ligandPdb={bestLigandPdb} />
            </div>
          )}

          {result.result?.vina_log && (
            <details className="glass-card p-5 group">
              <summary className="text-sm font-semibold text-text-primary cursor-pointer list-none flex items-center gap-2">
                Vina Log
              </summary>
              <pre className="mt-3 text-xs text-text-muted font-mono whitespace-pre-wrap max-h-48 overflow-y-auto">
                {result.result.vina_log}
              </pre>
            </details>
          )}
        </motion.div>
      )}
    </div>
  );
}

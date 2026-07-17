"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft, Play, Loader2, Activity } from "lucide-react";
import { fadeUp } from "@/lib/animations";
import { useAuditTrail } from "@/hooks/useAuditTrail";
import { runMD, getMDStatus, type MDSimulationResult } from "@/lib/api";

const MODES = [
  { value: "minimize", label: "Minimization Only", desc: "500 steps, ~5 sec" },
  { value: "equilibrate", label: "Minimize + Equilibrate", desc: "1500 steps, ~30 sec" },
  { value: "production", label: "Full Short Run", desc: "3500 steps, ~2-3 min" },
];

export default function MDPage() {
  const router = useRouter();
  useAuditTrail();

  const [pdbId, setPdbId] = useState("");
  const [mode, setMode] = useState("minimize");
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("");
  const [result, setResult] = useState<MDSimulationResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const poll = useCallback(async (id: string) => {
    try {
      const res = await getMDStatus(id);
      setStatus(res.status);
      if (res.status === "complete" && res.result) {
        setResult(res.result);
        setLoading(false);
      } else if (res.status === "failed") {
        setError(res.error || "Simulation failed");
        setLoading(false);
      }
    } catch {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!jobId) return;
    const start = Date.now();
    const MAX_POLL_MS = 5 * 60 * 1000;
    const iv = setInterval(() => {
      if (Date.now() - start > MAX_POLL_MS) {
        setError("Simulation timed out after 5 minutes");
        setLoading(false);
        clearInterval(iv);
        return;
      }
      poll(jobId);
    }, 2000);
    return () => clearInterval(iv);
  }, [jobId, poll]);

  const handleSubmit = async () => {
    if (!pdbId.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await runMD(pdbId.trim(), mode);
      setJobId(res.job_id);
      setStatus(res.status);
    } catch (e: any) {
      setError(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : e?.response?.data?.detail?.message || e.message || "Submission failed");
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <button onClick={() => router.push("/analyze")}
        className="flex items-center gap-1 text-sm text-text-muted hover:text-text-primary mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Choose a different operation
      </button>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary mb-1">MD Simulation</h1>
        <p className="text-sm text-text-secondary">Implicit solvent molecular dynamics using OpenMM. Free-tier safe with step ceilings and timeouts.</p>
      </motion.div>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show">
        <div className="glass-card p-5">
          <label className="block text-sm text-text-secondary mb-2">PDB ID</label>
          <div className="flex gap-2 mb-4">
            <input
              value={pdbId}
              onChange={(e) => setPdbId(e.target.value.toUpperCase())}
              placeholder="e.g. 1TIM"
              maxLength={4}
              className="w-32 px-3 py-2 rounded-lg bg-surface-1 border border-surface-3 text-text-primary text-sm font-mono uppercase placeholder:text-text-muted focus:outline-none focus:border-accent-cyan"
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            />
          </div>

          <label className="block text-sm text-text-secondary mb-2">Simulation Mode</label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-4">
            {MODES.map((m) => (
              <button key={m.value} onClick={() => setMode(m.value)}
                className={`p-3 rounded-lg border text-left transition-all ${
                  mode === m.value ? "border-accent-cyan bg-accent-cyan/10" : "border-surface-3 bg-surface-1 hover:bg-surface-2"
                }`}>
                <div className="text-sm font-medium text-text-primary">{m.label}</div>
                <div className="text-xs text-text-muted mt-0.5">{m.desc}</div>
              </button>
            ))}
          </div>

          <button onClick={handleSubmit} disabled={loading || !pdbId.trim()}
            className="btn-primary px-4 py-2 text-sm flex items-center gap-2">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {status === "running" || status === "queued" ? `Status: ${status}...` : "Run Simulation"}
          </button>
          <p className="text-xs text-text-muted mt-2">Constraints: implicit solvent, {mode === "minimize" ? "500" : mode === "equilibrate" ? "1500" : "3500"} steps, 5 min timeout.</p>
        </div>
      </motion.div>

      {error && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 glass-card p-4 border border-red-500/30">
          <p className="text-red-400 text-sm">{error}</p>
        </motion.div>
      )}

      {result && (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="mt-6 space-y-4">
          <div className="glass-card p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
              <Activity className="w-4 h-4 text-accent-cyan" /> Simulation Results
            </h3>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
              <div className="bg-surface-1 rounded-lg p-3">
                <div className="text-xs text-text-muted">Final Energy</div>
                <div className="text-lg font-semibold text-text-primary">{result.final_energy_kj_mol}</div>
                <div className="text-xs text-text-muted">kJ/mol</div>
              </div>
              <div className="bg-surface-1 rounded-lg p-3">
                <div className="text-xs text-text-muted">Minimization</div>
                <div className="text-lg font-semibold text-text-primary">{result.minimization_steps}</div>
                <div className="text-xs text-text-muted">steps</div>
              </div>
              <div className="bg-surface-1 rounded-lg p-3">
                <div className="text-xs text-text-muted">Equilibration</div>
                <div className="text-lg font-semibold text-text-primary">{result.equilibration_steps}</div>
                <div className="text-xs text-text-muted">steps</div>
              </div>
              <div className="bg-surface-1 rounded-lg p-3">
                <div className="text-xs text-text-muted">Production</div>
                <div className="text-lg font-semibold text-text-primary">{result.production_steps}</div>
                <div className="text-xs text-text-muted">steps</div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 mb-4">
              <span className="text-xs bg-surface-1 text-text-secondary px-2 py-1 rounded">{result.engine}</span>
              <span className="text-xs bg-surface-1 text-text-secondary px-2 py-1 rounded">{result.forcefield}</span>
              <span className="text-xs bg-surface-1 text-text-secondary px-2 py-1 rounded">{result.implicit_solvent} solvent</span>
              <span className="text-xs bg-surface-1 text-text-secondary px-2 py-1 rounded">{result.temperature_k}K</span>
              <span className="text-xs bg-surface-1 text-text-secondary px-2 py-1 rounded">{result.atom_count} atoms</span>
              <span className="text-xs bg-surface-1 text-text-secondary px-2 py-1 rounded">{result.residue_count} residues</span>
            </div>

            {result.energy.production.length > 0 && (
              <div>
                <h4 className="text-xs text-text-secondary mb-2">Energy Trace</h4>
                <div className="bg-surface-1 rounded-lg p-3 h-40 flex items-end gap-px">
                  {result.energy.production.slice(-60).map((pt, i) => {
                    const energies = result.energy.production.map(p => p.energy);
                    const min = Math.min(...energies);
                    const max = Math.max(...energies);
                    const range = max - min || 1;
                    const height = ((pt.energy - min) / range) * 100;
                    return (
                      <div key={i} className="flex-1 rounded-t bg-accent-cyan/60 hover:bg-accent-cyan transition-colors"
                        style={{ height: `${Math.max(height, 2)}%` }}
                        title={`${pt.step}: ${pt.energy.toFixed(1)} kJ/mol`} />
                    );
                  })}
                </div>
              </div>
            )}

            {result.rmsd.length > 0 && (
              <div className="mt-4">
                <h4 className="text-xs text-text-secondary mb-2">RMSD (vs minimized structure)</h4>
                <div className="bg-surface-1 rounded-lg p-3 h-32 flex items-end gap-px">
                  {result.rmsd.slice(-60).map((pt, i) => {
                    const maxRmsd = Math.max(...result.rmsd.map(r => r.rmsd));
                    const height = maxRmsd > 0 ? (pt.rmsd / maxRmsd) * 100 : 50;
                    return (
                      <div key={i} className="flex-1 rounded-t bg-accent-purple/60 hover:bg-accent-purple transition-colors"
                        style={{ height: `${Math.max(height, 2)}%` }}
                        title={`Frame ${pt.frame}: ${pt.rmsd.toFixed(3)} A`} />
                    );
                  })}
                </div>
              </div>
            )}

            {result.rmsf && result.rmsf.length > 0 && (
              <div className="mt-4">
                <h4 className="text-xs text-text-secondary mb-2">RMSF (per residue)</h4>
                <div className="bg-surface-1 rounded-lg p-3 h-32 flex items-end gap-px">
                  {result.rmsf.slice(-60).map((pt, i) => {
                    const maxRmsf = Math.max(...result.rmsf.map(r => r.rmsf_angstrom));
                    const height = maxRmsf > 0 ? (pt.rmsf_angstrom / maxRmsf) * 100 : 50;
                    return (
                      <div key={i} className="flex-1 rounded-t bg-green-500/60 hover:bg-green-500 transition-colors"
                        style={{ height: `${Math.max(height, 2)}%` }}
                        title={`${pt.residue}: ${pt.rmsf_angstrom.toFixed(3)} A`} />
                    );
                  })}
                </div>
              </div>
            )}

            {result.secondary_structure && (
              <div className="mt-4">
                <h4 className="text-xs text-text-secondary mb-2">Secondary Structure</h4>
                <div className="flex gap-3">
                  <div className="bg-surface-1 rounded-lg px-3 py-2 text-center flex-1">
                    <div className="text-lg font-semibold text-blue-400">{result.secondary_structure.helix}</div>
                    <div className="text-xs text-text-muted">alpha-helix</div>
                  </div>
                  <div className="bg-surface-1 rounded-lg px-3 py-2 text-center flex-1">
                    <div className="text-lg font-semibold text-yellow-400">{result.secondary_structure.sheet}</div>
                    <div className="text-xs text-text-muted">beta-sheet</div>
                  </div>
                  <div className="bg-surface-1 rounded-lg px-3 py-2 text-center flex-1">
                    <div className="text-lg font-semibold text-text-muted">{result.secondary_structure.coil}</div>
                    <div className="text-xs text-text-muted">coil</div>
                  </div>
                </div>
              </div>
            )}

            {result.radius_of_gyration_angstrom !== undefined && (
              <div className="mt-3 flex flex-wrap gap-3">
                <div className="bg-surface-1 rounded-lg px-3 py-2">
                  <div className="text-xs text-text-muted">Radius of Gyration</div>
                  <div className="text-sm font-semibold text-text-primary">{result.radius_of_gyration_angstrom} A</div>
                </div>
                {result.avg_bfactor !== undefined && (
                  <div className="bg-surface-1 rounded-lg px-3 py-2">
                    <div className="text-xs text-text-muted">Avg B-factor</div>
                    <div className="text-sm font-semibold text-text-primary">{result.avg_bfactor} A^2</div>
                  </div>
                )}
              </div>
            )}

            {result.note && (
              <div className="mt-4 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
                <p className="text-xs text-amber-400">{result.note}</p>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </div>
  );
}

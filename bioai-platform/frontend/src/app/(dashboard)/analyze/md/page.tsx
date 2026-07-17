"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft, Play, Loader2, Activity, Clock, Zap, BarChart3, Info } from "lucide-react";
import { fadeUp } from "@/lib/animations";
import { useAuditTrail } from "@/hooks/useAuditTrail";
import { runMD, getMDStatus, type MDSimulationResult } from "@/lib/api";

const MODES = [
  { value: "minimize", label: "Minimization Only", desc: "500 steps, ~5 sec", detail: "Energy minimization using L-BFGS. Removes steric clashes and high-energy contacts." },
  { value: "equilibrate", label: "Minimize + Equilibrate", desc: "1500 steps, ~30 sec", detail: "Minimization followed by NVT equilibration at 300K with Langevin thermostat." },
  { value: "production", label: "Full Short Run", desc: "3500 steps, ~2-3 min", detail: "Complete MD: minimization, equilibration, and 2000-step production run with trajectory recording." },
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

  const selectedMode = MODES.find(m => m.value === mode)!;

  return (
    <div className="max-w-4xl">
      <button onClick={() => router.push("/analyze")}
        className="flex items-center gap-1 text-sm text-text-muted hover:text-text-primary mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Choose a different operation
      </button>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary mb-1">MD Simulation</h1>
        <p className="text-sm text-text-secondary">Implicit solvent molecular dynamics using OpenMM/BioPython. AMBER14 force field, OBC2 generalized Born solvent model.</p>
      </motion.div>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show">
        <div className="glass-card p-5">
          <label className="block text-sm text-text-secondary mb-2">PDB ID</label>
          <div className="flex gap-2 mb-4">
            <input value={pdbId} onChange={(e) => setPdbId(e.target.value.toUpperCase())}
              placeholder="e.g. 1TIM" maxLength={4}
              className="w-32 px-3 py-2 rounded-lg bg-surface-1 border border-surface-3 text-text-primary text-sm font-mono uppercase placeholder:text-text-muted focus:outline-none focus:border-accent-cyan"
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()} />
          </div>

          <label className="block text-sm text-text-secondary mb-2">Simulation Mode</label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-3">
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
          <p className="text-xs text-text-muted mb-3">{selectedMode.detail}</p>

          <button onClick={handleSubmit} disabled={loading || !pdbId.trim()}
            className="btn-primary px-4 py-2 text-sm flex items-center gap-2">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {status === "running" || status === "queued" ? `Status: ${status}...` : "Run Simulation"}
          </button>
        </div>
      </motion.div>

      {error && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 glass-card p-4 border border-red-500/30">
          <p className="text-red-400 text-sm">{error}</p>
        </motion.div>
      )}

      {result && (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="mt-6 space-y-4">
          {/* Simulation Parameters */}
          <div className="glass-card p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
              <Activity className="w-4 h-4 text-accent-cyan" /> {result.engine === "openmm" ? "Simulation Parameters" : "Analysis Parameters"}
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
              <div className="bg-surface-1 rounded-lg p-3">
                <div className="text-xs text-text-muted">Engine</div>
                <div className="text-sm font-semibold text-text-primary">{result.engine === "openmm" ? "OpenMM" : "BioPython"}</div>
              </div>
              <div className="bg-surface-1 rounded-lg p-3">
                <div className="text-xs text-text-muted">Force Field</div>
                <div className="text-sm font-semibold text-text-primary">{result.engine === "openmm" ? result.forcefield : "None (structural)"}</div>
              </div>
              <div className="bg-surface-1 rounded-lg p-3">
                <div className="text-xs text-text-muted">Solvent Model</div>
                <div className="text-sm font-semibold text-text-primary">{result.engine === "openmm" ? result.implicit_solvent : "None (static)"}</div>
              </div>
              <div className="bg-surface-1 rounded-lg p-3">
                <div className="text-xs text-text-muted">{result.engine === "openmm" ? "Temperature" : "Mode"}</div>
                <div className="text-sm font-semibold text-text-primary">{result.engine === "openmm" ? `${result.temperature_k} K` : result.mode}</div>
              </div>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: "Atoms", value: result.atom_count },
                { label: "Residues", value: result.residue_count },
                ...(result.engine === "openmm" ? [
                  { label: "Timestep", value: `${result.timestep_fs} fs` },
                  { label: "Elapsed", value: `${result.elapsed_seconds}s` },
                ] : [
                  { label: "Elapsed", value: `${result.elapsed_seconds}s` },
                  { label: "Chains", value: result.chain_count ?? "N/A" },
                ]),
              ].map((p) => (
                <div key={p.label} className="bg-surface-1 rounded-lg p-3">
                  <div className="text-xs text-text-muted">{p.label}</div>
                  <div className="text-sm font-semibold text-text-primary">{p.value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Step Counts — only for OpenMM */}
          {result.engine === "openmm" && (
          <div className="glass-card p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-accent-purple" /> Integration Steps
            </h3>
            <div className="space-y-2">
              {[
                { label: "Minimization (L-BFGS)", steps: result.minimization_steps, total: 500, color: "bg-accent-cyan" },
                { label: "Equilibration (NVT, Langevin)", steps: result.equilibration_steps, total: 1000, color: "bg-accent-purple" },
                { label: "Production (Langevin)", steps: result.production_steps, total: 2000, color: "bg-accent-amber" },
              ].filter(s => s.steps > 0).map((s) => (
                <div key={s.label}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-text-secondary">{s.label}</span>
                    <span className="text-xs font-mono text-text-primary">{s.steps} steps</span>
                  </div>
                  <div className="w-full h-1.5 bg-surface-3 rounded-full">
                    <div className={`h-full rounded-full ${s.color}`} style={{ width: `${(s.steps / s.total) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
          )}

          {/* Energy */}
          {result.engine === "openmm" && (
          <div className="glass-card p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-1 flex items-center gap-2">
              <Zap className="w-4 h-4 text-accent-amber" /> Energy Analysis
            </h3>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div className="bg-surface-1 rounded-lg p-3">
                <div className="text-xs text-text-muted">Final Potential Energy</div>
                <div className="text-lg font-semibold text-text-primary">{result.final_energy_kj_mol} <span className="text-xs text-text-muted">kJ/mol</span></div>
              </div>
              <div className="bg-surface-1 rounded-lg p-3">
                <div className="text-xs text-text-muted">Energy per Atom</div>
                <div className="text-lg font-semibold text-text-primary">
                  {result.atom_count > 0 ? (result.final_energy_kj_mol / result.atom_count).toFixed(2) : "N/A"} <span className="text-xs text-text-muted">kJ/mol/atom</span>
                </div>
              </div>
            </div>
            {result.energy.production.length > 0 && (
              <div>
                <h4 className="text-xs text-text-secondary mb-2">Production Energy Trace ({result.energy.production.length} frames)</h4>
                <div className="bg-surface-1 rounded-lg p-3 h-48 flex items-end gap-px">
                  {result.energy.production.slice(-80).map((pt, i) => {
                    const energies = result.energy.production.map(p => p.energy);
                    const min = Math.min(...energies);
                    const max = Math.max(...energies);
                    const range = max - min || 1;
                    const height = ((pt.energy - min) / range) * 100;
                    return (
                      <div key={i} className="flex-1 rounded-t bg-accent-cyan/60 hover:bg-accent-cyan transition-colors"
                        style={{ height: `${Math.max(height, 2)}%` }}
                        title={`Step ${pt.step}: ${pt.energy.toFixed(1)} kJ/mol`} />
                    );
                  })}
                </div>
                <div className="flex justify-between text-xs text-text-muted mt-1">
                  <span>Min: {Math.min(...result.energy.production.map(p => p.energy)).toFixed(1)} kJ/mol</span>
                  <span>Max: {Math.max(...result.energy.production.map(p => p.energy)).toFixed(1)} kJ/mol</span>
                  <span>Range: {(Math.max(...result.energy.production.map(p => p.energy)) - Math.min(...result.energy.production.map(p => p.energy))).toFixed(1)} kJ/mol</span>
                </div>
              </div>
            )}
            {result.energy.minimization.length > 0 && (
              <div className="mt-3">
                <h4 className="text-xs text-text-secondary mb-2">Minimization Convergence</h4>
                <div className="bg-surface-1 rounded-lg p-3 h-32 flex items-end gap-px">
                  {result.energy.minimization.map((pt, i) => {
                    const energies = result.energy.minimization.map(p => p.energy);
                    const min = Math.min(...energies);
                    const max = Math.max(...energies);
                    const range = max - min || 1;
                    const height = ((pt.energy - min) / range) * 100;
                    return (
                      <div key={i} className="flex-1 rounded-t bg-green-500/60 hover:bg-green-500 transition-colors"
                        style={{ height: `${Math.max(height, 2)}%` }}
                        title={`Step ${pt.step}: ${pt.energy.toFixed(1)} kJ/mol`} />
                    );
                  })}
                </div>
              </div>
            )}
          </div>
          )}

          {/* RMSD */}
          {result.rmsd.length > 0 && (
            <div className="glass-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-1">RMSD — Structural Drift</h3>
              <p className="text-xs text-text-muted mb-3">Root-mean-square deviation vs minimized reference. Lower = more stable.</p>
              <div className="bg-surface-1 rounded-lg p-3 h-40 flex items-end gap-px">
                {result.rmsd.slice(-80).map((pt, i) => {
                  const maxRmsd = Math.max(...result.rmsd.map(r => r.rmsd));
                  const height = maxRmsd > 0 ? (pt.rmsd / maxRmsd) * 100 : 50;
                  return (
                    <div key={i} className="flex-1 rounded-t bg-accent-purple/60 hover:bg-accent-purple transition-colors"
                      style={{ height: `${Math.max(height, 2)}%` }}
                      title={`Frame ${pt.frame}: ${pt.rmsd.toFixed(3)} A`} />
                  );
                })}
              </div>
              <div className="grid grid-cols-3 gap-2 mt-2">
                <div className="text-center">
                  <div className="text-xs text-text-muted">Min RMSD</div>
                  <div className="text-sm font-mono font-medium text-text-primary">{Math.min(...result.rmsd.map(r => r.rmsd)).toFixed(3)} A</div>
                </div>
                <div className="text-center">
                  <div className="text-xs text-text-muted">Max RMSD</div>
                  <div className="text-sm font-mono font-medium text-text-primary">{Math.max(...result.rmsd.map(r => r.rmsd)).toFixed(3)} A</div>
                </div>
                <div className="text-center">
                  <div className="text-xs text-text-muted">Avg RMSD</div>
                  <div className="text-sm font-mono font-medium text-text-primary">{(result.rmsd.reduce((s, r) => s + r.rmsd, 0) / result.rmsd.length).toFixed(3)} A</div>
                </div>
              </div>
            </div>
          )}

          {/* RMSF */}
          {result.rmsf && result.rmsf.length > 0 && (
            <div className="glass-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-1">RMSF — Per-Residue Flexibility</h3>
              <p className="text-xs text-text-muted mb-3">Root-mean-square fluctuation per residue. High = flexible region, low = rigid/core.</p>
              <div className="bg-surface-1 rounded-lg p-3 h-40 flex items-end gap-px">
                {result.rmsf.slice(-80).map((pt, i) => {
                  const maxRmsf = Math.max(...result.rmsf.map(r => r.rmsf_angstrom));
                  const height = maxRmsf > 0 ? (pt.rmsf_angstrom / maxRmsf) * 100 : 50;
                  return (
                    <div key={i} className="flex-1 rounded-t bg-green-500/60 hover:bg-green-500 transition-colors"
                      style={{ height: `${Math.max(height, 2)}%` }}
                      title={`${pt.residue}: ${pt.rmsf_angstrom.toFixed(3)} A`} />
                  );
                })}
              </div>
              <div className="grid grid-cols-3 gap-2 mt-2">
                <div className="text-center">
                  <div className="text-xs text-text-muted">Min RMSF</div>
                  <div className="text-sm font-mono font-medium text-text-primary">{Math.min(...result.rmsf.map(r => r.rmsf_angstrom)).toFixed(3)} A</div>
                </div>
                <div className="text-center">
                  <div className="text-xs text-text-muted">Max RMSF</div>
                  <div className="text-sm font-mono font-medium text-text-primary">{Math.max(...result.rmsf.map(r => r.rmsf_angstrom)).toFixed(3)} A</div>
                </div>
                <div className="text-center">
                  <div className="text-xs text-text-muted">Avg RMSF</div>
                  <div className="text-sm font-mono font-medium text-text-primary">{(result.rmsf.reduce((s, r) => s + r.rmsf_angstrom, 0) / result.rmsf.length).toFixed(3)} A</div>
                </div>
              </div>
            </div>
          )}

          {/* Secondary Structure */}
          {result.secondary_structure && (
            <div className="glass-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3">Secondary Structure Composition</h3>
              <div className="flex gap-3 mb-3">
                {[
                  { label: "alpha-helix", count: result.secondary_structure.helix, color: "bg-blue-400", textColor: "text-blue-400" },
                  { label: "beta-sheet", count: result.secondary_structure.sheet, color: "bg-yellow-400", textColor: "text-yellow-400" },
                  { label: "coil", count: result.secondary_structure.coil, color: "bg-surface-3", textColor: "text-text-muted" },
                ].map((ss) => {
                  const total = result.secondary_structure!.helix + result.secondary_structure!.sheet + result.secondary_structure!.coil;
                  const pct = total > 0 ? ((ss.count / total) * 100).toFixed(1) : "0";
                  return (
                    <div key={ss.label} className="bg-surface-1 rounded-lg px-3 py-2 text-center flex-1">
                      <div className={`text-lg font-semibold ${ss.textColor}`}>{ss.count}</div>
                      <div className="text-xs text-text-muted">{ss.label}</div>
                      <div className="text-xs text-text-muted">{pct}%</div>
                    </div>
                  );
                })}
              </div>
              {/* Visual bar */}
              <div className="w-full h-3 rounded-full overflow-hidden flex">
                {(() => {
                  const total = result.secondary_structure.helix + result.secondary_structure.sheet + result.secondary_structure.coil;
                  if (total === 0) return <div className="w-full bg-surface-3" />;
                  return (
                    <>
                      <div className="bg-blue-400 h-full" style={{ width: `${(result.secondary_structure.helix / total) * 100}%` }} title={`Helix: ${result.secondary_structure.helix}`} />
                      <div className="bg-yellow-400 h-full" style={{ width: `${(result.secondary_structure.sheet / total) * 100}%` }} title={`Sheet: ${result.secondary_structure.sheet}`} />
                      <div className="bg-surface-3 h-full" style={{ width: `${(result.secondary_structure.coil / total) * 100}%` }} title={`Coil: ${result.secondary_structure.coil}`} />
                    </>
                  );
                })()}
              </div>
            </div>
          )}

          {/* Structural Metrics (BioPython fallback) */}
          {result.radius_of_gyration_angstrom !== undefined && (
            <div className="glass-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3">Structural Metrics</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <div className="bg-surface-1 rounded-lg p-3">
                  <div className="text-xs text-text-muted">Radius of Gyration</div>
                  <div className="text-sm font-semibold text-text-primary">{result.radius_of_gyration_angstrom} A</div>
                  <div className="text-xs text-text-muted">Compactness measure</div>
                </div>
                {result.avg_bfactor !== undefined && (
                  <div className="bg-surface-1 rounded-lg p-3">
                    <div className="text-xs text-text-muted">Avg B-factor</div>
                    <div className="text-sm font-semibold text-text-primary">{result.avg_bfactor} A2</div>
                    <div className="text-xs text-text-muted">Atomic displacement</div>
                  </div>
                )}
                {result.chain_count !== undefined && (
                  <div className="bg-surface-1 rounded-lg p-3">
                    <div className="text-xs text-text-muted">Chain Count</div>
                    <div className="text-sm font-semibold text-text-primary">{result.chain_count}</div>
                    <div className="text-xs text-text-muted">Polymer chains</div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Interpretation */}
          <div className="glass-card p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
              <Info className="w-4 h-4 text-accent-cyan" /> Interpretation
            </h3>
            <div className="space-y-2 text-xs text-text-secondary">
              {result.engine === "openmm" && result.rmsd.length > 0 && (() => {
                const lastRmsd = result.rmsd[result.rmsd.length - 1].rmsd;
                const avgRmsd = result.rmsd.reduce((s, r) => s + r.rmsd, 0) / result.rmsd.length;
                return (
                  <>
                    <p><strong className="text-text-primary">Structural Stability:</strong> {lastRmsd < 2.0 ? "The structure remains stable (RMSD < 2.0 A), indicating the force field and implicit solvent model maintain a reasonable conformation." : lastRmsd < 5.0 ? "Moderate structural drift observed. The protein may be exploring conformational space or transitioning from the initial crystal structure." : "Significant structural drift. This may indicate the need for explicit solvent, longer equilibration, or restraints on key residues."}</p>
                    <p><strong className="text-text-primary">Energy Convergence:</strong> {result.energy.production.length > 2 ? `Production energy spans ${Math.min(...result.energy.production.map(p => p.energy)).toFixed(1)} to ${Math.max(...result.energy.production.map(p => p.energy)).toFixed(1)} kJ/mol.` : "Short production run — limited energy statistics."}</p>
                  </>
                );
              })()}
              {result.engine === "biopython_structural" && (
                <p><strong className="text-text-primary">Structural Analysis (No MD):</strong> OpenMM was unavailable. Results are based on static structural analysis of the crystal structure — secondary structure, radius of gyration, B-factors, and bond geometry. This is NOT a dynamics simulation.</p>
              )}
              {result.secondary_structure && (() => {
                const total = result.secondary_structure.helix + result.secondary_structure.sheet + result.secondary_structure.coil;
                const helixPct = total > 0 ? (result.secondary_structure.helix / total) * 100 : 0;
                const sheetPct = total > 0 ? (result.secondary_structure.sheet / total) * 100 : 0;
                const coilPct = total > 0 ? (result.secondary_structure.coil / total) * 100 : 0;
                let desc: string;
                if (helixPct > 40 && sheetPct < 20) desc = "Predominantly alpha-helical — consistent with many globular proteins.";
                else if (sheetPct > 40 && helixPct < 20) desc = "Predominantly beta-sheet — likely a beta-barrel or beta-sandwich fold (e.g. TIM barrel, immunoglobulin).";
                else if (helixPct > 25 && sheetPct > 25) desc = "Mixed alpha/beta fold — common in enzymes and metabolic proteins.";
                else if (coilPct > 60) desc = "High coil content — may indicate flexible loops, linker regions, or intrinsically disordered segments.";
                else desc = "Mixed secondary structure composition.";
                return <p><strong className="text-text-primary">Secondary Structure:</strong> {desc}</p>;
              })()}
            </div>
          </div>

          {result.note && (
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg px-4 py-3">
              <p className="text-xs text-amber-400">{result.note}</p>
            </div>
          )}

          <p className="text-xs text-text-muted text-center">Free-tier: implicit solvent, limited steps. For production MD, use explicit solvent with sufficient sampling.</p>
        </motion.div>
      )}
    </div>
  );
}

"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft, Beaker, Check, X, AlertTriangle, Loader2 } from "lucide-react";
import { fadeUp } from "@/lib/animations";
import { useAuditTrail } from "@/hooks/useAuditTrail";
import { computeADMET, type ADMETResult } from "@/lib/api";

const EXAMPLES = [
  { name: "Aspirin", smiles: "CC(=O)OC1=CC=CC=C1C(=O)O" },
  { name: "Caffeine", smiles: "CN1C=NC2=C1C(=O)N(C(=O)N2C)C" },
  { name: "Ibuprofen", smiles: "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O" },
  { name: "Paracetamol", smiles: "CC(=O)NC1=CC=C(C=C1)O" },
];

export default function ADMETPage() {
  const router = useRouter();
  useAuditTrail();

  const [smiles, setSmiles] = useState("");
  const [result, setResult] = useState<ADMETResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!smiles.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await computeADMET(smiles.trim());
      setResult(res.result);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || "Computation failed");
    } finally {
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
        <h1 className="text-2xl font-bold text-text-primary mb-1">ADMET Descriptors</h1>
        <p className="text-sm text-text-secondary">Compute molecular descriptors from SMILES using RDKit. Lipinski, Veber, QED analysis.</p>
      </motion.div>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show">
        <div className="glass-card p-5">
          <label className="block text-sm text-text-secondary mb-2">SMILES String</label>
          <div className="flex gap-2">
            <input
              value={smiles}
              onChange={(e) => setSmiles(e.target.value)}
              placeholder="e.g. CC(=O)OC1=CC=CC=C1C(=O)O"
              className="flex-1 px-3 py-2 rounded-lg bg-surface-1 border border-surface-3 text-text-primary text-sm font-mono placeholder:text-text-muted focus:outline-none focus:border-accent-cyan"
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            />
            <button
              onClick={handleSubmit}
              disabled={loading || !smiles.trim()}
              className="btn-primary px-4 py-2 text-sm flex items-center gap-2"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Beaker className="w-4 h-4" />}
              Compute
            </button>
          </div>
          <div className="flex flex-wrap gap-2 mt-3">
            {EXAMPLES.map((ex) => (
              <button key={ex.name} onClick={() => setSmiles(ex.smiles)}
                className="text-xs px-2 py-1 rounded bg-surface-2 hover:bg-surface-3 text-text-secondary transition-colors">
                {ex.name}
              </button>
            ))}
          </div>
        </div>
      </motion.div>

      {error && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 glass-card p-4 border border-red-500/30">
          <p className="text-red-400 text-sm">{error}</p>
        </motion.div>
      )}

      {result && (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="mt-6 space-y-4">
          {/* QED Score */}
          <div className="glass-card p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3">Drug-likeness (QED)</h3>
            <div className="flex items-center gap-4">
              <div className="relative w-20 h-20">
                <svg viewBox="0 0 36 36" className="w-20 h-20 -rotate-90">
                  <circle cx="18" cy="18" r="15.9" fill="none" stroke="currentColor" className="text-surface-3" strokeWidth="3" />
                  <circle cx="18" cy="18" r="15.9" fill="none" stroke="currentColor"
                    className={result.qed_score > 0.5 ? "text-green-400" : result.qed_score > 0.3 ? "text-amber-400" : "text-red-400"}
                    strokeWidth="3" strokeDasharray={`${result.qed_score * 100} 100`} />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-lg font-bold text-text-primary">
                  {result.qed_score.toFixed(2)}
                </span>
              </div>
              <div>
                <p className="text-sm text-text-secondary">Quantitative Estimate of Drug-likeness</p>
                <p className="text-xs text-text-muted mt-1">Formula: {result.formula} | MW: {result.molecular_weight}</p>
              </div>
            </div>
          </div>

          {/* Properties Grid */}
          <div className="glass-card p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3">Molecular Properties</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: "MW", value: result.molecular_weight, unit: "g/mol", limit: 500 },
                { label: "LogP", value: result.logp, unit: "", limit: 5 },
                { label: "TPSA", value: result.tpsa, unit: "Å²", limit: 140 },
                { label: "HBD", value: result.hbd, unit: "", limit: 5 },
                { label: "HBA", value: result.hba, unit: "", limit: 10 },
                { label: "Rot. Bonds", value: result.rotatable_bonds, unit: "", limit: 10 },
                { label: "Heavy Atoms", value: result.heavy_atoms, unit: "", limit: Infinity },
                { label: "QED", value: result.qed_score, unit: "", limit: Infinity },
              ].map((p) => (
                <div key={p.label} className="bg-surface-1 rounded-lg p-3">
                  <div className="text-xs text-text-muted">{p.label}</div>
                  <div className="text-lg font-semibold text-text-primary">{p.value}</div>
                  <div className="text-xs text-text-muted">{p.unit}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Lipinski & Veber */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className={`glass-card p-5 border ${result.lipinski.pass ? "border-green-500/30" : "border-amber-500/30"}`}>
              <h3 className="text-sm font-semibold text-text-primary mb-2 flex items-center gap-2">
                {result.lipinski.pass ? <Check className="w-4 h-4 text-green-400" /> : <AlertTriangle className="w-4 h-4 text-amber-400" />}
                Lipinski Rule of Five
              </h3>
              {result.lipinski.violations.length === 0 ? (
                <p className="text-xs text-green-400">All rules satisfied</p>
              ) : (
                <ul className="space-y-1">
                  {result.lipinski.violations.map((v, i) => (
                    <li key={i} className="text-xs text-amber-400 flex items-start gap-1">
                      <X className="w-3 h-3 mt-0.5 shrink-0" />{v}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className={`glass-card p-5 border ${result.veber.pass ? "border-green-500/30" : "border-amber-500/30"}`}>
              <h3 className="text-sm font-semibold text-text-primary mb-2 flex items-center gap-2">
                {result.veber.pass ? <Check className="w-4 h-4 text-green-400" /> : <AlertTriangle className="w-4 h-4 text-amber-400" />}
                Veber Rules
              </h3>
              {result.veber.violations.length === 0 ? (
                <p className="text-xs text-green-400">All rules satisfied</p>
              ) : (
                <ul className="space-y-1">
                  {result.veber.violations.map((v, i) => (
                    <li key={i} className="text-xs text-amber-400 flex items-start gap-1">
                      <X className="w-3 h-3 mt-0.5 shrink-0" />{v}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <p className="text-xs text-text-muted text-center">Predicted by RDKit. For research use only.</p>
        </motion.div>
      )}
    </div>
  );
}

"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft, Brain, Loader2, ExternalLink } from "lucide-react";
import { fadeUp } from "@/lib/animations";
import { useAuditTrail } from "@/hooks/useAuditTrail";
import { predictFunction, getFunctionStatus, type FunctionPredictionResult } from "@/lib/api";

const NAMESPACE_COLORS: Record<string, string> = {
  MF: "text-accent-cyan",
  BP: "text-accent-purple",
  CC: "text-accent-amber",
};

export default function FunctionPage() {
  const router = useRouter();
  useAuditTrail();

  const [pdbId, setPdbId] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("");
  const [result, setResult] = useState<FunctionPredictionResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const poll = useCallback(async (id: string) => {
    try {
      const res = await getFunctionStatus(id);
      setStatus(res.status);
      if (res.status === "complete" && res.result) {
        setResult(res.result);
        setLoading(false);
      } else if (res.status === "failed") {
        setError(res.error || "Prediction failed");
        setLoading(false);
      }
    } catch {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!jobId) return;
    const iv = setInterval(() => poll(jobId), 2000);
    return () => clearInterval(iv);
  }, [jobId, poll]);

  const handleSubmit = async () => {
    if (!pdbId.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await predictFunction(pdbId.trim());
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
        <h1 className="text-2xl font-bold text-text-primary mb-1">Function Prediction</h1>
        <p className="text-sm text-text-secondary">Predict protein function (GO terms) from structure. DeepFRI-inspired analysis.</p>
      </motion.div>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show">
        <div className="glass-card p-5">
          <label className="block text-sm text-text-secondary mb-2">PDB ID</label>
          <div className="flex gap-2">
            <input
              value={pdbId}
              onChange={(e) => setPdbId(e.target.value.toUpperCase())}
              placeholder="e.g. 1TIM"
              maxLength={4}
              className="w-32 px-3 py-2 rounded-lg bg-surface-1 border border-surface-3 text-text-primary text-sm font-mono uppercase placeholder:text-text-muted focus:outline-none focus:border-accent-cyan"
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            />
            <button onClick={handleSubmit} disabled={loading || !pdbId.trim()}
              className="btn-primary px-4 py-2 text-sm flex items-center gap-2">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Brain className="w-4 h-4" />}
              {status === "running" || status === "queued" ? `Status: ${status}...` : "Predict Function"}
            </button>
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
          {/* GO Terms */}
          <div className="glass-card p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3">GO Term Predictions</h3>
            <div className="space-y-2">
              {result.go_terms.sort((a, b) => b.confidence - a.confidence).map((go, i) => (
                <div key={i} className="flex items-center gap-3 bg-surface-1 rounded-lg p-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-text-primary">{go.name}</span>
                      <span className={`text-xs font-mono ${NAMESPACE_COLORS[go.namespace] || "text-text-muted"}`}>
                        {go.namespace}
                      </span>
                    </div>
                    <div className="text-xs text-text-muted mt-0.5">{go.go_id}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-semibold text-text-primary">{(go.confidence * 100).toFixed(1)}%</div>
                    <div className="w-16 h-1.5 bg-surface-3 rounded-full mt-1">
                      <div className="h-full rounded-full bg-accent-cyan" style={{ width: `${go.confidence * 100}%` }} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Saliency Map */}
          {result.saliency.length > 0 && (
            <div className="glass-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3">Residue Importance (Saliency)</h3>
              <p className="text-xs text-text-muted mb-3">Higher values = more important for function prediction</p>
              <div className="bg-surface-1 rounded-lg p-3 overflow-x-auto">
                <div className="flex gap-px min-w-max">
                  {result.saliency.map((score, i) => {
                    const intensity = Math.round(score * 255);
                    const r = Math.round(59 + (220 - 59) * score);
                    const g = Math.round(130 + (50 - 130) * score);
                    const b = Math.round(246 + (80 - 246) * score);
                    return (
                      <div key={i} className="w-1.5 h-8 rounded-sm cursor-pointer hover:ring-1 hover:ring-white/50 transition-all"
                        style={{ backgroundColor: `rgb(${r},${g},${b})` }}
                        title={`Residue ${i + 1}: ${score.toFixed(3)}`} />
                    );
                  })}
                </div>
              </div>
              <div className="flex justify-between text-xs text-text-muted mt-1">
                <span>N-terminus</span>
                <span>C-terminus</span>
              </div>
            </div>
          )}

          {/* Metadata */}
          <div className="glass-card p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-text-muted">Method: {result.method}</p>
                <p className="text-xs text-text-muted">Sequence: {result.sequence_length} residues</p>
              </div>
              <a href={`https://www.rcsb.org/structure/${result.pdb_id}`} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 text-xs text-accent-cyan hover:underline">
                View on RCSB <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <p className="text-xs text-text-muted mt-2 italic">{result.note}</p>
          </div>
        </motion.div>
      )}
    </div>
  );
}

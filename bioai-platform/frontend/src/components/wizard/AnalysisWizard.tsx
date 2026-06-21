"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Dna, ArrowRight, LoaderCircle, FileText, CircleCheck, Circle } from "lucide-react";
import { PipelineResults } from "@/components/results/PipelineResults";

type WizardStep = "input" | "running";

const ALL_STEPS = [
  { id: "blast",    label: "BLAST & UniProt", essential: true },
  { id: "msa",      label: "Multiple Sequence Alignment", essential: false },
  { id: "phylo",    label: "Phylogenetic Tree", essential: false },
  { id: "domains",  label: "Domain Architecture", essential: false },
  { id: "interpret",label: "AI Interpretation", essential: true },
];

export function AnalysisWizard() {
  const [currentStep, setCurrentStep] = useState<WizardStep>("input");
  const [sequence, setSequence] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [enabledSteps, setEnabledSteps] = useState<string[]>(
    ALL_STEPS.filter(s => s.essential).map(s => s.id)
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  function toggleStep(id: string) {
    setEnabledSteps(prev =>
      prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]
    );
  }

  async function handleSubmit() {
    if (!sequence.trim()) { setError("Paste a protein sequence first."); return; }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/backend/api/pipeline/v2/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sequence: sequence.trim(), steps: enabledSteps }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Submit failed");
      const data = await res.json();
      setJobId(data.job_id);
      setCurrentStep("running");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="flex items-center gap-2 mb-8 justify-center">
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs border transition-all ${
          currentStep === "input"
            ? "border-accent-cyan bg-accent-cyan/10 text-accent-cyan"
            : "border-accent-cyan/40 bg-accent-cyan/5 text-accent-cyan/60"
        }`}>
          {currentStep === "running" ? <CircleCheck className="w-3.5 h-3.5" /> : <Dna className="w-3.5 h-3.5" />}
          Sequence Input
        </div>
        <div className="w-8 h-px bg-glass-border" />
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs border transition-all ${
          currentStep === "running"
            ? "border-accent-cyan bg-accent-cyan/10 text-accent-cyan"
            : "border-glass-border text-text-muted"
        }`}>
          {done ? <CircleCheck className="w-3.5 h-3.5" /> : currentStep === "running" ? <LoaderCircle className="w-3.5 h-3.5 animate-spin" /> : <Circle className="w-3.5 h-3.5" />}
          Results
        </div>
      </div>

      <AnimatePresence mode="wait">
        {currentStep === "input" ? (
          <motion.div
            key="input"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="glass-card p-6"
          >
            <h2 className="text-xl font-semibold text-text-primary mb-1">Paste Your Sequence</h2>
            <p className="text-sm text-text-secondary mb-4">FASTA or raw amino acid sequence. Choose which analyses to run.</p>

            <div className="flex gap-2 flex-wrap mb-4">
              {DEMOS.map(({ label, seq }) => (
                <button key={label} onClick={() => setSequence(seq)}
                  className="px-3 py-1 text-xs rounded-full bg-accent-cyan/10 border border-accent-cyan/30 text-accent-cyan hover:bg-accent-cyan/20 transition">
                  {label}
                </button>
              ))}
            </div>

            <textarea
              value={sequence}
              onChange={e => setSequence(e.target.value)}
              rows={5}
              placeholder={">MyProtein\nMEEPQSDPSVEPPLSQETFSD..."}
              className="w-full px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition font-mono text-sm resize-none bg-surface-1 text-text-primary"
            />

            {/* Step checkboxes */}
            <div className="mt-4 space-y-2">
              <p className="text-xs font-semibold text-text-muted uppercase tracking-wider">Analysis Steps</p>
              {ALL_STEPS.map(s => (
                <label key={s.id} className="flex items-center gap-3 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={enabledSteps.includes(s.id)}
                    onChange={() => toggleStep(s.id)}
                    disabled={s.essential}
                    className="w-4 h-4 rounded border-glass-border bg-surface-1 accent-accent-cyan disabled:opacity-60"
                  />
                  <span className={`text-sm ${s.essential ? "text-text-primary" : "text-text-secondary group-hover:text-text-primary transition"}`}>
                    {s.label}
                    {s.essential && <span className="text-xs text-text-muted ml-1">(required)</span>}
                  </span>
                </label>
              ))}
            </div>

            {error && <p className="text-error text-sm mt-3">{error}</p>}

            <button onClick={handleSubmit} disabled={loading}
              className="w-full btn-primary py-3 flex items-center justify-center gap-2 mt-4 disabled:opacity-40">
              {loading ? <><LoaderCircle className="w-4 h-4 animate-spin" /> Submitting&hellip;</> : <><ArrowRight className="w-4 h-4" /> Run Analysis</>}
            </button>
          </motion.div>
        ) : (
          <motion.div
            key="running"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
          >
            {jobId && <PipelineResults jobId={jobId} steps={enabledSteps} onComplete={() => setDone(true)} />}
            {done && (
              <div className="mt-4 flex gap-3">
                <a href={`/report/${jobId}`}
                  className="flex-1 text-center py-2.5 rounded-xl border border-accent-cyan/30 text-accent-cyan text-sm hover:bg-accent-cyan/10 transition">
                  <FileText className="w-4 h-4 inline mr-1.5" />Export Report
                </a>
                {jobId && <a href={`/jobs/${jobId}`}
                  className="flex-1 text-center py-2.5 rounded-xl border border-glass-border text-text-secondary text-sm hover:bg-surface-1 transition">
                  View Full Results
                </a>}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

const DEMOS = [
  { label: "p53 (TP53)", seq: "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYQGLNGTVNLFGQTVDDLYKLLPENNVLSPLPSQAMDDLML" },
  { label: "Insulin", seq: "MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKTRREAEDLQVGQVELGGGPGAGSLQPLALEGSLQKRGIVEQCCTSICSLYQLENYCN" },
  { label: "BRCA1", seq: "MDLSALRVEEVQNVINAMQKILECPICLELIKEPVSTKCDHIFCKFCMLKLLNQKKGPSQCPLCKNDITKRSLQESTRFSQLVEELLKIICAFQLDTGLEYANSYNFAKKENNSPEHLKDEVSIIQSMGYRNACKESSLSSSG" },
];

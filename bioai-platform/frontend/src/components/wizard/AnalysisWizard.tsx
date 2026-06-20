"use client";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Dna, Search, GitBranch, FileText, LoaderCircle, ArrowRight } from "lucide-react";

type WizardStep = "input" | "blast" | "enrich" | "report";

const STEPS: { id: WizardStep; label: string; icon: typeof Dna }[] = [
  { id: "input",  label: "Sequence Input",     icon: Dna },
  { id: "blast",  label: "BLAST + UniProt",    icon: Search },
  { id: "enrich", label: "Pathway & Domains",  icon: GitBranch },
  { id: "report", label: "AI Report",          icon: FileText },
];

export function AnalysisWizard() {
  const [currentStep, setCurrentStep] = useState<WizardStep>("input");
  const [sequence, setSequence]       = useState("");
  const [jobId,    setJobId]          = useState<string | null>(null);
  const [blastHit, setBlastHit]       = useState<any>(null);
  const [loading,  setLoading]        = useState(false);
  const [error,    setError]          = useState<string | null>(null);

  const stepIndex = STEPS.findIndex(s => s.id === currentStep);

  const go = (step: WizardStep) => { setError(null); setCurrentStep(step); };

  async function handleSubmit() {
    if (!sequence.trim()) { setError("Paste a protein sequence first."); return; }
    setLoading(true);
    try {
      const res = await fetch("/api/backend/api/pipelines/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sequence: sequence.trim(), demo_mode: false }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Submit failed");
      const data = await res.json();
      setJobId(data.job_id);
      go("blast");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto p-6">
      <div className="flex items-center gap-2 mb-8">
        {STEPS.map((step, i) => (
          <div key={step.id} className="flex items-center gap-2 flex-1">
            <button
              onClick={() => i < stepIndex && go(step.id)}
              className={`w-9 h-9 rounded-full border-2 flex items-center justify-center text-sm transition-all ${
                i === stepIndex
                  ? "border-accent-cyan bg-accent-cyan/10 text-accent-cyan"
                  : i < stepIndex
                  ? "border-accent-cyan/60 bg-accent-cyan/5 text-accent-cyan/60 cursor-pointer"
                  : "border-glass-border text-text-muted cursor-not-allowed"
              }`}
            >
              <step.icon className="w-4 h-4" />
            </button>
            <span className={`text-xs hidden sm:block ${i === stepIndex ? "text-accent-cyan" : "text-text-muted"}`}>
              {step.label}
            </span>
            {i < STEPS.length - 1 && (
              <div className={`flex-1 h-px ${i < stepIndex ? "bg-accent-cyan/40" : "bg-glass-border"}`} />
            )}
          </div>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={currentStep}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.2 }}
          className="glass-card p-6"
        >
          {currentStep === "input" && (
            <StepInput
              sequence={sequence}
              onSequence={setSequence}
              onSubmit={handleSubmit}
              loading={loading}
              error={error}
            />
          )}
          {currentStep === "blast" && jobId && (
            <StepBlast jobId={jobId} onHit={h => { setBlastHit(h); go("enrich"); }} />
          )}
          {currentStep === "enrich" && jobId && (
            <StepEnrich jobId={jobId} hit={blastHit} onNext={() => go("report")} />
          )}
          {currentStep === "report" && jobId && (
            <StepReport jobId={jobId} />
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

function StepInput({ sequence, onSequence, onSubmit, loading, error }: any) {
  const DEMOS: Record<string, string> = {
    "p53 (TP53)":     "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYQGLNGTVNLFGQTVDDLYKLLPENNVLSPLPSQAMDDLML",
    "Insulin":        "MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKTRREAEDLQVGQVELGGGPGAGSLQPLALEGSLQKRGIVEQCCTSICSLYQLENYCN",
    "BRCA1 fragment": "MDLSALRVEEVQNVINAMQKILECPICLELIKEPVSTKCDHIFCKFCMLKLLNQKKGPSQCPLCKNDITKRSLQESTRFSQLVEELLKIICAFQLDTGLEYANSYNFAKKENNSPEHLKDEVSIIQSMGYRNACKESSLSSSG",
  };

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-text-primary">Paste Your Protein Sequence</h2>
      <p className="text-sm text-text-secondary">FASTA or raw amino acid sequence. We&apos;ll run the full pipeline automatically.</p>

      <div className="flex gap-2 flex-wrap">
        {Object.entries(DEMOS).map(([label, seq]) => (
          <button key={label} onClick={() => onSequence(seq)}
            className="px-3 py-1 text-xs rounded-full bg-accent-cyan/10 border border-accent-cyan/30 text-accent-cyan hover:bg-accent-cyan/20 transition">
            {label}
          </button>
        ))}
      </div>

      <textarea
        value={sequence}
        onChange={e => onSequence(e.target.value)}
        rows={6}
        placeholder={">MyProtein\nMEEPQSDPSVEPPLSQETFSD..."}
        className="w-full px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition font-mono text-sm resize-none bg-surface-1 text-text-primary"
      />

      {error && <p className="text-error text-sm">{error}</p>}

      <button onClick={onSubmit} disabled={loading}
        className="w-full btn-primary py-3 flex items-center justify-center gap-2 disabled:opacity-40">
        {loading ? <><LoaderCircle className="w-4 h-4 animate-spin" /> Submitting&hellip;</> : <><ArrowRight className="w-4 h-4" /> Run Full Analysis</>}
      </button>
    </div>
  );
}

function StepBlast({ jobId, onHit }: { jobId: string; onHit: (h: any) => void }) {
  const [status, setStatus] = useState("Submitting to NCBI BLAST&hellip;");
  const [progress, setProgress] = useState(10);

  useEffect(() => {
    const POLL_MAP: Record<string, [string, number]> = {
      queued:              ["Queued&hellip;", 5],
      submitted_to_ncbi:  ["Submitted to NCBI BLAST", 15],
      polling_ncbi:       ["Polling NCBI (may take 1&ndash;2 min)&hellip;", 35],
      parsing:            ["Parsing BLAST results&hellip;", 55],
      interpreting:       ["AI interpretation&hellip;", 70],
      pathway_enrichment: ["Pathway enrichment&hellip;", 85],
      fetching_alphafold: ["Fetching AlphaFold structure&hellip;", 92],
      complete:           ["Complete!", 100],
    };

    const iv = setInterval(async () => {
      const r = await fetch(`/api/backend/api/jobs/${jobId}`);
      const d = await r.json();
      const [msg, pct] = POLL_MAP[d.status] ?? ["Running&hellip;", 50];
      setStatus(msg);
      setProgress(pct);
      if (d.status === "complete") {
        clearInterval(iv);
        onHit(d.context_json?.blast?.hits?.[0] ?? null);
      }
    }, 3000);
    return () => clearInterval(iv);
  }, [jobId]);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-text-primary">Running BLAST + UniProt</h2>
      <div className="space-y-2">
        <div className="flex justify-between text-sm text-text-secondary">
          <span>{status}</span><span>{progress}%</span>
        </div>
        <div className="w-full h-2 bg-surface-1 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-accent-cyan rounded-full"
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.5 }}
          />
        </div>
      </div>
      <p className="text-xs text-text-muted">NCBI BLAST typically takes 60&ndash;120 seconds on the free tier.</p>
    </div>
  );
}

function StepEnrich({ hit, onNext }: any) {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-text-primary">Enrichment &amp; Domains</h2>
      {hit && (
        <div className="bg-surface-1 rounded-xl p-4 space-y-1">
          <p className="text-accent-cyan font-mono text-sm">{hit.accession}</p>
          <p className="text-text-secondary text-sm">{hit.description}</p>
          <p className="text-text-muted text-xs">E-value: {hit.evalue?.toExponential?.(2) ?? hit.evalue}</p>
        </div>
      )}
      <p className="text-text-secondary text-sm">Pathway enrichment and domain analysis ran as part of the pipeline.</p>
      <button onClick={onNext} className="w-full btn-primary py-3">
        View AI Report &rarr;
      </button>
    </div>
  );
}

function StepReport({ jobId }: { jobId: string }) {
  const [report, setReport] = useState<string>("");
  useEffect(() => {
    fetch(`/api/backend/api/jobs/${jobId}`)
      .then(r => r.json())
      .then(d => setReport(d.context_json?.ai_interpretation ?? "No report generated."));
  }, [jobId]);

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-text-primary">AI Interpretation</h2>
      <div className="bg-surface-1 rounded-xl p-4 text-sm text-text-secondary leading-relaxed font-mono whitespace-pre-wrap max-h-64 overflow-y-auto">
        {report || "Loading&hellip;"}
      </div>
      <a href={`/jobs/${jobId}`}
        className="block text-center py-2 rounded-xl border border-accent-cyan/30 text-accent-cyan text-sm hover:bg-accent-cyan/10 transition">
        Open Full Results &rarr;
      </a>
    </div>
  );
}

"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Dna, ArrowRight, CircleNotch as LoaderCircle, FileText, CheckCircle as CircleCheck, Circle, Copy } from '@phosphor-icons/react';
import toast from 'react-hot-toast';
import { ClayToggle } from "@/components/ui/ClayToggle";
import { ClaySegmented } from "@/components/ui/ClaySegmented";
import { CriticalButton } from "@/components/ui/CriticalButton";
import { PipelineResults } from "@/components/results/PipelineResults";
import { createShareLink, getPipelineStatusV2 } from "@/lib/api";
import { getSupabase } from "@/lib/supabase";
import { extractErrorMessage } from "@/lib/errors";
import { shareResult, buildShareDetails } from "@/lib/share";

type WizardStep = "input" | "running";
type AlignMode = "global" | "local";

function getStoredAlignMode(): AlignMode {
  if (typeof window === "undefined") return "global";
  return sessionStorage.getItem("blast_align_mode") === "local" ? "local" : "global";
}

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
  const [alignMode, setAlignMode] = useState<AlignMode>(getStoredAlignMode);
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
      const supabase = getSupabase();
      const { data: { session } } = await supabase.auth.getSession();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (session?.access_token) {
        headers["Authorization"] = `Bearer ${session.access_token}`;
      }
      const res = await fetch("/api/backend/api/pipeline/v2/run", {
        method: "POST",
        headers,
        body: JSON.stringify({ sequence: sequence.trim(), steps: enabledSteps, alignment_mode: alignMode }),
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

  async function handleShare() {
    if (!jobId) return;
    try {
      const { url } = await createShareLink(jobId);
      let details;
      try {
        const status = await getPipelineStatusV2(jobId);
        details = buildShareDetails(status?.context ?? null);
      } catch {
        // Details are optional — share still works without them.
      }
      const mode = await shareResult(url, details);
      toast.success(mode === 'shared' ? 'Shared successfully!' : 'Share message copied to clipboard!');
    } catch (e) {
      toast.error(extractErrorMessage(e, 'Failed to create share link'));
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

            {/* Alignment mode — clay: discrete, low-stakes choice */}
            <div className="mt-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 rounded-xl border border-glass-border bg-surface-0/60 p-3">
              <div>
                <p className="text-xs font-semibold text-text-primary">Alignment mode</p>
                <p className="text-[11px] text-text-muted mt-0.5">
                  {alignMode === 'global'
                    ? 'Global — full-length MSA across all sequences (Clustal Omega).'
                    : 'Local — full MSA plus a Smith-Waterman refinement of query vs top hit.'}
                </p>
              </div>
              <ClaySegmented
                options={[
                  { value: 'global', label: 'Global' },
                  { value: 'local', label: 'Local' },
                ]}
                value={alignMode}
                onChange={(v) => { setAlignMode(v as AlignMode); sessionStorage.setItem('blast_align_mode', v); }}
              />
            </div>

            {/* Analysis step toggles — clay: discrete, low-stakes choices */}
            <div className="mt-4 space-y-2.5">
              <p className="text-xs font-semibold text-text-muted uppercase tracking-wider">Analysis Steps</p>
              {ALL_STEPS.map(s => (
                <ClayToggle
                  key={s.id}
                  checked={enabledSteps.includes(s.id)}
                  onChange={() => toggleStep(s.id)}
                  disabled={s.essential}
                  label={s.label}
                  hint={s.essential ? 'required' : undefined}
                  className="rounded-lg px-3 py-2 hover:bg-surface-1/60 transition-colors"
                />
              ))}
            </div>

            {error && <p className="text-error text-sm mt-3">{error}</p>}

            <CriticalButton
              onClick={handleSubmit}
              disabled={loading}
              className="mt-4 w-full py-3"
            >
              {loading ? <>Submitting&hellip;</> : <><ArrowRight className="w-4 h-4" /> Run Analysis</>}
            </CriticalButton>
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
              <>
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
                <div className="mt-3">
                  <button onClick={handleShare}
                    className="w-full text-center py-2.5 rounded-xl border border-accent-cyan/30 text-accent-cyan text-sm hover:bg-accent-cyan/10 transition flex items-center justify-center gap-2">
                    <Copy className="w-4 h-4" />Share Result
                  </button>
                </div>
              </>
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

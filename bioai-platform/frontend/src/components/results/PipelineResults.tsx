"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, Circle, LoaderCircle, XCircle, ArrowRight, Dna } from "lucide-react";
import { BlastPanel } from "./BlastPanel";
import { ScoreBars } from "./ScoreBars";
import { UniprotPanel } from "./UniprotPanel";
import PhyloTreeViewer from "@/components/phylo/PhyloTreeViewer";
import { AIInterpretation } from "./AIInterpretation";
import type { BlastHitSummary, UniprotSummary } from "@/types/pipeline";

const STEP_META: Record<string, { label: string; icon: string }> = {
  blast:    { label: "BLAST Search",       icon: "🔍" },
  uniprot:  { label: "UniProt Annotation",  icon: "📋" },
  msa:      { label: "Multiple Alignment", icon: "🧬" },
  phylo:    { label: "Phylogenetic Tree",   icon: "🌳" },
  domains:  { label: "Domain Architecture", icon: "🔗" },
  interpret:{ label: "AI Interpretation",   icon: "🤖" },
};

interface PipelineResultsProps {
  jobId: string;
  steps?: string[];
  onComplete?: () => void;
}

export function PipelineResults({ jobId, steps: enabledSteps, onComplete }: PipelineResultsProps) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const completedSteps = data?.steps ? Object.entries(data.steps).filter(([, s]: any) => s.status === "complete").map(([k]) => k) : [];

  useEffect(() => {
    setError(null);
    const iv = setInterval(async () => {
      try {
        const res = await fetch(`/api/backend/api/pipeline/v2/status/${jobId}`);
        if (!res.ok) { clearInterval(iv); setError("Pipeline job not found"); return; }
        const d = await res.json();
        setData(d);
        if (d.status === "complete") { clearInterval(iv); onComplete?.(); }
        if (d.status === "failed") clearInterval(iv);
      } catch { /* poll retry */ }
    }, 3000);
    return () => clearInterval(iv);
  }, [jobId]);

  if (error) {
    return (
      <div className="text-center py-12">
        <XCircle className="w-12 h-12 text-error mx-auto mb-4" />
        <p className="text-text-secondary">{error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-12">
        <LoaderCircle className="w-8 h-8 text-accent-cyan animate-spin mx-auto mb-3" />
        <p className="text-text-muted text-sm">Starting analysis&hellip;</p>
      </div>
    );
  }

  const steps = enabledSteps || data.requested_steps || Object.keys(data.steps);

  return (
    <div className="space-y-6">
      {/* Progress tracker */}
      <div className="glass-card p-4">
        <h3 className="text-sm font-semibold text-text-primary mb-3">Pipeline Progress</h3>
        <div className="flex items-center gap-2 flex-wrap">
          {steps.map((step: string, i: number) => {
            const s = data.steps?.[step];
            const meta = STEP_META[step] || { label: step, icon: "•" };
            const isRunning = s?.status === "running";
            const isDone = s?.status === "complete";
            const isFailed = s?.status === "failed";
            return (
              <div key={step} className="flex items-center gap-1.5">
                {i > 0 && <div className={`w-4 h-px ${isDone ? "bg-accent-cyan" : "bg-glass-border"}`} />}
                <div className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs border transition-all
                  ${isDone ? "border-accent-cyan/40 bg-accent-cyan/10 text-accent-cyan" : ""}
                  ${isRunning ? "border-accent-cyan/30 bg-accent-cyan/5 text-accent-cyan animate-pulse" : ""}
                  ${isFailed ? "border-error/40 bg-error/10 text-error" : ""}
                  ${s?.status === "pending" ? "border-glass-border text-text-muted" : ""}
                `}>
                  {isDone ? <CheckCircle2 className="w-3.5 h-3.5" /> : isRunning ? <LoaderCircle className="w-3.5 h-3.5 animate-spin" /> : isFailed ? <XCircle className="w-3.5 h-3.5" /> : <Circle className="w-3.5 h-3.5" />}
                  <span>{meta.label}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Step results */}
      {steps.includes("blast") && data.steps?.blast?.status === "complete" && (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
          <BlastPanel hits={data.steps.blast.data?.hits as BlastHitSummary[]} count={data.steps.blast.data?.count ?? 0} source={data.steps.blast.data?.source} />
          <ScoreBars hits={data.steps.blast.data?.hits as BlastHitSummary[]} />
        </motion.div>
      )}

      {steps.includes("uniprot") && data.steps?.uniprot?.status === "complete" && (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
          <UniprotPanel data={data.steps.uniprot.data as UniprotSummary} />
        </motion.div>
      )}

      {steps.includes("msa") && data.steps?.msa?.status === "complete" && data.steps.msa.data?.aln_fasta && (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-4">
          <h3 className="text-sm font-semibold text-text-primary mb-2">Multiple Sequence Alignment</h3>
          <p className="text-xs text-text-muted mb-2">{data.steps.msa.data.sequence_count} sequences aligned via Clustal Omega</p>
          <pre className="bg-surface-1 rounded-xl p-4 text-xs font-mono text-text-secondary leading-relaxed overflow-x-auto max-h-80 overflow-y-auto whitespace-pre">
            {data.steps.msa.data.aln_fasta}
          </pre>
        </motion.div>
      )}

      {steps.includes("phylo") && data.steps?.phylo?.status === "complete" && data.steps.phylo.data?.phylotree_newick && (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-4">
          <h3 className="text-sm font-semibold text-text-primary mb-2">Phylogenetic Tree</h3>
          <PhyloTreeViewer newick={data.steps.phylo.data.phylotree_newick} />
        </motion.div>
      )}

      {steps.includes("domains") && data.steps?.domains?.status === "complete" && data.steps.domains.data?.uniprot_accession && (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-4">
          <h3 className="text-sm font-semibold text-text-primary mb-2">Domain Architecture</h3>
          <DomainSummary data={data.steps.domains.data} />
        </motion.div>
      )}

      {steps.includes("interpret") && data.steps?.interpret?.status === "complete" && data.steps.interpret.data?.interpretation && (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-4">
          <h3 className="text-sm font-semibold text-text-primary mb-2">AI Interpretation</h3>
          <div className="prose prose-sm max-w-none text-text-secondary whitespace-pre-wrap font-mono text-sm leading-relaxed">
            {data.steps.interpret.data.interpretation}
          </div>
        </motion.div>
      )}

      {data.status === "failed" && (
        <div className="glass-card p-4 border border-error/30 bg-error/5">
          <div className="flex items-center gap-2 text-error">
            <XCircle className="w-5 h-5" />
            <span className="font-semibold text-sm">Pipeline Failed</span>
          </div>
          <p className="text-sm text-text-secondary mt-1">{data.error || "An unknown error occurred"}</p>
        </div>
      )}
    </div>
  );
}

function DomainSummary({ data }: { data: any }) {
  const domains = data?.domains || [];
  if (domains.length === 0) return <p className="text-sm text-text-muted">No domains found.</p>;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs text-text-muted">
        <span>Sequence length: {data.sequence_length} aa</span>
        <span>•</span>
        <span>{domains.length} domain{domains.length !== 1 ? "s" : ""} found</span>
      </div>
      <div className="space-y-1.5">
        {domains.map((d: any, i: number) => (
          <div key={i} className="flex items-center gap-3 bg-surface-1 rounded-lg px-3 py-2 text-sm">
            <span className="font-mono text-accent-cyan text-xs">{d.source_db}</span>
            <span className="text-text-primary font-medium">{d.name}</span>
            <span className="text-text-muted text-xs ml-auto">{d.start}–{d.end}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

"use client";
import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { fadeUp } from "@/lib/animations";
import { StringDBViewer } from "@/components/interactions/StringDBViewer";
import { useAuditTrail } from "@/hooks/useAuditTrail";

const GENE_EXAMPLES = ["TP53", "BRCA1", "EGFR", "TNF", "INS"];

export default function InteractionsPage() {
  const router = useRouter();
  const audit = useAuditTrail();
  const [geneName, setGeneName] = useState("");
  const [submitted, setSubmitted] = useState("");

  const submitGene = useCallback((g: string) => {
    if (!g.trim()) return;
    setGeneName(g);
    setSubmitted(g);
    audit.emitStarted('interactions_search', 'STRING-DB', g);
  }, [audit]);

  return (
    <div className="max-w-3xl">
      <button onClick={() => router.push("/analyze")}
        className="flex items-center gap-1 text-sm text-text-muted hover:text-text-primary mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Choose a different operation
      </button>

      <motion.div variants={fadeUp} initial="hidden" animate="show" className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary mb-1">Protein-Protein Interactions</h1>
        <p className="text-sm text-text-secondary">Explore interaction partners from the STRING database.</p>
      </motion.div>

      <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-5 mb-6 space-y-4">
        <div className="flex gap-3">
          <input type="text" value={geneName}
            onChange={e => setGeneName(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === "Enter" && submitGene(geneName)}
            placeholder="e.g. TP53"
            className="flex-1 px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm font-mono bg-surface-1 text-text-primary" />
          <button onClick={() => submitGene(geneName)} disabled={!geneName.trim()}
            className="btn-primary px-5 py-3 disabled:opacity-50">
            Find Partners
          </button>
        </div>
        <div className="flex gap-2 flex-wrap">
          <span className="text-xs text-text-muted">Examples:</span>
          {GENE_EXAMPLES.map(g => (
            <button key={g} onClick={() => submitGene(g)}
              className="px-2 py-1 text-xs rounded bg-accent-cyan/10 text-accent-cyan hover:bg-accent-cyan/20 transition">
              {g}
            </button>
          ))}
        </div>
      </motion.div>

      {submitted && (
        <motion.div variants={fadeUp} initial="hidden" animate="show">
          <div className="glass-card p-5">
            <StringDBViewer geneName={submitted} />
          </div>
        </motion.div>
      )}
    </div>
  );
}

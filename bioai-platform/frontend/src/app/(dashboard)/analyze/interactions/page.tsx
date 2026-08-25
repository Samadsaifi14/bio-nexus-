"use client";
import { useState, useCallback, useEffect } from "react";
import { motion } from "framer-motion";
import { fadeUp } from "@/lib/animations";
import { StringDBViewer } from "@/components/interactions/StringDBViewer";
import { useAuditTrail } from "@/hooks/useAuditTrail";
import { BackButton, CriticalButton, FlatInput, PageHeader } from "@/components/ui";
import { consumeParam } from '@/lib/cross-link';

const GENE_EXAMPLES = ["TP53", "BRCA1", "EGFR", "TNF", "INS"];

export default function InteractionsPage() {
  const audit = useAuditTrail();
  const [geneName, setGeneName] = useState("");
  const [submitted, setSubmitted] = useState("");

  const submitGene = useCallback((g: string) => {
    if (!g.trim()) return;
    setGeneName(g);
    setSubmitted(g);
    audit.emitStarted('interactions_search', 'STRING-DB', g);
  }, [audit]);

  useEffect(() => {
    const stored = consumeParam('interaction_gene');
    if (stored) {
      setGeneName(stored);
    }
  }, []);

  return (
    <div className="max-w-3xl">
      <BackButton />

      <PageHeader
        title="Protein-Protein Interactions"
        subtitle="Explore interaction partners from the STRING database."
      />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-6 space-y-4">
        <div className="flex gap-3">
          <FlatInput type="text" value={geneName}
            onChange={e => { setGeneName(e.target.value.toUpperCase()); setSubmitted(""); }}
            onKeyDown={e => e.key === "Enter" && submitGene(geneName)}
            placeholder="e.g. TP53"
            className="flex-1 font-mono" />
          <CriticalButton onClick={() => submitGene(geneName)} disabled={!geneName.trim()}>
            Find Partners
          </CriticalButton>
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
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show">
          <div className="data-card p-5">
            <StringDBViewer geneName={submitted} />
          </div>
        </motion.div>
      )}
    </div>
  );
}

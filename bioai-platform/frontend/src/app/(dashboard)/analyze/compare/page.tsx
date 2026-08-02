"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { fadeUp } from "@/lib/animations";
import { StructureComparison } from "@/components/structure/StructureComparison";
import { BackButton, CriticalButton, FlatInput, PageHeader } from "@/components/ui";

const PDB_EXAMPLES = ["1TUP", "4HBE", "2FE5", "7A6F"];

export default function ComparePage() {
  const [pdbId, setPdbId] = useState("");
  const [submitted, setSubmitted] = useState("");

  return (
    <div className="max-w-3xl">
      <BackButton />

      <PageHeader
        title="Structure Comparison"
        subtitle="Find structurally similar proteins using PDBeFold (TM-align)."
      />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-6 space-y-4">
        <div className="flex gap-3">
          <FlatInput type="text" value={pdbId}
            onChange={e => { setPdbId(e.target.value.toUpperCase()); setSubmitted(""); }}
            onKeyDown={e => e.key === "Enter" && setSubmitted(pdbId)}
            placeholder="e.g. 1TUP"
            className="flex-1 font-mono" />
          <CriticalButton onClick={() => setSubmitted(pdbId)} disabled={!pdbId.trim()}>
            Compare
          </CriticalButton>
        </div>
        <div className="flex gap-2 flex-wrap">
          <span className="text-xs text-text-muted">Examples:</span>
          {PDB_EXAMPLES.map(p => (
            <button key={p} onClick={() => { setPdbId(p); setSubmitted(p); }}
              className="px-2 py-1 text-xs rounded bg-accent-cyan/10 text-accent-cyan hover:bg-accent-cyan/20 transition">
              {p}
            </button>
          ))}
        </div>
      </motion.div>

      {submitted && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show">
          <div className="data-card p-5">
            <StructureComparison pdbId={submitted} />
          </div>
        </motion.div>
      )}
    </div>
  );
}

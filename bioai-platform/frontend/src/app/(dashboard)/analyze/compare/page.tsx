"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { fadeUp } from "@/lib/animations";
import { StructureComparison } from "@/components/structure/StructureComparison";

const PDB_EXAMPLES = ["1TUP", "4HBE", "2FE5", "7A6F"];

export default function ComparePage() {
  const router = useRouter();
  const [pdbId, setPdbId] = useState("");
  const [submitted, setSubmitted] = useState("");

  return (
    <div className="max-w-3xl">
      <button onClick={() => router.push("/analyze")}
        className="flex items-center gap-1 text-sm text-text-muted hover:text-text-primary mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Choose a different operation
      </button>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary mb-1">Structure Comparison</h1>
        <p className="text-sm text-text-secondary">Find structurally similar proteins using PDBeFold (TM-align).</p>
      </motion.div>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-5 mb-6 space-y-4">
        <div className="flex gap-3">
          <input type="text" value={pdbId}
            onChange={e => setPdbId(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === "Enter" && setSubmitted(pdbId)}
            placeholder="e.g. 1TUP"
            className="flex-1 px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm font-mono bg-surface-1 text-text-primary" />
          <button onClick={() => setSubmitted(pdbId)} disabled={!pdbId.trim()}
            className="btn-primary px-5 py-3 disabled:opacity-50">
            Compare
          </button>
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
          <div className="glass-card p-5">
            <StructureComparison pdbId={submitted} />
          </div>
        </motion.div>
      )}
    </div>
  );
}

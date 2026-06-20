"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { fadeUp } from "@/lib/animations";
import { DomainArchitecture } from "@/components/domains/DomainArchitecture";

export default function DomainsPage() {
  const router = useRouter();
  const [accession, setAccession] = useState("");
  const [submitted, setSubmitted] = useState("");

  return (
    <div className="max-w-3xl">
      <button onClick={() => router.push("/analyze")}
        className="flex items-center gap-1 text-sm text-text-muted hover:text-text-primary mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Choose a different operation
      </button>

      <motion.div variants={fadeUp} initial="hidden" animate="show" className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary mb-1">Domain &amp; Motif Analysis</h1>
        <p className="text-sm text-text-secondary">Fetch domain annotations from InterPro for any UniProt accession.</p>
      </motion.div>

      <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-5 mb-6">
        <div className="flex gap-3">
          <input type="text" value={accession}
            onChange={e => setAccession(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === "Enter" && setSubmitted(accession)}
            placeholder="e.g. P04637, Q9Y261"
            className="flex-1 px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm font-mono bg-surface-1 text-text-primary" />
          <button onClick={() => setSubmitted(accession)} disabled={!accession.trim()}
            className="btn-primary px-5 py-3 disabled:opacity-50">
            Fetch Domains
          </button>
        </div>
      </motion.div>

      {submitted && (
        <motion.div variants={fadeUp} initial="hidden" animate="show">
          <div className="glass-card p-5">
            <DomainArchitecture accession={submitted} />
          </div>
        </motion.div>
      )}
    </div>
  );
}

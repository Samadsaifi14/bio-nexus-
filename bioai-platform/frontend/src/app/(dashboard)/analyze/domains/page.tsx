"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ExternalLink, Dna, Search } from "lucide-react";
import { fadeUp } from "@/lib/animations";
import { DomainArchitecture } from "@/components/domains/DomainArchitecture";
import { BackButton, CriticalButton, FlatInput, PageHeader } from "@/components/ui";

const EXAMPLE_ACCESSIONS = [
  { id: "P04637", label: "TP53", desc: "Tumor suppressor p53" },
  { id: "P00698", label: "LYZ", desc: "Lysozyme C" },
  { id: "P00533", label: "EGFR", desc: "Epidermal growth factor receptor" },
  { id: "P01308", label: "INS", desc: "Insulin" },
  { id: "P68871", label: "HBB", desc: "Hemoglobin subunit beta" },
];

export default function DomainsPage() {
  const router = useRouter();
  const [accession, setAccession] = useState("");
  const [submitted, setSubmitted] = useState("");

  useEffect(() => {
    const stored = sessionStorage.getItem("domains_accession");
    if (stored) {
      sessionStorage.removeItem("domains_accession");
      setAccession(stored.toUpperCase());
    }
  }, []);

  const handleSubmit = () => {
    if (accession.trim()) setSubmitted(accession.trim().toUpperCase());
  };

  return (
    <div className="max-w-4xl">
      <BackButton />

      <PageHeader
        title="Domain & Motif Analysis"
        subtitle="Comprehensive protein feature analysis powered by InterPro and UniProtKB. Visualize domain architecture, functional sites, post-translational modifications, structural motifs, variants, and pathway annotations for any protein."
      />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-4">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <FlatInput type="text" value={accession}
              onChange={e => { setAccession(e.target.value.toUpperCase()); setSubmitted(""); }}
              onKeyDown={e => e.key === "Enter" && handleSubmit()}
              placeholder="UniProt accession, e.g. P04637, P00698, Q9Y261"
              className="w-full pl-10 pr-4 font-mono" />
          </div>
          <CriticalButton onClick={handleSubmit} disabled={!accession.trim()}>
            Analyze
          </CriticalButton>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {EXAMPLE_ACCESSIONS.map(ex => (
            <button key={ex.id}
              onClick={() => { setAccession(ex.id); setSubmitted(ex.id); }}
              className="px-2.5 py-1 text-[11px] rounded-lg border border-glass-border bg-surface-1 hover:bg-surface-2 text-text-muted hover:text-text-primary transition-colors">
              <span className="font-mono text-accent-cyan">{ex.id}</span>
              <span className="ml-1.5">{ex.label}</span>
            </button>
          ))}
        </div>
      </motion.div>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="mb-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {[
            { icon: <Dna className="w-3.5 h-3.5" />, label: "Domain Architecture", color: "text-cyan-400" },
            { icon: <span className="text-xs">⚡</span>, label: "Functional Sites", color: "text-amber-400" },
            { icon: <span className="text-xs">🔧</span>, label: "PTMs &amp; Modifications", color: "text-purple-400" },
            { icon: <span className="text-xs">🏷️</span>, label: "GO Terms &amp; Pathways", color: "text-green-400" },
          ].map(item => (
            <div key={item.label} className="flex items-center gap-2 px-3 py-2 rounded-xl border border-glass-border bg-surface-1">
              <span className={item.color}>{item.icon}</span>
              <span className="text-[11px] text-text-muted">{item.label}</span>
            </div>
          ))}
        </div>
      </motion.div>

      {submitted && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show">
          <div className="data-card p-5">
            <DomainArchitecture accession={submitted} />
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <BridgeLink
              label="BLAST this sequence"
              onClick={() => {
                sessionStorage.setItem("domains_accession", submitted);
                router.push("/analyze/blast");
              }}
            />
            <BridgeLink
              label="View 3D structure"
              onClick={() => {
                sessionStorage.setItem("structure_query", submitted);
                router.push("/analyze/structure");
              }}
            />
            <BridgeLink
              label="UniProt details"
              onClick={() => {
                sessionStorage.setItem("uniprot_accession", submitted);
                router.push("/analyze/uniprot");
              }}
            />
            <BridgeLink
              label="Protein interactions"
              onClick={() => {
                sessionStorage.setItem("interaction_gene", submitted);
                router.push("/analyze/interactions");
              }}
            />
            <BridgeLink
              label="Pathway search"
              onClick={() => {
                sessionStorage.setItem("pathway_query", submitted);
                router.push("/analyze/pathway");
              }}
            />
          </div>
        </motion.div>
      )}
    </div>
  );
}

function BridgeLink({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button onClick={onClick}
      className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-glass-border bg-surface-1 hover:bg-surface-2 text-text-muted hover:text-accent-cyan transition-colors">
      {label}
      <ExternalLink className="w-3 h-3" />
    </button>
  );
}

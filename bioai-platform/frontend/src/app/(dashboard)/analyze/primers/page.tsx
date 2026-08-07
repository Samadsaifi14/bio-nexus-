"use client";
import { motion } from "framer-motion";
import { fadeUp } from "@/lib/animations";
import { PrimerDesigner } from "@/components/primers/PrimerDesigner";
import { useAuditTrail } from "@/hooks/useAuditTrail";
import { BackButton, PageHeader } from "@/components/ui";

export default function PrimersPage() {
  useAuditTrail();

  return (
    <div className="max-w-3xl">
      <BackButton />

      <PageHeader
        title="Primer Design"
        subtitle="Search NCBI for a gene, retrieve its mRNA/CDS, and design PCR primers with Primer3 — with hairpin/dimer QC and in-silico PCR verification."
      />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show">
        <div className="data-card p-5">
          <PrimerDesigner />
        </div>
      </motion.div>
    </div>
  );
}

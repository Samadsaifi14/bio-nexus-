"use client";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft } from "lucide-react";
import { fadeUp } from "@/lib/animations";
import { PrimerDesigner } from "@/components/primers/PrimerDesigner";

export default function PrimersPage() {
  const router = useRouter();

  return (
    <div className="max-w-3xl">
      <button onClick={() => router.push("/analyze")}
        className="flex items-center gap-1 text-sm text-text-muted hover:text-text-primary mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Choose a different operation
      </button>

      <motion.div variants={fadeUp} initial="hidden" animate="show" className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary mb-1">Primer Design</h1>
        <p className="text-sm text-text-secondary">Design PCR primers using Primer3. Runs locally &mdash; instant results.</p>
      </motion.div>

      <motion.div variants={fadeUp} initial="hidden" animate="show">
        <div className="glass-card p-5">
          <PrimerDesigner />
        </div>
      </motion.div>
    </div>
  );
}

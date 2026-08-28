"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowSquareOut as ExternalLink, Dna, MagnifyingGlass as Search, CircleNotch as LoaderCircle } from '@phosphor-icons/react';
import { fadeUp } from "@/lib/animations";
import { DomainArchitecture } from "@/components/domains/DomainArchitecture";
import { scanPrositeSequence, type ScanPrositeResult } from "@/lib/api";
import { extractErrorMessage } from "@/lib/errors";
import { useAuditTrail } from "@/hooks/useAuditTrail";
import { BackButton, CriticalButton, FlatInput, FlatTextarea, PageHeader } from "@/components/ui";
import { AIResultSummary } from "@/components/results/AIResultSummary";
import { consumeParam, setPrefill } from '@/lib/cross-link';

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
  const [scanSeq, setScanSeq] = useState("");
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ScanPrositeResult | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const audit = useAuditTrail();

  useEffect(() => {
    const stored = consumeParam("domains_accession");
    if (stored) {
      setAccession(stored.toUpperCase());
    }
  }, []);

  const handleSubmit = () => {
    if (accession.trim()) setSubmitted(accession.trim().toUpperCase());
  };

  const handleScan = async () => {
    const clean = scanSeq.replace(/[^A-Za-z]/g, "");
    if (clean.length < 10) {
      setScanError("Sequence too short (min 10 amino acids)");
      return;
    }
    audit.emitStarted("prosite_scan", "ScanProsite", `len:${clean.length}`);
    setScanning(true);
    setScanError(null);
    setScanResult(null);
    try {
      const res = await scanPrositeSequence(clean.toUpperCase());
      setScanResult(res);
      audit.emitSuccess("prosite_scan", "ScanProsite", `len:${clean.length}`, `matches:${res.count}`);
    } catch (err: unknown) {
      const errMsg = extractErrorMessage(err, "Scan failed");
      audit.emitFailed("prosite_scan", "ScanProsite", `len:${clean.length}`, errMsg);
      setScanError(errMsg);
    } finally {
      setScanning(false);
    }
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

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-4">
        <h3 className="text-sm font-semibold text-text-primary mb-1">Scan a raw sequence for PROSITE motifs</h3>
        <p className="text-xs text-text-muted mb-3">No accession needed — paste any protein sequence (FASTA header optional) to find PROSITE pattern matches.</p>
        <FlatTextarea
          value={scanSeq}
          onChange={(e) => { setScanSeq(e.target.value); setScanError(null); setScanResult(null); }}
          placeholder={`MEEPQSDPSVEPPLSQETFSDLWKLLPENN...`}
          className="h-28"
        />
        <div className="mt-3 flex items-center justify-end gap-3">
          {scanning && <span className="text-xs text-text-muted flex items-center gap-1"><LoaderCircle className="w-3 h-3 animate-spin" /> scanning...</span>}
          <CriticalButton onClick={handleScan} disabled={scanning || scanSeq.replace(/[^A-Za-z]/g, "").length < 10}>
            <Dna className="w-4 h-4" />
            Scan
          </CriticalButton>
        </div>
        {scanError && <p className="mt-2 text-xs text-error">{scanError}</p>}
        {scanResult && (
          <div className="mt-4">
            <AIResultSummary toolName="domains" result={scanResult as unknown as Record<string, unknown>} />
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-medium text-text-muted uppercase tracking-wider">
                {scanResult.count} PROSITE match{scanResult.count !== 1 ? "es" : ""} in a {scanResult.sequence_length}-residue sequence
              </p>
            </div>
            {scanResult.count === 0 ? (
              <p className="text-sm text-text-secondary">No PROSITE signatures matched this sequence.</p>
            ) : (
              <div className="space-y-2">
                {scanResult.matches.map((m, i) => (
                  <div key={`${m.signature_ac}-${i}`} className="flex items-center gap-3 bg-surface-1 rounded-xl p-3 border border-glass-border">
                    <a
                      href={`https://prosite.expasy.org/${m.signature_ac}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-sm text-accent-cyan hover:underline flex items-center gap-1 shrink-0"
                    >
                      {m.signature_ac} <ExternalLink className="w-3 h-3" />
                    </a>
                    <span className="text-sm text-text-primary truncate">{m.name || "PROSITE signature"}</span>
                    <span className="ml-auto shrink-0 text-xs font-mono text-text-muted">{m.start}–{m.stop}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </motion.div>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="mb-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {[
            { icon: <Dna className="w-3.5 h-3.5" />, label: "Domain Architecture", color: "text-accent-cyan" },
            { icon: <span className="text-xs">⚡</span>, label: "Functional Sites", color: "text-warn" },
            { icon: <span className="text-xs">🔧</span>, label: "PTMs &amp; Modifications", color: "text-accent-purple" },
            { icon: <span className="text-xs">🏷️</span>, label: "GO Terms &amp; Pathways", color: "text-good" },
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
              onClick={() => setPrefill(router, "domains_accession", submitted, "/analyze/blast")}
            />
            <BridgeLink
              label="View 3D structure"
              onClick={() => setPrefill(router, "structure_query", submitted, "/analyze/structure")}
            />
            <BridgeLink
              label="UniProt details"
              onClick={() => setPrefill(router, "uniprot_accession", submitted, "/analyze/uniprot")}
            />
            <BridgeLink
              label="Protein interactions"
              onClick={() => setPrefill(router, "interaction_gene", submitted, "/analyze/interactions")}
            />
            <BridgeLink
              label="Pathway search"
              onClick={() => setPrefill(router, "pathway_query", submitted, "/analyze/pathway")}
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

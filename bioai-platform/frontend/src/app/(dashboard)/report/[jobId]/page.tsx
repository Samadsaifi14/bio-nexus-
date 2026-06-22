"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Printer, Download, LoaderCircle, XCircle } from "lucide-react";
import Link from "next/link";
import { downloadJson } from "@/lib/export-utils";
import { BlastPanel } from "@/components/results/BlastPanel";
import { ScoreBars } from "@/components/results/ScoreBars";
import { UniprotPanel } from "@/components/results/UniprotPanel";
import PhyloTreeViewer from "@/components/phylo/PhyloTreeViewer";
import type { BlastHitSummary, UniprotSummary } from "@/types/pipeline";

export default function ReportPage() {
  const params = useParams();
  const jobId = params.jobId as string;
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;
    fetch(`/api/backend/api/pipeline/v2/status/${jobId}`)
      .then(r => { if (!r.ok) throw new Error("Report not found"); return r.json(); })
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [jobId]);

  if (loading) return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <LoaderCircle className="w-8 h-8 text-accent-cyan animate-spin" />
    </div>
  );

  if (error || !data) return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <XCircle className="w-12 h-12 text-error" />
      <p className="text-text-secondary">{error || "Report not found"}</p>
      <Link href="/wizard" className="text-accent-cyan text-sm hover:underline">Back to Wizard</Link>
    </div>
  );

  const steps = data.steps || {};
  const blastData = steps.blast?.data;
  const uniprotData = steps.uniprot?.data;
  const msaData = steps.msa?.data;
  const phyloData = steps.phylo?.data;
  const domainsData = steps.domains?.data;
  const interpretData = steps.interpret?.data;

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* Toolbar — hidden when printing */}
      <div className="flex items-center justify-between mb-6 print:hidden">
        <Link href="/wizard" className="inline-flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition">
          <ArrowLeft className="w-4 h-4" /> Back to Wizard
        </Link>
        <div className="flex gap-2">
          <button onClick={() => window.print()}
            className="px-4 py-2 rounded-xl border border-accent-cyan/30 text-accent-cyan text-sm hover:bg-accent-cyan/10 transition flex items-center gap-1.5">
            <Printer className="w-4 h-4" /> PDF
          </button>
          <button onClick={() => downloadJson(data, `bio-nexus-report-${jobId}.json`)}
            className="px-4 py-2 rounded-xl border border-glass-border text-text-secondary text-sm hover:bg-surface-1 transition flex items-center gap-1.5">
            <Download className="w-4 h-4" /> JSON
          </button>
        </div>
      </div>

      {/* Title */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary">Bio Nexus Analysis Report</h1>
        <p className="text-sm text-text-muted mt-1">Job {jobId.slice(0, 8)}&hellip; &middot; {data.created_at ? new Date(data.created_at).toLocaleString() : ""}</p>
        <p className="text-xs text-text-muted mt-0.5">Sequence length: {data.sequence?.length || "—"} aa</p>
      </div>

      {/* BLAST */}
      {blastData && (
        <section className="mb-8">
          <BlastPanel hits={blastData.hits as BlastHitSummary[]} count={blastData.count ?? 0} source={blastData.source} />
          <ScoreBars hits={blastData.hits as BlastHitSummary[]} />
        </section>
      )}

      {/* UniProt */}
      {uniprotData && (
        <section className="mb-8">
          <UniprotPanel data={uniprotData as UniprotSummary} />
        </section>
      )}

      {/* MSA */}
      {msaData?.aln_fasta && (
        <section className="glass-card p-6 mb-8">
          <h2 className="font-semibold text-text-primary mb-2">Multiple Sequence Alignment</h2>
          <p className="text-xs text-text-muted mb-2">{msaData.sequence_count} sequences aligned</p>
          <pre className="bg-surface-1 rounded-xl p-4 text-xs font-mono text-text-secondary leading-relaxed overflow-x-auto whitespace-pre max-h-96 overflow-y-auto">
            {msaData.aln_fasta}
          </pre>
        </section>
      )}

      {/* Phylo Tree */}
      {phyloData?.phylotree_newick && (
        <section className="glass-card p-6 mb-8">
          <h2 className="font-semibold text-text-primary mb-3">Phylogenetic Tree</h2>
          <PhyloTreeViewer newick={phyloData.phylotree_newick} />
        </section>
      )}

      {/* Domain Architecture */}
      {domainsData?.domains && domainsData.domains.length > 0 && (
        <section className="glass-card p-6 mb-8">
          <h2 className="font-semibold text-text-primary mb-3">Domain Architecture</h2>
          <p className="text-xs text-text-muted mb-2">{domainsData.uniprot_accession} &middot; {domainsData.sequence_length} aa &middot; {domainsData.domains.length} domain{domainsData.domains.length !== 1 ? "s" : ""}</p>
          <div className="space-y-1.5">
            {domainsData.domains.map((d: any, i: number) => (
              <div key={i} className="flex items-center gap-3 bg-surface-1 rounded-lg px-3 py-2 text-sm">
                <span className="font-mono text-accent-cyan text-xs">{d.source_db}</span>
                <span className="text-text-primary font-medium">{d.name}</span>
                <span className="text-text-muted text-xs ml-auto">{d.start}–{d.end}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* AI Interpretation */}
      {interpretData?.interpretation && (
        <section className="glass-card p-6 mb-8">
          <h2 className="font-semibold text-text-primary mb-3">AI Interpretation</h2>
          <div className="text-sm text-text-secondary leading-relaxed whitespace-pre-wrap font-mono">
            {interpretData.interpretation}
          </div>
        </section>
      )}

      {/* Footer */}
      <div className="text-center text-xs text-text-muted py-8 print:block hidden">
        Generated by Bio Nexus &middot; {new Date().toLocaleDateString()}
      </div>
    </div>
  );
}

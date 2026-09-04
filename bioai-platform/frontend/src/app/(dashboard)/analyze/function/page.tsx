"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowSquareOut as ExternalLink,
  Brain,
  CircleNotch as Loader2,
  DownloadSimple as Download,
  Flask,
  Info,
  Target,
} from "@phosphor-icons/react";
import { fadeUp } from "@/lib/animations";
import { useAuditTrail } from "@/hooks/useAuditTrail";
import {
  getFunctionEvidenceStatus,
  predictFunctionEvidence,
  type FunctionEvidenceResult,
} from "@/lib/functionEvidenceApi";
import { BackButton, CriticalButton, FlatInput, PageHeader, ResultsReadyBanner } from "@/components/ui";
import { AIResultSummary } from "@/components/results/AIResultSummary";
import { LearnPopover } from "@/components/LearnPopover";
import { consumeParam } from "@/lib/cross-link";

const NS_LABELS: Record<string, string> = {
  MF: "Molecular Function",
  BP: "Biological Process",
  CC: "Cellular Component",
};

export default function FunctionPage() {
  useAuditTrail();
  const [pdbId, setPdbId] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [result, setResult] = useState<FunctionEvidenceResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const poll = useCallback(async (id: string) => {
    try {
      const res = await getFunctionEvidenceStatus(id);
      setStatus(res.status);
      if (res.status === "complete" && res.result) {
        setResult(res.result);
        setLoading(false);
      } else if (res.status === "failed") {
        setError(res.error || "Function inference failed");
        setLoading(false);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not read prediction status");
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const stored = consumeParam("function_pdb_id");
    if (stored) setPdbId(stored);
  }, []);

  useEffect(() => {
    if (!jobId) return;
    const start = Date.now();
    const maxPollMs = 65 * 60 * 1000;
    const iv = window.setInterval(() => {
      if (Date.now() - start > maxPollMs) {
        setError("The InterPro-backed analysis is still running. The job was not converted into a result or confidence claim.");
        setLoading(false);
        window.clearInterval(iv);
        return;
      }
      void poll(jobId);
    }, 2000);
    return () => window.clearInterval(iv);
  }, [jobId, poll]);

  const grouped = useMemo(() => {
    const base: Record<string, FunctionEvidenceResult["go_terms"]> = { MF: [], BP: [], CC: [] };
    for (const term of result?.go_terms || []) {
      (base[term.namespace] ||= []).push(term);
    }
    for (const terms of Object.values(base)) {
      terms.sort((a, b) => b.support_count - a.support_count || b.supporting_domain_hits - a.supporting_domain_hits);
    }
    return base;
  }, [result]);

  const submit = async () => {
    if (!pdbId.trim()) return;
    setLoading(true);
    setResult(null);
    setError("");
    try {
      const res = await predictFunctionEvidence(pdbId.trim());
      setJobId(res.job_id);
      setStatus(res.status);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submission failed");
      setLoading(false);
    }
  };

  const exportJson = () => {
    if (!result) return;
    const a = document.createElement("a");
    a.download = `${result.pdb_id}_function_evidence.json`;
    a.href = "data:application/json;charset=utf-8," + encodeURIComponent(JSON.stringify(result, null, 2));
    a.click();
  };

  return (
    <div className="max-w-5xl">
      <BackButton />
      <PageHeader
        title="Function Evidence"
        subtitle="InterProScan → InterPro2GO evidence mapping for a PDB-derived protein sequence. Support counts are evidence counts, not probabilities."
      />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show">
        <div className="data-card p-5">
          <label className="mb-2 block text-sm text-text-secondary">PDB ID</label>
          <div className="flex gap-2">
            <FlatInput
              value={pdbId}
              onChange={(e) => {
                setPdbId(e.target.value.toUpperCase());
                setResult(null);
                setError("");
              }}
              placeholder="e.g. 1TIM"
              maxLength={4}
              className="w-32 font-mono uppercase"
              onKeyDown={(e) => e.key === "Enter" && void submit()}
            />
            <CriticalButton onClick={() => void submit()} disabled={loading || !pdbId.trim()}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Brain className="h-4 w-4" />}
              {status === "running" || status === "queued" ? `Status: ${status}...` : "Map Function Evidence"}
            </CriticalButton>
          </div>
        </div>
      </motion.div>

      {error && <div className="mt-4 data-card border border-error/30 p-4 text-sm text-error">{error}</div>}

      {result && (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="mt-6 space-y-4">
          <ResultsReadyBanner
            title={`${result.status === "inferred" ? "Evidence mapping complete" : "Insufficient mapping evidence"} · ${result.pdb_id}`}
            subtitle={`${result.method_version} · ${result.sequence_length} residues`}
          />

          <div className="flex flex-wrap items-center gap-3">
            <button onClick={exportJson} className="flex items-center gap-1.5 rounded border border-glass-border bg-surface-1 px-2.5 py-1 text-xs text-text-secondary hover:text-accent-cyan">
              <Download className="h-3.5 w-3.5" /> Export JSON
            </button>
            <span className="text-xs text-text-muted">No calibrated function probability or residue saliency is reported.</span>
          </div>

          <AIResultSummary toolName="function_predict" result={result as unknown as Record<string, unknown>} />

          <div className="data-card p-5">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div><p className="text-xs text-text-muted">PDB entry</p><a className="flex items-center gap-1 font-mono text-sm text-accent-cyan hover:underline" target="_blank" rel="noreferrer" href={`https://www.rcsb.org/structure/${result.pdb_id}`}>{result.pdb_id}<ExternalLink className="h-3 w-3" /></a></div>
              <div><p className="text-xs text-text-muted">GO mappings</p><p className="text-sm font-semibold text-text-primary">{result.go_terms.length}</p></div>
              <div><p className="text-xs text-text-muted">Domain hits</p><p className="text-sm font-semibold text-text-primary">{result.domain_hits.length}</p></div>
              <div><p className="text-xs text-text-muted">Inference state</p><p className="text-sm font-semibold text-text-primary">{result.status.replace(/_/g, " ")}</p></div>
            </div>
          </div>

          {result.status === "insufficient_evidence" && (
            <div className="data-card border border-warn/30 p-5">
              <div className="flex items-start gap-2"><Info className="mt-0.5 h-4 w-4 text-warn" /><div><h3 className="text-sm font-semibold text-text-primary">No supported GO mapping returned</h3><p className="mt-1 text-xs text-text-secondary">{result.note}</p></div></div>
            </div>
          )}

          {Object.entries(grouped).map(([ns, terms]) => terms.length > 0 && (
            <div key={ns} className="data-card p-5">
              <div className="mb-3 flex items-center gap-2">
                <Target className="h-4 w-4 text-accent-cyan" />
                <LearnPopover term={`GO ${NS_LABELS[ns] || ns}`} topic="function" explanation="GO mapping support here means distinct InterPro entries associated with the GO term. It is not a calibrated posterior probability.">
                  <h3 className="text-sm font-semibold text-text-primary">{NS_LABELS[ns] || ns}</h3>
                </LearnPopover>
                <span className="text-xs text-text-muted">({terms.length} mappings)</span>
              </div>
              <div className="space-y-2">
                {terms.map((go) => (
                  <div key={go.go_id} className="rounded-lg bg-surface-1 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div><span className="text-sm font-medium text-text-primary">{go.name}</span><span className="ml-2 font-mono text-xs text-text-muted">{go.go_id}</span></div>
                      <span className="text-xs text-text-secondary">{go.support_count} InterPro entr{go.support_count === 1 ? "y" : "ies"} · {go.supporting_domain_hits} hit{go.supporting_domain_hits === 1 ? "" : "s"}</span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">{go.supporting_interpro_entries.map((entry) => <span key={entry} className="rounded bg-surface-2 px-2 py-0.5 font-mono text-[11px] text-text-secondary">{entry}</span>)}</div>
                    <p className="mt-2 text-[11px] text-text-muted">{go.confidence_note}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}

          <div className="data-card p-5">
            <div className="mb-3 flex items-center gap-2"><Flask className="h-4 w-4 text-accent-amber" /><h3 className="text-sm font-semibold text-text-primary">Method provenance</h3></div>
            <div className="grid gap-3 text-xs text-text-secondary sm:grid-cols-2">
              <p><strong className="text-text-primary">Sequence source:</strong> {result.provenance.sequence_source}</p>
              <p><strong className="text-text-primary">Domain source:</strong> {result.provenance.domain_source}</p>
              <p><strong className="text-text-primary">GO mapping:</strong> {result.provenance.go_mapping_source}</p>
              <p><strong className="text-text-primary">Method:</strong> {result.method_version}</p>
            </div>
            <p className="mt-3 text-xs text-text-muted">{result.note}</p>
            <p className="mt-2 text-xs text-text-muted">{result.ec_scope_note}</p>
          </div>

          {result.composition && (
            <div className="data-card p-5">
              <h3 className="text-sm font-semibold text-text-primary">Descriptive amino-acid composition</h3>
              <p className="mt-1 text-xs text-text-muted">Measured directly from the fetched sequence. These measurements are not used as calibrated function evidence.</p>
              <div className="mt-3 grid grid-cols-5 gap-2 sm:grid-cols-10">
                {result.composition.aa.split("").map((aa) => <div key={aa} className="rounded bg-surface-1 p-2 text-center"><div className="font-mono text-sm text-text-primary">{aa}</div><div className="text-[11px] text-text-muted">{((result.composition.fractions[aa] || 0) * 100).toFixed(1)}%</div></div>)}
              </div>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}

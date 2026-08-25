"use client";
import { useEffect, useState, useRef } from "react";
import { useAuditTrail } from "@/hooks/useAuditTrail";
import { LearnPopover } from "@/components/LearnPopover";
import { viewerBg } from "@/lib/theme-canvas";
import { downloadTsv, downloadJson, downloadCanvasPng } from "@/lib/export-utils";

type Interaction = {
  partner_gene: string;
  combined_score: number;
  escore: number;
  dscore: number;
  tscore: number;
  ascore: number;
};

type EvidenceFilter = "all" | "experimental" | "database" | "coexpression" | "textmining";

const EVIDENCE_THRESHOLD = 0.3;

export function StringDBViewer({ geneName, initialData }: { geneName: string; initialData?: { interactions: Interaction[] } | null }) {
  const audit = useAuditTrail();
  const [data, setData] = useState<{ interactions: Interaction[] } | null>(initialData ?? null);
  const [loading, setLoading] = useState(!initialData);
  const [error, setError] = useState<string | null>(null);
  const [imgError, setImgError] = useState(false);
  const [copied, setCopied] = useState(false);
  const [filter, setFilter] = useState<EvidenceFilter>("all");
  const auditedRef = useRef(false);

  const species = 9606;

  useEffect(() => {
    if (initialData) return;
    setError(null);
    auditedRef.current = false;
    fetch(`/api/backend/api/interactions/${encodeURIComponent(geneName)}?limit=12`)
      .then(r => { if (!r.ok) return r.json().then(e => Promise.reject(new Error(e.detail || `Status ${r.status}`))); return r.json(); })
      .then(d => { setData(d); if (!auditedRef.current) { auditedRef.current = true; audit.emitSuccess('interactions_view', 'STRING-DB', geneName, `${d.interactions?.length || 0} partners`); } })
      .catch(e => { setError(e.message); audit.emitFailed('interactions_view', 'STRING-DB', geneName, e.message); })
      .finally(() => setLoading(false));
  }, [geneName, initialData, audit]);

  const scoreChannels = [
    { key: "escore" as const, label: "Experimental", color: "#4ADE80", filter: "experimental" as const, explain: "Support from physical interaction experiments (yeast two-hybrid, affinity capture, co-crystallisation)." },
    { key: "dscore" as const, label: "Database", color: "#7C3AED", filter: "database" as const, explain: "Support from curated interaction databases that collect evidence from published literature." },
    { key: "ascore" as const, label: "Co-expression", color: "#FBBF24", filter: "coexpression" as const, explain: "Support from correlated mRNA expression across many experiments — proteins that move together often work together." },
    { key: "tscore" as const, label: "Text mining", color: "#FBBF24", filter: "textmining" as const, explain: "Support from automated scanning of the scientific literature for co-occurrence of the two genes." },
  ];

  const stringDbUrl = `https://string-db.org/api/image/network?identifiers=${geneName}&species=${species}`;

  const visibleInteractions = (data?.interactions ?? []).filter(i => {
    if (filter === "all") return true;
    const channel = scoreChannels.find(c => c.filter === filter);
    if (!channel) return true;
    return i[channel.key] >= EVIDENCE_THRESHOLD;
  });

  const exportPng = () => {
    const img = new window.Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = viewerBg('#06060B');
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
      downloadCanvasPng(canvas, `${geneName}_stringdb_network.png`);
    };
    img.src = stringDbUrl;
  };

  const exportTsv = () => {
    if (!data?.interactions) return;
    downloadTsv(
      ["Partner", "Combined", "Experimental", "Database", "Co-expression", "Text mining"],
      data.interactions.map(i => [i.partner_gene, i.combined_score.toFixed(3), i.escore.toFixed(3), i.dscore.toFixed(3), i.ascore.toFixed(3), i.tscore.toFixed(3)]),
      `${geneName}_stringdb_scores.tsv`
    );
  };

  const exportJson = () => {
    if (!data?.interactions) return;
    downloadJson({
      gene: geneName,
      species,
      source: "STRING-DB",
      interactions: data.interactions,
    }, `${geneName}_stringdb_interactions.json`);
  };

  const copyGeneList = () => {
    if (!data?.interactions) return;
    const genes = data.interactions.map(i => i.partner_gene).join("\n");
    navigator.clipboard.writeText(genes).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  if (loading) return <div className="text-text-muted text-sm animate-pulse">Fetching STRING-DB interactions&hellip;</div>;
  if (error) return <div className="text-error text-sm">{error}</div>;
  if (!data?.interactions?.length) return <div className="text-text-muted text-sm">No interactions found.</div>;

  const { interactions } = data;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="text-text-primary font-semibold">STRING-DB Interactions — {geneName}</h3>
        <div className="flex items-center gap-2">
          <button onClick={exportPng}
            className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition-colors">
            Export PNG
          </button>
          <button onClick={exportTsv}
            className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition-colors">
            Export TSV
          </button>
          <button onClick={exportJson}
            className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition-colors">
            Export JSON
          </button>
          <button onClick={copyGeneList}
            className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition-colors">
            {copied ? "Copied!" : "Copy genes"}
          </button>
          <a href={`https://string-db.org/network/${geneName}`} target="_blank" rel="noreferrer"
            className="text-xs text-accent-cyan hover:underline">View on STRING-DB &nearr;</a>
        </div>
      </div>

      <div className="data-card p-2 flex items-center justify-center bg-viewer min-h-[300px]">
        {!imgError ? (
          <img
            src={stringDbUrl}
            alt={`STRING-DB network for ${geneName}`}
            className="w-full max-h-[400px] object-contain"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="text-text-muted text-sm p-4 text-center">
            STRING-DB image unavailable.
            <a href={`https://string-db.org/network/${geneName}`} target="_blank" rel="noreferrer"
              className="block text-accent-cyan hover:underline mt-1">Open on STRING-DB &nearr;</a>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-text-muted">Evidence filter:</span>
        {[{ key: "all" as const, label: "All" }, ...scoreChannels.map(c => ({ key: c.filter, label: c.label }))].map(opt => (
          <button
            key={opt.key}
            onClick={() => setFilter(opt.key)}
            className={`text-xs px-2.5 py-1 rounded border transition-colors ${
              filter === opt.key
                ? "bg-accent-cyan/10 border-accent-cyan/40 text-accent-cyan"
                : "bg-surface-1 border-glass-border text-text-secondary hover:text-text-primary"
            }`}
          >
            {opt.label}
          </button>
        ))}
        <span className="text-xs text-text-muted ml-auto">Showing {visibleInteractions.length} of {interactions.length} partners</span>
      </div>

      <div className="overflow-x-auto rounded-xl border border-glass-border">
        <table className="w-full text-xs">
          <thead className="bg-surface-1">
            <tr>
              <th className="px-3 py-2 text-left text-text-muted">Partner</th>
              <th className="px-3 py-2 text-left text-text-muted">
                <LearnPopover term="Combined score" topic="interactions"
                  explanation="STRING's confidence (0-1) that the interaction is real, integrating all evidence channels below.">
                  Combined
                </LearnPopover>
              </th>
              {scoreChannels.map(c => (
                <th key={c.key} className="px-3 py-2 text-left" style={{ color: c.color + "99" }}>
                  <LearnPopover term={`${c.label} evidence`} topic="interactions" explanation={c.explain}>
                    {c.label}
                  </LearnPopover>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleInteractions.map((inter, i) => (
              <tr key={i} className="border-t border-glass-border hover:bg-surface-1">
                <td className="px-3 py-2 text-accent-cyan font-mono font-bold">{inter.partner_gene}</td>
                <td className="px-3 py-2 text-text-secondary">{inter.combined_score.toFixed(3)}</td>
                {scoreChannels.map(c => (
                  <td key={c.key} className="px-3 py-2 text-text-muted">{inter[c.key].toFixed(3)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
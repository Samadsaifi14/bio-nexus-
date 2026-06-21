"use client";
import { useEffect, useState } from "react";

type Interaction = {
  partner_gene: string;
  combined_score: number;
  escore: number;
  dscore: number;
  tscore: number;
  ascore: number;
};

export function StringDBViewer({ geneName }: { geneName: string }) {
  const [data, setData] = useState<{ interactions: Interaction[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imgError, setImgError] = useState(false);
  const [copied, setCopied] = useState(false);

  const species = 9606;

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`/api/backend/api/interactions/${encodeURIComponent(geneName)}?limit=12`)
      .then(r => { if (!r.ok) return r.json().then(e => Promise.reject(new Error(e.detail || `Status ${r.status}`))); return r.json(); })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [geneName]);

  const scoreChannels = [
    { key: "escore" as const, label: "Experimental", color: "#00F5D4" },
    { key: "dscore" as const, label: "Database", color: "#7C3AED" },
    { key: "ascore" as const, label: "Co-expression", color: "#F59E0B" },
    { key: "tscore" as const, label: "Text mining", color: "#EF4444" },
  ];

  const stringDbUrl = `https://string-db.org/api/image/network?identifiers=${geneName}&species=${species}`;
  const allGenes = data?.interactions?.map(i => i.partner_gene).join("%0d") ?? "";

  const exportPng = () => {
    const img = new window.Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = "#04040A";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
      const a = document.createElement("a");
      a.download = `${geneName}_stringdb_network.png`;
      a.href = canvas.toDataURL("image/png");
      a.click();
    };
    img.src = stringDbUrl;
  };

  const exportSvgTable = () => {
    if (!data?.interactions) return;
    const rows = data.interactions.map(i =>
      `${i.partner_gene}\t${i.combined_score.toFixed(3)}\t${i.escore.toFixed(3)}\t${i.dscore.toFixed(3)}\t${i.ascore.toFixed(3)}\t${i.tscore.toFixed(3)}`
    ).join("\n");
    const tsv = `Partner\tCombined\tExperimental\tDatabase\tCo-expression\tText mining\n${rows}`;
    const a = document.createElement("a");
    a.download = `${geneName}_stringdb_scores.tsv`;
    a.href = "data:text/tab-separated-values;charset=utf-8," + encodeURIComponent(tsv);
    a.click();
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
          <button onClick={exportSvgTable}
            className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition-colors">
            Export TSV
          </button>
          <button onClick={copyGeneList}
            className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition-colors">
            {copied ? "Copied!" : "Copy genes"}
          </button>
          <a href={`https://string-db.org/network/${geneName}`} target="_blank" rel="noreferrer"
            className="text-xs text-accent-cyan hover:underline">View on STRING-DB &nearr;</a>
        </div>
      </div>

      <div className="glass-card p-2 flex items-center justify-center bg-[#04040A] min-h-[300px]">
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

      <div className="overflow-x-auto rounded-xl border border-glass-border">
        <table className="w-full text-xs">
          <thead className="bg-surface-1">
            <tr>
              <th className="px-3 py-2 text-left text-text-muted">Partner</th>
              <th className="px-3 py-2 text-left text-text-muted">Combined</th>
              {scoreChannels.map(c => (
                <th key={c.key} className="px-3 py-2 text-left" style={{ color: c.color + "99" }}>{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {interactions.map((inter, i) => (
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
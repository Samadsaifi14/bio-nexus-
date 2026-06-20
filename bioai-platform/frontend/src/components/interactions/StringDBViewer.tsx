"use client";
import { useEffect, useRef, useState } from "react";

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
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`/api/backend/api/interactions/${encodeURIComponent(geneName)}?limit=12`)
      .then(r => { if (!r.ok) return r.json().then(e => Promise.reject(new Error(e.detail || `Status ${r.status}`))); return r.json(); })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [geneName]);

  if (loading) return <div className="text-text-muted text-sm animate-pulse">Fetching STRING-DB interactions&hellip;</div>;
  if (error) return <div className="text-error text-sm">{error}</div>;
  if (!data?.interactions?.length) return <div className="text-text-muted text-sm">No interactions found.</div>;

  const { interactions } = data;
  const W = 500, H = 400, CX = W / 2, CY = H / 2, R = 150;

  const scoreChannels = [
    { key: "escore" as const, label: "Experimental", color: "#00F5D4" },
    { key: "dscore" as const, label: "Database", color: "#7C3AED" },
    { key: "ascore" as const, label: "Co-expression", color: "#F59E0B" },
    { key: "tscore" as const, label: "Text mining", color: "#EF4444" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-text-primary font-semibold">STRING-DB Interactions</h3>
        <a href={`https://string-db.org/network/${geneName}`} target="_blank" rel="noreferrer"
          className="text-xs text-accent-cyan hover:underline">View on STRING-DB &nearr;</a>
      </div>

      <div className="glass-card p-2">
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="w-full max-h-[380px]">
          {interactions.map((inter, i) => {
            const angle = (i / interactions.length) * 2 * Math.PI - Math.PI / 2;
            const nx = CX + R * Math.cos(angle);
            const ny = CY + R * Math.sin(angle);
            const strokeW = 1 + inter.combined_score * 4;
            const opacity = 0.2 + inter.combined_score * 0.6;
            return (
              <g key={i}>
                <line x1={CX} y1={CY} x2={nx} y2={ny}
                  stroke="#00F5D4" strokeWidth={strokeW} strokeOpacity={opacity} />
                <circle cx={nx} cy={ny} r={18} fill="#04040A" stroke="#00F5D4"
                  strokeOpacity={opacity} strokeWidth={1.5} />
                <text x={nx} y={ny + 4} textAnchor="middle" fill="rgba(255,255,255,0.8)" fontSize={9} fontWeight="bold">
                  {inter.partner_gene}
                </text>
              </g>
            );
          })}
          <circle cx={CX} cy={CY} r={30} fill="#00F5D4" fillOpacity={0.15} stroke="#00F5D4" strokeWidth={2} />
          <text x={CX} y={CY + 4} textAnchor="middle" fill="#00F5D4" fontSize={11} fontWeight="bold">
            {geneName}
          </text>
        </svg>
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

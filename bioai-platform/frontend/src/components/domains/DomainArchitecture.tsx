"use client";
import { useEffect, useState, useRef } from "react";
import { downloadTsv, exportSvgPng } from "@/lib/export-utils";

const DB_COLORS: Record<string, string> = {
  PFAM:    "#00F5D4",
  PANTHER: "#7C3AED",
  PRINTS:  "#F59E0B",
  PROSITE: "#EF4444",
  SMART:   "#3B82F6",
  CDD:     "#10B981",
};

type Domain = { accession: string; name: string; source_db: string; start: number; end: number };
type DomainsResponse = { uniprot_accession: string; sequence_length: number; domains: Domain[] };

export function DomainArchitecture({ accession }: { accession: string }) {
  const [data, setData] = useState<DomainsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [tooltip, setTooltip] = useState<{ domain: Domain; x: number; y: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`/api/backend/api/domains/${accession}`)
      .then(r => { if (!r.ok) return r.json().then(e => Promise.reject(new Error(e.detail || `Status ${r.status}`))); return r.json(); })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [accession]);

  if (loading) return <div className="text-text-muted text-sm animate-pulse">Loading domain annotations&hellip;</div>;
  if (error) return <div className="text-error text-sm">{error}</div>;
  if (!data) return <div className="text-error text-sm">No domain data returned.</div>;

  const { sequence_length: seqLen, domains } = data;
  const W = 700;
  const scale = (pos: number) => (pos / seqLen) * W;

  const dbs = Array.from(new Set(domains.map(d => d.source_db)));

  return (
    <div className="space-y-4 relative">
      <div className="flex items-center justify-between">
        <h3 className="text-text-primary font-semibold">Domain Architecture</h3>
        <div className="flex items-center gap-2">
          <button onClick={() => exportSvgPng(svgRef.current, `domains-${accession}.png`)}
            className="btn-ghost text-xs px-2 py-1">Export PNG</button>
          <button onClick={() => downloadTsv(
            ["Accession", "Name", "DB", "Start", "End"],
            domains.map(d => [d.accession, d.name, d.source_db, String(d.start), String(d.end)]),
            `domains-${accession}.tsv`
          )} className="btn-ghost text-xs px-2 py-1">Export TSV</button>
          <span className="text-text-muted text-xs">{seqLen} aa &middot; {domains.length} annotations</span>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        {dbs.map(db => (
          <div key={db} className="flex items-center gap-1.5 text-xs text-text-muted">
            <div className="w-3 h-3 rounded-sm" style={{ background: DB_COLORS[db] ?? "#888" }} />
            {db}
          </div>
        ))}
      </div>

      <div className="overflow-x-auto">
        <svg ref={svgRef} viewBox={`0 0 ${W + 40} 70`} className="w-full min-w-[400px]">
          <rect x={20} y={30} width={W} height={8} rx={4} fill="rgba(255,255,255,0.08)" />

          {[0, 0.25, 0.5, 0.75, 1].map(t => (
            <g key={t}>
              <line x1={20 + t * W} y1={38} x2={20 + t * W} y2={44} stroke="rgba(255,255,255,0.2)" />
              <text x={20 + t * W} y={55} textAnchor="middle" fill="rgba(255,255,255,0.3)" fontSize={9}>
                {Math.round(t * seqLen)}
              </text>
            </g>
          ))}

          {domains.map((d, i) => {
            const x = 20 + scale(d.start);
            const w = Math.max(scale(d.end - d.start), 6);
            const color = DB_COLORS[d.source_db] ?? "#888";
            return (
              <g key={`${d.accession}-${i}`}
                onMouseEnter={e => setTooltip({ domain: d, x: e.clientX, y: e.clientY })}
                onMouseLeave={() => setTooltip(null)}
                className="cursor-pointer">
                <rect x={x} y={20} width={w} height={28} rx={4}
                  fill={color} fillOpacity={0.3} stroke={color} strokeWidth={1.5} />
                {w > 40 && (
                  <text x={x + w / 2} y={36} textAnchor="middle" fill={color} fontSize={8} fontWeight="bold">
                    {d.name.length > 12 ? d.name.slice(0, 11) + "&hellip;" : d.name}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {tooltip && (
        <div className="fixed z-50 bg-[#04040A] border border-glass-border rounded-xl p-3 text-xs text-text-primary shadow-2xl pointer-events-none"
          style={{ left: tooltip.x + 12, top: tooltip.y - 10 }}>
          <p className="font-bold text-accent-cyan">{tooltip.domain.name}</p>
          <p className="text-text-muted">{tooltip.domain.accession} &middot; {tooltip.domain.source_db}</p>
          <p className="text-text-muted">Residues {tooltip.domain.start}&ndash;{tooltip.domain.end}</p>
        </div>
      )}

      <div className="max-h-52 overflow-y-auto rounded-xl border border-glass-border">
        <table className="w-full text-xs">
          <thead className="bg-surface-1 sticky top-0">
            <tr>
              {["Accession", "Name", "DB", "Start", "End"].map(h => (
                <th key={h} className="px-3 py-2 text-left text-text-muted font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {domains.map((d, i) => (
              <tr key={i} className="border-t border-glass-border hover:bg-surface-1">
                <td className="px-3 py-2 font-mono text-accent-cyan">{d.accession}</td>
                <td className="px-3 py-2 text-text-secondary">{d.name}</td>
                <td className="px-3 py-2 text-text-muted">{d.source_db}</td>
                <td className="px-3 py-2 text-text-muted">{d.start}</td>
                <td className="px-3 py-2 text-text-muted">{d.end}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

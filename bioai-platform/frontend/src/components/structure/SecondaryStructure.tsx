"use client";
import { useEffect, useState } from "react";

type SSResidue = { position: number; residue: string; ss: string; source: string };

const SS_COLOR: Record<string, string> = { H: "#00F5D4", E: "#7C3AED", C: "rgba(255,255,255,0.15)" };
const SS_LABEL: Record<string, string> = { H: "&alpha;-Helix", E: "&beta;-Sheet", C: "Coil" };

export function SecondaryStructureViewer({ identifier }: { identifier: string }) {
  const [data, setData] = useState<{ method: string; residues: SSResidue[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`/api/backend/api/structure_analysis/secondary_structure/${identifier}`)
      .then(r => { if (!r.ok) return r.json().then(e => Promise.reject(new Error(e.detail || `Status ${r.status}`))); return r.json(); })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [identifier]);

  if (loading) return <div className="text-text-muted text-sm animate-pulse">Predicting secondary structure&hellip;</div>;
  if (error) return <div className="text-error text-sm">{error}</div>;
  if (!data) return <div className="text-error text-sm">Failed to load.</div>;

  const { residues, method } = data;
  const CHUNK = 50;
  const rows: SSResidue[][] = [];
  for (let i = 0; i < residues.length; i += CHUNK) rows.push(residues.slice(i, i + CHUNK));

  const counts = {
    H: residues.filter(r => r.ss === "H").length,
    E: residues.filter(r => r.ss === "E").length,
    C: residues.filter(r => r.ss === "C").length,
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-text-primary font-semibold">Secondary Structure</h3>
        <span className="text-xs text-text-muted">{method}</span>
      </div>

      <div className="flex h-4 rounded-full overflow-hidden gap-px">
        {(["H", "E", "C"] as const).map(ss => (
          <div key={ss} style={{ width: `${(counts[ss] / residues.length) * 100}%`, background: SS_COLOR[ss] }}
            title={`${SS_LABEL[ss]}: ${((counts[ss] / residues.length) * 100).toFixed(1)}%`} />
        ))}
      </div>

      <div className="flex gap-4 text-xs text-text-muted">
        {(["H", "E", "C"] as const).map(ss => (
          <span key={ss} className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ background: SS_COLOR[ss] }} />
            {SS_LABEL[ss]} {((counts[ss] / residues.length) * 100).toFixed(0)}%
          </span>
        ))}
      </div>

      <div className="bg-surface-1 rounded-xl p-4 border border-glass-border space-y-3 max-h-72 overflow-y-auto">
        {rows.map((row, ri) => (
          <div key={ri} className="space-y-0.5">
            <div className="flex gap-px">
              {row.map((r, i) => (
                <div key={i} className="w-[14px] h-5 rounded-sm flex-shrink-0"
                  style={{ background: SS_COLOR[r.ss] ?? "#333", opacity: 0.8 }}
                  title={`${r.residue}${r.position}: ${SS_LABEL[r.ss]}`} />
              ))}
            </div>
            <div className="flex gap-px">
              {row.map((r, i) => (
                <span key={i} className="w-[14px] text-center text-[9px] text-text-muted flex-shrink-0 font-mono">{r.residue}</span>
              ))}
            </div>
            <div className="text-[9px] text-text-muted font-mono">{row[0].position}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

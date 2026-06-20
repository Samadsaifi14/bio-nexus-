"use client";
import { useEffect, useState } from "react";

type StructureMatch = {
  pdb_id: string; chain: string; description: string;
  tm_score: number; rmsd: number; seq_identity: number; aligned_length: number;
};

export function StructureComparison({ pdbId, chain = "A" }: { pdbId: string; chain?: string }) {
  const [matches, setMatches] = useState<StructureMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/backend/api/structure_analysis/compare/${pdbId}?chain=${chain}`)
      .then(r => r.ok ? r.json() : r.json().then(d => { throw new Error(d.detail); }))
      .then(d => setMatches(d.matches))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [pdbId, chain]);

  if (loading) return <div className="text-text-muted text-sm animate-pulse">Searching structural homologs (PDBeFold)&hellip;</div>;
  if (error) return <div className="text-error text-sm">{error}</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-text-primary font-semibold">Structural Homologs</h3>
        <span className="text-text-muted text-xs">{matches.length} hits &middot; PDBeFold</span>
      </div>

      <div className="space-y-1">
        <div className="flex justify-between text-xs text-text-muted mb-2">
          <span>TM-score (0&rarr;1)</span>
          <span>TM &gt; 0.5 = same fold</span>
        </div>
        {matches.map((m, i) => (
          <div key={i} className="flex items-center gap-3">
            <span className="text-xs font-mono text-accent-cyan w-16 flex-shrink-0">{m.pdb_id}:{m.chain}</span>
            <div className="flex-1 h-4 bg-surface-1 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${m.tm_score * 100}%`,
                  background: m.tm_score > 0.5 ? "#00F5D4" : m.tm_score > 0.3 ? "#F59E0B" : "#EF4444",
                  opacity: 0.7,
                }} />
            </div>
            <span className="text-xs text-text-muted w-10 text-right">{m.tm_score.toFixed(3)}</span>
          </div>
        ))}
      </div>

      <div className="overflow-x-auto rounded-xl border border-glass-border">
        <table className="w-full text-xs">
          <thead className="bg-surface-1">
            <tr>
              {["PDB", "Chain", "RMSD", "Seq ID%", "Aligned", "Description"].map(h => (
                <th key={h} className="px-3 py-2 text-left text-text-muted font-medium whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matches.map((m, i) => (
              <tr key={i} className="border-t border-glass-border hover:bg-surface-1">
                <td className="px-3 py-2">
                  <a href={`https://www.rcsb.org/structure/${m.pdb_id}`} target="_blank" rel="noreferrer"
                    className="text-accent-cyan font-mono hover:underline">{m.pdb_id}</a>
                </td>
                <td className="px-3 py-2 text-text-muted">{m.chain}</td>
                <td className="px-3 py-2 text-text-muted">{m.rmsd.toFixed(2)}&Aring;</td>
                <td className="px-3 py-2 text-text-muted">{(m.seq_identity * 100).toFixed(1)}%</td>
                <td className="px-3 py-2 text-text-muted">{m.aligned_length} aa</td>
                <td className="px-3 py-2 text-text-muted max-w-48 truncate">{m.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

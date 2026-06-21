"use client";
import { useRef } from "react";
import { exportSvgPng } from "@/lib/export-utils";

const GROUPS: Record<string, string[]> = {
  polar_positive: ["K", "R", "H"],
  polar_negative: ["D", "E"],
  polar_uncharged: ["S", "T", "N", "Q"],
  nonpolar:       ["A", "V", "I", "L", "M", "F", "W", "P"],
  special:        ["C", "G", "Y"],
};

function groupOf(aa: string): string {
  for (const [g, members] of Object.entries(GROUPS)) {
    if (members.includes(aa.toUpperCase())) return g;
  }
  return "other";
}

function columnConservation(column: string[]): number {
  const filtered = column.filter(c => c !== "-" && c !== ".");
  if (!filtered.length) return 0;

  const freqs = new Map<string, number>();
  for (const aa of filtered) freqs.set(aa, (freqs.get(aa) ?? 0) + 1);
  const maxFreq = Math.max(...Array.from(freqs.values()));
  const identityScore = maxFreq / filtered.length;

  const groups = new Set(filtered.map(groupOf));
  const groupScore = Array.from(groups).length === 1 ? 0.15 : 0;

  return Math.min(1, identityScore + groupScore);
}

interface Props {
  alignedSeqs: string[];
}

export function ConservationTrack({ alignedSeqs }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  if (!alignedSeqs.length) return null;
  const L = alignedSeqs[0].length;

  const scores: number[] = [];
  for (let i = 0; i < L; i++) {
    scores.push(columnConservation(alignedSeqs.map(s => s[i] ?? "-")));
  }

  const scoreColor = (s: number) => {
    if (s > 0.9) return "#00F5D4";
    if (s > 0.7) return "#F59E0B";
    if (s > 0.4) return "#7C3AED";
    return "rgba(255,255,255,0.1)";
  };

  const avgConservation = (scores.reduce((a, b) => a + b, 0) / scores.length * 100).toFixed(1);
  const highlyConserved = scores.filter(s => s > 0.9).length;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-text-primary font-semibold">Conservation Analysis</h3>
        <button onClick={() => exportSvgPng(svgRef.current, "conservation.png")}
          className="btn-ghost text-xs px-2 py-1">Export PNG</button>
        <div className="flex gap-4 text-xs text-text-muted">
          <span>Avg: <span className="text-text-secondary">{avgConservation}%</span></span>
          <span>Fully conserved: <span className="text-accent-cyan">{highlyConserved} positions</span></span>
        </div>
      </div>

      <div className="bg-surface-1 rounded-xl p-3 border border-glass-border overflow-x-auto">
        <svg ref={svgRef} viewBox={`0 0 ${L * 4} 60`} className="w-full" style={{ minWidth: L * 4 }}>
          {scores.map((s, i) => (
            <rect key={i} x={i * 4} y={60 - s * 55} width={3} height={s * 55}
              fill={scoreColor(s)} rx={1} />
          ))}
        </svg>
        <div className="flex justify-between text-xs text-text-muted mt-1 font-mono">
          <span>1</span>
          <span>{Math.floor(L / 2)}</span>
          <span>{L}</span>
        </div>
      </div>

      <div className="flex gap-4 text-xs text-text-muted">
        {[
          { color: "#00F5D4", label: ">90% conserved" },
          { color: "#F59E0B", label: ">70% conserved" },
          { color: "#7C3AED", label: ">40% conserved" },
          { color: "rgba(255,255,255,0.2)", label: "Variable" },
        ].map(({ color, label }) => (
          <span key={label} className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: color }} />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}

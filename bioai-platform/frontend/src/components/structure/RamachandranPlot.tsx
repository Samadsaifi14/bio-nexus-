"use client";
import { useEffect, useState } from "react";

type RPoint = { residue: string; chain: string; resnum: number; phi: number; psi: number; region: string };

const REGION_COLOR: Record<string, string> = {
  core_alpha: "#00F5D4",
  core_beta:  "#7C3AED",
  allowed:    "#F59E0B",
  outlier:    "#EF4444",
};

export function RamachandranPlot({ pdbId, chain = "A" }: { pdbId: string; chain?: string }) {
  const [points, setPoints] = useState<RPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [hovered, setHovered] = useState<RPoint | null>(null);

  useEffect(() => {
    fetch(`/api/backend/api/structure_analysis/ramachandran/${pdbId}?chain=${chain}`)
      .then(r => r.json())
      .then(setPoints)
      .finally(() => setLoading(false));
  }, [pdbId, chain]);

  if (loading) return <div className="text-text-muted text-sm animate-pulse">Calculating &phi;/&psi; angles&hellip;</div>;

  const W = 400, H = 400, PAD = 40;
  const toX = (phi: number) => PAD + ((phi + 180) / 360) * (W - PAD * 2);
  const toY = (psi: number) => PAD + ((180 - psi) / 360) * (H - PAD * 2);

  const counts = {
    core_alpha: points.filter(p => p.region === "core_alpha").length,
    core_beta:  points.filter(p => p.region === "core_beta").length,
    allowed:    points.filter(p => p.region === "allowed").length,
    outlier:    points.filter(p => p.region === "outlier").length,
  };
  const outlierPct = points.length ? ((counts.outlier / points.length) * 100).toFixed(1) : "0";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-text-primary font-semibold">Ramachandran Plot</h3>
        <span className={`text-xs px-2 py-0.5 rounded-full ${
          +outlierPct < 2 ? "text-emerald-400 bg-emerald-400/10"
            : +outlierPct < 5 ? "text-amber-400 bg-amber-400/10"
            : "text-error bg-error/10"
        }`}>
          {outlierPct}% outliers
        </span>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        <div className="glass-card relative">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-80 h-80">
            <ellipse cx={toX(-57)} cy={toY(-47)} rx={30} ry={30}
              fill="#00F5D4" fillOpacity={0.06} stroke="#00F5D4" strokeOpacity={0.15} />
            <ellipse cx={toX(-119)} cy={toY(113)} rx={30} ry={30}
              fill="#7C3AED" fillOpacity={0.06} stroke="#7C3AED" strokeOpacity={0.15} />

            <line x1={PAD} y1={toY(0)} x2={W - PAD} y2={toY(0)} stroke="rgba(255,255,255,0.1)" />
            <line x1={toX(0)} y1={PAD} x2={toX(0)} y2={H - PAD} stroke="rgba(255,255,255,0.1)" />

            <text x={W / 2} y={H - 8} textAnchor="middle" fill="rgba(255,255,255,0.4)" fontSize={11}>&phi; (phi)</text>
            <text x={12} y={H / 2} textAnchor="middle" fill="rgba(255,255,255,0.4)" fontSize={11}
              transform={`rotate(-90, 12, ${H / 2})`}>&psi; (psi)</text>

            {[-180, -90, 0, 90, 180].map(v => (
              <g key={v}>
                <text x={toX(v)} y={H - PAD + 14} textAnchor="middle" fill="rgba(255,255,255,0.25)" fontSize={8}>{v}&deg;</text>
                <text x={PAD - 10} y={toY(v) + 3} textAnchor="end" fill="rgba(255,255,255,0.25)" fontSize={8}>{v}&deg;</text>
              </g>
            ))}

            {points.map((p, i) => (
              <circle key={i} cx={toX(p.phi)} cy={toY(p.psi)} r={3}
                fill={REGION_COLOR[p.region] ?? "#888"} fillOpacity={0.7}
                className="cursor-pointer"
                onMouseEnter={() => setHovered(p)}
                onMouseLeave={() => setHovered(null)} />
            ))}
          </svg>

          {hovered && (
            <div className="absolute top-2 right-2 bg-[#04040A]/90 border border-glass-border rounded-lg p-2 text-xs text-text-secondary pointer-events-none">
              <p className="text-accent-cyan font-bold">{hovered.residue}{hovered.resnum}</p>
              <p>&phi; {hovered.phi.toFixed(1)}&deg; &middot; &psi; {hovered.psi.toFixed(1)}&deg;</p>
              <p className="capitalize">{hovered.region.replace("_", " ")}</p>
            </div>
          )}
        </div>

        <div className="space-y-3 flex-1">
          <p className="text-text-muted text-xs">n = {points.length} residues</p>
          {Object.entries(counts).map(([region, count]) => (
            <div key={region}>
              <div className="flex justify-between text-xs mb-1">
                <span className="capitalize" style={{ color: REGION_COLOR[region] }}>{region.replace("_", " ")}</span>
                <span className="text-text-muted">{points.length > 0 ? ((count / points.length) * 100).toFixed(1) : "0"}%</span>
              </div>
              <div className="w-full h-1.5 bg-surface-1 rounded-full overflow-hidden">
                <div className="h-full rounded-full" style={{
                  width: `${points.length > 0 ? (count / points.length) * 100 : 0}%`,
                  background: REGION_COLOR[region],
                  opacity: 0.7,
                }} />
              </div>
            </div>
          ))}
          <p className="text-text-muted text-xs mt-4">&gt;98% in favoured regions = high quality model</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-4">
        {Object.entries(REGION_COLOR).map(([region, color]) => (
          <div key={region} className="flex items-center gap-1.5 text-xs text-text-muted">
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
            <span className="capitalize">{region.replace("_", " ")}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

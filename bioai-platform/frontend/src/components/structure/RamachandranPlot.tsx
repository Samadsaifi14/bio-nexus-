"use client";

import { useEffect, useState } from "react";
import { apiUrl } from "@/lib/api";
import { downloadTsv } from "@/lib/export-utils";

type RPoint = {
  residue: string;
  chain: string;
  resnum: number;
  phi: number;
  psi: number;
  region: string;
};

type Props = {
  pdbId?: string | null;
  pdbUrl?: string | null;
  pdbData?: string | null;
  chain?: string;
  sourceLabel?: string;
};

const REGION_COLOR: Record<string, string> = {
  alpha: "#4ADE80",
  beta: "#7C3AED",
  left_handed: "#FBBF24",
  other: "#94A3B8",
};

const REGION_LABEL: Record<string, string> = {
  alpha: "α-helical basin",
  beta: "β / extended basin",
  left_handed: "Left-handed α basin",
  other: "Other torsion space",
};

export function RamachandranPlot({
  pdbId,
  pdbUrl,
  pdbData,
  chain = "",
  sourceLabel,
}: Props) {
  const [points, setPoints] = useState<RPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [hovered, setHovered] = useState<RPoint | null>(null);
  const [error, setError] = useState<string | null>(null);

  const hasStructure = Boolean(pdbId || pdbUrl || pdbData);

  useEffect(() => {
    if (!hasStructure) {
      setPoints([]);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setPoints([]);

    const load = async () => {
      let response: Response;
      if (pdbId) {
        const chainParam = encodeURIComponent(chain);
        response = await fetch(
          apiUrl(`/api/structure_analysis/ramachandran/${encodeURIComponent(pdbId)}?chain=${chainParam}`),
          { signal: controller.signal },
        );
      } else {
        response = await fetch(apiUrl("/api/structure_analysis/ramachandran"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify({
            pdb_text: pdbData || null,
            pdb_url: pdbData ? null : pdbUrl || null,
            chain,
          }),
        });
      }

      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail || `Ramachandran analysis failed (HTTP ${response.status})`);
      }
      const result = await response.json();
      if (!controller.signal.aborted) setPoints(Array.isArray(result) ? result : []);
    };

    load()
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : "Ramachandran analysis failed");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [pdbId, pdbUrl, pdbData, chain, hasStructure]);

  if (!hasStructure) {
    return (
      <div className="text-text-muted text-sm">
        No 3D coordinates are available. Ramachandran analysis requires an experimental or predicted structure.
      </div>
    );
  }

  if (loading) {
    return <div className="text-text-muted text-sm animate-pulse">Calculating φ/ψ torsion angles…</div>;
  }

  if (error) return <div className="text-error text-sm">{error}</div>;

  const W = 400;
  const H = 400;
  const PAD = 40;
  const toX = (phi: number) => PAD + ((phi + 180) / 360) * (W - PAD * 2);
  const toY = (psi: number) => PAD + ((180 - psi) / 360) * (H - PAD * 2);

  const counts = {
    alpha: points.filter((p) => p.region === "alpha").length,
    beta: points.filter((p) => p.region === "beta").length,
    left_handed: points.filter((p) => p.region === "left_handed").length,
    other: points.filter((p) => p.region === "other").length,
  };

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h3 className="text-text-primary font-semibold">Ramachandran Plot</h3>
          <p className="text-[11px] text-text-muted mt-0.5">
            φ/ψ angles calculated directly from {sourceLabel || (pdbId ? `PDB ${pdbId}` : "the displayed structure")}.
          </p>
        </div>
        <button
          onClick={() =>
            downloadTsv(
              ["Residue", "Chain", "Residue number", "Phi (deg)", "Psi (deg)", "Descriptive basin"],
              points.map((p) => [p.residue, p.chain, String(p.resnum), String(p.phi), String(p.psi), p.region]),
              `ramachandran-${pdbId || "structure"}.tsv`,
            )
          }
          className="btn-ghost text-xs px-2 py-1"
        >
          Export TSV
        </button>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        <div className="data-card relative">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-80 h-80" role="img" aria-label="Ramachandran phi psi plot">
            <ellipse
              cx={toX(-63)}
              cy={toY(-43)}
              rx={34}
              ry={34}
              fill="#4ADE80"
              fillOpacity={0.06}
              stroke="#4ADE80"
              strokeOpacity={0.15}
            />
            <ellipse
              cx={toX(-120)}
              cy={toY(125)}
              rx={49}
              ry={49}
              fill="#7C3AED"
              fillOpacity={0.06}
              stroke="#7C3AED"
              strokeOpacity={0.15}
            />
            <ellipse
              cx={toX(60)}
              cy={toY(40)}
              rx={31}
              ry={38}
              fill="#FBBF24"
              fillOpacity={0.05}
              stroke="#FBBF24"
              strokeOpacity={0.13}
            />

            <line x1={PAD} y1={toY(0)} x2={W - PAD} y2={toY(0)} stroke="rgba(255,255,255,0.1)" />
            <line x1={toX(0)} y1={PAD} x2={toX(0)} y2={H - PAD} stroke="rgba(255,255,255,0.1)" />

            <text x={W / 2} y={H - 8} textAnchor="middle" fill="rgba(255,255,255,0.4)" fontSize={11}>
              φ (phi)
            </text>
            <text
              x={12}
              y={H / 2}
              textAnchor="middle"
              fill="rgba(255,255,255,0.4)"
              fontSize={11}
              transform={`rotate(-90, 12, ${H / 2})`}
            >
              ψ (psi)
            </text>

            {[-180, -90, 0, 90, 180].map((value) => (
              <g key={value}>
                <text x={toX(value)} y={H - PAD + 14} textAnchor="middle" fill="rgba(255,255,255,0.25)" fontSize={8}>
                  {value}°
                </text>
                <text x={PAD - 10} y={toY(value) + 3} textAnchor="end" fill="rgba(255,255,255,0.25)" fontSize={8}>
                  {value}°
                </text>
              </g>
            ))}

            {points.map((point, index) => (
              <circle
                key={`${point.chain}-${point.resnum}-${index}`}
                cx={toX(point.phi)}
                cy={toY(point.psi)}
                r={3}
                fill={REGION_COLOR[point.region] ?? REGION_COLOR.other}
                fillOpacity={0.75}
                className="cursor-pointer"
                onMouseEnter={() => setHovered(point)}
                onMouseLeave={() => setHovered(null)}
              />
            ))}
          </svg>

          {hovered && (
            <div className="absolute top-2 right-2 bg-viewer/90 border border-glass-border rounded-lg p-2 text-xs text-text-secondary pointer-events-none">
              <p className="text-accent-cyan font-bold">
                {hovered.residue}
                {hovered.resnum} · chain {hovered.chain}
              </p>
              <p>
                φ {hovered.phi.toFixed(1)}° · ψ {hovered.psi.toFixed(1)}°
              </p>
              <p>{REGION_LABEL[hovered.region] || REGION_LABEL.other}</p>
            </div>
          )}
        </div>

        <div className="space-y-3 flex-1">
          <p className="text-text-muted text-xs">n = {points.length} residues with defined φ/ψ angles</p>
          {Object.entries(counts).map(([region, count]) => (
            <div key={region}>
              <div className="flex justify-between text-xs mb-1">
                <span style={{ color: REGION_COLOR[region] }}>{REGION_LABEL[region]}</span>
                <span className="text-text-muted">
                  {points.length > 0 ? ((count / points.length) * 100).toFixed(1) : "0"}%
                </span>
              </div>
              <div className="w-full h-1.5 bg-surface-1 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${points.length > 0 ? (count / points.length) * 100 : 0}%`,
                    background: REGION_COLOR[region],
                    opacity: 0.7,
                  }}
                />
              </div>
            </div>
          ))}
          <p className="text-text-muted text-xs mt-4 leading-5">
            Basin labels are descriptive only. They are not a MolProbity-style residue-specific favored/allowed/outlier
            validation and should not be interpreted as an independent structure-quality score.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-4">
        {Object.entries(REGION_COLOR).map(([region, color]) => (
          <div key={region} className="flex items-center gap-1.5 text-xs text-text-muted">
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
            <span>{REGION_LABEL[region]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

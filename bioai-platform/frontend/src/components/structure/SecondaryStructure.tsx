"use client";

import { useEffect, useState } from "react";
import { apiUrl } from "@/lib/api";
import { downloadTsv } from "@/lib/export-utils";

type SSResidue = { position: number; residue: string; ss: string; source: string };

type SSResponse = {
  identifier?: string;
  method: string;
  evidence_class?: string;
  source?: string;
  residues: SSResidue[];
};

type Props = {
  identifier?: string | null;
  sequence?: string | null;
};

const SS_COLOR: Record<string, string> = {
  H: "#4ADE80",
  E: "#7C3AED",
  C: "rgba(255,255,255,0.15)",
};
const SS_LABEL: Record<string, string> = {
  H: "α-Helix",
  E: "β-Sheet",
  C: "Coil",
};

export function SecondaryStructureViewer({ identifier, sequence }: Props) {
  const [data, setData] = useState<SSResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const cleanSequence = (sequence || "").replace(/[^A-Za-z]/g, "").toUpperCase();
  const hasInput = Boolean(identifier || cleanSequence.length >= 5);

  useEffect(() => {
    if (!hasInput) {
      setLoading(false);
      setData(null);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);

    const load = async () => {
      const response = identifier
        ? await fetch(
            apiUrl(`/api/structure_analysis/secondary_structure/${encodeURIComponent(identifier)}`),
            { signal: controller.signal },
          )
        : await fetch(apiUrl("/api/structure_analysis/secondary_structure"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            signal: controller.signal,
            body: JSON.stringify({ sequence: cleanSequence }),
          });

      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail || `Secondary-structure analysis failed (HTTP ${response.status})`);
      }
      const result = await response.json();
      if (!controller.signal.aborted) setData(result);
    };

    load()
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err.message : "Secondary-structure analysis failed");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [identifier, cleanSequence, hasInput]);

  if (!hasInput) {
    return <div className="text-text-muted text-sm">No protein sequence is available for secondary-structure analysis.</div>;
  }
  if (loading) {
    return <div className="text-text-muted text-sm animate-pulse">Estimating secondary structure…</div>;
  }
  if (error) return <div className="text-error text-sm">{error}</div>;
  if (!data) return <div className="text-error text-sm">Failed to load.</div>;

  const { residues, method } = data;
  const chunkSize = 50;
  const rows: SSResidue[][] = [];
  for (let i = 0; i < residues.length; i += chunkSize) rows.push(residues.slice(i, i + chunkSize));

  const counts = {
    H: residues.filter((r) => r.ss === "H").length,
    E: residues.filter((r) => r.ss === "E").length,
    C: residues.filter((r) => r.ss === "C").length,
  };

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h3 className="text-text-primary font-semibold">Secondary Structure</h3>
          <p className="text-[11px] text-text-muted mt-0.5">
            {method} · {data.source || (identifier ? `UniProt ${identifier}` : "submitted protein sequence")}
          </p>
        </div>
        <button
          onClick={() =>
            downloadTsv(
              ["Position", "Residue", "Assignment", "Evidence class"],
              residues.map((r) => [
                String(r.position),
                r.residue,
                SS_LABEL[r.ss] || r.ss,
                data.evidence_class || r.source || "heuristic",
              ]),
              `secondary-structure-${identifier || "query"}.tsv`,
            )
          }
          className="btn-ghost text-xs px-2 py-1"
        >
          Export TSV
        </button>
      </div>

      <div className="flex h-4 rounded-full overflow-hidden gap-px">
        {(["H", "E", "C"] as const).map((ss) => (
          <div
            key={ss}
            style={{
              width: `${residues.length ? (counts[ss] / residues.length) * 100 : 0}%`,
              background: SS_COLOR[ss],
            }}
            title={`${SS_LABEL[ss]}: ${residues.length ? ((counts[ss] / residues.length) * 100).toFixed(1) : "0"}%`}
          />
        ))}
      </div>

      <div className="flex gap-4 text-xs text-text-muted flex-wrap">
        {(["H", "E", "C"] as const).map((ss) => (
          <span key={ss} className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ background: SS_COLOR[ss] }} />
            {SS_LABEL[ss]} {residues.length ? ((counts[ss] / residues.length) * 100).toFixed(0) : "0"}%
          </span>
        ))}
      </div>

      <div className="bg-surface-1 rounded-xl p-4 border border-glass-border space-y-3 max-h-72 overflow-y-auto">
        {rows.map((row, rowIndex) => (
          <div key={rowIndex} className="space-y-0.5">
            <div className="flex gap-px">
              {row.map((residue) => (
                <div
                  key={residue.position}
                  className="w-[14px] h-5 rounded-sm flex-shrink-0"
                  style={{ background: SS_COLOR[residue.ss] ?? "#333", opacity: 0.8 }}
                  title={`${residue.residue}${residue.position}: ${SS_LABEL[residue.ss] || residue.ss}`}
                />
              ))}
            </div>
            <div className="flex gap-px">
              {row.map((residue) => (
                <span
                  key={residue.position}
                  className="w-[14px] text-center text-[9px] text-text-muted flex-shrink-0 font-mono"
                >
                  {residue.residue}
                </span>
              ))}
            </div>
            <div className="text-[9px] text-text-muted font-mono">{row[0]?.position}</div>
          </div>
        ))}
      </div>

      <p className="text-[11px] leading-5 text-text-muted">
        This panel is a Chou-Fasman propensity heuristic and is reported as heuristic evidence. It is not a
        replacement for experimentally assigned secondary structure or a modern structure-based assignment such as DSSP.
      </p>
    </div>
  );
}

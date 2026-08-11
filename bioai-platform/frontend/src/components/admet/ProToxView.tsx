"use client";

import { useState } from "react";
import { CircleNotch as Loader2, Flask as Beaker, Warning as AlertTriangle, Check } from "@phosphor-icons/react";
import { computeProTox, type ProToxResult } from "@/lib/api";

const GREEN = "#4ADE80";
const AMBER = "#FBBF24";
const ORANGE = "#FB923C";
const RED = "#F87171";
const VIOLET = "#A78BFA";
const SLATE = "#848CA4";

const MODEL_LABELS: Record<string, string> = {
  dili: "Hepatotoxicity", neuro: "Neurotoxicity", nephro: "Nephrotoxicity",
  respi: "Respiratory", cardio: "Cardiotoxicity", carcino: "Carcinogenicity",
  immuno: "Immunotoxicity", mutagen: "Mutagenicity", cyto: "Cytotoxicity",
  bbb: "BBB barrier", eco: "Ecotoxicity", clinical: "Clinical", nutri: "Nutritional",
  nr_ahr: "AhR", nr_ar: "AR", nr_ar_lbd: "AR-LBD", nr_aromatase: "Aromatase",
  nr_er: "ER-α", nr_er_lbd: "ER-LBD", nr_ppar_gamma: "PPAR-γ",
  sr_are: "Nrf2/ARE", sr_hse: "HSE", sr_mmp: "MMP", sr_p53: "p53", sr_atad5: "ATAD5",
  mie_thr_alpha: "THR-α", mie_thr_beta: "THR-β", mie_ttr: "TTR", mie_ryr: "RYR",
  mie_gabar: "GABA-A R", mie_nmdar: "NMDA R", mie_ampar: "AMPA R", mie_kar: "KA R",
  mie_ache: "AChE", mie_car: "CAR", mie_pxr: "PXR", mie_nadhox: "NADH ox",
  mie_vgsc: "VGSC", mie_nis: "NIS",
};

function cellKey(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}

function findValue(row: Record<string, string>, keys: string[]): string {
  const entry = Object.entries(row).find(([k, v]) => v && keys.includes(cellKey(k)));
  return entry ? entry[1] : "";
}

function ToxLabel({ active }: { active: string }) {
  const a = active.toLowerCase();
  if (["1", "active", "toxic", "true"].includes(a)) {
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-molecule-rna"><AlertTriangle className="w-3 h-3" />Active</span>;
  }
  if (["0", "inactive", "false", "nontoxic"].includes(a)) {
    return <span className="inline-flex items-center gap-1 text-xs font-medium text-good"><Check className="w-3 h-3" />Inactive</span>;
  }
  return <span className="inline-flex items-center gap-1 text-xs font-medium text-warn"><AlertTriangle className="w-3 h-3" />{active}</span>;
}

function ClassBadge({ cls }: { cls: string }) {
  const num = parseInt(cls, 10);
  const cfg = [
    { label: "Class VI (non-toxic)", color: GREEN },
    { label: "Class V", color: "#86EFAC" },
    { label: "Class IV", color: AMBER },
    { label: "Class III", color: ORANGE },
    { label: "Class II", color: "#F87171" },
    { label: "Class I (highly toxic)", color: RED },
  ][(num && num >= 1 && num <= 6 ? num : 0) - 1];
  if (!cfg) return <span className="text-xs text-text-muted">{cls}</span>;
  return <span className="text-xs font-medium px-2 py-0.5 rounded" style={{ backgroundColor: `${cfg.color}22`, color: cfg.color }}>{cfg.label}</span>;
}

function ProbBar({ value }: { value: string }) {
  const num = parseFloat(value);
  if (isNaN(num)) return <span className="text-xs text-text-muted">{value}</span>;
  const v = Math.min(100, Math.max(0, num));
  const pct = v > 1 && num <= 100 ? v : v * 100;
  const color = num <= 100 && v > 1 ? (v >= 65 ? RED : v >= 45 ? AMBER : GREEN) : (pct >= 65 ? RED : pct >= 45 ? AMBER : GREEN);
  return (
    <div className="flex items-center gap-2">
      <div className="w-24 h-1.5 rounded bg-surface-3 overflow-hidden">
        <div className="h-full rounded" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="text-xs font-mono text-text-primary">{value}</span>
    </div>
  );
}

function GenericTable({ rows, kind }: { rows: Record<string, string>[]; kind: "model" | "target" }) {
  if (!rows || rows.length === 0) return <p className="text-xs text-text-muted py-2">No rows returned.</p>;
  const allKeys = Array.from(new Set(rows.flatMap((r) => Object.keys(r))));
  const labelKey = allKeys.find((k) => cellKey(k).includes("target") || cellKey(k).includes("name")) || allKeys[0];
  const predKey = allKeys.find((k) => cellKey(k).includes("prediction")) || "";
  const probKey = allKeys.find((k) => cellKey(k).includes("prob") || cellKey(k).includes("conf") || cellKey(k).includes("similar")) || "";
  return (
    <table className="w-full text-left text-xs">
      <thead>
        <tr className="text-text-muted border-b border-surface-3">
          <th className="py-2 pr-3 font-medium">Target</th>
          <th className="py-2 pr-3 font-medium">Prediction</th>
          {probKey && <th className="py-2 font-medium">Confidence</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => {
          const label = row[labelKey] ?? "";
          const labelDisplay = kind === "model" && MODEL_LABELS[cellKey(label)] ? MODEL_LABELS[cellKey(label)] : label;
          const pred = predKey ? (row[predKey] ?? "") : "";
          const prob = probKey ? (row[probKey] ?? "") : "";
          return (
            <tr key={i} className="border-b border-surface-3/50 last:border-0">
              <td className="py-2 pr-3 text-text-primary">{labelDisplay}</td>
              <td className="py-2 pr-3">{kind === "model" ? <ToxLabel active={pred} /> : <span className="text-text-primary">{pred || "—"}</span>}</td>
              {probKey && <td className="py-2">{prob ? <ProbBar value={prob} /> : "—"}</td>}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function AcuteCard({ acute, name }: { acute: Record<string, string>; name: string }) {
  const entries = Object.entries(acute).filter(([, v]) => v);
  if (entries.length === 0) return null;
  const ld50 = findValue(acute, ["ld50", "predicted_ld50"]);
  const cls = findValue(acute, ["tox_class", "class"]);
  const sim = findValue(acute, ["similarity", "avg_similarity"]);
  return (
    <div className="data-card p-5">
      <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2"><Beaker className="w-4 h-4 text-good" />Acute toxicity</h3>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-lg bg-surface-2 p-3 border border-surface-3">
          <div className="text-xs text-text-muted mb-1">Predicted LD50</div>
          <div className="text-lg font-mono font-semibold" style={{ color: ld50 && parseFloat(ld50) < 50 ? RED : GREEN }}>{ld50 || "—"}</div>
          <div className="text-xs text-text-muted">mg/kg (rat, oral)</div>
        </div>
        <div className="rounded-lg bg-surface-2 p-3 border border-surface-3">
          <div className="text-xs text-text-muted mb-1">Toxicity class</div>
          <ClassBadge cls={cls || ""} />
          <div className="text-[11px] text-text-muted mt-1.5">Globally Harmonized System (1–6)</div>
        </div>
        <div className="rounded-lg bg-surface-2 p-3 border border-surface-3">
          <div className="text-xs text-text-muted mb-1">Avg. similarity</div>
          <div className="text-lg font-mono font-semibold text-text-primary">{sim || "—"}</div>
          <div className="text-xs text-text-muted">to training compounds</div>
        </div>
      </div>
      {name && <p className="text-[11px] text-text-muted mt-3">Compound: <span className="text-text-primary">{name}</span></p>}
    </div>
  );
}

export default function ProToxView({ smiles, name }: { smiles: string; name?: string }) {
  const [data, setData] = useState<ProToxResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const run = async () => {
    setError("");
    setData(null);
    setLoading(true);
    try {
      const res = await computeProTox({ smiles: smiles || undefined, name: name || undefined });
      setData(res.result);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      const detail = msg.includes("502") ? "ProTox server is currently unreachable or the daily quota is exhausted. Try again later." : msg;
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  const modelCount = data ? data.requested_models.split(/\s+/).length : 0;

  return (
    <div className="space-y-4">
      <div className="data-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2"><Beaker className="w-4 h-4 text-good" />ProTox 3.0 toxicity prediction</h3>
            <p className="text-xs text-text-muted mt-1">
              Real ML prediction from Charité (61 endpoints): acute toxicity (LD50), organ toxicity, Tox21 pathways, targets &amp; CYP inhibition.
              Queued upstream — a run can take up to ~5 min.
            </p>
          </div>
          <button
            onClick={run}
            disabled={loading || (!smiles && !name)}
            className="inline-flex items-center gap-2 rounded-lg bg-good px-4 py-2 text-sm font-semibold text-ink transition-colors hover:bg-good/90 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Beaker className="w-4 h-4" />}
            {loading ? "Running…" : data ? "Run again" : "Run prediction"}
          </button>
        </div>
        {error && (
          <div className="mt-4 flex items-start gap-2 rounded-lg bg-molecule-rna/10 border border-molecule-rna/30 p-3">
            <AlertTriangle className="w-4 h-4 shrink-0 text-molecule-rna" />
            <p className="text-xs text-molecule-rna">{error}</p>
          </div>
        )}
        {loading && (
          <div className="mt-4 rounded-lg bg-surface-2 border border-surface-3 p-4 flex items-center gap-3">
            <Loader2 className="w-5 h-5 animate-spin text-good" />
            <div>
              <div className="text-xs font-medium text-text-primary">Submitting to ProTox 3.0…</div>
              <div className="text-[11px] text-text-muted">The Charité server queues requests; this usually takes 30 s – 5 min.</div>
            </div>
          </div>
        )}
      </div>

      {data && (
        <>
          <div className="flex items-center gap-2 text-[11px] text-text-muted">
            <span className="px-2 py-0.5 rounded bg-surface-2 border border-surface-3 font-mono">task {data.task_id}</span>
            <span>{modelCount} model groups · {data.chemical_name || data.input}</span>
          </div>
          <AcuteCard acute={data.acute_toxicity} name={data.chemical_name || ""} />

          {(data.model_results?.length ?? 0) > 0 && (
            <div className="data-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3">Organ toxicity · Endpoints · CYPs</h3>
              <GenericTable rows={data.model_results} kind="model" />
            </div>
          )}

          {(data.toxicity_targets?.length ?? 0) > 0 && (
            <div className="data-card p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3">Toxicity targets</h3>
              <GenericTable rows={data.toxicity_targets} kind="target" />
            </div>
          )}

          {data.methodology && (
            <div className="rounded-lg bg-surface-2 border border-surface-3 p-4">
              <div className="text-[11px] font-medium text-text-muted mb-1">METHODOLOGY</div>
              <p className="text-xs text-text-muted">{data.methodology.method}</p>
              <p className="text-[11px] text-text-muted mt-1">{data.methodology.note}</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

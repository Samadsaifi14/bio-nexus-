"use client";

import type { ADMETSwissADME } from "@/lib/api";
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  ScatterChart,
  XAxis,
  YAxis,
  Scatter,
  CartesianGrid,
  Customized,
  BarChart,
  Bar,
  ReferenceLine,
  LabelList,
} from "recharts";

const CYAN = "#2DD4BF";
const GREEN = "#34D399";
const AMBER = "#FBBF24";
const ORANGE = "#FB923C";
const RED = "#F87171";
const SLATE = "#848CA4";
const INK = "#DDE0EE";

function Section({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`data-card p-5 ${className}`}>
      <h3 className="text-sm font-semibold text-text-primary mb-3">{title}</h3>
      {children}
    </div>
  );
}

function Row({ label, value, unit, sub, color }: { label: string; value: React.ReactNode; unit?: string; sub?: string; color?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-surface-3 last:border-0">
      <span className="text-xs text-text-muted">{label}</span>
      <div className="text-right">
        <span className="text-sm font-mono font-medium" style={{ color: color ?? undefined }}>{value}</span>
        {unit && <span className="text-xs text-text-muted ml-1">{unit}</span>}
        {sub && <div className="text-xs text-text-muted">{sub}</div>}
      </div>
    </div>
  );
}

function Pill({ pass }: { pass: boolean }) {
  return pass
    ? <span className="text-xs text-good">Pass</span>
    : <span className="text-xs text-warn">Fail</span>;
}

function FilterCard({ name, data }: { name: string; data: { pass: boolean; violations: string[]; violation_count: number } }) {
  return (
    <div className="bg-surface-1 rounded-lg p-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-text-primary">{name}</span>
        <Pill pass={data.pass} />
      </div>
      <span className="text-[11px] text-text-muted">{data.violation_count} violation{data.violation_count === 1 ? "" : "s"}</span>
      {data.violations.length > 0 && (
        <ul className="mt-1 space-y-0.5">
          {data.violations.map((v, i) => <li key={i} className="text-[11px] text-warn/80">{v}</li>)}
        </ul>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Bioavailability Radar (SwissADME-style, 6 axes)                     */
/* ------------------------------------------------------------------ */

function BioavailabilityRadar({ radar }: { radar: ADMETSwissADME["bioavailability_radar"] }) {
  const data = radar.axes.map((a) => {
    const max = a.max || 1;
    const min = a.min;
    const value = Math.max(0, Math.min(1, a.value / max));
    const zoneStart = Math.max(0, Math.min(1, min / max));
    const zoneEnd = Math.max(0, Math.min(1, max / max));
    return { axis: a.axis, label: a.label, value, zoneStart, zoneEnd, raw: a.value, min, max, note: a.note };
  });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-center">
      <div className="w-full h-[340px]">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data} outerRadius="78%">
            <PolarGrid stroke="rgba(100,110,180,0.25)" />
            <PolarAngleAxis dataKey="axis" tick={{ fill: INK, fontSize: 12 }} />
            <Radar dataKey="zoneStart" stroke={CYAN} strokeOpacity={0.55} strokeWidth={1} strokeDasharray="3 3" fill="none" />
            <Radar dataKey="zoneEnd" stroke="none" fill="#2DD4BF" fillOpacity={0.10} />
            <Radar dataKey="value" stroke={CYAN} strokeWidth={2} fill={CYAN} fillOpacity={0.12} dot={{ r: 3, fill: CYAN, strokeWidth: 0 }} />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <div className="space-y-1.5">
        <p className="text-xs text-text-muted">Optimal zone (teal band), molecule (teal line).</p>
        {data.map((d) => {
          const ok = d.raw >= d.min && d.raw <= d.max;
          return (
            <div key={d.axis} className="flex items-center justify-between py-1 border-b border-surface-3 last:border-0">
              <div>
                <span className="text-xs font-medium text-text-primary">{d.axis}</span>
                <span className="text-[11px] text-text-muted ml-2">{d.label}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-text-secondary">{d.raw}</span>
                <span className="text-[10px] w-10 text-right" style={{ color: ok ? GREEN : AMBER }}>{ok ? "OK" : "out"}</span>
              </div>
            </div>
          );
        })}
        <p className={`text-xs pt-1 ${radar.all_optimal ? "text-good" : "text-warn"}`}>
          {radar.all_optimal ? "All six axes within optimal ranges." : "Some axes fall outside the optimal (pink) zone."}
        </p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* BOILED-Egg (ScatterChart + ellipse polygons)                        */
/* ------------------------------------------------------------------ */

function BoiledEgg({ egg }: { egg: ADMETSwissADME["pharmacokinetics"]["boiled_egg"] }) {
  const point = [{ tpsa: egg.tpsa, wlogp: egg.wlogp, region: egg.region }];
  const pointColor = egg.region === "yolk" ? AMBER : egg.region === "white" ? CYAN : RED;

  const Polygons = (props: any) => {
    const xScale = props?.xAxisMap?.["0"]?.scale;
    const yScale = props?.yAxisMap?.["0"]?.scale;
    if (!xScale || !yScale) return null;
    const toPoints = (arr: [number, number][]) => arr.map(([x, y]) => `${xScale(x)},${yScale(y)}`).join(" ");
    return (
      <g>
        <polygon points={toPoints(egg.polygons.white)} fill="rgba(226,232,240,0.14)" stroke="rgba(148,163,184,0.7)" strokeWidth={1.5} />
        <polygon points={toPoints(egg.polygons.yolk)} fill="rgba(251,191,36,0.22)" stroke={AMBER} strokeWidth={1.5} />
      </g>
    );
  };

  const CompoundDot = (props: any) => {
    const { cx, cy, payload } = props;
    return (
      <g>
        <circle cx={cx} cy={cy} r={7} fill={payload?.region === "yolk" ? AMBER : payload?.region === "white" ? CYAN : RED} stroke="#fff" strokeWidth={2} />
        <text x={cx} y={cy - 12} textAnchor="middle" fontSize={11} fill={INK}>compound</text>
      </g>
    );
  };

  return (
    <div>
      <div className="w-full h-[400px]">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 28, right: 20, bottom: 24, left: 8 }}>
            <CartesianGrid stroke="rgba(100,110,180,0.08)" strokeDasharray="3 3" />
            <XAxis type="number" dataKey="tpsa" name="TPSA" domain={[0, 140]} tickCount={8}
              tick={{ fill: SLATE, fontSize: 11 }} axisLine={{ stroke: "rgba(100,110,180,0.3)" }} tickLine={false}
              label={{ value: "TPSA (Å²)", position: "insideBottom", offset: -16, fill: SLATE, fontSize: 11 }} />
            <YAxis type="number" dataKey="wlogp" name="WLOGP" domain={[-7, 7]} tickCount={8}
              tick={{ fill: SLATE, fontSize: 11 }} axisLine={{ stroke: "rgba(100,110,180,0.3)" }} tickLine={false}
              label={{ value: "WLOGP", position: "insideLeft", angle: -90, offset: 6, fill: SLATE, fontSize: 11 }} />
            <Customized component={Polygons} />
            <Scatter name="compound" data={point} shape={CompoundDot} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-wrap items-center gap-4 mt-2 text-xs text-text-muted">
        <span className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm inline-block" style={{ background: "rgba(226,232,240,0.3)", border: "1px solid rgba(148,163,184,0.7)" }} />GI absorption — High</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm inline-block" style={{ background: "rgba(251,191,36,0.35)", border: "1px solid #FBBF24" }} />BBB permeant — Yes</span>
        <span className="inline-flex items-center gap-1.5"><span className="w-3 h-3 rounded-full inline-block" style={{ background: pointColor }} />This molecule</span>
        <span className="text-[11px] text-text-muted ml-auto">Region: <span className="font-mono text-text-secondary capitalize">{egg.region}</span> (TPSA {egg.tpsa}, WLOGP {egg.wlogp})</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Range bars (recharts) — ESOL / WLOGP / Log Kp on shared 0-100% axis */
/* ------------------------------------------------------------------ */

type RangeItem = { key: string; value: number; display: string; note: string; color: string; tick: string };

function RangeBars({ items }: { items: RangeItem[] }) {
  const data = items.map((it) => ({ key: it.key, value: it.value }));
  return (
    <div className="w-full h-[180px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart layout="vertical" data={data} margin={{ top: 0, right: 8, bottom: 0, left: 8 }} barCategoryGap={18}>
          <XAxis type="number" domain={[0, 1]} hide />
          <YAxis type="category" dataKey="key" width={150} tick={{ fill: INK, fontSize: 11 }} axisLine={false} tickLine={false} />
          <ReferenceLine x={0.5} stroke="rgba(100,110,180,0.4)" strokeDasharray="4 4" />
          <Bar dataKey="value" radius={[3, 3, 3, 3]}>
            {items.map((it) => (
              <LabelList key={it.key} dataKey="value" position="right" formatter={(v: number) => `${Math.round(v * 100)}%`} fill={SLATE} fontSize={10} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function norm(v: number, min: number, max: number) {
  return Math.max(0, Math.min(1, (v - min) / (max - min)));
}

/* ------------------------------------------------------------------ */
/* Main panel                                                          */
/* ------------------------------------------------------------------ */

export default function SwissADMEView({ data }: { data: ADMETSwissADME }) {
  const phys = data.physicochemical;
  const lipo = data.lipophilicity;
  const sol = data.water_solubility;
  const pk = data.pharmacokinetics;
  const dl = data.drug_likeness;
  const mc = data.medicinal_chemistry;

  const rangeItems: RangeItem[] = [
    { key: "WLOGP", value: norm(lipo.wlogp, -2, 6), display: `${lipo.wlogp}`, note: "domain -2..6", color: CYAN, tick: `${lipo.wlogp}` },
    { key: "ESOL log S", value: norm(sol.esol_log_s, -6, 0), display: `${sol.esol_log_s}`, note: "domain -6..0", color: GREEN, tick: `${sol.esol_log_s}` },
    { key: "Log Kp (skin, cm/s)", value: norm(pk.log_kp_skin, -8, -1), display: `${pk.log_kp_skin}`, note: "domain -8..-1", color: ORANGE, tick: `${pk.log_kp_skin}` },
  ];

  return (
    <div className="space-y-4">
      <div className="glass-card p-3 border-l-2 border-accent-cyan/50">
        <p className="text-xs text-text-muted">
          SwissADME-parity panel. Descriptors computed locally with RDKit (WLOGP = Wildman-Crippen). XLOGP3, MLOGP, SILICOS-IT
          and iLOGP are proprietary models and are marked unavailable; consensus Log P reflects WLOGP only. BOILED-Egg and ESOL
          use the published boundaries/models (Daina & Zoete 2016; Delaney 2004).
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Section title="Physicochemical Properties">
          <Row label="Formula" value={phys.formula} />
          <Row label="Molecular Weight" value={phys.molecular_weight} unit="g/mol" />
          <Row label="Fraction Csp3" value={phys.fraction_csp3} />
          <Row label="Rotatable Bonds" value={phys.rotatable_bonds} />
          <Row label="H-bond Acceptors" value={phys.hba} />
          <Row label="H-bond Donors" value={phys.hbd} />
          <Row label="TPSA" value={phys.tpsa} unit="Å²" />
        </Section>

        <Section title="Lipophilicity">
          <Row label="iLOGP" value={lipo.ilogp ?? "—"} />
          <Row label="XLOGP3" value={lipo.xlogp3 ?? "—"} />
          <Row label="WLOGP" value={lipo.wlogp} color={CYAN} />
          <Row label="MLOGP" value={lipo.mlogp ?? "—"} />
          <Row label="SILICOS-IT" value={lipo.silicos_it ?? "—"} />
          <Row label="Consensus Log P" value={lipo.consensus_log_p} color={CYAN} />
          <p className="text-[11px] text-text-muted pt-2">{lipo.note}</p>
        </Section>

        <Section title="Water Solubility (ESOL)">
          <Row label="Log S (ESOL)" value={sol.esol_log_s} />
          <Row label="Class" value={sol.esol_class} />
          <Row label="Solubility" value={sol.esol_mg_per_ml} unit="mg/ml" />
          <Row label="Solubility" value={sol.esol_mol_per_l} unit="mol/l" />
          <p className="text-[11px] text-text-muted pt-2">{sol.note}</p>
        </Section>

        <Section title="Pharmacokinetics">
          <Row label="GI Absorption" value={pk.gi_absorption} color={pk.gi_absorption === "High" ? GREEN : AMBER} />
          <Row label="BBB Permeant" value={pk.bbb_permeant} color={pk.bbb_permeant === "Yes" ? GREEN : AMBER} />
          <Row label="P-gp Substrate" value={pk.pgp_substrate} />
          <Row label="CYP1A2 Inhibitor" value={pk.cyp1a2_inhibitor} />
          <Row label="CYP2C19 Inhibitor" value={pk.cyp2c19_inhibitor} />
          <Row label="CYP2C9 Inhibitor" value={pk.cyp2c9_inhibitor} />
          <Row label="CYP2D6 Inhibitor" value={pk.cyp2d6_inhibitor} />
          <Row label="CYP3A4 Inhibitor" value={pk.cyp3a4_inhibitor} />
          <Row label="Log Kp (skin)" value={pk.log_kp_skin} unit="cm/s" />
        </Section>
      </div>

      <Section title="Bioavailability Radar">
        <BioavailabilityRadar radar={data.bioavailability_radar} />
      </Section>

      <Section title="BOILED-Egg (WLOGP vs TPSA)">
        <BoiledEgg egg={pk.boiled_egg} />
      </Section>

      <Section title="Profile Ranges">
        <RangeBars items={rangeItems} />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-1">
          {rangeItems.map((it) => (
            <div key={it.key} className="bg-surface-1 rounded-lg p-2 text-center">
              <div className="text-xs text-text-muted">{it.key}</div>
              <div className="text-sm font-mono font-medium text-text-primary">{it.tick}</div>
              <div className="text-[10px] text-text-muted">{it.note}</div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Drug Likeness">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <FilterCard name="Lipinski" data={dl.lipinski} />
          <FilterCard name="Ghose" data={dl.ghose} />
          <FilterCard name="Veber" data={dl.veber} />
          <FilterCard name="Egan" data={dl.egan} />
          <FilterCard name="Muegge" data={dl.muegge} />
          <div className="bg-surface-1 rounded-lg p-3 flex flex-col justify-center">
            <span className="text-xs text-text-muted">Bioavailability Score</span>
            <span className="text-lg font-bold text-accent-cyan">{dl.bioavailability_score}</span>
            <span className="text-[11px] text-text-muted">Martin 2005</span>
          </div>
        </div>
      </Section>

      <Section title="Medicinal Chemistry">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="bg-surface-1 rounded-lg p-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-text-primary">PAINS</span>
              <Pill pass={mc.pains_alerts.pass} />
            </div>
            <span className="text-[11px] text-text-muted">{mc.pains_alerts.alert_count} alert(s)</span>
            {mc.pains_alerts.alerts.length > 0 && (
              <ul className="mt-1 space-y-0.5">
                {mc.pains_alerts.alerts.map((a, i) => <li key={i} className="text-[11px] text-warn/80">{a}</li>)}
              </ul>
            )}
          </div>
          <div className="bg-surface-1 rounded-lg p-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-text-primary">Brenk</span>
              <Pill pass={mc.brenk_alerts.pass} />
            </div>
            <span className="text-[11px] text-text-muted">{mc.brenk_alerts.alert_count} alert(s)</span>
            {mc.brenk_alerts.alerts.length > 0 && (
              <ul className="mt-1 space-y-0.5">
                {mc.brenk_alerts.alerts.map((a, i) => <li key={i} className="text-[11px] text-warn/80">{a}</li>)}
              </ul>
            )}
          </div>
          <div className="bg-surface-1 rounded-lg p-3">
            <Row label="Lead-likeness violations" value={mc.lead_likeness_violations} />
            <Row label="Synthetic Accessibility" value={mc.synthetic_accessibility ?? "—"} />
            <p className="text-[11px] text-text-muted pt-1">SA score (1 = easy, 10 = hard), RDKit sascorer.</p>
          </div>
        </div>
      </Section>

      <p className="text-xs text-text-muted">Reference: Daina A., Michielin O., Zoete V. <span className="font-mono">Sci Rep 7, 42717 (2017)</span> — SwissADME.</p>
    </div>
  );
}

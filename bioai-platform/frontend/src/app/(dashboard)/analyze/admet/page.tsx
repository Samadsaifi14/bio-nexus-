"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, Beaker, Check, X, AlertTriangle, Loader2, Shield, Activity, Brain, Zap, Droplets } from "lucide-react";
import { fadeUp } from "@/lib/animations";
import { useAuditTrail } from "@/hooks/useAuditTrail";
import { computeADMET, type ADMETResult } from "@/lib/api";

const EXAMPLES = [
  { name: "Aspirin", smiles: "CC(=O)OC1=CC=CC=C1C(=O)O" },
  { name: "Caffeine", smiles: "CN1C=NC2=C1C(=O)N(C(=O)N2C)C" },
  { name: "Ibuprofen", smiles: "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O" },
  { name: "Paracetamol", smiles: "CC(=O)NC1=CC=C(C=C1)O" },
  { name: "Metformin", smiles: "CN(C)C(=N)NC(=N)N" },
  { name: "Omeprazole", smiles: "CC1=CN=C(C(=C1OC)C)CS(=O)C2=NC3=C(N2)C=CC=C3" },
];

const TABS = [
  { key: "overview", label: "Overview", icon: Activity },
  { key: "properties", label: "Properties", icon: Brain },
  { key: "druglikeness", label: "Drug-likeness", icon: Beaker },
  { key: "admet", label: "ADMET", icon: Shield },
  { key: "alerts", label: "Alerts", icon: AlertTriangle },
];

type TabKey = typeof TABS[number]["key"];

function PassFail({ pass }: { pass: boolean }) {
  return pass
    ? <span className="inline-flex items-center gap-1 text-xs text-green-400"><Check className="w-3 h-3" />Pass</span>
    : <span className="inline-flex items-center gap-1 text-xs text-amber-400"><AlertTriangle className="w-3 h-3" />Fail</span>;
}

function RiskBadge({ level }: { level: string }) {
  const low = ["Low", "Unlikely", "Non-inhibitor", "Non-mutagen", "Favorable", "Low toxicity"].some(s => level.includes(s));
  const high = ["High", "Likely", "Toxic", "Unfavorable"].some(s => level.includes(s));
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded ${
      low ? "bg-green-500/15 text-green-400" : high ? "bg-red-500/15 text-red-400" : "bg-amber-500/15 text-amber-400"
    }`}>{level}</span>
  );
}

function SectionCard({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`glass-card p-5 ${className}`}>
      <h3 className="text-sm font-semibold text-text-primary mb-3">{title}</h3>
      {children}
    </div>
  );
}

function PropRow({ label, value, unit, note }: { label: string; value: string | number; unit?: string; note?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-surface-3 last:border-0">
      <span className="text-xs text-text-muted">{label}</span>
      <div className="text-right">
        <span className="text-sm font-mono font-medium text-text-primary">{value}</span>
        {unit && <span className="text-xs text-text-muted ml-1">{unit}</span>}
        {note && <div className="text-xs text-text-muted">{note}</div>}
      </div>
    </div>
  );
}

export default function ADMETPage() {
  const router = useRouter();
  useAuditTrail();
  const [smiles, setSmiles] = useState("");
  const [result, setResult] = useState<ADMETResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<TabKey>("overview");

  const handleSubmit = async () => {
    if (!smiles.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await computeADMET(smiles.trim());
      setResult(res.result);
    } catch (e: any) {
      setError(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : e?.response?.data?.detail?.message || e.message || "Computation failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl">
      <button onClick={() => router.push("/analyze")}
        className="flex items-center gap-1 text-sm text-text-muted hover:text-text-primary mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Choose a different operation
      </button>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary mb-1">ADMET Analysis</h1>
        <p className="text-sm text-text-secondary">Comprehensive molecular descriptor computation: 50+ properties, ADMET predictions, drug-likeness filters, structural alerts.</p>
      </motion.div>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show">
        <div className="glass-card p-5">
          <label className="block text-sm text-text-secondary mb-2">SMILES String</label>
          <div className="flex gap-2">
            <input value={smiles} onChange={(e) => setSmiles(e.target.value)}
              placeholder="e.g. CC(=O)OC1=CC=CC=C1C(=O)O"
              className="flex-1 px-3 py-2 rounded-lg bg-surface-1 border border-surface-3 text-text-primary text-sm font-mono placeholder:text-text-muted focus:outline-none focus:border-accent-cyan"
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()} />
            <button onClick={handleSubmit} disabled={loading || !smiles.trim()}
              className="btn-primary px-4 py-2 text-sm flex items-center gap-2">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Beaker className="w-4 h-4" />}
              Analyze
            </button>
          </div>
          <div className="flex flex-wrap gap-2 mt-3">
            {EXAMPLES.map((ex) => (
              <button key={ex.name} onClick={() => setSmiles(ex.smiles)}
                className="text-xs px-2 py-1 rounded bg-surface-2 hover:bg-surface-3 text-text-secondary transition-colors">
                {ex.name}
              </button>
            ))}
          </div>
        </div>
      </motion.div>

      {error && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 glass-card p-4 border border-red-500/30">
          <p className="text-red-400 text-sm">{error}</p>
        </motion.div>
      )}

      {result && (
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="mt-6 space-y-4">
          {/* Header strip */}
          <div className="glass-card p-4 flex flex-wrap items-center gap-4">
            <div>
              <p className="text-xs text-text-muted">Formula</p>
              <p className="text-sm font-mono font-medium text-text-primary">{result.formula}</p>
            </div>
            <div className="h-6 w-px bg-surface-3" />
            <div>
              <p className="text-xs text-text-muted">SMILES</p>
              <p className="text-xs font-mono text-text-secondary max-w-md truncate">{result.smiles}</p>
            </div>
            <div className="ml-auto flex items-center gap-3">
              <div className="text-right">
                <p className="text-xs text-text-muted">Drug-likeness Score</p>
                <p className="text-xl font-bold text-accent-cyan">{result.drug_likeness.overall_score}<span className="text-xs text-text-muted">/100</span></p>
              </div>
              <div className="relative w-14 h-14">
                <svg viewBox="0 0 36 36" className="w-14 h-14 -rotate-90">
                  <circle cx="18" cy="18" r="15.9" fill="none" stroke="currentColor" className="text-surface-3" strokeWidth="3" />
                  <circle cx="18" cy="18" r="15.9" fill="none" stroke="currentColor"
                    className={result.drug_likeness.overall_score > 60 ? "text-green-400" : result.drug_likeness.overall_score > 40 ? "text-amber-400" : "text-red-400"}
                    strokeWidth="3" strokeDasharray={`${result.drug_likeness.overall_score} 100`} />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-text-primary">
                  {result.drug_likeness.overall_score > 60 ? "Good" : result.drug_likeness.overall_score > 40 ? "Fair" : "Poor"}
                </span>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 p-1 bg-surface-1 rounded-lg overflow-x-auto">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              return (
                <button key={tab.key} onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-medium transition-all whitespace-nowrap ${
                    activeTab === tab.key
                      ? "bg-accent-cyan/15 text-accent-cyan"
                      : "text-text-muted hover:text-text-secondary hover:bg-surface-2"
                  }`}>
                  <Icon className="w-3.5 h-3.5" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          <AnimatePresence mode="wait">
            {/* ---- OVERVIEW TAB ---- */}
            {activeTab === "overview" && (
              <motion.div key="overview" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-4">
                <SectionCard title="Quick Summary">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {[
                      { label: "MW", value: result.molecular_weight, unit: "g/mol", limit: 500 },
                      { label: "LogP", value: result.logp, unit: "", limit: 5 },
                      { label: "TPSA", value: result.tpsa, unit: "A2", limit: 140 },
                      { label: "HBD", value: result.hbd, unit: "", limit: 5 },
                      { label: "HBA", value: result.hba, unit: "", limit: 10 },
                      { label: "Rot. Bonds", value: result.rotatable_bonds, unit: "", limit: 10 },
                      { label: "QED", value: result.qed_score.toFixed(3), unit: "" },
                      { label: "Fsp3", value: result.fsp3, unit: "" },
                    ].map((p) => (
                      <div key={p.label} className="bg-surface-1 rounded-lg p-3">
                        <div className="text-xs text-text-muted">{p.label}</div>
                        <div className="text-lg font-semibold text-text-primary">{p.value}</div>
                        <div className="text-xs text-text-muted">{p.unit}</div>
                      </div>
                    ))}
                  </div>
                </SectionCard>

                <SectionCard title="ADMET Risk Overview">
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                    {[
                      { label: "Oral Bioavailability", value: `${(result.absorption.oral_bioavailability * 100).toFixed(0)}%` },
                      { label: "BBB Permeability", value: result.distribution.bbb_permeability },
                      { label: "CYP Inhibition", value: result.metabolism.cyp_substrate_risk },
                      { label: "AMES Mutagenicity", value: result.toxicity.ames_mutagenicity },
                      { label: "hERG Risk", value: result.toxicity.herg_liability },
                    ].map((p) => (
                      <div key={p.label} className="bg-surface-1 rounded-lg p-3 text-center">
                        <div className="text-xs text-text-muted mb-1">{p.label}</div>
                        <RiskBadge level={p.value} />
                      </div>
                    ))}
                  </div>
                </SectionCard>

                <SectionCard title="Drug-likeness Filters">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {[
                      { name: "Lipinski", data: result.drug_likeness.lipinski },
                      { name: "Veber", data: result.drug_likeness.veber },
                      { name: "Ghose", data: result.drug_likeness.ghose },
                      { name: "Egan", data: result.drug_likeness.egan },
                      { name: "MDDR", data: result.drug_likeness.mddr },
                    ].map((filter) => (
                      <div key={filter.name} className="bg-surface-1 rounded-lg p-3">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-medium text-text-primary">{filter.name}</span>
                          <PassFail pass={filter.data.pass} />
                        </div>
                        {filter.data.violations.length > 0 && (
                          <ul className="mt-1 space-y-0.5">
                            {filter.data.violations.map((v, i) => (
                              <li key={i} className="text-xs text-amber-400/80">{v}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                </SectionCard>
              </motion.div>
            )}

            {/* ---- PROPERTIES TAB ---- */}
            {activeTab === "properties" && (
              <motion.div key="properties" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-4">
                <SectionCard title="Physicochemical Properties">
                  <div className="space-y-0">
                    <PropRow label="Molecular Weight" value={result.molecular_weight} unit="g/mol" />
                    <PropRow label="LogP (Crippen)" value={result.logp} />
                    <PropRow label="TPSA" value={result.tpsa} unit="A2" />
                    <PropRow label="H-bond Donors (HBD)" value={result.hbd} />
                    <PropRow label="H-bond Acceptors (HBA)" value={result.hba} />
                    <PropRow label="Rotatable Bonds" value={result.rotatable_bonds} />
                    <PropRow label="Heavy Atoms" value={result.heavy_atoms} />
                    <PropRow label="Molar Refractivity" value={result.molar_refractivity} unit="cm3/mol" />
                    <PropRow label="Molecular Volume" value={result.molecular_volume} unit="A3" />
                    <PropRow label="Fsp3 (Fraction sp3)" value={result.fsp3} />
                    <PropRow label="Labute ASA" value={result.labute_asa} unit="A2" />
                    <PropRow label="E-state Sum" value={result.estate_sum} />
                    <PropRow label="Wiener Index" value={result.wiener_index} />
                    <PropRow label="Zagreb Index" value={result.zagreb_index} />
                  </div>
                </SectionCard>

                <SectionCard title="Ring & Scaffold Analysis">
                  <div className="space-y-0">
                    <PropRow label="Total Rings" value={result.ring_count} />
                    <PropRow label="Aromatic Rings" value={result.aromatic_ring_count} />
                    <PropRow label="Aliphatic Rings" value={result.aliphatic_ring_count} />
                    <PropRow label="Heteroatoms" value={result.num_heteroatoms} />
                    <PropRow label="Amide Bonds" value={result.num_amide_bonds} />
                    <PropRow label="Stereocenters" value={result.num_atom_stereocenters} />
                    <PropRow label="Unspecified Stereocenters" value={result.num_unspecified_stereocenters} />
                  </div>
                </SectionCard>

                <SectionCard title="Functional Groups">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {Object.entries(result.functional_groups).map(([name, count]) => (
                      <div key={name} className="bg-surface-1 rounded-lg p-2 text-center">
                        <div className="text-lg font-semibold text-text-primary">{count}</div>
                        <div className="text-xs text-text-muted capitalize">{name.replace(/_/g, " ")}</div>
                      </div>
                    ))}
                  </div>
                </SectionCard>
              </motion.div>
            )}

            {/* ---- DRUG-LIKENESS TAB ---- */}
            {activeTab === "druglikeness" && (
              <motion.div key="druglikeness" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-4">
                <SectionCard title="QED — Quantitative Estimate of Drug-likeness">
                  <div className="flex items-center gap-4">
                    <div className="relative w-20 h-20">
                      <svg viewBox="0 0 36 36" className="w-20 h-20 -rotate-90">
                        <circle cx="18" cy="18" r="15.9" fill="none" stroke="currentColor" className="text-surface-3" strokeWidth="3" />
                        <circle cx="18" cy="18" r="15.9" fill="none" stroke="currentColor"
                          className={result.qed_score > 0.5 ? "text-green-400" : result.qed_score > 0.3 ? "text-amber-400" : "text-red-400"}
                          strokeWidth="3" strokeDasharray={`${result.qed_score * 100} 100`} />
                      </svg>
                      <span className="absolute inset-0 flex items-center justify-center text-lg font-bold text-text-primary">{result.qed_score.toFixed(3)}</span>
                    </div>
                    <div>
                      <p className="text-sm text-text-secondary">
                        {result.qed_score > 0.6 ? "High drug-likeness" : result.qed_score > 0.3 ? "Moderate drug-likeness" : "Low drug-likeness"}
                      </p>
                      <p className="text-xs text-text-muted mt-1">Composite desirability score (Bickerton et al. 2012)</p>
                    </div>
                  </div>
                </SectionCard>

                <SectionCard title="Drug-likeness Filters">
                  <div className="space-y-4">
                    {[
                      { name: "Lipinski Rule of Five", desc: "MW<=500, LogP<=5, HBD<=5, HBA<=10 (violation<=1 allowed)", data: result.drug_likeness.lipinski },
                      { name: "Veber Rules", desc: "Rotatable bonds<=10, TPSA<=140", data: result.drug_likeness.veber },
                      { name: "Ghose Filter", desc: "160<=MW<=480, -0.4<=LogP<=5.6, 20<=atoms<=70, 40<=MR<=130", data: result.drug_likeness.ghose },
                      { name: "Egan Filter", desc: "TPSA<=132, LogP<=5.88 (oral absorption)", data: result.drug_likeness.egan },
                      { name: "MDDR-like Rules", desc: "200<=MW<=700, -2<=LogP<=6, TPSA<=180, rot<=15, rings<=8", data: result.drug_likeness.mddr },
                    ].map((filter) => (
                      <div key={filter.name} className={`rounded-lg p-3 border ${filter.data.pass ? "border-green-500/20 bg-green-500/5" : "border-amber-500/20 bg-amber-500/5"}`}>
                        <div className="flex items-center justify-between mb-1">
                          <div>
                            <span className="text-sm font-medium text-text-primary">{filter.name}</span>
                            <span className="text-xs text-text-muted ml-2">({filter.data.violation_count} violations)</span>
                          </div>
                          <PassFail pass={filter.data.pass} />
                        </div>
                        <p className="text-xs text-text-muted mb-1">{filter.desc}</p>
                        {filter.data.violations.length > 0 && (
                          <ul className="space-y-0.5">
                            {filter.data.violations.map((v, i) => (
                              <li key={i} className="text-xs text-amber-400/80 flex items-start gap-1">
                                <X className="w-3 h-3 mt-0.5 shrink-0" /> {v}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                </SectionCard>
              </motion.div>
            )}

            {/* ---- ADMET TAB ---- */}
            {activeTab === "admet" && (
              <motion.div key="admet" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-4">
                {/* Absorption */}
                <SectionCard title="Absorption">
                  <div className="space-y-0">
                    <PropRow label="Oral Bioavailability" value={`${(result.absorption.oral_bioavailability * 100).toFixed(0)}%`} note={result.absorption.oral_bioavailability > 0.7 ? "Good" : result.absorption.oral_bioavailability > 0.4 ? "Moderate" : "Poor"} />
                    <PropRow label="Caco-2 Permeability" value="" />
                    <div className="flex items-center gap-2 py-1.5 border-b border-surface-3">
                      <RiskBadge level={result.absorption.caco2_permeability} />
                    </div>
                    <PropRow label="Human Intestinal Absorption" value="" />
                    <div className="flex items-center gap-2 py-1.5 border-b border-surface-3">
                      <RiskBadge level={result.absorption.hia} />
                    </div>
                    <PropRow label="P-gp Substrate" value="" />
                    <div className="flex items-center gap-2 py-1.5 border-b border-surface-3">
                      <RiskBadge level={result.absorption.pgp_substrate} />
                    </div>
                    <PropRow label="P-gp Inhibitor" value="" />
                    <div className="flex items-center gap-2 py-1.5 border-b border-surface-3">
                      <RiskBadge level={result.absorption.pgp_inhibitor} />
                    </div>
                  </div>
                </SectionCard>

                {/* Distribution */}
                <SectionCard title="Distribution">
                  <div className="space-y-0">
                    <PropRow label="Volume of Distribution (Vd)" value={result.distribution.volume_of_distribution} unit="L/kg" />
                    <PropRow label="BBB Permeability" value="" />
                    <div className="flex items-center gap-2 py-1.5 border-b border-surface-3">
                      <RiskBadge level={result.distribution.bbb_permeability} />
                    </div>
                    <PropRow label="Plasma Protein Binding" value="" />
                    <div className="flex items-center gap-2 py-1.5 border-b border-surface-3">
                      <RiskBadge level={result.distribution.plasma_protein_binding} />
                    </div>
                    <PropRow label="CNS Penetration" value="" />
                    <div className="flex items-center gap-2 py-1.5 border-b border-surface-3">
                      <RiskBadge level={result.distribution.cns_penetration} />
                    </div>
                  </div>
                </SectionCard>

                {/* Metabolism */}
                <SectionCard title="Metabolism">
                  <div className="space-y-0">
                    <PropRow label="CYP Substrate Risk" value="" />
                    <div className="flex items-center gap-2 py-1.5 border-b border-surface-3">
                      <RiskBadge level={result.metabolism.cyp_substrate_risk} />
                    </div>
                    <PropRow label="Half-life Estimate" value="" />
                    <div className="flex items-center gap-2 py-1.5 border-b border-surface-3">
                      <RiskBadge level={result.metabolism.half_life_class} />
                    </div>
                    <PropRow label="Lipophilic Efficiency (LipE)" value={result.metabolism.lipophilic_efficiency} note="pIC50-LogP estimate" />
                  </div>
                  <div className="mt-3">
                    <p className="text-xs text-text-secondary mb-2">CYP Inhibition Panel</p>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                      {Object.entries(result.metabolism.cyp_inhibition).map(([cyp, status]) => (
                        <div key={cyp} className="bg-surface-1 rounded-lg p-2 text-center">
                          <div className="text-xs font-mono font-medium text-text-primary">{cyp}</div>
                          <div className="mt-1"><RiskBadge level={status} /></div>
                        </div>
                      ))}
                    </div>
                  </div>
                </SectionCard>

                {/* Toxicity */}
                <SectionCard title="Toxicity">
                  <div className="space-y-0">
                    <PropRow label="AMES Mutagenicity" value="" />
                    <div className="flex items-center gap-2 py-1.5 border-b border-surface-3">
                      <RiskBadge level={result.toxicity.ames_mutagenicity} />
                      {result.toxicity.ames_alerts.length > 0 && (
                        <span className="text-xs text-text-muted">({result.toxicity.ames_alerts.join(", ")})</span>
                      )}
                    </div>
                    <PropRow label="hERG Channel Liability" value="" />
                    <div className="flex items-center gap-2 py-1.5 border-b border-surface-3">
                      <RiskBadge level={result.toxicity.herg_liability} />
                    </div>
                    <PropRow label="Hepatotoxicity (DILI)" value="" />
                    <div className="flex items-center gap-2 py-1.5 border-b border-surface-3">
                      <RiskBadge level={result.toxicity.hepatotoxicity_dili} />
                    </div>
                    <PropRow label="Skin Sensitization" value="" />
                    <div className="flex items-center gap-2 py-1.5 border-b border-surface-3">
                      <RiskBadge level={result.toxicity.skin_sensitization} />
                      {result.toxicity.skin_sensitization_factors.length > 0 && (
                        <span className="text-xs text-text-muted">({result.toxicity.skin_sensitization_factors.join(", ")})</span>
                      )}
                    </div>
                    <PropRow label="Acute Toxicity (LD50)" value="" />
                    <div className="flex items-center gap-2 py-1.5 border-b border-surface-3">
                      <RiskBadge level={result.toxicity.acute_toxicity_ld50} />
                      <span className="text-xs text-text-muted">(log LD50 ~{result.toxicity.ld50_estimate_log})</span>
                    </div>
                    <PropRow label="Toxicity Risk Score" value={`${result.toxicity.risk_score}/10`} note={result.toxicity.risk_score <= 2 ? "Low risk" : result.toxicity.risk_score <= 5 ? "Moderate risk" : "High risk"} />
                  </div>
                </SectionCard>

                {/* Clearance */}
                <SectionCard title="Clearance & Elimination">
                  <div className="space-y-0">
                    <PropRow label="Clearance Class" value="" />
                    <div className="flex items-center gap-2 py-1.5 border-b border-surface-3">
                      <RiskBadge level={result.clearance.clearance_class} />
                    </div>
                    <PropRow label="Half-life Class" value="" />
                    <div className="flex items-center gap-2 py-1.5 border-b border-surface-3">
                      <RiskBadge level={result.clearance.half_life_class} />
                    </div>
                  </div>
                </SectionCard>
              </motion.div>
            )}

            {/* ---- ALERTS TAB ---- */}
            {activeTab === "alerts" && (
              <motion.div key="alerts" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-4">
                <SectionCard title="PAINS — Pan Assay Interference Compounds">
                  <div className="flex items-center gap-2 mb-2">
                    <PassFail pass={result.structural_alerts.pains.pass} />
                    <span className="text-xs text-text-muted">{result.structural_alerts.pains.alert_count} alerts</span>
                  </div>
                  {result.structural_alerts.pains.alerts.length > 0 ? (
                    <div className="bg-surface-1 rounded-lg p-3">
                      <ul className="space-y-1">
                        {result.structural_alerts.pains.alerts.map((a, i) => (
                          <li key={i} className="text-xs text-amber-400 flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" /> {a}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <p className="text-xs text-green-400">No PAINS patterns detected</p>
                  )}
                </SectionCard>

                <SectionCard title="Brenk Structural Alerts">
                  <div className="flex items-center gap-2 mb-2">
                    <PassFail pass={result.structural_alerts.brenk.pass} />
                    <span className="text-xs text-text-muted">{result.structural_alerts.brenk.alert_count} alerts</span>
                  </div>
                  {result.structural_alerts.brenk.alerts.length > 0 ? (
                    <div className="bg-surface-1 rounded-lg p-3">
                      <ul className="space-y-1">
                        {result.structural_alerts.brenk.alerts.map((a, i) => (
                          <li key={i} className="text-xs text-amber-400 flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" /> {a}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <p className="text-xs text-green-400">No Brenk alerts detected</p>
                  )}
                </SectionCard>

                <SectionCard title="Structural Alert Summary">
                  <div className="bg-surface-1 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-text-primary">Total Structural Alerts</span>
                      <span className={`text-lg font-bold ${result.structural_alerts.total_alert_count === 0 ? "text-green-400" : result.structural_alerts.total_alert_count <= 2 ? "text-amber-400" : "text-red-400"}`}>
                        {result.structural_alerts.total_alert_count}
                      </span>
                    </div>
                    <div className="w-full h-2 bg-surface-3 rounded-full">
                      <div className={`h-full rounded-full transition-all ${result.structural_alerts.total_alert_count === 0 ? "bg-green-400" : result.structural_alerts.total_alert_count <= 2 ? "bg-amber-400" : "bg-red-400"}`}
                        style={{ width: `${Math.min(result.structural_alerts.total_alert_count * 15, 100)}%` }} />
                    </div>
                    <p className="text-xs text-text-muted mt-2">
                      {result.structural_alerts.total_alert_count === 0
                        ? "Clean profile — no known problematic patterns"
                        : `${result.structural_alerts.total_alert_count} structural alert(s) flagged. Review before advancing to synthesis.`}
                    </p>
                  </div>
                </SectionCard>

                <SectionCard title="Toxicity Risk Score">
                  <div className="bg-surface-1 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-text-primary">Overall ADMET Risk</p>
                        <p className="text-xs text-text-muted mt-0.5">Composite of AMES, hERG, DILI, skin sensitization</p>
                      </div>
                      <div className={`text-2xl font-bold ${result.toxicity.risk_score <= 2 ? "text-green-400" : result.toxicity.risk_score <= 5 ? "text-amber-400" : "text-red-400"}`}>
                        {result.toxicity.risk_score}<span className="text-sm text-text-muted">/10</span>
                      </div>
                    </div>
                    <div className="w-full h-3 bg-surface-3 rounded-full mt-3">
                      <div className={`h-full rounded-full transition-all ${result.toxicity.risk_score <= 2 ? "bg-green-400" : result.toxicity.risk_score <= 5 ? "bg-amber-400" : "bg-red-400"}`}
                        style={{ width: `${result.toxicity.risk_score * 10}%` }} />
                    </div>
                  </div>
                </SectionCard>
              </motion.div>
            )}
          </AnimatePresence>

          <p className="text-xs text-text-muted text-center pt-2">Computed by RDKit. Rule-based heuristic predictions. For research use only.</p>
        </motion.div>
      )}
    </div>
  );
}

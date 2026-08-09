"use client";
import { useEffect, useState, useRef, useCallback } from "react";
import { downloadTsv, exportSvgPng } from "@/lib/export-utils";
import { useAuditTrail } from "@/hooks/useAuditTrail";

const DB_COLORS: Record<string, string> = {
  PFAM:    "#2DD4BF",
  PANTHER: "#7C3AED",
  PRINTS:  "#E0A94E",
  PROSITE: "#FBBF24",
  SMART:   "#3B82F6",
  CDD:     "#10B981",
};

const SITE_COLORS: Record<string, string> = {
  "Active site":          "#FBBF24",
  "Catalytic residue":    "#FB923C",
  "Binding site":         "#FFB84D",
  "Metal ion-binding site": "#FFD700",
};

const PTM_COLORS: Record<string, string> = {
  "Modified residue":  "#A78BFA",
  "Phosphorylation":   "#8B93D6",
  "Glycosylation":     "#06B6D4",
  "Acetylation":       "#10B981",
  "Ubiquitination":    "#E0A94E",
  "Methylation":       "#6366F1",
  "Sumoylation":       "#EC4899",
};

const MOTIF_COLORS: Record<string, string> = {
  "Zinc finger":                "#FBBF24",
  "Coiled-coil":                "#60A5FA",
  "Leucine-rich repeat":        "#34D399",
  "Immunoglobulin-like domain": "#F472B6",
  "SH2 domain":                 "#FB923C",
  "SH3 domain":                 "#A78BFA",
  "EGF-like domain":            "#2DD4BF",
  "PH domain":                  "#F87171",
  "Bromodomain":                "#818CF8",
  "default":                    "#9CA3AF",
};

type Domain = { accession: string; name: string; source_db: string; start: number; end: number; score?: number | null };
type DomainsResponse = { uniprot_accession: string; sequence_length: number; domains: Domain[] };

type FeatureItem = { type: string; description: string; begin: number | null; end: number | null; amino_acid?: string[] };
type FunctionalSite = FeatureItem;
type PTMItem = FeatureItem;
type TopologyItem = FeatureItem;
type MotifItem = FeatureItem;
type VariantItem = FeatureItem;
type DisulfideBond = { begin: number | null; end: number | null; description: string };
type CompositionBias = { type: string; description: string; begin: number | null; end: number | null };
type GOTerm = { id: string; term: string; category: string };
type PathwayAnnotation = { database: string; id: string; name: string };

type FullAnalysis = {
  accession: string;
  protein_name: string;
  organism: string;
  sequence_length: number;
  sequence: string;
  domains: Domain[];
  active_sites: FunctionalSite[];
  ptms: PTMItem[];
  topology: TopologyItem[];
  structural_motifs: MotifItem[];
  variants: VariantItem[];
  disulfide_bonds: DisulfideBond[];
  composition_bias: CompositionBias[];
  go_terms: GOTerm[];
  pathways: PathwayAnnotation[];
  feature_summary: Record<string, number>;
};

const TABS = [
  { id: "domains",    label: "Domains",    icon: "🧩" },
  { id: "sites",      label: "Sites",      icon: "⚡" },
  { id: "ptm",        label: "PTMs",       icon: "🔧" },
  { id: "motifs",     label: "Motifs",     icon: "🎯" },
  { id: "topology",   label: "Topology",   icon: "📐" },
  { id: "variants",   label: "Variants",   icon: "🔀" },
  { id: "go",         label: "GO Terms",   icon: "🏷️" },
  { id: "pathways",   label: "Pathways",   icon: "🛤️" },
  { id: "structure",  label: "Structure",  icon: "💎" },
] as const;

type TabId = typeof TABS[number]["id"];

export function DomainArchitecture({ accession }: { accession: string }) {
  const audit = useAuditTrail();
  const [data, setData] = useState<FullAnalysis | null>(null);
  const [domainsOnly, setDomainsOnly] = useState<DomainsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("domains");
  const [tooltip, setTooltip] = useState<{ text: string; sub: string; x: number; y: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const auditedRef = useRef(false);

  const fetchAll = useCallback(async () => {
    setError(null);
    auditedRef.current = false;
    try {
      const [fullResp, domainsResp] = await Promise.allSettled([
        fetch(`/api/backend/api/domains/${accession}/all`),
        fetch(`/api/backend/api/domains/${accession}`),
      ]);

      if (fullResp.status === "fulfilled" && fullResp.value.ok) {
        const full = await fullResp.value.json();
        setData(full);
        setDomainsOnly(null);
        if (!auditedRef.current) {
          auditedRef.current = true;
          audit.emitSuccess("domain_view", "InterPro+UniProt", accession,
            `${full.domains?.length || 0} domains, ${full.active_sites?.length || 0} sites, ${full.ptms?.length || 0} PTMs`);
        }
      } else if (domainsResp.status === "fulfilled" && domainsResp.value.ok) {
        const d = await domainsResp.value.json();
        setDomainsOnly(d);
        setData(null);
        if (!auditedRef.current) {
          auditedRef.current = true;
          audit.emitSuccess("domain_view", "InterPro", accession, `${d.domains?.length || 0} domains`);
        }
      } else {
        const detail = fullResp.status === "fulfilled"
          ? await fullResp.value.json().then(e => e.detail).catch(() => `Status ${fullResp.value.status}`)
          : "Network error";
        throw new Error(detail);
      }
    } catch (e: any) {
      setError(e.message);
      audit.emitFailed("domain_view", "InterPro", accession, e.message);
    } finally {
      setLoading(false);
    }
  }, [accession, audit]);

  useEffect(() => { setLoading(true); fetchAll(); }, [fetchAll]);

  const seqLen = data?.sequence_length ?? domainsOnly?.sequence_length ?? 0;
  const domains = data?.domains ?? domainsOnly?.domains ?? [];

  if (loading) return <div className="text-text-muted text-sm animate-pulse">Loading domain annotations&hellip;</div>;
  if (error) return <div className="text-error text-sm">{error}</div>;
  if (!data && !domainsOnly) return <div className="text-error text-sm">No data returned.</div>;

  return (
    <div className="space-y-4 relative">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 className="text-text-primary font-semibold">Domain &amp; Motif Analysis</h3>
          {data && (
            <p className="text-xs text-text-muted mt-0.5">
              {data.protein_name} &middot; {data.organism} &middot; {seqLen} aa
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <ExportMenu accession={accession} data={data} domains={domains} svgRef={svgRef} />
          <span className="text-text-muted text-xs">
            {domains.length} domains{data ? `, ${data.active_sites?.length || 0} sites, ${data.ptms?.length || 0} PTMs` : ""}
          </span>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        {Array.from(new Set(domains.map(d => d.source_db))).map(db => (
          <div key={db} className="flex items-center gap-1.5 text-xs text-text-muted">
            <div className="w-3 h-3 rounded-sm" style={{ background: DB_COLORS[db] ?? "#888" }} />
            {db}
          </div>
        ))}
      </div>

      {data && (
        <div className="flex flex-wrap gap-1 border-b border-glass-border pb-1">
          {TABS.map(tab => {
            const count = getTabCount(tab.id, data);
            return (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                  activeTab === tab.id
                    ? "bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/30"
                    : "text-text-muted hover:text-text-primary hover:bg-surface-1 border border-transparent"
                }`}>
                <span className="mr-1">{tab.icon}</span>
                {tab.label}
                {count > 0 && <span className="ml-1 text-[10px] opacity-60">{count}</span>}
              </button>
            );
          })}
        </div>
      )}

      {activeTab === "domains" && <DomainsTrack domains={domains} seqLen={seqLen} svgRef={svgRef} setTooltip={setTooltip} accession={accession} />}
      {activeTab === "sites" && data && <SitesTrack sites={data.active_sites} seqLen={seqLen} svgRef={svgRef} setTooltip={setTooltip} />}
      {activeTab === "ptm" && data && <PTMTrack ptms={data.ptms} seqLen={seqLen} svgRef={svgRef} setTooltip={setTooltip} />}
      {activeTab === "motifs" && data && <MotifsTrack motifs={data.structural_motifs} seqLen={seqLen} svgRef={svgRef} setTooltip={setTooltip} />}
      {activeTab === "topology" && data && <TopologyView topology={data.topology} seqLen={seqLen} />}
      {activeTab === "variants" && data && <VariantsTable variants={data.variants} />}
      {activeTab === "go" && data && <GOTermsView terms={data.go_terms} />}
      {activeTab === "pathways" && data && <PathwaysView pathways={data.pathways} />}
      {activeTab === "structure" && data && <StructureInfoView data={data} />}

      {tooltip && (
        <div className="fixed z-50 bg-viewer border border-glass-border rounded-xl p-3 text-xs text-text-primary shadow-2xl pointer-events-none max-w-xs"
          style={{ left: tooltip.x + 12, top: tooltip.y - 10 }}>
          <p className="font-bold text-accent-cyan">{tooltip.text}</p>
          <p className="text-text-muted">{tooltip.sub}</p>
        </div>
      )}
    </div>
  );
}

/* ---------- helpers ---------- */
function getTabCount(tabId: TabId, data: FullAnalysis): number {
  switch (tabId) {
    case "domains":   return data.domains?.length || 0;
    case "sites":     return data.active_sites?.length || 0;
    case "ptm":       return data.ptms?.length || 0;
    case "motifs":    return data.structural_motifs?.length || 0;
    case "topology":  return data.topology?.length || 0;
    case "variants":  return data.variants?.length || 0;
    case "go":        return data.go_terms?.length || 0;
    case "pathways":  return data.pathways?.length || 0;
    case "structure": return (data.disulfide_bonds?.length || 0) + (data.composition_bias?.length || 0);
    default: return 0;
  }
}

/* ---------- SVG track components ---------- */

function MultiTrackSVG({ seqLen, svgRef, setTooltip, children }: {
  seqLen: number;
  svgRef: React.RefObject<SVGSVGElement>;
  setTooltip: (t: { text: string; sub: string; x: number; y: number } | null) => void;
  children: React.ReactNode;
}) {
  const W = 700;
  const H = 60;
  return (
    <div className="overflow-x-auto">
      <svg ref={svgRef} viewBox={`0 0 ${W + 40} ${H + 20}`} className="w-full min-w-[400px]">
        <rect x={20} y={H / 2 - 4} width={W} height={8} rx={4} fill="rgba(255,255,255,0.08)" />
        {[0, 0.25, 0.5, 0.75, 1].map(t => (
          <g key={t}>
            <line x1={20 + t * W} y1={H / 2 + 4} x2={20 + t * W} y2={H / 2 + 10} stroke="rgba(255,255,255,0.2)" />
            <text x={20 + t * W} y={H / 2 + 20} textAnchor="middle" fill="rgba(255,255,255,0.3)" fontSize={9}>
              {Math.round(t * seqLen)}
            </text>
          </g>
        ))}
        {children}
      </svg>
    </div>
  );
}

function DomainsTrack({ domains, seqLen, svgRef, setTooltip, accession }: {
  domains: Domain[];
  seqLen: number;
  svgRef: React.RefObject<SVGSVGElement>;
  setTooltip: (t: { text: string; sub: string; x: number; y: number } | null) => void;
  accession: string;
}) {
  const W = 700;
  const scale = (pos: number) => (pos / seqLen) * W;
  return (
    <div className="space-y-4">
      <MultiTrackSVG seqLen={seqLen} svgRef={svgRef} setTooltip={setTooltip}>
        {domains.map((d, i) => {
          const x = 20 + scale(d.start);
          const w = Math.max(scale(d.end - d.start), 6);
          const color = DB_COLORS[d.source_db] ?? "#888";
          return (
            <g key={`${d.accession}-${i}`}
              onMouseEnter={e => setTooltip({ text: d.name, sub: `${d.accession} \u00b7 ${d.source_db} \u00b7 ${d.start}\u2013${d.end}`, x: e.clientX, y: e.clientY })}
              onMouseLeave={() => setTooltip(null)}
              className="cursor-pointer">
              <rect x={x} y={16} width={w} height={28} rx={4}
                fill={color} fillOpacity={0.3} stroke={color} strokeWidth={1.5} />
              {w > 40 && (
                <text x={x + w / 2} y={33} textAnchor="middle" fill={color} fontSize={8} fontWeight="bold">
                  {d.name.length > 12 ? d.name.slice(0, 11) + "\u2026" : d.name}
                </text>
              )}
            </g>
          );
        })}
      </MultiTrackSVG>

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

function SitesTrack({ sites, seqLen, svgRef, setTooltip }: {
  sites: FunctionalSite[];
  seqLen: number;
  svgRef: React.RefObject<SVGSVGElement>;
  setTooltip: (t: { text: string; sub: string; x: number; y: number } | null) => void;
}) {
  const W = 700;
  const scale = (pos: number) => (pos / seqLen) * W;
  if (!sites.length) return <p className="text-sm text-text-muted">No functional sites annotated.</p>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        {Object.entries(SITE_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1.5 text-xs text-text-muted">
            <div className="w-3 h-3 rounded-full" style={{ background: color }} />
            {type}
          </div>
        ))}
      </div>
      <MultiTrackSVG seqLen={seqLen} svgRef={svgRef} setTooltip={setTooltip}>
        {sites.map((s, i) => {
          const pos = s.begin ?? 0;
          const x = 20 + scale(pos);
          const color = SITE_COLORS[s.type] ?? "#FF6B6B";
          return (
            <g key={i}
              onMouseEnter={e => setTooltip({ text: s.type, sub: `${s.description || ""} \u00b7 Position ${s.begin}`, x: e.clientX, y: e.clientY })}
              onMouseLeave={() => setTooltip(null)}
              className="cursor-pointer">
              <line x1={x} y1={10} x2={x} y2={50} stroke={color} strokeWidth={2} />
              <circle cx={x} cy={30} r={5} fill={color} fillOpacity={0.5} stroke={color} strokeWidth={1.5} />
            </g>
          );
        })}
      </MultiTrackSVG>
      <div className="max-h-52 overflow-y-auto rounded-xl border border-glass-border">
        <table className="w-full text-xs">
          <thead className="bg-surface-1 sticky top-0">
            <tr>
              {["Type", "Description", "Position"].map(h => (
                <th key={h} className="px-3 py-2 text-left text-text-muted font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sites.map((s, i) => (
              <tr key={i} className="border-t border-glass-border hover:bg-surface-1">
                <td className="px-3 py-2 text-text-primary font-medium">{s.type}</td>
                <td className="px-3 py-2 text-text-secondary">{s.description || "\u2014"}</td>
                <td className="px-3 py-2 text-text-muted">{s.begin}{s.end && s.end !== s.begin ? `\u2013${s.end}` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PTMTrack({ ptms, seqLen, svgRef, setTooltip }: {
  ptms: PTMItem[];
  seqLen: number;
  svgRef: React.RefObject<SVGSVGElement>;
  setTooltip: (t: { text: string; sub: string; x: number; y: number } | null) => void;
}) {
  const W = 700;
  const scale = (pos: number) => (pos / seqLen) * W;
  if (!ptms.length) return <p className="text-sm text-text-muted">No post-translational modifications annotated.</p>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        {Object.entries(PTM_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1.5 text-xs text-text-muted">
            <div className="w-3 h-3 rounded-sm" style={{ background: color }} />
            {type}
          </div>
        ))}
      </div>
      <MultiTrackSVG seqLen={seqLen} svgRef={svgRef} setTooltip={setTooltip}>
        {ptms.map((p, i) => {
          const pos = p.begin ?? 0;
          const x = 20 + scale(pos);
          const color = PTM_COLORS[p.type] ?? "#A78BFA";
          return (
            <g key={i}
              onMouseEnter={e => setTooltip({ text: p.type, sub: `${p.description || ""} \u00b7 Position ${p.begin}`, x: e.clientX, y: e.clientY })}
              onMouseLeave={() => setTooltip(null)}
              className="cursor-pointer">
              <rect x={x - 3} y={18} width={6} height={24} rx={2} fill={color} fillOpacity={0.6} />
            </g>
          );
        })}
      </MultiTrackSVG>
      <div className="max-h-52 overflow-y-auto rounded-xl border border-glass-border">
        <table className="w-full text-xs">
          <thead className="bg-surface-1 sticky top-0">
            <tr>
              {["Type", "Description", "Position"].map(h => (
                <th key={h} className="px-3 py-2 text-left text-text-muted font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ptms.map((p, i) => (
              <tr key={i} className="border-t border-glass-border hover:bg-surface-1">
                <td className="px-3 py-2 text-text-primary font-medium">{p.type}</td>
                <td className="px-3 py-2 text-text-secondary">{p.description || "\u2014"}</td>
                <td className="px-3 py-2 text-text-muted">{p.begin}{p.end && p.end !== p.begin ? `\u2013${p.end}` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MotifsTrack({ motifs, seqLen, svgRef, setTooltip }: {
  motifs: MotifItem[];
  seqLen: number;
  svgRef: React.RefObject<SVGSVGElement>;
  setTooltip: (t: { text: string; sub: string; x: number; y: number } | null) => void;
}) {
  const W = 700;
  const scale = (pos: number) => (pos / seqLen) * W;
  if (!motifs.length) return <p className="text-sm text-text-muted">No structural motifs annotated.</p>;
  return (
    <div className="space-y-4">
      <MultiTrackSVG seqLen={seqLen} svgRef={svgRef} setTooltip={setTooltip}>
        {motifs.map((m, i) => {
          const begin = m.begin ?? 0;
          const end = m.end ?? begin + 10;
          const x = 20 + scale(begin);
          const w = Math.max(scale(end - begin), 6);
          const color = MOTIF_COLORS[m.type] ?? MOTIF_COLORS.default;
          return (
            <g key={i}
              onMouseEnter={e => setTooltip({ text: m.type, sub: `${m.description || ""} \u00b7 ${begin}\u2013${end}`, x: e.clientX, y: e.clientY })}
              onMouseLeave={() => setTooltip(null)}
              className="cursor-pointer">
              <rect x={x} y={18} width={w} height={24} rx={4}
                fill={color} fillOpacity={0.25} stroke={color} strokeWidth={1.5} strokeDasharray="4 2" />
            </g>
          );
        })}
      </MultiTrackSVG>
      <div className="max-h-52 overflow-y-auto rounded-xl border border-glass-border">
        <table className="w-full text-xs">
          <thead className="bg-surface-1 sticky top-0">
            <tr>
              {["Type", "Description", "Start", "End"].map(h => (
                <th key={h} className="px-3 py-2 text-left text-text-muted font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {motifs.map((m, i) => (
              <tr key={i} className="border-t border-glass-border hover:bg-surface-1">
                <td className="px-3 py-2 text-text-primary font-medium">{m.type}</td>
                <td className="px-3 py-2 text-text-secondary">{m.description || "\u2014"}</td>
                <td className="px-3 py-2 text-text-muted">{m.begin}</td>
                <td className="px-3 py-2 text-text-muted">{m.end}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ---------- list / table components ---------- */

function TopologyView({ topology, seqLen }: { topology: TopologyItem[]; seqLen: number }) {
  if (!topology.length) return <p className="text-sm text-text-muted">No topological features annotated.</p>;
  const TYPE_STYLE: Record<string, string> = {
    "Signal peptide": "bg-good/15 text-good border-good/30",
    "Transmembrane region": "bg-info/15 text-info border-info/30",
    "Chain": "bg-accent-purple/15 text-accent-purple border-accent-purple/30",
    "Propeptide": "bg-accent-amber/15 text-accent-amber border-accent-amber/30",
    "Peptide": "bg-accent-cyan/15 text-accent-cyan border-accent-cyan/30",
  };
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-xl border border-glass-border">
        <table className="w-full text-xs">
          <thead className="bg-surface-1 sticky top-0">
            <tr>
              {["Type", "Description", "Start", "End", "Length"].map(h => (
                <th key={h} className="px-3 py-2 text-left text-text-muted font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {topology.map((t, i) => (
              <tr key={i} className="border-t border-glass-border hover:bg-surface-1">
                <td className="px-3 py-2">
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${TYPE_STYLE[t.type] ?? "bg-surface-3/15 text-text-muted border-glass-border"}`}>
                    {t.type}
                  </span>
                </td>
                <td className="px-3 py-2 text-text-secondary">{t.description || "\u2014"}</td>
                <td className="px-3 py-2 text-text-muted">{t.begin}</td>
                <td className="px-3 py-2 text-text-muted">{t.end}</td>
                <td className="px-3 py-2 text-text-muted">{t.begin && t.end ? t.end - t.begin + 1 : "\u2014"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function VariantsTable({ variants }: { variants: VariantItem[] }) {
  if (!variants.length) return <p className="text-sm text-text-muted">No variants or mutagenesis data.</p>;
  return (
    <div className="max-h-80 overflow-y-auto rounded-xl border border-glass-border">
      <table className="w-full text-xs">
        <thead className="bg-surface-1 sticky top-0">
          <tr>
            {["Type", "Position", "Description"].map(h => (
              <th key={h} className="px-3 py-2 text-left text-text-muted font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {variants.map((v, i) => (
            <tr key={i} className="border-t border-glass-border hover:bg-surface-1">
              <td className="px-3 py-2">
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                  v.type === "Mutagenesis" ? "bg-warn/15 text-warn border-warn/30" : "bg-info/15 text-info border-info/30"
                }`}>{v.type}</span>
              </td>
              <td className="px-3 py-2 text-text-muted">{v.begin}</td>
              <td className="px-3 py-2 text-text-secondary max-w-sm">{v.description || "\u2014"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GOTermsView({ terms }: { terms: GOTerm[] }) {
  if (!terms.length) return <p className="text-sm text-text-muted">No Gene Ontology terms.</p>;
  const cats = [
    { id: "molecular_function", label: "Molecular Function", color: "text-info" },
    { id: "biological_process", label: "Biological Process", color: "text-good" },
    { id: "cellular_component", label: "Cellular Component", color: "text-accent-purple" },
  ];
  return (
    <div className="space-y-4">
      {cats.map(cat => {
        const items = terms.filter(t => t.category === cat.id);
        if (!items.length) return null;
        return (
          <div key={cat.id}>
            <h4 className={`text-xs font-semibold mb-2 ${cat.color}`}>{cat.label} ({items.length})</h4>
            <div className="flex flex-wrap gap-1.5">
              {items.map((t, i) => (
                <span key={i} className="px-2 py-1 text-[10px] rounded-lg bg-surface-1 border border-glass-border text-text-secondary">
                  {t.id} &middot; {t.term.replace(/^[FPC]:\s*/, "")}
                </span>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PathwaysView({ pathways }: { pathways: PathwayAnnotation[] }) {
  if (!pathways.length) return <p className="text-sm text-text-muted">No pathway annotations.</p>;
  const DB_ICONS: Record<string, string> = { KEGG: "🟠", Reactome: "🔵", WikiPathways: "🟣" };
  return (
    <div className="space-y-2">
      {pathways.map((p, i) => {
        const url = p.database === "KEGG"
          ? `https://www.genome.jp/entry/${p.id}`
          : p.database === "Reactome"
          ? `https://reactome.org/content/detail/${p.id}`
          : `https://www.wikipathways.org/index.php/${p.id}`;
        return (
          <a key={i} href={url} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-3 px-3 py-2 rounded-xl border border-glass-border hover:bg-surface-1 transition-colors">
            <span className="text-lg">{DB_ICONS[p.database] ?? "📋"}</span>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-text-primary truncate">{p.name || p.id}</p>
              <p className="text-[10px] text-text-muted">{p.database} &middot; {p.id}</p>
            </div>
            <span className="text-text-muted text-[10px]">\u2197</span>
          </a>
        );
      })}
    </div>
  );
}

function StructureInfoView({ data }: { data: FullAnalysis }) {
  return (
    <div className="space-y-4">
      {data.disulfide_bonds.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-text-primary mb-2">Disulfide Bonds ({data.disulfide_bonds.length})</h4>
          <div className="flex flex-wrap gap-1.5">
            {data.disulfide_bonds.map((b, i) => (
              <span key={i} className="px-2 py-1 text-[10px] rounded-lg bg-accent-amber/10 border border-accent-amber/30 text-accent-amber">
                Cys{b.begin}\u2013Cys{b.end}
              </span>
            ))}
          </div>
        </div>
      )}
      {data.composition_bias.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-text-primary mb-2">Composition Bias ({data.composition_bias.length})</h4>
          <div className="max-h-40 overflow-y-auto rounded-xl border border-glass-border">
            <table className="w-full text-xs">
              <thead className="bg-surface-1 sticky top-0">
                <tr>
                  {["Type", "Description", "Start", "End"].map(h => (
                    <th key={h} className="px-3 py-2 text-left text-text-muted font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.composition_bias.map((b, i) => (
                  <tr key={i} className="border-t border-glass-border hover:bg-surface-1">
                    <td className="px-3 py-2 text-text-primary">{b.type}</td>
                    <td className="px-3 py-2 text-text-secondary">{b.description || "\u2014"}</td>
                    <td className="px-3 py-2 text-text-muted">{b.begin}</td>
                    <td className="px-3 py-2 text-text-muted">{b.end}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {!data.disulfide_bonds.length && !data.composition_bias.length && (
        <p className="text-sm text-text-muted">No structural annotations.</p>
      )}
    </div>
  );
}

/* ---------- export menu ---------- */

function ExportMenu({ accession, data, domains, svgRef }: {
  accession: string;
  data: FullAnalysis | null;
  domains: Domain[];
  svgRef: React.RefObject<SVGSVGElement>;
}) {
  return (
    <div className="flex items-center gap-2">
      <button onClick={() => exportSvgPng(svgRef.current, `domains-${accession}.png`)}
        className="btn-ghost text-xs px-2 py-1">Export PNG</button>
      <button onClick={() => {
        const rows: [string, string, string, string, string, string][] = domains.map(d =>
          [d.accession, d.name, d.source_db, String(d.start), String(d.end), String(d.score ?? "")]
        );
        downloadTsv(["Accession", "Name", "DB", "Start", "End", "Score"], rows, `domains-${accession}.tsv`);
      }} className="btn-ghost text-xs px-2 py-1">Export TSV</button>
      {data && (
        <button onClick={() => {
          const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url; a.download = `domains-${accession}.json`; a.click();
          URL.revokeObjectURL(url);
        }} className="btn-ghost text-xs px-2 py-1">Export JSON</button>
      )}
    </div>
  );
}

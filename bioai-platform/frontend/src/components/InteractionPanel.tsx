'use client';

import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { fadeUp } from '@/lib/animations';
import {
  Flask as Beaker,
  WaveSine as Waves,
  Hexagon,
  Lightning as Zap,
  CaretDown as ChevronDown,
  CaretRight as ChevronRight,
  DownloadSimple as Download,
  ChartBar,
  Target,
  ShieldCheck,
} from '@phosphor-icons/react';
import type { DockingInteraction } from '@/lib/api';
import { downloadTsv } from '@/lib/export-utils';

interface InteractionPanelProps {
  interactions: DockingInteraction;
  onHighlight?: (coords: [number, number, number] | null) => void;
}

type ContactKind = 'H-bond' | 'Hydrophobic' | 'Pi-stacking' | 'Salt bridge';

type ContactRow = {
  kind: ContactKind;
  residue: string;
  chain: string;
  distance: number;
};

function safeMean(values: number[]): number | null {
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function ContactCountChart({ interactions }: { interactions: DockingInteraction }) {
  const data = [
    { label: 'H-bonds', value: interactions.hbonds.length },
    { label: 'Hydrophobic', value: interactions.hydrophobic.length },
    { label: 'Pi-stacking', value: interactions.pi_stacking.length },
    { label: 'Salt bridges', value: interactions.salt_bridges.length },
  ];
  const max = Math.max(1, ...data.map(item => item.value));

  return (
    <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
      <div className="mb-4 flex items-center gap-2">
        <ChartBar className="h-4 w-4 text-accent-cyan" />
        <div>
          <p className="text-sm font-semibold text-text-primary">Interaction counts</p>
          <p className="text-[11px] text-text-muted">Detected contacts for the reported best pose</p>
        </div>
      </div>
      <div className="space-y-3">
        {data.map(item => (
          <div key={item.label}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="text-text-secondary">{item.label}</span>
              <span className="font-mono text-text-primary">{item.value}</span>
            </div>
            <div className="h-2 overflow-hidden rounded bg-white/5">
              <div
                className="h-full rounded bg-accent-cyan/70 transition-all"
                style={{ width: `${(item.value / max) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DistancePlot({ rows }: { rows: ContactRow[] }) {
  const finite = rows.filter(row => Number.isFinite(row.distance));
  if (!finite.length) return null;

  const min = Math.min(...finite.map(row => row.distance));
  const max = Math.max(...finite.map(row => row.distance));
  const span = Math.max(0.25, max - min);
  const width = 520;
  const height = 180;
  const left = 52;
  const right = 18;
  const top = 18;
  const bottom = 34;
  const innerW = width - left - right;
  const innerH = height - top - bottom;
  const x = (distance: number) => left + ((distance - min) / span) * innerW;
  const y = (index: number) => top + (index / Math.max(1, finite.length - 1)) * innerH;

  return (
    <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
      <div className="mb-2 flex items-center gap-2">
        <Target className="h-4 w-4 text-accent-amber" />
        <div>
          <p className="text-sm font-semibold text-text-primary">Contact-distance map</p>
          <p className="text-[11px] text-text-muted">Every plotted point is a returned geometric contact, in Å</p>
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Docking contact distance plot" className="w-full overflow-visible">
        <line x1={left} x2={left + innerW} y1={top + innerH} y2={top + innerH} stroke="currentColor" className="text-white/15" />
        {[0, 0.25, 0.5, 0.75, 1].map(tick => {
          const value = min + span * tick;
          const tx = left + innerW * tick;
          return (
            <g key={tick}>
              <line x1={tx} x2={tx} y1={top} y2={top + innerH} stroke="currentColor" className="text-white/5" />
              <text x={tx} y={height - 10} textAnchor="middle" fontSize="10" fill="currentColor" className="text-text-muted">
                {value.toFixed(1)}
              </text>
            </g>
          );
        })}
        <text x={left + innerW / 2} y={height} textAnchor="middle" fontSize="10" fill="currentColor" className="text-text-muted">Distance (Å)</text>
        {finite.map((row, index) => (
          <g key={`${row.kind}-${row.residue}-${row.chain}-${index}`}>
            <circle cx={x(row.distance)} cy={y(index)} r="4" fill="currentColor" className="text-accent-cyan" />
            <title>{`${row.kind}: ${row.residue} chain ${row.chain}, ${row.distance.toFixed(2)} Å`}</title>
          </g>
        ))}
      </svg>
      <div className="mt-2 text-[11px] text-text-muted">Range: {min.toFixed(2)}–{max.toFixed(2)} Å · n={finite.length}</div>
    </div>
  );
}

function ResidueContactChart({ rows }: { rows: ContactRow[] }) {
  const ranked = useMemo(() => {
    const counts = new Map<string, number>();
    rows.forEach(row => {
      const key = `${row.residue}:${row.chain}`;
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return Array.from(counts.entries())
      .map(([label, value]) => ({ label, value }))
      .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label))
      .slice(0, 10);
  }, [rows]);

  if (!ranked.length) return null;
  const max = Math.max(...ranked.map(item => item.value), 1);

  return (
    <div className="rounded-xl border border-glass-border bg-surface-1 p-4">
      <p className="text-sm font-semibold text-text-primary">Most-contacted residues</p>
      <p className="mb-4 text-[11px] text-text-muted">Ranked only from returned interaction records</p>
      <div className="space-y-2">
        {ranked.map(item => (
          <div key={item.label} className="grid grid-cols-[92px_1fr_28px] items-center gap-2 text-xs">
            <span className="truncate font-mono text-text-secondary">{item.label}</span>
            <div className="h-2 overflow-hidden rounded bg-white/5">
              <div className="h-full rounded bg-accent-purple/70" style={{ width: `${(item.value / max) * 100}%` }} />
            </div>
            <span className="text-right font-mono text-text-primary">{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function HbondTable({ data, onHighlight }: { data: DockingInteraction['hbonds']; onHighlight?: (c: [number, number, number] | null) => void }) {
  const [collapsed, setCollapsed] = useState(false);
  if (!data.length) return null;
  return (
    <Section title="Hydrogen Bonds" icon={<Beaker className="w-4 h-4 text-interaction-hbond" />} count={data.length} color="bg-interaction-hbond/20 text-interaction-hbond" collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)}>
      {!collapsed && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="border-t border-white/5 text-text-muted uppercase tracking-wide">
              <th className="text-left px-3 py-1.5">Residue</th><th className="text-left px-3 py-1.5">Atom</th><th className="text-left px-3 py-1.5">Ligand atom</th><th className="text-left px-3 py-1.5">Distance</th><th className="text-left px-3 py-1.5">Confidence</th>
            </tr></thead>
            <tbody className="divide-y divide-white/5">
              {data.map((item, i) => (
                <tr key={i} className="text-text-secondary hover:bg-white/[0.02] cursor-pointer" onMouseEnter={() => onHighlight?.(item.protein_coords)} onMouseLeave={() => onHighlight?.(null)}>
                  <td className="px-3 py-1.5 font-mono">{item.protein_residue}{item.protein_residue_seq}<span className="text-text-muted">:{item.protein_chain}</span></td>
                  <td className="px-3 py-1.5 font-mono">{item.protein_atom}</td>
                  <td className="px-3 py-1.5 font-mono">{item.ligand_atom}</td>
                  <td className="px-3 py-1.5 font-mono">{item.distance.toFixed(2)} Å</td>
                  <td className="px-3 py-1.5"><span className="rounded border border-glass-border px-1.5 py-0.5 text-[10px]">{item.confidence}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function HydrophobicTable({ data, onHighlight }: { data: DockingInteraction['hydrophobic']; onHighlight?: (c: [number, number, number] | null) => void }) {
  const [collapsed, setCollapsed] = useState(false);
  if (!data.length) return null;
  return (
    <Section title="Hydrophobic Contacts" icon={<Waves className="w-4 h-4 text-interaction-hydrophobic" />} count={data.length} color="bg-interaction-hydrophobic/20 text-interaction-hydrophobic" collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)}>
      {!collapsed && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="border-t border-white/5 text-text-muted uppercase tracking-wide"><th className="text-left px-3 py-1.5">Residue</th><th className="text-left px-3 py-1.5">Atom</th><th className="text-left px-3 py-1.5">Ligand atom</th><th className="text-left px-3 py-1.5">Distance</th></tr></thead>
            <tbody className="divide-y divide-white/5">
              {data.map((item, i) => (
                <tr key={i} className="text-text-secondary hover:bg-white/[0.02] cursor-pointer" onMouseEnter={() => onHighlight?.(item.protein_coords)} onMouseLeave={() => onHighlight?.(null)}>
                  <td className="px-3 py-1.5 font-mono">{item.protein_residue}{item.protein_residue_seq}<span className="text-text-muted">:{item.protein_chain}</span></td>
                  <td className="px-3 py-1.5 font-mono">{item.protein_atom}</td><td className="px-3 py-1.5 font-mono">{item.ligand_atom}</td><td className="px-3 py-1.5 font-mono">{item.distance.toFixed(2)} Å</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function PiStackTable({ data, onHighlight }: { data: DockingInteraction['pi_stacking']; onHighlight?: (c: [number, number, number] | null) => void }) {
  const [collapsed, setCollapsed] = useState(false);
  if (!data.length) return null;
  return (
    <Section title="Pi-Stacking" icon={<Hexagon className="w-4 h-4 text-interaction-pi" />} count={data.length} color="bg-interaction-pi/20 text-interaction-pi" collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)}>
      {!collapsed && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="border-t border-white/5 text-text-muted uppercase tracking-wide"><th className="text-left px-3 py-1.5">Residue</th><th className="text-left px-3 py-1.5">Type</th><th className="text-left px-3 py-1.5">Distance</th><th className="text-left px-3 py-1.5">Angle</th><th className="text-left px-3 py-1.5">Confidence</th></tr></thead>
            <tbody className="divide-y divide-white/5">
              {data.map((item, i) => (
                <tr key={i} className="text-text-secondary hover:bg-white/[0.02] cursor-pointer" onMouseEnter={() => onHighlight?.(item.ring_centroid)} onMouseLeave={() => onHighlight?.(null)}>
                  <td className="px-3 py-1.5 font-mono">{item.protein_residue}{item.protein_residue_seq}<span className="text-text-muted">:{item.protein_chain}</span></td><td className="px-3 py-1.5 font-mono">{item.stacking_type}</td><td className="px-3 py-1.5 font-mono">{item.distance.toFixed(2)} Å</td><td className="px-3 py-1.5 font-mono">{item.angle.toFixed(1)}°</td><td className="px-3 py-1.5">{item.confidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function SaltBridgeTable({ data, onHighlight }: { data: DockingInteraction['salt_bridges']; onHighlight?: (c: [number, number, number] | null) => void }) {
  const [collapsed, setCollapsed] = useState(false);
  if (!data.length) return null;
  return (
    <Section title="Salt Bridges" icon={<Zap className="w-4 h-4 text-interaction-salt" />} count={data.length} color="bg-interaction-salt/20 text-interaction-salt" collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)}>
      {!collapsed && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs"><thead><tr className="border-t border-white/5 text-text-muted uppercase tracking-wide"><th className="text-left px-3 py-1.5">Residue</th><th className="text-left px-3 py-1.5">Atom</th><th className="text-left px-3 py-1.5">Ligand atom</th><th className="text-left px-3 py-1.5">Distance</th><th className="text-left px-3 py-1.5">Charge pair</th></tr></thead><tbody className="divide-y divide-white/5">
            {data.map((item, i) => <tr key={i} className="text-text-secondary hover:bg-white/[0.02] cursor-pointer" onMouseEnter={() => onHighlight?.(item.protein_coords)} onMouseLeave={() => onHighlight?.(null)}><td className="px-3 py-1.5 font-mono">{item.protein_residue}{item.protein_residue_seq}<span className="text-text-muted">:{item.protein_chain}</span></td><td className="px-3 py-1.5 font-mono">{item.protein_atom}</td><td className="px-3 py-1.5 font-mono">{item.ligand_atom}</td><td className="px-3 py-1.5 font-mono">{item.distance.toFixed(2)} Å</td><td className="px-3 py-1.5 font-mono text-[10px]">{item.charge_pair}</td></tr>)}
          </tbody></table>
        </div>
      )}
    </Section>
  );
}

function Section({ title, icon, count, color, collapsed, onToggle, children }: { title: string; icon: React.ReactNode; count: number; color: string; collapsed: boolean; onToggle: () => void; children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-lg border border-glass-border">
      <button onClick={onToggle} className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-white/5 transition-colors">
        <div className="flex items-center gap-2 text-sm font-medium text-text-primary">{icon}<span>{title}</span><span className={`text-xs px-1.5 py-0.5 rounded ${color}`}>{count}</span></div>
        {collapsed ? <ChevronRight className="w-4 h-4 text-text-muted" /> : <ChevronDown className="w-4 h-4 text-text-muted" />}
      </button>
      {children}
    </div>
  );
}

export function InteractionPanel({ interactions, onHighlight }: InteractionPanelProps) {
  const rows = useMemo<ContactRow[]>(() => [
    ...interactions.hbonds.map(item => ({ kind: 'H-bond' as const, residue: `${item.protein_residue}${item.protein_residue_seq}`, chain: item.protein_chain, distance: item.distance })),
    ...interactions.hydrophobic.map(item => ({ kind: 'Hydrophobic' as const, residue: `${item.protein_residue}${item.protein_residue_seq}`, chain: item.protein_chain, distance: item.distance })),
    ...interactions.pi_stacking.map(item => ({ kind: 'Pi-stacking' as const, residue: `${item.protein_residue}${item.protein_residue_seq}`, chain: item.protein_chain, distance: item.distance })),
    ...interactions.salt_bridges.map(item => ({ kind: 'Salt bridge' as const, residue: `${item.protein_residue}${item.protein_residue_seq}`, chain: item.protein_chain, distance: item.distance })),
  ], [interactions]);

  const total = rows.length;
  if (!total) return null;

  const meanDistance = safeMean(rows.map(row => row.distance).filter(Number.isFinite));
  const uniqueResidues = new Set(rows.map(row => `${row.residue}:${row.chain}`)).size;

  const exportInteractions = () => {
    const exportRows: string[][] = [];
    interactions.hbonds.forEach(it => exportRows.push(['hbond', it.protein_residue + it.protein_residue_seq + it.protein_chain, it.protein_atom, it.ligand_atom, it.distance.toFixed(2), it.confidence, '']));
    interactions.hydrophobic.forEach(it => exportRows.push(['hydrophobic', it.protein_residue + it.protein_residue_seq + it.protein_chain, it.protein_atom, it.ligand_atom, it.distance.toFixed(2), '', '']));
    interactions.pi_stacking.forEach(it => exportRows.push(['pi_stacking', it.protein_residue + it.protein_residue_seq + it.protein_chain, '', '', it.distance.toFixed(2), it.confidence, it.angle.toFixed(1)]));
    interactions.salt_bridges.forEach(it => exportRows.push(['salt_bridge', it.protein_residue + it.protein_residue_seq + it.protein_chain, it.protein_atom, it.ligand_atom, it.distance.toFixed(2), '', it.charge_pair]));
    downloadTsv(['Type', 'Residue', 'Protein atom', 'Ligand atom', 'Distance (A)', 'Confidence', 'Note'], exportRows, `docking_interactions_${total}.tsv`);
  };

  return (
    <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5">
      <div className="mb-4 flex flex-wrap items-start gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary"><Hexagon className="w-4 h-4 text-accent-cyan" />Interaction evidence</h3>
          <p className="mt-1 text-xs text-text-muted">Geometric contacts computed from the returned docked pose. No contacts are synthesized for display.</p>
        </div>
        <button onClick={exportInteractions} title="Download interactions as TSV" className="ml-auto flex items-center gap-1.5 rounded border border-glass-border bg-surface-1 px-2 py-1 text-xs text-text-secondary transition-colors hover:text-accent-cyan"><Download className="w-3.5 h-3.5" /> TSV</button>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-glass-border bg-surface-1 p-3"><p className="text-[11px] uppercase tracking-wide text-text-muted">Detected contacts</p><p className="mt-1 font-mono text-xl font-semibold text-text-primary">{total}</p></div>
        <div className="rounded-xl border border-glass-border bg-surface-1 p-3"><p className="text-[11px] uppercase tracking-wide text-text-muted">Contacted residues</p><p className="mt-1 font-mono text-xl font-semibold text-text-primary">{uniqueResidues}</p></div>
        <div className="rounded-xl border border-glass-border bg-surface-1 p-3"><p className="text-[11px] uppercase tracking-wide text-text-muted">Mean contact distance</p><p className="mt-1 font-mono text-xl font-semibold text-text-primary">{meanDistance == null ? '—' : `${meanDistance.toFixed(2)} Å`}</p></div>
      </div>

      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        <ContactCountChart interactions={interactions} />
        <ResidueContactChart rows={rows} />
      </div>
      <div className="mb-4"><DistancePlot rows={rows} /></div>

      <div className="mb-4 rounded-xl border border-accent-cyan/20 bg-accent-cyan/5 p-3 text-xs text-text-secondary">
        <div className="mb-1 flex items-center gap-2 font-medium text-text-primary"><ShieldCheck className="h-4 w-4 text-accent-cyan" />Evidence boundary</div>
        Contact geometry and Vina scores are computational docking outputs. They do not establish experimental binding affinity, efficacy, selectivity, or biological activity.
      </div>

      <div className="space-y-2">
        <HbondTable data={interactions.hbonds} onHighlight={onHighlight} />
        <HydrophobicTable data={interactions.hydrophobic} onHighlight={onHighlight} />
        <PiStackTable data={interactions.pi_stacking} onHighlight={onHighlight} />
        <SaltBridgeTable data={interactions.salt_bridges} onHighlight={onHighlight} />
      </div>
    </motion.div>
  );
}

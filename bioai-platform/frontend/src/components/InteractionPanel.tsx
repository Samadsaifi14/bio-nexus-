'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { fadeUp } from '@/lib/animations';
import { Beaker, Waves, Hexagon, ChevronDown, ChevronRight } from 'lucide-react';
import type { DockingInteraction } from '@/lib/api';

interface InteractionPanelProps {
  interactions: DockingInteraction;
}

function HbondTable({ data }: { data: DockingInteraction['hbonds'] }) {
  const [collapsed, setCollapsed] = useState(false);
  if (!data.length) return null;
  return (
    <Section title="Hydrogen Bonds" icon={<Beaker className="w-4 h-4 text-blue-400" />} count={data.length} color="bg-blue-500/20 text-blue-400" collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)}>
      {!collapsed && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="border-t border-white/5 text-white/40 uppercase tracking-wide">
              <th className="text-left px-3 py-1.5">Residue</th><th className="text-left px-3 py-1.5">Atom</th><th className="text-left px-3 py-1.5">Distance (Å)</th><th className="text-left px-3 py-1.5">Confidence</th>
            </tr></thead>
            <tbody className="divide-y divide-white/5">
              {data.map((item, i) => (
                <tr key={i} className="text-white/80 hover:bg-white/[0.02]">
                  <td className="px-3 py-1.5 font-mono">{item.protein_residue}</td>
                  <td className="px-3 py-1.5 font-mono">{item.protein_atom_name}</td>
                  <td className="px-3 py-1.5 font-mono">{item.distance.toFixed(2)}</td>
                  <td className="px-3 py-1.5">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                      item.confidence === 'high' ? 'bg-green-500/20 text-green-400' :
                      item.confidence === 'moderate' ? 'bg-amber-500/20 text-amber-400' :
                      'bg-yellow-500/20 text-yellow-400'
                    }`}>{item.confidence}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function HydrophobicTable({ data }: { data: DockingInteraction['hydrophobic'] }) {
  const [collapsed, setCollapsed] = useState(false);
  if (!data.length) return null;
  return (
    <Section title="Hydrophobic Contacts" icon={<Waves className="w-4 h-4 text-amber-400" />} count={data.length} color="bg-amber-500/20 text-amber-400" collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)}>
      {!collapsed && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="border-t border-white/5 text-white/40 uppercase tracking-wide">
              <th className="text-left px-3 py-1.5">Residue</th><th className="text-left px-3 py-1.5">Atom</th><th className="text-left px-3 py-1.5">Distance (Å)</th>
            </tr></thead>
            <tbody className="divide-y divide-white/5">
              {data.map((item, i) => (
                <tr key={i} className="text-white/80 hover:bg-white/[0.02]">
                  <td className="px-3 py-1.5 font-mono">{item.protein_residue}</td>
                  <td className="px-3 py-1.5 font-mono">{item.protein_atom_name}</td>
                  <td className="px-3 py-1.5 font-mono">{item.distance.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function PiStackTable({ data }: { data: DockingInteraction['pi_stacking'] }) {
  const [collapsed, setCollapsed] = useState(false);
  if (!data.length) return null;
  return (
    <Section title="Pi-Stacking" icon={<Hexagon className="w-4 h-4 text-purple-400" />} count={data.length} color="bg-purple-500/20 text-purple-400" collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)}>
      {!collapsed && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="border-t border-white/5 text-white/40 uppercase tracking-wide">
              <th className="text-left px-3 py-1.5">Residue</th><th className="text-left px-3 py-1.5">Centroid Dist (Å)</th><th className="text-left px-3 py-1.5">Confidence</th>
            </tr></thead>
            <tbody className="divide-y divide-white/5">
              {data.map((item, i) => (
                <tr key={i} className="text-white/80 hover:bg-white/[0.02]">
                  <td className="px-3 py-1.5 font-mono">{item.protein_residue}</td>
                  <td className="px-3 py-1.5 font-mono">{item.centroid_distance.toFixed(2)}</td>
                  <td className="px-3 py-1.5">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                      item.confidence === 'high' ? 'bg-green-500/20 text-green-400' :
                      item.confidence === 'moderate' ? 'bg-amber-500/20 text-amber-400' :
                      'bg-yellow-500/20 text-yellow-400'
                    }`}>{item.confidence}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function Section({ title, icon, count, color, collapsed, onToggle, children }: {
  title: string;
  icon: React.ReactNode;
  count: number;
  color: string;
  collapsed: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-white/10 rounded-lg overflow-hidden">
      <button onClick={onToggle} className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-white/5 transition-colors">
        <div className="flex items-center gap-2 text-sm font-medium text-white/90">
          {icon}
          <span>{title}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded ${color}`}>{count}</span>
        </div>
        {collapsed ? <ChevronRight className="w-4 h-4 text-white/40" /> : <ChevronDown className="w-4 h-4 text-white/40" />}
      </button>
      {children}
    </div>
  );
}

export function InteractionPanel({ interactions }: InteractionPanelProps) {
  const total =
    (interactions.hbonds?.length || 0) +
    (interactions.hydrophobic?.length || 0) +
    (interactions.pi_stacking?.length || 0);

  if (!total) return null;

  return (
    <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-5">
      <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
        <Hexagon className="w-4 h-4 text-accent-cyan" />
        Interaction Fingerprint
        <span className="text-xs font-normal text-text-muted">({total} contacts)</span>
      </h3>
      <div className="space-y-2">
        <HbondTable data={interactions.hbonds} />
        <HydrophobicTable data={interactions.hydrophobic} />
        <PiStackTable data={interactions.pi_stacking} />
      </div>
    </motion.div>
  );
}

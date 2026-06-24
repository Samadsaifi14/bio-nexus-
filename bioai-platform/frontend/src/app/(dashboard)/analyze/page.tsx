'use client';

import { useRouter } from 'next/navigation';
import { Dna, Layout, Search, Globe, GitBranch, Beaker, Layers, Share2, FlaskConical, Shuffle, GitFork, Atom } from 'lucide-react';
import { motion } from 'framer-motion';
import { fadeUp, stagger, cardHover } from '@/lib/animations';
import { ReactNode } from 'react';

type Operation = {
  id: string;
  name: string;
  description: string;
  icon: typeof Dna;
  active: boolean;
  badge?: string | null;
};

const groups: { title: string; items: Operation[] }[] = [
  {
    title: 'Sequence Analysis',
    items: [
      { id: 'blast',     name: 'BLAST Search',             description: 'Find similar sequences across organisms.',                 icon: Search,    active: true },
      { id: 'uniprot',   name: 'UniProt Lookup',           description: 'Retrieve detailed annotations for a known protein.',       icon: Globe,     active: true },
      { id: 'alignment', name: 'Multiple Sequence Alignment', description: 'Align sequences to find conserved regions and relationships.', icon: Layout, active: true },
      { id: 'domains',   name: 'Domain Analysis',          description: 'Fetch domain/motif annotations from InterPro.',             icon: Layers,    active: true },
      { id: 'phylo',     name: 'Phylogenetic Tree',        description: 'Build and visualize phylogenetic trees from sequences.',     icon: GitFork,   active: true },
      { id: 'sequencing', name: 'Sequencing Pipeline',     description: 'Raw FASTQ → QC → alignment → variant calling → report for genomic data.', icon: Dna, active: true, badge: 'New' },
    ],
  },
  {
    title: 'Structure & Networks',
    items: [
      { id: 'structure',   name: 'Structure Lookup',       description: 'Fetch 3D protein structures from PDB and visualize them.',  icon: Dna,       active: true },
      { id: 'pathway',     name: 'Pathway Analysis',       description: 'Map genes to biological pathways from Reactome/KEGG.',      icon: GitBranch, active: true },
      { id: 'interactions', name: 'Protein Interactions',  description: 'Explore interaction partners from the STRING database.',     icon: Share2,    active: true },
      { id: 'compare',     name: 'Structure Compare',      description: 'Find structurally similar proteins via PDBeFold (TM-align).', icon: Shuffle, active: true },
      { id: 'docking',     name: 'Molecular Docking',      description: 'Dock a small molecule into a protein using AutoDock Vina (free, CPU-based).', icon: Atom, active: true, badge: 'New' },
    ],
  },
  {
    title: 'Utilities',
    items: [
      { id: 'tools',   name: 'Utility Tools',   description: 'Format conversion, sequence validation, and everyday utilities.', icon: Beaker, active: true },
      { id: 'primers', name: 'Primer Design',   description: 'Design PCR primers using Primer3 — instant, no rate limits.',      icon: FlaskConical, active: true },
    ],
  },
];

function OperationCard({ op, router }: { op: Operation; router: ReturnType<typeof useRouter> }) {
  const Icon = op.icon;
  return (
    <motion.div variants={fadeUp} whileHover={op.active ? cardHover : undefined}>
      <button
        onClick={() => op.active && router.push(`/analyze/${op.id}`)}
        disabled={!op.active}
        className="relative text-left p-5 rounded-2xl border border-glass-border bg-glass-card cursor-pointer hover:bg-surface-1 transition w-full disabled:opacity-50"
      >
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-xl bg-accent-cyan/10">
            <Icon className="w-5 h-5 text-accent-cyan" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-text-primary">{op.name}</h3>
              {op.badge && (
                <span className="text-[10px] font-medium text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded-full whitespace-nowrap">
                  {op.badge}
                </span>
              )}
            </div>
            <p className="text-sm text-text-muted mt-1 leading-relaxed">{op.description}</p>
          </div>
        </div>
      </button>
    </motion.div>
  );
}

export default function AnalyzePage() {
  const router = useRouter();

  return (
    <div>
      <motion.div variants={fadeUp} initial="hidden" animate="show" className="mb-8">
        <div className="glass-card p-6 border border-accent-cyan/20 bg-accent-cyan/5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-text-primary">New: Guided Analysis Wizard</h2>
              <p className="text-sm text-text-secondary mt-1">A step-by-step 4-step pipeline &mdash; paste a sequence and get BLAST, pathways, and AI interpretation in one flow.</p>
            </div>
            <button onClick={() => router.push('/wizard')}
              className="btn-primary px-5 py-2.5 text-sm flex-shrink-0">
              Launch Wizard &rarr;
            </button>
          </div>
        </div>
      </motion.div>

      <motion.h1 variants={fadeUp} className="text-2xl font-bold text-text-primary mb-1">What do you want to do?</motion.h1>
      <motion.p variants={fadeUp} className="text-text-muted mb-8">Choose an operation to get started with your analysis.</motion.p>

      {groups.map(group => (
        <div key={group.title} className="mb-10">
          <motion.h2 variants={fadeUp} className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">{group.title}</motion.h2>
          <motion.div variants={stagger} initial="hidden" whileInView="show" viewport={{ once: true, margin: '-40px' }} className="grid md:grid-cols-2 gap-4">
            {group.items.map(op => (
              <OperationCard key={op.id} op={op} router={router} />
            ))}
          </motion.div>
        </div>
      ))}
    </div>
  );
}

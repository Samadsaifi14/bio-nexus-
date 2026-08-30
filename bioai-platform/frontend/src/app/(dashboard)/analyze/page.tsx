'use client';

import { useRouter } from 'next/navigation';
import { Dna, SquaresFour as Layout, MagnifyingGlass as Search, Globe, GitBranch, Flask as Beaker, Stack as Layers, ShareNetwork as Share2, TestTube as FlaskConical, Shuffle, GitFork, Atom, Pill, Pulse as Activity, Brain, ArrowsLeftRight as ArrowSwap, Calculator, Target, ChartScatter, Funnel, Rocket, HouseLine, Wrench } from '@phosphor-icons/react';
import { motion } from 'framer-motion';
import { fadeUp, stagger, press } from '@/lib/animations';
import { CriticalButton } from '@/components/ui';

type Operation = { id: string; name: string; description: string; icon: typeof Dna; badge?: string };
type Group = { title: string; description: string; items: Operation[] };

const groups: Group[] = [
  { title: 'Genomics', description: 'Raw sequencing data to quality-controlled, traceable evidence.', items: [
    { id: 'ngs-v2', name: 'NGS Analysis', description: 'Multi-assay FASTQ workflow with 21-stage QC contracts, coverage, contamination, identity, variant evidence and an analysis-readiness gate.', icon: Dna, badge: 'Flagship' },
    { id: 'sequencing', name: 'Consensus Sequencing', description: 'Focused reference/consensus workflow for compact sequencing analyses and teaching datasets.', icon: Layers },
  ]},
  { title: 'Sequence Biology', description: 'Similarity, conservation, evolution, motifs and sequence-level interpretation.', items: [
    { id: 'blast', name: 'BLAST Search', description: 'Similarity search with hit-level scores, identity, coverage, alignments and source evidence.', icon: Search },
    { id: 'pairwise', name: 'Pairwise Alignment', description: 'Global or local two-sequence alignment with scoring and complete match/mismatch/gap views.', icon: ArrowSwap },
    { id: 'alignment', name: 'Multiple Sequence Alignment', description: 'Conservation-aware MSA with alignment statistics and exportable aligned sequences.', icon: Layout },
    { id: 'phylo', name: 'Phylogenetic Analysis', description: 'Tree inference and interactive visualization with branch/support evidence.', icon: GitFork },
    { id: 'domains', name: 'Domains & Families', description: 'InterPro-backed domain architecture, coordinates and functional evidence.', icon: Layers },
    { id: 'motif', name: 'Motif Scanner', description: 'PROSITE/custom motif scanning with residue coordinates and match evidence.', icon: Target },
    { id: 'uniprot', name: 'UniProt Evidence', description: 'Curated protein annotations, identifiers and functional evidence.', icon: Globe },
    { id: 'sequences', name: 'Sequence Utilities', description: 'GC content, reverse complement, translation, molecular weight and restriction sites.', icon: Calculator },
    { id: 'dotplot', name: 'Dot Plot', description: 'Pairwise/self similarity visualization with tunable window and stringency.', icon: ChartScatter },
  ]},
  { title: 'Structural Biology', description: 'Structure retrieval, validation, pockets and simulation with explicit QC states.', items: [
    { id: 'structure', name: 'Structure Analysis', description: 'PDB structures with 3D visualization and structural quality context.', icon: Dna },
    { id: 'structure-prep', name: 'Structure Preparation', description: 'Broken-chain detection, repair, cleanup and pocket preparation workflow.', icon: Wrench },
    { id: 'castp', name: 'Pocket Analysis', description: 'CASTp-style cavity and solvent-accessible pocket characterization.', icon: Funnel },
    { id: 'compare', name: 'Structure Compare', description: 'Structural similarity and comparative geometry.', icon: Shuffle },
    { id: 'predict-structure', name: 'Structure Prediction', description: 'Sequence-to-structure prediction with confidence-aware output.', icon: Rocket },
    { id: 'swissmodel', name: 'SWISS-MODEL', description: 'Homology-model and experimental-structure retrieval.', icon: HouseLine },
    { id: 'md-v2', name: 'Molecular Dynamics', description: 'Staged MD with structure QC, force-field gate, equilibration, production, trajectory QC and convergence evidence.', icon: Activity, badge: 'QC workflow' },
    { id: 'function', name: 'Function Prediction', description: 'Structure-informed functional predictions with confidence context.', icon: Brain },
  ]},
  { title: 'Drug Discovery', description: 'Molecular interaction and developability evidence for research workflows.', items: [
    { id: 'docking', name: 'Molecular Docking', description: 'AutoDock Vina docking with pose, affinity and interaction evidence.', icon: Atom },
    { id: 'admet', name: 'ADMET & Drug-likeness', description: 'Physicochemical, pharmacokinetic, structural-alert and toxicity-oriented evidence.', icon: Pill },
  ]},
  { title: 'Systems Biology & Utilities', description: 'Networks, pathways and experimental design helpers.', items: [
    { id: 'pathway', name: 'Pathway Analysis', description: 'Pathway enrichment with gene membership and statistical evidence.', icon: GitBranch },
    { id: 'interactions', name: 'Protein Interactions', description: 'STRING-backed interaction networks and evidence channels.', icon: Share2 },
    { id: 'primers', name: 'Primer Design', description: 'Primer3-backed primer design and oligo QC.', icon: FlaskConical },
    { id: 'tools', name: 'Utility Tools', description: 'Validation, formatting and common bioinformatics helpers.', icon: Beaker },
  ]},
];

function OperationCard({ op, router }: { op: Operation; router: ReturnType<typeof useRouter> }) {
  const Icon = op.icon;
  return <motion.button variants={fadeUp} whileTap={press} onClick={() => router.push(`/analyze/${op.id}`)} className="group w-full rounded-xl border border-glass-border bg-surface-0 p-4 text-left transition hover:border-accent-cyan/35 hover:bg-surface-1">
    <div className="flex items-start gap-3"><div className="mt-0.5 rounded-lg border border-glass-border bg-surface-1 p-2"><Icon className="h-4 w-4 text-accent-cyan" /></div><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><h3 className="text-sm font-semibold text-text-primary">{op.name}</h3>{op.badge && <span className="rounded border border-accent-cyan/25 bg-accent-cyan/8 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-accent-cyan">{op.badge}</span>}</div><p className="mt-1 text-xs leading-5 text-text-muted">{op.description}</p></div></div>
  </motion.button>;
}

export default function AnalyzePage() {
  const router = useRouter();
  return <div className="max-w-6xl">
    <motion.div variants={fadeUp} initial={{ y: 18 }} animate="show" className="mb-8 flex flex-col justify-between gap-4 border-b border-glass-border pb-6 md:flex-row md:items-end"><div><p className="mb-2 font-mono text-[10px] uppercase tracking-[0.18em] text-accent-cyan">Scientific workspace</p><h1 className="text-2xl font-semibold text-text-primary">Choose a research workflow</h1><p className="mt-2 max-w-2xl text-sm text-text-muted">Run established bioinformatics methods while preserving QC, raw outputs, methods and provenance as first-class results.</p></div><CriticalButton onClick={() => router.push('/wizard')} className="px-4 py-2.5 text-sm">Guided workflow</CriticalButton></motion.div>
    {groups.map((group) => <section key={group.title} className="mb-9"><div className="mb-3"><h2 className="text-sm font-semibold text-text-primary">{group.title}</h2><p className="mt-0.5 text-xs text-text-muted">{group.description}</p></div><motion.div variants={stagger} initial="hidden" animate="show" className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{group.items.map((op) => <OperationCard key={op.id} op={op} router={router} />)}</motion.div></section>)}
  </div>;
}

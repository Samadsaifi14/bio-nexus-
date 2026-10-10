'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Dna, SquaresFour as Layout, MagnifyingGlass as Search, Globe, GitBranch, Flask as Beaker, Stack as Layers, ShareNetwork as Share2, TestTube as FlaskConical, Shuffle, GitFork, Atom, Pill, Pulse as Activity, Brain, ArrowsLeftRight as ArrowSwap, Calculator, Target, ChartScatter, Funnel, Rocket, HouseLine, Wrench, ArrowUpRight, X } from '@phosphor-icons/react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';

type Operation = { id: string; name: string; description: string; icon: typeof Dna; badge?: string };
type Group = { title: string; description: string; items: Operation[] };

const groups: Group[] = [
  { title: 'Genomics', description: 'Raw sequencing data to quality-controlled, traceable evidence.', items: [
    { id: 'ngs-v2', name: 'RNA-seq Analysis', description: 'GEO discovery, FASTQ quality control, reference alignment, raw counts and DESeq2 figures.', icon: Dna, badge: 'Flagship' },
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
    { id: 'function', name: 'Function Evidence & Functional Hints', description: 'Explore source-linked annotations and clearly labelled functional hints.', icon: Brain },
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

export default function AnalyzePage() {
  const [category, setCategory] = useState('All methods');
  const [query, setQuery] = useState('');
  const reduceMotion = useReducedMotion();
  const filtered = useMemo(() => groups.map(group => ({ ...group, items: group.items.filter(op =>
    (category === 'All methods' || category === group.title) &&
    `${op.name} ${op.description} ${group.title}`.toLowerCase().includes(query.trim().toLowerCase())
  ) })).filter(group => group.items.length > 0), [category, query]);
  const count = filtered.reduce((total, group) => total + group.items.length, 0);

  return <div className="bn-catalog max-w-7xl">
    <div className="bn-catalog-heading">
      <div><p className="bn-kicker">BioNexus / Methods</p><h1>What would you like to investigate?</h1><p>Search by question or choose a field. Each method opens a dedicated workspace with its own inputs and result views.</p></div>
      <Link href="/wizard" className="bn-button bn-button-primary shrink-0">Help me choose <ArrowUpRight size={18} aria-hidden="true" /></Link>
    </div>
    <div className="bn-catalog-layout">
      <aside className="bn-catalog-filters" aria-label="Filter methods by field">
        <p className="bn-kicker">Fields</p>
        {['All methods', ...groups.map(group => group.title)].map(label => <button key={label} type="button" aria-pressed={category === label} onClick={() => setCategory(label)} className={`bn-filter ${category === label ? 'is-active' : ''}`}><span>{label}</span><span className="font-mono text-xs">{label === 'All methods' ? groups.reduce((n, g) => n + g.items.length, 0) : groups.find(g => g.title === label)?.items.length}</span></button>)}
        <div className="bn-filter-help"><span>NEW TO THE WORKSPACE?</span><p>Answer a few questions and follow a guided path.</p><Link href="/wizard">Open guide <ArrowUpRight size={15} aria-hidden="true" /></Link></div>
      </aside>
      <div className="bn-catalog-results">
        <div className="bn-catalog-toolbar"><label className="bn-search-field"><Search size={19} aria-hidden="true" /><span className="sr-only">Search methods</span><input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search methods, inputs or evidence" /></label><span className="bn-result-count" aria-live="polite">{count} {count === 1 ? 'method' : 'methods'}</span></div>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={`${category}:${query}`} initial={reduceMotion ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -6 }} transition={{ duration: .2 }}>
            {count ? filtered.map(group => <section key={group.title} className="bn-catalog-group"><div className="bn-catalog-group-heading"><div><p className="bn-kicker">{group.title}</p><h2>{group.description}</h2></div><span className="font-mono text-xs text-text-muted">{String(group.items.length).padStart(2, '0')}</span></div>
              <div className="bn-catalog-rows">{group.items.map(op => { const Icon = op.icon; return <Link href={`/analyze/${op.id}`} key={op.id} className="bn-catalog-row group"><span className="bn-catalog-icon"><Icon size={21} aria-hidden="true" /></span><span className="min-w-0"><span className="bn-catalog-name">{op.name} {op.badge && <small>{op.badge}</small>}</span><span className="bn-catalog-description">{op.description}</span></span><ArrowUpRight className="bn-catalog-arrow" size={19} aria-hidden="true" /></Link>; })}</div>
            </section>) : <div className="bn-catalog-empty"><Search size={30} aria-hidden="true" /><h2>No methods match that search.</h2><p>Try another term or show every method.</p><button type="button" onClick={() => { setQuery(''); setCategory('All methods'); }}>Clear filters <X size={16} aria-hidden="true" /></button></div>}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  </div>;
}

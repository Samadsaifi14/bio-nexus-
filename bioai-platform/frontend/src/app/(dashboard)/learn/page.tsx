'use client';

import Link from 'next/link';
import {
  Search, Dna, Layout, Layers, GitFork, Globe,
  GitBranch, Share2, FlaskConical, Beaker, BookOpen, ArrowRight,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { fadeUp, stagger, cardHover } from '@/lib/animations';
import { useState } from 'react';
import type { LucideIcon } from 'lucide-react';

type Topic = {
  id: string;
  title: string;
  description: string;
  icon: LucideIcon;
};

const groups: { title: string; items: Topic[] }[] = [
  {
    title: 'Sequence Analysis',
    items: [
      { id: 'blast',     title: 'BLAST Search',            description: 'Find similar sequences and understand E-values, bit scores, and identity.',   icon: Search },
      { id: 'alignment', title: 'Sequence Alignment',      description: 'Pairwise and multiple alignment — scoring matrices, gap penalties, and output.', icon: Layout },
      { id: 'domains',   title: 'Domain Analysis',         description: 'Protein domains, Pfam, InterPro, and domain architecture.',                     icon: Layers },
      { id: 'phylo',     title: 'Phylogenetic Trees',      description: 'Tree-building methods, bootstrap values, and branch lengths.',                  icon: GitFork },
    ],
  },
  {
    title: 'Structure & Networks',
    items: [
      { id: 'structure',   title: 'Protein Structure',     description: 'PDB format, AlphaFold, pLDDT scores, and structure visualization.',            icon: Dna },
      { id: 'pathways',    title: 'Pathway Analysis',      description: 'Reactome vs KEGG, pathway mapping, and enrichment analysis.',                  icon: GitBranch },
      { id: 'interactions', title: 'Protein Interactions', description: 'STRING database, interaction networks, and confidence scores.',                icon: Globe },
    ],
  },
  {
    title: 'Utilities',
    items: [
      { id: 'primers', title: 'Primer Design',        description: 'PCR basics, Primer3, melting temperature, and GC content.',           icon: FlaskConical },
      { id: 'tools',   title: 'Format Converter',     description: 'Sequence format conversion and validation utilities.',                 icon: Beaker },
      { id: 'glossary', title: 'Glossary',            description: 'A–Z of bioinformatics terms with plain-English definitions.',          icon: BookOpen },
    ],
  },
];

function TopicCard({ topic }: { topic: Topic }) {
  const Icon = topic.icon;
  return (
    <motion.div variants={fadeUp} whileHover={cardHover}>
      <Link
        href={`/learn/${topic.id}`}
        className="relative block p-5 rounded-2xl border border-glass-border bg-glass-card hover:bg-surface-1 transition h-full"
      >
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-xl bg-accent-cyan/10 flex-shrink-0">
            <Icon className="w-5 h-5 text-accent-cyan" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-text-primary">{topic.title}</h3>
            <p className="text-sm text-text-muted mt-1 leading-relaxed">{topic.description}</p>
            <div className="flex items-center gap-1 mt-3 text-xs text-accent-cyan font-medium">
              Learn more <ArrowRight className="w-3 h-3" />
            </div>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}

export default function LearnPage() {
  const [query, setQuery] = useState('');

  const filtered = query.trim()
    ? groups.map(g => ({
        ...g,
        items: g.items.filter(t =>
          t.title.toLowerCase().includes(query.toLowerCase()) ||
          t.description.toLowerCase().includes(query.toLowerCase())
        ),
      })).filter(g => g.items.length > 0)
    : groups;

  return (
    <div>
      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show">
        <h1 className="text-2xl font-bold text-text-primary mb-1">Documentation & Learning</h1>
        <p className="text-text-muted mb-6">Learn the concepts behind every tool in Bio Nexus.</p>
      </motion.div>

      <motion.div variants={fadeUp} className="relative mb-10 max-w-xl">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search topics..."
          className="w-full pl-11 pr-4 py-3 rounded-2xl border border-glass-border bg-glass-card text-text-primary text-sm placeholder:text-text-muted/50 outline-none focus:border-accent-cyan/30 transition"
        />
      </motion.div>

      {filtered.map(group => (
        <div key={group.title} className="mb-10">
          <motion.h2 variants={fadeUp} className="text-sm font-semibold text-text-muted uppercase tracking-wider mb-4">
            {group.title}
          </motion.h2>
          <motion.div
            variants={stagger}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: '-40px' }}
            className="grid md:grid-cols-2 gap-4"
          >
            {group.items.map(topic => (
              <TopicCard key={topic.id} topic={topic} />
            ))}
          </motion.div>
        </div>
      ))}

      {filtered.length === 0 && (
        <motion.p variants={fadeUp} className="text-text-muted text-sm text-center py-12">
          No topics found for &ldquo;{query}&rdquo;.
        </motion.p>
      )}
    </div>
  );
}

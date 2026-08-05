'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { CaretDown as ChevronDown, CaretUp as ChevronUp, ArrowSquareOut as ExternalLink, Download } from '@phosphor-icons/react';
import type { BlastHitSummary } from '@/types/pipeline';
import { AlignmentView } from './AlignmentView';
import { PairwiseAlignView } from './PairwiseAlignView';
import { downloadTsv } from '@/lib/export-utils';
import { fadeUp, stagger, cardHover } from '@/lib/animations';
import { confidenceBand, formatEvalue, coverageColor } from '@/lib/confidence';

interface BlastPanelProps {
  hits: BlastHitSummary[] | undefined | null;
  count: number;
  source?: string;
  queryLength?: number;
  querySequence?: string;
}

export function BlastPanel({ hits, count, source, querySequence }: BlastPanelProps) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const safeHits = hits ?? [];

  return (
    <motion.div variants={fadeUp} whileHover={cardHover} className="data-card overflow-hidden">
      <div className="px-6 py-4 border-b border-glass-border bg-surface-1 flex items-center justify-between">
        <h2 className="font-semibold text-text-primary">
          BLAST Hits
          <span className="text-xs text-text-muted ml-2 font-normal">({count} found{source ? ` via ${source}` : ''})</span>
        </h2>
        <div className="flex items-center gap-2">
          <button onClick={() => downloadTsv(
            ["Accession", "Description", "Organism", "E-value", "Identity%", "Coverage%", "Score", "Confidence"],
            safeHits.map(h => [h.accession, h.description, h.organism ?? '', h.evalue_raw || String(h.evalue), String(h.identity_pct), String(h.query_coverage_pct ?? ''), String(h.bit_score), confidenceBand(h.evalue).label]),
            "blast-hits.tsv"
          )} className="btn-ghost text-xs px-2 py-1 flex items-center gap-1">
            <Download className="w-3 h-3" /> Export CSV
          </button>
          <button onClick={() => {
            const fasta = safeHits.map(h => `>${h.accession} ${h.description}\n${(h.hit_alignment || h.midline || "").replace(/-/g, "")}`).join("\n");
            const a = document.createElement("a");
            a.download = "blast-hits.fasta";
            a.href = "data:text/fasta;charset=utf-8," + encodeURIComponent(fasta);
            a.click();
          }} className="btn-ghost text-xs px-2 py-1 flex items-center gap-1">
            <Download className="w-3 h-3" /> FASTA
          </button>
        </div>
      </div>
      <motion.div variants={stagger} className="divide-y divide-glass-border">
        {safeHits.length === 0 ? (
          <div className="px-6 py-8 text-center text-sm text-text-muted">No hits to display</div>
        ) : safeHits.map((hit, i) => {
          const band = confidenceBand(hit.evalue);
          const isExpanded = expanded === i;
          return (
            <motion.div key={hit.accession} variants={fadeUp}>
              <button
                onClick={() => setExpanded(isExpanded ? null : i)}
                className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-surface-1 transition"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono bg-surface-1 px-2 py-0.5 rounded text-text-secondary">{hit.accession}</span>
                    <span className="text-sm text-text-primary truncate">{hit.description}</span>
                    {hit.organism && <span className="text-xs text-text-muted hidden sm:inline ml-auto">{hit.organism}</span>}
                  </div>
                  <div className="flex items-center gap-4 mt-2 text-xs text-text-muted">
                    <span>
                      E-value:{' '}
                      <strong className={band.color}>{formatEvalue(hit.evalue, hit.evalue_raw)}</strong>
                      <span className={`ml-1 px-1.5 py-0.5 rounded-full text-xs ${band.bg} ${band.color}`}>
                        {band.label}
                      </span>
                    </span>
                    <span>Identity: <strong className="text-text-primary">{hit.identity_pct}%</strong></span>
                    <span>Coverage: <strong className={coverageColor(hit.query_coverage_pct ?? 0)}>{hit.query_coverage_pct ?? '—'}%</strong></span>
                    <span>Score: <strong className="text-text-primary">{hit.bit_score}</strong></span>
                  </div>
                </div>
                {isExpanded ? <ChevronUp className="w-5 h-5 text-text-muted" /> : <ChevronDown className="w-5 h-5 text-text-muted" />}
              </button>
              {isExpanded && (
                <div className="px-6 pb-4">
                  <AlignmentView hit={hit} />
                  <PairwiseAlignView hit={hit} querySequence={querySequence} />
                  <a
                    href={`https://www.ncbi.nlm.nih.gov/protein/${hit.accession}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 inline-flex items-center gap-1 text-sm text-accent-cyan hover:text-accent-cyan/80 transition"
                  >
                    View on NCBI <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              )}
            </motion.div>
          );
        })}
      </motion.div>
    </motion.div>
  );
}

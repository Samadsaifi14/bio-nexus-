'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';
import type { BlastHitSummary } from '@/types/pipeline';
import { AlignmentView } from './AlignmentView';
import { fadeUp, stagger, cardHover } from '@/lib/animations';

interface BlastPanelProps {
  hits: BlastHitSummary[];
  count: number;
  source?: string;
}

function confidenceBand(evalue: number): { label: string; color: string; bg: string } {
  if (evalue < 1e-50) return { label: 'Very High', color: 'text-teal-700', bg: 'bg-teal-50' };
  if (evalue < 1e-10) return { label: 'High', color: 'text-blue-700', bg: 'bg-blue-50' };
  if (evalue < 1e-3) return { label: 'Moderate', color: 'text-amber-700', bg: 'bg-amber-50' };
  return { label: 'Low', color: 'text-gray-500', bg: 'bg-gray-100' };
}

function formatEvalue(evalue: number, evalue_raw?: string): string {
  if (evalue === 0) {
    const raw = evalue_raw?.trim();
    if (raw && raw !== '0') return raw;
    return '≈ 0';
  }
  if (evalue < 0.0001) return evalue.toExponential(2);
  return evalue.toFixed(4);
}

export function BlastPanel({ hits, count, source }: BlastPanelProps) {
  const [expanded, setExpanded] = useState<number | null>(null);

  return (
    <motion.div variants={fadeUp} whileHover={cardHover} className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
        <h2 className="font-semibold text-gray-900">
          BLAST Hits
          <span className="text-xs text-gray-400 ml-2 font-normal">({count} found{source ? ` via ${source}` : ''})</span>
        </h2>
      </div>
      <motion.div variants={stagger} className="divide-y divide-gray-100">
        {hits.map((hit, i) => {
          const band = confidenceBand(hit.evalue);
          const isExpanded = expanded === i;
          return (
            <motion.div key={hit.accession} variants={fadeUp}>
              <button
                onClick={() => setExpanded(isExpanded ? null : i)}
                className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-gray-50 transition"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono bg-gray-100 px-2 py-0.5 rounded text-gray-600">{hit.accession}</span>
                    <span className="text-sm text-gray-700 truncate">{hit.description}</span>
                  </div>
                  <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                    <span>
                      E-value:{' '}
                      <strong className={band.color}>{formatEvalue(hit.evalue, hit.evalue_raw)}</strong>
                      <span className={`ml-1 px-1.5 py-0.5 rounded-full text-xs ${band.bg} ${band.color}`}>
                        {band.label}
                      </span>
                    </span>
                    <span>Identity: <strong className="text-gray-900">{hit.identity_pct}%</strong></span>
                    <span>Score: <strong className="text-gray-900">{hit.bit_score}</strong></span>
                  </div>
                </div>
                {isExpanded ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}
              </button>
              {isExpanded && (
                <div className="px-6 pb-4">
                  <AlignmentView hit={hit} />
                  <a
                    href={`https://www.ncbi.nlm.nih.gov/protein/${hit.accession}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 inline-flex items-center gap-1 text-sm text-teal-600 hover:text-teal-700"
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

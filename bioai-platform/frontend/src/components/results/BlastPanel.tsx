'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';
import type { BlastHitSummary } from '@/types/pipeline';

interface BlastPanelProps {
  hits: BlastHitSummary[];
  count: number;
  source?: string;
}

export default function BlastPanel({ hits, count, source }: BlastPanelProps) {
  const [expanded, setExpanded] = useState<number | null>(null);

  return (
    <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
        <h2 className="font-semibold text-gray-900">
          BLAST Hits
          <span className="text-xs text-gray-400 ml-2 font-normal">({count} found{source ? ` via ${source}` : ''})</span>
        </h2>
      </div>
      <div className="divide-y divide-gray-100">
        {hits.map((hit, i) => (
          <div key={i}>
            <button
              onClick={() => setExpanded(expanded === i ? null : i)}
              className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-gray-50 transition"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono bg-gray-100 px-2 py-0.5 rounded text-gray-600">{hit.accession}</span>
                  <span className="text-sm text-gray-700 truncate">{hit.description}</span>
                </div>
                <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                  <span>E-value: <strong className="text-gray-900">{hit.evalue.toExponential(1)}</strong></span>
                  <span>Identity: <strong className="text-gray-900">{hit.identity_pct}%</strong></span>
                  <span>Score: <strong className="text-gray-900">{hit.bit_score}</strong></span>
                </div>
              </div>
              {expanded === i ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}
            </button>
            {expanded === i && (
              <div className="px-6 pb-4 border-t border-gray-100">
                <a href={`https://www.ncbi.nlm.nih.gov/protein/${hit.accession}`} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-1 text-sm text-green-600 hover:text-green-700">
                  View on NCBI <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

'use client';

import { motion } from 'framer-motion';
import type { BlastHitSummary } from '@/types/pipeline';
import { fadeUp, cardHover } from '@/lib/animations';
import { confidenceColor, formatEvalue } from '@/lib/confidence';

interface ScoreBarsProps {
  hits: BlastHitSummary[] | undefined | null;
}

export function ScoreBars({ hits }: ScoreBarsProps) {
  if (!hits || hits.length === 0) return null;

  const maxScore = hits[0]?.bit_score || 1;

  return (
    <motion.div variants={fadeUp} whileHover={cardHover} className="data-card p-6">
      <h2 className="text-lg font-semibold text-text-primary mb-4">Score Distribution</h2>
      <div className="space-y-2">
        {hits.slice(0, 15).map((hit, i) => {
          const pct = Math.min((hit.bit_score / maxScore) * 100, 100);
          const barColor = confidenceColor(hit.evalue);
          return (
            <div key={hit.accession} className="flex items-center gap-3">
              <span className="w-5 text-xs text-text-muted text-right shrink-0">{i + 1}</span>
              <span className="w-20 text-xs text-text-secondary font-mono truncate shrink-0" title={hit.accession}>
                {hit.accession}
              </span>
              <div className="flex-1 h-5 bg-surface-1 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${pct}%`, backgroundColor: barColor }}
                />
              </div>
              <span className="w-16 text-right text-xs text-text-muted font-mono shrink-0">
                {hit.bit_score?.toFixed(1)}
              </span>
              <span className="w-20 text-right text-xs text-text-muted font-mono shrink-0">
                {formatEvalue(hit.evalue, hit.evalue_raw)}
              </span>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

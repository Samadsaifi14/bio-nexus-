'use client';

import { motion } from 'framer-motion';
import type { BlastHitSummary } from '@/types/pipeline';
import { fadeUp, cardHover } from '@/lib/animations';

interface ScoreBarsProps {
  hits: BlastHitSummary[];
}

function confidenceColor(evalue: number): string {
  if (evalue < 1e-50) return '#00F5D4';
  if (evalue < 1e-10) return '#8B5CF6';
  if (evalue < 1e-3) return '#F59E0B';
  return '#4A5568';
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

export function ScoreBars({ hits }: ScoreBarsProps) {
  if (hits.length === 0) return null;

  const maxScore = hits[0]?.bit_score || 1;

  return (
    <motion.div variants={fadeUp} whileHover={cardHover} className="glass-card p-6">
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

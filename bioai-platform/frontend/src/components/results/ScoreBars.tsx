'use client';

import { motion } from 'framer-motion';
import type { BlastHitSummary } from '@/types/pipeline';
import { fadeUp, cardHover } from '@/lib/animations';
import { confidenceColor, formatEvalue } from '@/lib/confidence';

interface ScoreBarsProps {
  hits: BlastHitSummary[] | undefined | null;
}

function finite(value: unknown, fallback = 0): number {
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function evalueSignificance(value: unknown): number {
  const e = finite(value, 1);
  if (e <= 0) return 300;
  return Math.min(300, Math.max(0, -Math.log10(e)));
}

export function ScoreBars({ hits }: ScoreBarsProps) {
  if (!hits || hits.length === 0) return null;

  const safeHits = hits.slice(0, 20).map((hit) => ({
    ...hit,
    bit_score: finite(hit.bit_score),
    identity_pct: finite(hit.identity_pct),
    query_coverage_pct: finite(hit.query_coverage_pct),
    evalue: finite(hit.evalue, 1),
  }));

  const maxScore = Math.max(...safeHits.map(hit => hit.bit_score), 1);
  const maxSignificance = Math.max(...safeHits.map(hit => evalueSignificance(hit.evalue)), 1);

  return (
    <motion.div variants={fadeUp} className="grid gap-4 xl:grid-cols-3">
      <motion.section whileHover={cardHover} className="data-card p-5">
        <div className="mb-4">
          <h2 className="text-sm font-semibold text-text-primary">BLAST bit-score ranking</h2>
          <p className="mt-1 text-[11px] leading-4 text-text-muted">
            Relative alignment score for the returned hits. Values come directly from the BLAST result.
          </p>
        </div>
        <div className="space-y-2">
          {safeHits.slice(0, 15).map((hit, i) => {
            const pct = Math.min((hit.bit_score / maxScore) * 100, 100);
            const barColor = confidenceColor(hit.evalue);
            return (
              <div key={`${hit.accession}-score-${i}`} className="flex items-center gap-2">
                <span className="w-5 shrink-0 text-right text-[10px] text-text-muted">{i + 1}</span>
                <span className="w-20 shrink-0 truncate font-mono text-[10px] text-text-secondary" title={hit.accession}>
                  {hit.accession}
                </span>
                <div className="h-4 flex-1 overflow-hidden rounded-full bg-surface-1">
                  <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: barColor }} />
                </div>
                <span className="w-14 shrink-0 text-right font-mono text-[10px] text-text-muted">
                  {hit.bit_score.toFixed(1)}
                </span>
              </div>
            );
          })}
        </div>
      </motion.section>

      <motion.section whileHover={cardHover} className="data-card p-5">
        <div className="mb-3">
          <h2 className="text-sm font-semibold text-text-primary">Identity vs query coverage</h2>
          <p className="mt-1 text-[11px] leading-4 text-text-muted">
            Each point is one BLAST hit. High identity with broad query coverage is visually separated from short local matches.
          </p>
        </div>
        <div className="overflow-hidden rounded-lg border border-glass-border bg-surface-1 p-2">
          <svg viewBox="0 0 360 260" className="h-[250px] w-full" role="img" aria-label="BLAST identity versus query coverage scatter plot">
            <line x1="42" y1="218" x2="340" y2="218" className="stroke-glass-border" strokeWidth="1" />
            <line x1="42" y1="18" x2="42" y2="218" className="stroke-glass-border" strokeWidth="1" />
            {[0, 25, 50, 75, 100].map(tick => (
              <g key={`x-${tick}`}>
                <line x1={42 + tick * 2.98} y1="218" x2={42 + tick * 2.98} y2="223" className="stroke-glass-border" />
                <text x={42 + tick * 2.98} y="238" textAnchor="middle" className="fill-text-muted text-[9px]">{tick}</text>
              </g>
            ))}
            {[0, 25, 50, 75, 100].map(tick => (
              <g key={`y-${tick}`}>
                <line x1="37" y1={218 - tick * 2} x2="42" y2={218 - tick * 2} className="stroke-glass-border" />
                <text x="32" y={221 - tick * 2} textAnchor="end" className="fill-text-muted text-[9px]">{tick}</text>
              </g>
            ))}
            {safeHits.map((hit, i) => {
              const x = 42 + Math.max(0, Math.min(100, hit.identity_pct)) * 2.98;
              const y = 218 - Math.max(0, Math.min(100, hit.query_coverage_pct)) * 2;
              return (
                <g key={`${hit.accession}-scatter-${i}`}>
                  <circle cx={x} cy={y} r="4" className="fill-accent-cyan stroke-surface-0" strokeWidth="1.5">
                    <title>{`${hit.accession}: identity ${hit.identity_pct.toFixed(1)}%, coverage ${hit.query_coverage_pct.toFixed(1)}%, E=${formatEvalue(hit.evalue, hit.evalue_raw)}`}</title>
                  </circle>
                </g>
              );
            })}
            <text x="191" y="255" textAnchor="middle" className="fill-text-muted text-[10px]">Identity (%)</text>
            <text x="11" y="118" textAnchor="middle" transform="rotate(-90 11 118)" className="fill-text-muted text-[10px]">Query coverage (%)</text>
          </svg>
        </div>
      </motion.section>

      <motion.section whileHover={cardHover} className="data-card p-5">
        <div className="mb-4">
          <h2 className="text-sm font-semibold text-text-primary">E-value significance</h2>
          <p className="mt-1 text-[11px] leading-4 text-text-muted">
            Bars show −log10(E-value); longer bars indicate stronger statistical evidence for sequence similarity.
          </p>
        </div>
        <div className="space-y-2">
          {safeHits.slice(0, 15).map((hit, i) => {
            const significance = evalueSignificance(hit.evalue);
            const pct = Math.min((significance / maxSignificance) * 100, 100);
            return (
              <div key={`${hit.accession}-evalue-${i}`} className="flex items-center gap-2">
                <span className="w-20 shrink-0 truncate font-mono text-[10px] text-text-secondary" title={hit.accession}>
                  {hit.accession}
                </span>
                <div className="h-4 flex-1 overflow-hidden rounded-full bg-surface-1">
                  <div className="h-full rounded-full bg-accent-cyan/70" style={{ width: `${pct}%` }} />
                </div>
                <span className="w-20 shrink-0 text-right font-mono text-[9px] text-text-muted">
                  {formatEvalue(hit.evalue, hit.evalue_raw)}
                </span>
              </div>
            );
          })}
        </div>
      </motion.section>
    </motion.div>
  );
}

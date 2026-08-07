'use client';

import type { AlignmentStats } from '@/lib/alignment-stats';

function StatChip({
  label,
  value,
  valueClass,
  hint,
}: {
  label: string;
  value: string;
  valueClass: string;
  hint?: string;
}) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-0 border border-glass-border">
      <span className="text-[10px] uppercase tracking-wider text-text-muted">{label}</span>
      <span className={`text-sm font-bold font-mono ${valueClass}`}>{value}</span>
      {hint && <span className="text-[10px] text-text-muted">{hint}</span>}
    </div>
  );
}

/**
 * Renders the four core alignment metrics — Matched, Mismatched, Gaps and
 * Length — plus percent identity. Used by every alignment viewer in the app
 * so the numbers are always presented identically.
 */
export function AlignmentStatsBar({
  stats,
  gapDetail,
  className = '',
}: {
  stats: AlignmentStats;
  /** Extra text appended to the Gaps chip, e.g. total gap characters. */
  gapDetail?: string;
  className?: string;
}) {
  if (stats.length === 0) return null;

  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`}>
      <StatChip label="Matched" value={String(stats.matched)} valueClass="text-accent-cyan" hint={`${stats.identity_pct}%`} />
      <StatChip label="Mismatched" value={String(stats.mismatched)} valueClass="text-text-primary" />
      <StatChip
        label="Gaps"
        value={String(stats.gapped)}
        valueClass="text-accent-purple"
        hint={gapDetail ?? (stats.total_gaps ? `${stats.total_gaps} gap chars` : undefined)}
      />
      <StatChip label="Length" value={`${stats.length} cols`} valueClass="text-accent-amber" />
    </div>
  );
}

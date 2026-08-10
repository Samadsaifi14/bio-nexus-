/**
 * Shared scientific-confidence color scales.
 *
 * Thresholds follow BLAST e-value conventions. Red is intentionally never
 * used here — the `error` token is reserved for genuine failures (API
 * errors, failed jobs), not for "low confidence" scientific output.
 */

const VERY_HIGH = '#4ADE80'; // < 1e-50
const HIGH      = '#60A5FA'; // < 1e-10  (matches --confidence-high)
const MODERATE  = '#FBBF24'; // < 1e-3   (matches --confidence-moderate)
const LOW       = '#94A3B8'; // fallback (matches --confidence-low)

/** Hex colour for data-ink (bars, tracks, SVG fills). */
export function confidenceColor(evalue: number): string {
  if (evalue < 1e-50) return VERY_HIGH;
  if (evalue < 1e-10) return HIGH;
  if (evalue < 1e-3) return MODERATE;
  return LOW;
}

export interface ConfidenceBand {
  label: string;
  color: string;
  bg: string;
}

/** Tailwind class pair for badges/chips. */
export function confidenceBand(evalue: number): ConfidenceBand {
  if (evalue < 1e-50) return { label: 'Very High', color: 'text-accent-cyan', bg: 'bg-accent-cyan/10' };
  if (evalue < 1e-10) return { label: 'High', color: 'text-info', bg: 'bg-info/10' };
  if (evalue < 1e-3) return { label: 'Moderate', color: 'text-warn', bg: 'bg-warn/10' };
  return { label: 'Low', color: 'text-text-muted', bg: 'bg-surface-1' };
}

/** Human-readable e-value formatting shared by BLAST result views. */
export function formatEvalue(evalue: number, evalue_raw?: string): string {
  if (evalue === 0) {
    const raw = evalue_raw?.trim();
    if (raw && raw !== '0') return raw;
    return '≈ 0';
  }
  if (evalue < 0.0001) return evalue.toExponential(2);
  return evalue.toFixed(4);
}

/** Coverage percentage → chip colour. */
export function coverageColor(pct: number): string {
  if (pct >= 90) return 'text-accent-cyan';
  if (pct >= 50) return 'text-warn';
  return 'text-text-muted';
}

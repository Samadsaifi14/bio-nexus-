// Alignment statistics helpers — shared by every alignment viewer so the
// matched / mismatched / gaps / length metrics are always shown consistently.

export interface AlignmentStats {
  /** Number of alignment columns */
  length: number;
  /** Columns where every non-gap residue is identical */
  matched: number;
  /** Columns with >=2 distinct residues and no gaps */
  mismatched: number;
  /** Columns containing at least one gap character */
  gapped: number;
  /** Total '-' gap characters across all sequences */
  total_gaps: number;
  /** matched / length * 100 */
  identity_pct: number;
}

const GAP_CHARS = new Set(['-', '.']);

/** Physico-chemical amino acid groups — shared by the conservation track and
 *  the per-column CLUSTAL-style consensus symbols in the MSA viewer. */
export const PHYSICOCHEMICAL_GROUPS: Record<string, string[]> = {
  polar_positive: ['K', 'R', 'H'],
  polar_negative: ['D', 'E'],
  polar_uncharged: ['S', 'T', 'N', 'Q'],
  nonpolar: ['A', 'V', 'I', 'L', 'M', 'F', 'W', 'P'],
  special: ['C', 'G', 'Y'],
};

export function groupOf(aa: string): string {
  const up = aa.toUpperCase();
  for (const [g, members] of Object.entries(PHYSICOCHEMICAL_GROUPS)) {
    if (members.includes(up)) return g;
  }
  return 'other';
}

/** Loosely related groups used for the CLUSTAL '.' (weak conservation) symbol. */
const WEAK_GROUPS: string[][] = [
  ['A', 'S', 'T', 'P', 'G'],
  ['N', 'D', 'E', 'Q'],
  ['R', 'K', 'H'],
  ['V', 'I', 'L', 'M'],
  ['F', 'Y', 'W'],
  ['C'],
];

function weakGroupOf(aa: string): string {
  const up = aa.toUpperCase();
  for (let i = 0; i < WEAK_GROUPS.length; i++) {
    if (WEAK_GROUPS[i].includes(up)) return String(i);
  }
  return 'other';
}

export interface ColumnAnalysis {
  /** Most frequent non-gap residue; '-' when the column is all gaps. */
  consensus: string;
  /** CLUSTAL conservation symbol: '*' identical, ':' strong, '.' weak, ' ' variable. */
  symbol: string;
}

/**
 * Per-column analysis of an already-aligned set of sequences. The consensus is
 * the majority non-gap residue; the symbol follows the CLUSTALX convention.
 */
export function analyzeColumns(seqs: string[]): ColumnAnalysis[] {
  if (!seqs.length) return [];
  const L = Math.max(...seqs.map(s => s.length));
  const columns: ColumnAnalysis[] = [];
  for (let i = 0; i < L; i++) {
    const residues: string[] = [];
    for (const s of seqs) {
      const c = (s[i] ?? '-').toUpperCase();
      if (!GAP_CHARS.has(c)) residues.push(c);
    }
    if (!residues.length) {
      columns.push({ consensus: '-', symbol: ' ' });
      continue;
    }
    const freqs = new Map<string, number>();
    for (const r of residues) freqs.set(r, (freqs.get(r) ?? 0) + 1);
    let consensus = residues[0];
    let max = 0;
    for (const [r, n] of Array.from(freqs.entries())) {
      if (n > max) {
        max = n;
        consensus = r;
      }
    }
    let symbol = ' ';
    if (freqs.size === 1) {
      symbol = '*';
    } else if (new Set(residues.map(groupOf)).size === 1) {
      symbol = ':';
    } else if (new Set(residues.map(weakGroupOf)).size === 1) {
      symbol = '.';
    }
    columns.push({ consensus, symbol });
  }
  return columns;
}

/**
 * Compute column-wise statistics from an already-aligned set of sequences
 * (equal-length strings). Works for both pairwise (2 sequences) and multiple
 * sequence alignments. Columns are classified as:
 *
 *   matched      — all non-gap residues identical (invariant column)
 *   mismatched   — >= 2 distinct residues, no gaps (variable column)
 *   gapped       — at least one gap character present
 *
 * so that matched + mismatched + gapped === length.
 */
export function computeAlignmentStats(seqs: string[]): AlignmentStats {
  const empty: AlignmentStats = {
    length: 0,
    matched: 0,
    mismatched: 0,
    gapped: 0,
    total_gaps: 0,
    identity_pct: 0,
  };
  if (!seqs.length) return empty;

  const L = Math.max(...seqs.map(s => s.length));
  if (L === 0) return empty;

  let matched = 0;
  let mismatched = 0;
  let gapped = 0;
  let totalGaps = 0;

  for (let i = 0; i < L; i++) {
    const distinct = new Set<string>();
    let colHasGap = false;
    for (const s of seqs) {
      const c = (s[i] ?? '-').toUpperCase();
      if (GAP_CHARS.has(c)) {
        colHasGap = true;
        totalGaps++;
      } else {
        distinct.add(c);
      }
    }
    if (colHasGap) gapped++;
    else if (distinct.size <= 1) matched++;
    else mismatched++;
  }

  return {
    length: L,
    matched,
    mismatched,
    gapped,
    total_gaps: totalGaps,
    identity_pct: L > 0 ? Math.round((matched / L) * 1000) / 10 : 0,
  };
}

/**
 * Parse an aligned FASTA string into headers and equal-length sequences.
 * Shared so every MSA viewer (and stats bar) reads sequences the same way.
 */
export function parseAlignedFasta(fasta: string): { headers: string[]; seqs: string[] } {
  const headers: string[] = [];
  const seqs: string[] = [];
  let header = '';
  let seq = '';
  for (const line of fasta.split('\n')) {
    const t = line.trim();
    if (t.startsWith('>')) {
      if (header) {
        headers.push(header);
        seqs.push(seq);
      }
      header = t.slice(1);
      seq = '';
    } else if (header) {
      seq += t;
    }
  }
  if (header) {
    headers.push(header);
    seqs.push(seq);
  }
  return { headers, seqs };
}

'use client';

import { useMemo } from 'react';
import { analyzeColumns, parseAlignedFasta } from '@/lib/alignment-stats';

const AA_COLORS: Record<string, string> = {
  A: '#A78BFA', C: '#FBBF24', D: '#EF4444', E: '#EF4444',
  F: '#7C3AED', G: '#848CA4', H: '#60A5FA', I: '#7C3AED',
  K: '#4ADE80', L: '#7C3AED', M: '#FBBF24', N: '#60A5FA',
  P: '#FB923C', Q: '#60A5FA', R: '#4ADE80', S: '#60A5FA',
  T: '#60A5FA', V: '#7C3AED', W: '#7C3AED', Y: '#7C3AED',
};

function aaColor(ch: string): string {
  if (ch === '-') return 'rgba(132,140,164,0.25)';
  return AA_COLORS[ch.toUpperCase()] ?? 'rgb(var(--text-primary))';
}

type CellClass = 'match' | 'mismatch' | 'gap';

function cellClass(ch: string, consensus: string): CellClass {
  if (ch === '-' || ch === '.') return 'gap';
  return ch.toUpperCase() === consensus ? 'match' : 'mismatch';
}

const CELL_BG: Record<CellClass, string> = {
  match: 'rgba(74,222,128,0.16)',
  mismatch: 'rgba(239,68,68,0.12)',
  gap: 'rgba(132,140,164,0.08)',
};

function symbolClass(symbol: string): string {
  if (symbol === '*') return 'text-accent-cyan font-bold';
  if (symbol === ':') return 'text-accent-amber';
  if (symbol === '.') return 'text-text-muted/40';
  return 'text-transparent';
}

interface AlignmentBlockProps {
  /** Aligned FASTA text (headers + equal-length gapped sequences). */
  alnFasta: string;
  /** Extra classes for the scroll container (e.g. max-height). */
  className?: string;
}

/**
 * Colored MSA grid shared by every alignment surface. Each cell is tinted by
 * its relationship to the column consensus — green = matched, red = mismatched,
 * gray = gap — with the per-residue chemistry color kept as the foreground and
 * a CLUSTAL-style consensus row (* : .) beneath the sequences.
 */
export function AlignmentBlock({ alnFasta, className = '' }: AlignmentBlockProps) {
  const { headers, seqs } = useMemo(() => parseAlignedFasta(alnFasta), [alnFasta]);
  const length = seqs[0]?.length ?? 0;
  const columns = useMemo(() => analyzeColumns(seqs), [seqs]);

  if (!seqs.length) return null;

  return (
    <div className={`rounded-xl border border-glass-border bg-surface-1 overflow-auto ${className}`}>
      <div className="min-w-max p-3 font-mono text-xs leading-[1.7]">
        <div className="flex">
          <span className="w-24 shrink-0 pr-3 text-right text-[10px] text-text-muted/60" />
          <span className="whitespace-pre text-[10px] text-text-muted/50">
            {Array.from({ length }).map((_, i) => ((i + 1) % 10 === 0 ? (i + 1) / 10 % 10 : ' ').toString()).join('')}
          </span>
        </div>
        {headers.map((h, i) => (
          <div key={i} className="flex">
            <span
              className="w-24 shrink-0 pr-3 text-right text-[10px] text-accent-cyan/80 truncate"
              title={h}
            >
              {h.length > 12 ? `${h.slice(0, 11)}…` : h}
            </span>
            <span className="whitespace-pre" style={{ color: 'inherit' }}>
              {Array.from(seqs[i] ?? '').map((ch, j) => {
                const cls = cellClass(ch, columns[j]?.consensus ?? '-');
                return (
                  <span key={j} style={{ color: aaColor(ch), backgroundColor: CELL_BG[cls] }}>
                    {ch}
                  </span>
                );
              })}
            </span>
          </div>
        ))}
        <div className="flex">
          <span className="w-24 shrink-0 pr-3 text-right text-[10px] text-accent-amber/80 truncate">
            consensus
          </span>
          <span className="whitespace-pre">
            {columns.map((col, j) => (
              <span key={j} className={symbolClass(col.symbol)}>
                {col.symbol}
              </span>
            ))}
          </span>
        </div>
      </div>

      <div className="px-3 pb-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-[10px] text-text-muted">
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm" style={{ background: CELL_BG.match }} />
          Matched
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm" style={{ background: CELL_BG.mismatch }} />
          Mismatched
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm" style={{ background: CELL_BG.gap }} />
          Gap
        </span>
        <span className="flex items-center gap-1.5">
          <span className="font-bold text-accent-cyan">*</span> Identical
        </span>
        <span className="flex items-center gap-1.5">
          <span className="text-accent-amber font-bold">:</span> Strongly conserved group
        </span>
        <span className="flex items-center gap-1.5">
          <span className="text-text-muted/50 font-bold">.</span> Weakly conserved
        </span>
      </div>
    </div>
  );
}

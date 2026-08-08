'use client';

import { useMemo } from 'react';
import { DownloadSimple as Download, ChartScatter as Scatter } from '@phosphor-icons/react';
import type { PairwiseAlignResult } from '@/types/pipeline';
import { downloadText, downloadTsv } from '@/lib/export-utils';
import { computeAlignmentStats } from '@/lib/alignment-stats';
import { AlignmentStatsBar } from '@/components/alignment/AlignmentStatsBar';

const DOTPLOT_MATRICES = ['blosum62', 'blosum50', 'blosum45', 'pam30', 'pam70', 'pam250'];

function dotplotScoringFor(matrix: string): string {
  const m = matrix.toLowerCase();
  return DOTPLOT_MATRICES.includes(m) ? m : 'identity';
}

const BLOCK_SIZE = 60;

interface Column {
  q: string;
  h: string;
  qPos: number;
  hPos: number;
  match: boolean;
  gap: boolean;
}

function buildColumns(result: PairwiseAlignResult): Column[] {
  const a = result.aligned_query;
  const b = result.aligned_hit;
  const cols: Column[] = [];
  let qPos = result.query_start;
  let hPos = result.hit_start;
  for (let i = 0; i < a.length; i++) {
    const q = a[i];
    const h = b[i];
    cols.push({
      q,
      h,
      qPos,
      hPos,
      match: q !== '-' && h !== '-' && q === h,
      gap: q === '-' || h === '-',
    });
    if (q !== '-') qPos++;
    if (h !== '-') hPos++;
  }
  return cols;
}

function charClass(c: string, match: boolean): string {
  if (c === '-') return 'text-text-muted/25';
  return match ? 'text-accent-cyan' : 'text-text-primary';
}

function CoverageStrip({
  label,
  start,
  end,
  length,
}: {
  label: string;
  start: number;
  end: number;
  length: number;
}) {
  const covered = length > 0 ? ((end - start + 1) / length) * 100 : 0;
  const left = length > 0 ? ((start - 1) / length) * 100 : 0;
  return (
    <div className="flex items-center gap-2">
      <span className="w-10 shrink-0 text-[10px] uppercase tracking-wider text-text-muted">{label}</span>
      <div className="h-1.5 flex-1 rounded-full bg-surface-1 overflow-hidden relative">
        <div
          className="absolute inset-y-0 rounded-full bg-gradient-to-r from-accent-cyan/40 to-accent-cyan/80"
          style={{ left: `${left}%`, width: `${covered}%` }}
        />
      </div>
      <span className="w-8 shrink-0 text-right text-[10px] font-mono text-text-muted">{Math.round(covered)}%</span>
    </div>
  );
}

function CoverageNote({ result }: { result: PairwiseAlignResult }) {
  if (result.alignment_length === 0) {
    return (
      <p className="mt-3 text-sm text-accent-amber">
        No significant {result.mode} alignment detected — the two sequences show no local similarity.
      </p>
    );
  }
  const queryOnlyCoversPart =
    result.query_start > 1 || result.query_end < result.query_length;
  const hitOnlyCoversPart = result.hit_start > 1 || result.hit_end < result.hit_length;
  if (!queryOnlyCoversPart && !hitOnlyCoversPart) return null;
  return (
    <p className="text-xs text-text-muted">
      {queryOnlyCoversPart && (
        <>
          Alignment covers residues <strong className="text-accent-cyan">{result.query_start}–{result.query_end}</strong> of a {result.query_length}-residue query.
        </>
      )}
      {queryOnlyCoversPart && hitOnlyCoversPart && <span className="mx-1.5">·</span>}
      {hitOnlyCoversPart && (
        <>
          Residues <strong className="text-accent-cyan">{result.hit_start}–{result.hit_end}</strong> of a {result.hit_length}-residue subject.
        </>
      )}
    </p>
  );
}

function AlignmentBlocks({ result }: { result: PairwiseAlignResult }) {
  const cols = useMemo(() => buildColumns(result), [result]);
  const blocks = useMemo(() => {
    const out: Column[][] = [];
    for (let i = 0; i < cols.length; i += BLOCK_SIZE) out.push(cols.slice(i, i + BLOCK_SIZE));
    return out;
  }, [cols]);

  if (cols.length === 0) return null;

  return (
    <div className="rounded-xl bg-surface-0 border border-glass-border overflow-x-auto">
      <div className="min-w-max font-mono text-[13px] leading-[1.55] p-4 space-y-3">
        {blocks.map((block, bi) => (
          <div key={bi} className="space-y-0.5">
            <div className="flex">
              <span className="w-14 shrink-0 pr-3 text-right text-[10px] text-text-muted/70 pt-[3px]">
                Q{block[0].qPos}
              </span>
              <span className="whitespace-pre">
                {block.map((c, i) => (
                  <span key={i} className={charClass(c.q, c.match)}>{c.q}</span>
                ))}
              </span>
            </div>
            <div className="flex">
              <span className="w-14 shrink-0 pr-3" />
              <span className="whitespace-pre">
                {block.map((c, i) => (
                  <span key={i} className={c.match ? 'text-accent-cyan/50' : 'text-text-muted/10'}>
                    {c.match ? '|' : ' '}
                  </span>
                ))}
              </span>
            </div>
            <div className="flex">
              <span className="w-14 shrink-0 pr-3 text-right text-[10px] text-text-muted/70 pt-[3px]">
                S{block[0].hPos}
              </span>
              <span className="whitespace-pre">
                {block.map((c, i) => (
                  <span key={i} className={charClass(c.h, c.match)}>{c.h}</span>
                ))}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Legend() {
  return (
    <div className="flex items-center gap-4 text-[10px] text-text-muted flex-wrap">
      <span className="flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-[2px] bg-accent-cyan" /> Match
      </span>
      <span className="flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-[2px] bg-text-primary" /> Mismatch
      </span>
      <span className="flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-[2px] bg-text-muted/25" /> Gap
      </span>
      <span className="flex items-center gap-1.5">
        <span className="font-mono text-accent-cyan/50">|</span> Identical position
      </span>
    </div>
  );
}

export function PairwiseResultDisplay({
  result,
  queryLabel = 'Query',
  subjectLabel = 'Subject',
}: {
  result: PairwiseAlignResult;
  queryLabel?: string;
  subjectLabel?: string;
}) {
  const stats = useMemo(
    () => computeAlignmentStats([result.aligned_query, result.aligned_hit]),
    [result],
  );

  if (result.alignment_length === 0) {
    return <CoverageNote result={result} />;
  }

  const exportFasta = () => {
    const fasta = `>${queryLabel}\n${result.aligned_query.replace(/-/g, '')}\n>${subjectLabel}\n${result.aligned_hit.replace(/-/g, '')}`;
    downloadText(fasta, `${result.mode}_alignment.fasta`);
  };

  const exportTsv = () => {
    downloadTsv(
      ['Field', 'Value'],
      [
        ['Mode', result.mode],
        ['Matrix', result.matrix],
        ['Score', String(result.score)],
        ['Matched', String(stats.matched)],
        ['Mismatched', String(stats.mismatched)],
        ['Gapped columns', String(stats.gapped)],
        ['Gap characters', String(result.gaps_total)],
        ['Alignment length', String(stats.length)],
        ['Identity (%)', String(result.pct_identity)],
        ['Identical residues', String(result.identity)],
        ['Query start', String(result.query_start)],
        ['Query end', String(result.query_end)],
        ['Query length', String(result.query_length)],
        ['Subject start', String(result.hit_start)],
        ['Subject end', String(result.hit_end)],
        ['Subject length', String(result.hit_length)],
      ],
      `${result.mode}_alignment_stats.tsv`,
    );
  };

  return (
    <div>
      <div className="flex items-center gap-x-4 gap-y-1 text-xs text-text-muted mb-3 flex-wrap">
        <span>
          Score: <strong className="text-text-primary">{result.score}</strong>
        </span>
        <span>
          Identity: <strong className="text-accent-cyan">{result.pct_identity}%</strong> ({result.identity}/{result.alignment_length})
        </span>
        <span>
          Matrix: <strong className="text-text-primary">{result.matrix.toUpperCase()}</strong>
        </span>
        <span>
          Mode: <strong className="text-text-primary capitalize">{result.mode} {result.mode === 'global' ? 'Needleman-Wunsch' : 'Smith-Waterman'}</strong>
        </span>
        <span className="ml-auto flex items-center gap-2">
          <a
            href={`/analyze/dotplot?seq_a=${encodeURIComponent(result.aligned_query.replace(/-/g, ''))}&seq_b=${encodeURIComponent(result.aligned_hit.replace(/-/g, ''))}&scoring=${dotplotScoringFor(result.matrix)}`}
            className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition-colors flex items-center gap-1.5"
          >
            <Scatter className="w-3.5 h-3.5" /> Dot plot
          </a>
          <button onClick={exportFasta}
            className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition-colors flex items-center gap-1.5">
            <Download className="w-3.5 h-3.5" /> FASTA
          </button>
          <button onClick={exportTsv}
            className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition-colors flex items-center gap-1.5">
            <Download className="w-3.5 h-3.5" /> TSV
          </button>
        </span>
      </div>

      <AlignmentStatsBar
        stats={stats}
        gapDetail={`${result.gaps_total} gap chars`}
        className="mb-3"
      />

      <div className="mb-3 space-y-1.5">
        <CoverageStrip label="Query" start={result.query_start} end={result.query_end} length={result.query_length} />
        <CoverageStrip label="Subject" start={result.hit_start} end={result.hit_end} length={result.hit_length} />
      </div>

      <div className="rounded-xl border border-glass-border overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2 border-b border-glass-border bg-surface-1/80 backdrop-blur text-[10px] font-mono text-text-muted">
          <span>{queryLabel}</span>
          <span className="hidden sm:inline">{result.query_start}–{result.query_end} · {result.query_length} aa</span>
        </div>
        <AlignmentBlocks result={result} />
        <div className="flex items-center justify-between px-4 py-2 border-t border-glass-border bg-surface-1/80 backdrop-blur text-[10px] font-mono text-text-muted">
          <span>{subjectLabel}</span>
          <span className="hidden sm:inline">{result.hit_start}–{result.hit_end} · {result.hit_length} aa</span>
        </div>
      </div>

      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <Legend />
        <CoverageNote result={result} />
      </div>
    </div>
  );
}

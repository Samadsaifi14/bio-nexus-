'use client';

import { useState } from 'react';
import { GitMerge as GitCompareArrows, CircleNotch as LoaderCircle } from '@phosphor-icons/react';
import { runPairwiseAlignment } from '@/lib/api';
import type { BlastHitSummary, PairwiseAlignResult } from '@/types/pipeline';

interface PairwiseAlignViewProps {
  hit: BlastHitSummary;
  querySequence?: string;
}

function AlignedRow({ label, seq }: { label: string; seq: string }) {
  return (
    <div className="flex gap-3 text-xs font-mono leading-relaxed">
      <span className="w-16 shrink-0 text-text-muted">{label}</span>
      <span className="break-all whitespace-pre-wrap">
        {seq.split('').map((ch, i) => (
          <span key={i} className={ch === '-' ? 'text-text-muted/25' : 'text-text-primary'}>
            {ch}
          </span>
        ))}
      </span>
    </div>
  );
}

function CoverageNote({ result }: { result: PairwiseAlignResult }) {
  if (result.alignment_length === 0) {
    return (
      <p className="mt-2 text-sm text-accent-amber">
        No significant {result.mode} alignment detected — the two sequences show no local similarity.
      </p>
    );
  }
  const queryOnlyCoversPart =
    result.query_start > 1 || result.query_end < result.query_length;
  const hitOnlyCoversPart = result.hit_start > 1 || result.hit_end < result.hit_length;
  if (!queryOnlyCoversPart && !hitOnlyCoversPart) return null;
  return (
    <p className="mt-2 text-sm text-text-muted">
      {queryOnlyCoversPart && (
        <>
          Subject covers only residues <strong className="text-accent-cyan">{result.query_start}–{result.query_end}</strong> of a {result.query_length}-residue query.
        </>
      )}
      {queryOnlyCoversPart && hitOnlyCoversPart && <span className="mx-2">·</span>}
      {hitOnlyCoversPart && (
        <>
          Query covers only residues <strong className="text-accent-cyan">{result.hit_start}–{result.hit_end}</strong> of a {result.hit_length}-residue subject.
        </>
      )}
      <span className="ml-1 text-text-muted/70">(dimmed residues lie outside the aligned region)</span>
    </p>
  );
}

export function PairwiseAlignView({ hit, querySequence }: PairwiseAlignViewProps) {
  const [result, setResult] = useState<PairwiseAlignResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await runPairwiseAlignment({
        hit_accession: hit.accession,
        query_sequence: querySequence,
      });
      setResult(res);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      setError(
        typeof detail === 'string' && detail
          ? detail
          : 'Pairwise alignment failed. Please try again.',
      );
    } finally {
      setLoading(false);
    }
  };

  if (!querySequence) {
    return (
      <p className="mt-2 text-xs text-text-muted">
        Query sequence is not available in this view, so pairwise re-alignment is disabled.
      </p>
    );
  }

  return (
    <div className="mt-3 pt-3 border-t border-glass-border">
      <button
        onClick={run}
        disabled={loading}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-cyan/10 text-accent-cyan text-xs font-medium hover:bg-accent-cyan/20 transition border border-accent-cyan/20 disabled:opacity-60"
      >
        {loading ? (
          <LoaderCircle className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <GitCompareArrows className="w-3.5 h-3.5" />
        )}
        {result ? 'Re-align pair' : 'Align pair (full sequences)'}
      </button>
      <span className="ml-2 text-xs text-text-muted">
        Global Needleman-Wunsch vs <code className="font-mono">{hit.accession}</code>
      </span>

      {error && (
        <div className="mt-3 rounded-lg bg-error/10 border border-error/30 px-3 py-2 text-xs text-error">
          <strong>Alignment failed:</strong> {error}
        </div>
      )}

      {result && result.alignment_length === 0 && <CoverageNote result={result} />}

      {result && result.alignment_length > 0 && (
        <div className="mt-3">
          <div className="flex items-center gap-4 text-xs text-text-muted mb-2 flex-wrap">
            <span>
              Score: <strong className="text-text-primary">{result.score}</strong>
            </span>
            <span>
              Identity: <strong className="text-text-primary">{result.pct_identity}%</strong> ({result.identity}/{result.alignment_length})
            </span>
            <span>
              Gaps: <strong className="text-text-primary">{result.gaps_total}</strong>
            </span>
            <span>
              Matrix: <strong className="text-text-primary">{result.matrix.toUpperCase()}</strong>
            </span>
            <span>
              Mode: <strong className="text-text-primary">{result.mode}</strong>
            </span>
            {result.hit_source && (
              <span>
                Subject: <strong className="text-text-primary">{result.hit_source}</strong>
              </span>
            )}
          </div>
          <div className="bg-surface-1 rounded-xl p-3 space-y-1 overflow-x-auto">
            <AlignedRow label="Query" seq={result.aligned_query} />
            <AlignedRow label="Subject" seq={result.aligned_hit} />
          </div>
          <CoverageNote result={result} />
        </div>
      )}
    </div>
  );
}

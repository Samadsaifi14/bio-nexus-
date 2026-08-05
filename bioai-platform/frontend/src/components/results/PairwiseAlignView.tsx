'use client';

import { useRef, useState } from 'react';
import { GitMerge as GitCompareArrows, CircleNotch as LoaderCircle } from '@phosphor-icons/react';
import { runPairwiseAlignment } from '@/lib/api';
import { ClaySegmented } from '@/components/ui';
import { PairwiseResultDisplay } from '@/components/alignment/PairwiseResultDisplay';
import type { BlastHitSummary, PairwiseAlignResult } from '@/types/pipeline';

interface PairwiseAlignViewProps {
  hit: BlastHitSummary;
  querySequence?: string;
}

type AlignMode = 'global' | 'local';

function getStoredAlignMode(): AlignMode {
  if (typeof window === 'undefined') return 'global';
  return sessionStorage.getItem('blast_align_mode') === 'local' ? 'local' : 'global';
}

export function PairwiseAlignView({ hit, querySequence }: PairwiseAlignViewProps) {
  const [result, setResult] = useState<PairwiseAlignResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<AlignMode>(getStoredAlignMode);
  const hasRun = useRef(false);

  const run = async (m: AlignMode) => {
    if (!querySequence) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await runPairwiseAlignment({
        hit_accession: hit.accession,
        query_sequence: querySequence,
        mode: m,
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

  const handleRun = () => {
    hasRun.current = true;
    run(mode);
  };

  const handleModeChange = (m: AlignMode) => {
    setMode(m);
    sessionStorage.setItem('blast_align_mode', m);
    if (hasRun.current) run(m);
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
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={handleRun}
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
          <span className="text-xs text-text-muted">
            vs <code className="font-mono">{hit.accession}</code>
          </span>
        </div>
        <ClaySegmented
          size="sm"
          options={[
            { value: 'global', label: 'Global (NW)' },
            { value: 'local', label: 'Local (SW)' },
          ]}
          value={mode}
          onChange={handleModeChange}
        />
      </div>

      {error && (
        <div className="mt-3 rounded-lg bg-error/10 border border-error/30 px-3 py-2 text-xs text-error">
          <strong>Alignment failed:</strong> {error}
        </div>
      )}

      {result && (
        <div className="mt-4">
          <PairwiseResultDisplay result={result} subjectLabel={hit.accession} />
        </div>
      )}
    </div>
  );
}

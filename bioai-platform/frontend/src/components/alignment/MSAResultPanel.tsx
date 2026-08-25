'use client';

import { useMemo } from 'react';
import { Download } from '@phosphor-icons/react';
import type { PairwiseAlignResult } from '@/types/pipeline';
import PhyloTreeViewer from '@/components/phylo/PhyloTreeViewer';
import { ConservationTrack } from '@/components/alignment/ConservationTrack';
import { PairwiseResultDisplay } from '@/components/alignment/PairwiseResultDisplay';
import { AlignmentStatsBar } from '@/components/alignment/AlignmentStatsBar';
import { AlignmentBlock } from '@/components/alignment/AlignmentBlock';
import { computeAlignmentStats, parseAlignedFasta } from '@/lib/alignment-stats';
import { downloadText } from '@/lib/export-utils';

interface MSAResultPanelProps {
  alnFasta: string;
  phylotree?: string | null;
  sequenceCount?: number;
  alignmentMode?: 'global' | 'local';
  pairwise?: PairwiseAlignResult | null;
  pairwiseSubject?: string | null;
  jobId?: string;
}

export function MSAResultPanel({
  alnFasta,
  phylotree,
  sequenceCount,
  alignmentMode,
  pairwise,
  pairwiseSubject,
  jobId,
}: MSAResultPanelProps) {
  const { seqs } = useMemo(() => parseAlignedFasta(alnFasta), [alnFasta]);
  const stats = useMemo(() => computeAlignmentStats(seqs), [seqs]);

  const download = () => {
    downloadText(alnFasta, `msa-${jobId?.slice(0, 8) ?? 'result'}.fasta`);
  };

  return (
    <div className="space-y-4">
      <div className="data-card p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-sm font-semibold text-text-primary">Multiple Sequence Alignment</h3>
            <p className="text-xs text-text-muted mt-0.5">
              {sequenceCount ?? seqs.length} sequences aligned via Clustal Omega
              {alignmentMode === 'local' && (
                <span className="ml-2 px-2 py-0.5 rounded-full bg-accent-amber/10 border border-accent-amber/30 text-accent-amber font-medium">
                  local refinement
                </span>
              )}
            </p>
          </div>
          <button
            onClick={download}
            className="px-3 py-1.5 rounded-lg border border-glass-border text-xs text-text-secondary hover:bg-surface-1 hover:border-accent-cyan/40 transition"
          >
            <Download className="w-3.5 h-3.5 inline mr-1" />FASTA
          </button>
        </div>

        <AlignmentStatsBar stats={stats} className="mb-3" />

        <AlignmentBlock alnFasta={alnFasta} />
      </div>

      {seqs.length >= 2 && (
        <div className="data-card p-5">
          <ConservationTrack alignedSeqs={seqs} />
        </div>
      )}

      {pairwise && (
        <div className="data-card p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-text-primary">
              Query vs Top Hit — {pairwise.mode === 'local' ? 'Smith-Waterman (local)' : 'Needleman-Wunsch (global)'}
            </h3>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-amber/10 border border-accent-amber/30 text-accent-amber font-medium">
              {pairwise.mode} refinement
            </span>
          </div>
          <PairwiseResultDisplay
            result={pairwise}
            queryLabel="Query"
            subjectLabel={pairwiseSubject || 'Top hit'}
          />
        </div>
      )}

      {phylotree && (
        <div className="data-card p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-2">Phylogenetic Tree</h3>
          <PhyloTreeViewer newick={phylotree} alignment={alnFasta} />
        </div>
      )}
    </div>
  );
}

'use client';

import { useMemo } from 'react';
import { Download } from '@phosphor-icons/react';
import type { PairwiseAlignResult } from '@/types/pipeline';
import PhyloTreeViewer from '@/components/phylo/PhyloTreeViewer';
import { ConservationTrack } from '@/components/alignment/ConservationTrack';
import { PairwiseResultDisplay } from '@/components/alignment/PairwiseResultDisplay';

const AA_COLORS: Record<string, string> = {
  A: '#8B93D6', C: '#E0A94E', D: '#EF4444', E: '#EF4444',
  F: '#7C3AED', G: '#848CA4', H: '#60A5FA', I: '#7C3AED',
  K: '#2DD4BF', L: '#7C3AED', M: '#E0A94E', N: '#60A5FA',
  P: '#FB923C', Q: '#60A5FA', R: '#2DD4BF', S: '#60A5FA',
  T: '#60A5FA', V: '#7C3AED', W: '#7C3AED', Y: '#7C3AED',
};

function aaColor(ch: string): string {
  if (ch === '-') return 'rgba(132,140,164,0.25)';
  return AA_COLORS[ch.toUpperCase()] ?? 'var(--text-primary)';
}

function parseAlignedFasta(fasta: string): { headers: string[]; seqs: string[] } {
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
  const { headers, seqs } = useMemo(() => parseAlignedFasta(alnFasta), [alnFasta]);
  const length = seqs[0]?.length ?? 0;

  const download = () => {
    const blob = new Blob([alnFasta], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `msa-${jobId?.slice(0, 8) ?? 'result'}.fasta`;
    a.click();
    URL.revokeObjectURL(url);
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

        <div className="rounded-xl border border-glass-border bg-surface-1 overflow-x-auto">
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
                  {Array.from(seqs[i] ?? '').map((ch, j) => (
                    <span key={j} style={{ color: aaColor(ch) }}>
                      {ch}
                    </span>
                  ))}
                </span>
              </div>
            ))}
          </div>
        </div>
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

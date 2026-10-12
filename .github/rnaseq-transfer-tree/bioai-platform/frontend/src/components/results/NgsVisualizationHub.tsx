'use client';

import { DownloadSimple } from '@phosphor-icons/react';
import type { Ngs2Stage } from '@/lib/api';
import NgsRunDiagram from '@/components/results/NgsRunDiagram';
import NgsScientificPlots from '@/components/results/NgsScientificPlots';

function downloadJson(filename: string, value: unknown) {
  const blob = new Blob([JSON.stringify(value, null, 2)], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export default function NgsVisualizationHub({ stages }: { stages: Ngs2Stage[] }) {
  if (!Array.isArray(stages) || !stages.length) return null;

  return (
    <section className="space-y-4" aria-label="NGS figures, graphs and diagrams">
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-glass-border bg-surface-0 p-4">
        <div>
          <p className="text-sm font-semibold text-text-primary">Figures, graphs & diagrams</p>
          <p className="mt-1 max-w-3xl text-[11px] leading-5 text-text-muted">
            Every visualization below is derived from measurements present in this run. Unsupported series remain absent rather than being filled with placeholders.
          </p>
        </div>
        <button
          type="button"
          onClick={() => downloadJson('bionexus_ngs_visualization_source.json', stages)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-[11px] text-text-secondary hover:text-text-primary"
        >
          <DownloadSimple /> Source JSON
        </button>
      </div>
      <NgsRunDiagram stages={stages} />
      <NgsScientificPlots stages={stages} />
    </section>
  );
}

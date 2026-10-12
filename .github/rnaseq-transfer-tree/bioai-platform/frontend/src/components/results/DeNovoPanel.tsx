'use client';

import { motion } from 'framer-motion';
import { Sparkle, Info } from '@phosphor-icons/react';
import type { UniprotSummary } from '@/types/pipeline';
import { fadeUp, cardHover } from '@/lib/animations';

interface DeNovoPanelProps {
  data: UniprotSummary;
}

interface CompRow {
  label: string;
  value: string;
}

export function DeNovoPanel({ data }: DeNovoPanelProps) {
  const comp = data.composition ?? {};
  const hints = data.function_hints ?? {};

  const rows: CompRow[] = [];
  if (comp.length) rows.push({ label: 'Length', value: `${comp.length} ${comp.sequence_type === 'protein' ? 'aa' : 'nt'}` });
  if (comp.molecular_weight) rows.push({ label: 'Mol. weight', value: `${comp.molecular_weight} Da` });
  if (comp.gc_content != null) rows.push({ label: 'GC content', value: `${comp.gc_content}%` });
  if (comp.isoelectric_point) rows.push({ label: 'Isoelectric point', value: `pI ≈ ${comp.isoelectric_point}` });

  const topAa: Array<{ aa: string; pct: number }> = Array.isArray(comp.aa_composition)
    ? [...comp.aa_composition].sort((a, b) => b.pct - a.pct).slice(0, 8)
    : [];

  return (
    <motion.div variants={fadeUp} whileHover={cardHover} className="data-card p-6 border border-dashed border-accent-purple/40">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="font-medium text-text-primary flex items-center gap-2">
            <Sparkle className="w-4 h-4 text-accent-purple" weight="fill" />
            De novo sequence analysis
          </h3>
          <p className="text-sm text-text-secondary mt-1">
            No homolog was found in reference databases — the annotations below are computed
            directly from your sequence.
          </p>
        </div>
      </div>

      {rows.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          {rows.map((r) => (
            <div key={r.label} className="bg-surface-1 rounded-lg p-3">
              <div className="text-xs font-semibold text-text-muted uppercase tracking-wider">{r.label}</div>
              <div className="text-sm font-mono text-text-primary mt-1">{r.value}</div>
            </div>
          ))}
        </div>
      )}

      {topAa.length > 0 && (
        <div className="mb-4">
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Amino acid composition</h4>
          <div className="flex flex-wrap gap-1.5">
            {topAa.map(({ aa, pct }) => (
              <span key={aa} className="text-xs bg-surface-1 px-2 py-1 rounded font-mono text-text-secondary">
                {aa} <span className="text-text-muted">{pct}%</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {(hints.go_terms?.length ?? 0) > 0 && (
        <div className="mt-4 pt-4 border-t border-glass-border">
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Function hints</h4>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {hints.go_terms!.slice(0, 12).map((go, i) => (
              <span key={i} className="text-xs bg-accent-purple/10 text-accent-purple px-2 py-0.5 rounded font-mono">{go}</span>
            ))}
          </div>
          {hints._note && (
            <p className="text-xs text-text-muted flex items-start gap-1.5">
              <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              {hints._note}
            </p>
          )}
        </div>
      )}

      <p className="text-xs text-text-muted mt-4 pt-4 border-t border-glass-border leading-relaxed">
        These are heuristic predictions on raw sequence composition — not database annotations.
        Treat them as hypotheses for experimental follow-up.
      </p>
    </motion.div>
  );
}

'use client';

import { SealCheck, Copy, Sparkle } from '@phosphor-icons/react';
import type { QueryConfidence } from '@/types/pipeline';

interface ConfidenceBadgeProps {
  confidence?: QueryConfidence | null;
  className?: string;
}

const CONFIDENCE_META: Record<
  QueryConfidence,
  { label: string; title: string; cls: string; icon: typeof SealCheck }
> = {
  identified: {
    label: 'Identified',
    title: 'Matched an exact database entry (direct, cross-reference, or name lookup)',
    cls: 'bg-accent-cyan/10 text-accent-cyan border-accent-cyan/30',
    icon: SealCheck,
  },
  homolog: {
    label: 'Homolog',
    title: 'Resolved via sequence similarity — results describe a homologous protein, not the exact query',
    cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    icon: Copy,
  },
  de_novo: {
    label: 'De novo · no database match',
    title: 'No homolog found in reference databases. Annotations below are computational predictions on the raw sequence.',
    cls: 'bg-accent-purple/10 text-accent-purple border-dashed border-accent-purple/40',
    icon: Sparkle,
  },
};

export function ConfidenceBadge({ confidence, className = '' }: ConfidenceBadgeProps) {
  if (!confidence) return null;
  const meta = CONFIDENCE_META[confidence];
  if (!meta) return null;
  const Icon = meta.icon;
  return (
    <span
      title={meta.title}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium ${meta.cls} ${className}`}
    >
      <Icon className="w-3.5 h-3.5" weight="fill" />
      {meta.label}
    </span>
  );
}

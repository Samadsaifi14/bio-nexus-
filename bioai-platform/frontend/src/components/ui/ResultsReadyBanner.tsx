'use client';

import { CheckCircle as CheckCircle2 } from '@phosphor-icons/react';

/**
 * Distinct "results arrived" notification shown at the top of a tool's
 * results section. Job pages poll in the background; this banner is the
 * explicit signal that a run finished so users aren't left staring at
 * the form wondering if anything happened.
 */

interface ResultsReadyBannerProps {
  title?: string;
  subtitle?: string;
  className?: string;
}

export function ResultsReadyBanner({ title = 'Results ready', subtitle, className = '' }: ResultsReadyBannerProps) {
  return (
    <div className={`rounded-xl bg-good/10 border border-good/25 px-4 py-3 flex items-center gap-3 ${className}`}>
      <CheckCircle2 className="w-5 h-5 text-good shrink-0" />
      <div className="min-w-0">
        <p className="text-sm font-semibold text-text-primary">{title}</p>
        {subtitle && <p className="text-xs text-text-muted mt-0.5 truncate">{subtitle}</p>}
      </div>
    </div>
  );
}

'use client';

import { motion } from 'framer-motion';
import { FileText, ArrowSquareOut as ExternalLink } from '@phosphor-icons/react';
import type { FinalSynthesisReport } from '@/types/pipeline';
import { fadeUp } from '@/lib/animations';
import { ConfidenceBadge } from '@/components/results/ConfidenceBadge';

const TOOL_LABELS: Record<string, string> = {
  blast: 'BLAST',
  uniprot: 'UniProt',
  domains: 'Domains',
  msa: 'MSA',
  pathway_enrichment: 'Pathways',
  alphafold: 'Structure',
};

interface FinalReportProps {
  data: FinalSynthesisReport;
}

export function FinalReport({ data }: FinalReportProps) {
  if (!data || !data.findings?.length) return null;

  return (
    <motion.div variants={fadeUp} className="data-card p-6">
      <div className="flex items-start justify-between gap-4 mb-3">
        <div>
          <h2 className="text-lg font-semibold text-text-primary flex items-center gap-2">
            <FileText className="w-5 h-5 text-accent-cyan" />
            Final Report
          </h2>
          <p className="text-sm text-text-secondary mt-1">{data.headline}</p>
        </div>
        {data._mode === 'llm_polished' && (
          <span className="text-[10px] uppercase tracking-wider text-text-muted border border-glass-border rounded px-1.5 py-0.5 shrink-0">
            AI-polished
          </span>
        )}
      </div>

      {data.summary && data.summary !== data.headline && (
        <p className="text-sm text-text-secondary leading-relaxed mb-4">{data.summary}</p>
      )}

      <div className="space-y-2 mt-4">
        {data.findings.map((f, i) => (
          <div key={i} className="flex items-start justify-between gap-3 bg-surface-1 rounded-lg px-3 py-2">
            <div className="text-sm text-text-secondary leading-relaxed min-w-0">
              {f.claim}
              {f.page_url && (
                <a
                  href={f.page_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ml-1.5 text-accent-cyan hover:text-accent-cyan/80 inline-flex items-center gap-0.5"
                  title={`Source page: ${f.page_url}`}
                >
                  source <ExternalLink className="w-3 h-3" />
                </a>
              )}
              <span className="text-xs text-text-muted ml-2">({TOOL_LABELS[f.source_tool] ?? f.source_tool})</span>
            </div>
            <ConfidenceBadge confidence={f.confidence_tier} className="shrink-0 scale-90 origin-right" />
          </div>
        ))}
      </div>

      {data.caveats?.length > 0 && (
        <div className="mt-4 pt-4 border-t border-glass-border">
          {data.caveats.map((c, i) => (
            <p key={i} className="text-xs text-text-muted leading-relaxed mt-1 first:mt-0">
              {c}
            </p>
          ))}
        </div>
      )}
    </motion.div>
  );
}

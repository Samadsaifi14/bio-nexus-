'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { GitBranch, ChevronDown, ChevronRight, ExternalLink, AlertCircle, Download } from 'lucide-react';
import { fadeUp } from '@/lib/animations';
import type { PathwayEnrichment as PathwayEnrichmentData } from '@/types/pipeline';
import { downloadTsv, copyText } from '@/lib/export-utils';
import PathwayDiagram from './PathwayDiagram';

interface Props {
  data: PathwayEnrichmentData;
}

export function PathwayEnrichment({ data }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (!data || !data.pathways || data.pathways.length === 0) return null;

  return (
    <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <GitBranch className="w-5 h-5 text-accent-cyan" />
          <h3 className="text-lg font-semibold text-text-primary">Pathway Enrichment</h3>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => copyText(data.pathways.map(p => `https://reactome.org/content/detail/${p.stId}`).join("\n"))}
            className="btn-ghost text-xs px-2 py-1 flex items-center gap-1">
            <Download className="w-3 h-3" /> Copy links
          </button>
          <button onClick={() => downloadTsv(
            ["ID", "Name", "Species", "Found/Total", "FDR"],
            data.pathways.map(p => [p.stId, p.name, p.species, `${p.entitiesFound}/${p.entitiesTotal}`, p.entitiesFDR.toExponential(2)]),
            "pathways.tsv"
          )} className="btn-ghost text-xs px-2 py-1 flex items-center gap-1">
            <Download className="w-3 h-3" /> Export TSV
          </button>
        </div>
      </div>
      <p className="text-xs text-text-muted mb-4">
        {data.pathways.length} enriched pathway{data.pathways.length !== 1 ? 's' : ''} found · Sorted by FDR
      </p>
      <div className="space-y-2">
        {data.pathways.map((pw) => (
          <div key={pw.stId} className="border border-glass-border rounded-xl overflow-hidden">
            <button
              onClick={() => setExpanded(expanded === pw.stId ? null : pw.stId)}
              className="w-full flex items-center justify-between p-3 hover:bg-surface-2 transition text-left"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-text-primary truncate">{pw.name}</p>
                <p className="text-xs text-text-muted mt-0.5">
                  <span className="text-accent-cyan">{pw.entitiesFound}/{pw.entitiesTotal}</span> genes · FDR{' '}
                  <span className={pw.entitiesFDR < 0.05 ? 'text-emerald-400' : 'text-text-muted'}>
                    {pw.entitiesFDR.toExponential(2)}
                  </span>
                  {' · '}{pw.species}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0 ml-3">
                <a
                  href={`https://reactome.org/content/detail/${pw.stId}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="text-text-muted hover:text-accent-cyan transition"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
                {expanded === pw.stId ? <ChevronDown className="w-4 h-4 text-text-muted" /> : <ChevronRight className="w-4 h-4 text-text-muted" />}
              </div>
            </button>
            <AnimatePresence>
              {expanded === pw.stId && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className="overflow-hidden border-t border-glass-border"
                >
                  <div className="p-4">
                    <PathwayDiagram stId={pw.stId} />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        ))}
      </div>
      {data.pathways.length > 0 && data.pathways[0].entitiesFDR >= 0.05 && (
        <div className="flex items-start gap-2 mt-4 p-3 rounded-xl bg-amber-500/5 border border-amber-500/20">
          <AlertCircle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
          <p className="text-xs text-amber-300">No pathways passed the 0.05 FDR significance threshold. Results shown for reference.</p>
        </div>
      )}
    </motion.div>
  );
}

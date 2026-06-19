'use client';

import { motion } from 'framer-motion';
import { ExternalLink } from 'lucide-react';
import type { UniprotSummary } from '@/types/pipeline';
import { fadeUp, cardHover } from '@/lib/animations';

interface UniprotPanelProps {
  data: UniprotSummary | null;
}

export function UniprotPanel({ data }: UniprotPanelProps) {
  if (!data) return null;
  return (
    <motion.div variants={fadeUp} whileHover={cardHover} className="glass-card p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="font-medium text-text-primary">{data.full_name}</h3>
          <div className="flex items-center gap-3 mt-1">
            <span className="font-mono text-xs bg-accent-cyan/10 text-accent-cyan px-2 py-0.5 rounded">{data.accession}</span>
            <span className="text-sm text-text-secondary">{data.organism}</span>
          </div>
        </div>
        <a href={`https://www.uniprot.org/uniprotkb/${data.accession}`} target="_blank" rel="noopener noreferrer" className="text-sm text-accent-cyan hover:text-accent-cyan/80 transition flex items-center gap-1">
          UniProt <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div>
          {data.gene_names?.length > 0 && (
            <div className="mb-3">
              <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-1">Gene</h4>
              <div className="flex flex-wrap gap-1">{data.gene_names.map(g => <span key={g} className="text-sm bg-surface-1 px-2 py-0.5 rounded font-mono text-text-secondary">{g}</span>)}</div>
            </div>
          )}
          {data.subcellular_locations?.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-1">Location</h4>
              <div className="flex flex-wrap gap-1">{data.subcellular_locations.map(loc => <span key={loc} className="text-sm bg-accent-purple/10 text-accent-purple px-2 py-0.5 rounded">{loc}</span>)}</div>
            </div>
          )}
        </div>
        <div>
          {data.keywords?.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-1">Keywords</h4>
              <div className="flex flex-wrap gap-1">{data.keywords.map(kw => <span key={kw} className="text-xs bg-surface-1 text-text-muted px-2 py-0.5 rounded">{kw}</span>)}</div>
            </div>
          )}
        </div>
      </div>

      {data.functions?.length > 0 && (
        <div className="mt-4 pt-4 border-t border-glass-border">
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Function</h4>
          {data.functions.map((f, fi) => <p key={fi} className="text-sm text-text-secondary leading-relaxed mb-1">{f}</p>)}
        </div>
      )}

      {data.features?.length > 0 && (
        <div className="mt-4 pt-4 border-t border-glass-border">
          <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Active Sites & Features</h4>
          <div className="space-y-1">
            {data.features.map((f, fi) => (
              <div key={fi} className="text-sm text-text-secondary">
                <span className="font-medium">{f.type}:</span> {f.description}
                {(f.begin || f.end) && <span className="text-text-muted"> ({f.begin}–{f.end})</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}

'use client';

import { ExternalLink } from 'lucide-react';
import type { UniprotSummary } from '@/types/pipeline';

interface UniprotPanelProps {
  data: UniprotSummary;
}

export default function UniprotPanel({ data }: UniprotPanelProps) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="font-medium text-gray-900">{data.full_name}</h3>
          <div className="flex items-center gap-3 mt-1">
            <span className="font-mono text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">{data.accession}</span>
            <span className="text-sm text-gray-500">{data.organism}</span>
          </div>
        </div>
        <a href={`https://www.uniprot.org/uniprotkb/${data.accession}`} target="_blank" rel="noopener noreferrer" className="text-sm text-green-600 hover:text-green-700 flex items-center gap-1">
          UniProt <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div>
          {data.gene_names?.length > 0 && (
            <div className="mb-3">
              <h4 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1">Gene</h4>
              <div className="flex flex-wrap gap-1">{data.gene_names.map(g => <span key={g} className="text-sm bg-gray-100 px-2 py-0.5 rounded font-mono">{g}</span>)}</div>
            </div>
          )}
          {data.subcellular_locations?.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1">Location</h4>
              <div className="flex flex-wrap gap-1">{data.subcellular_locations.map(loc => <span key={loc} className="text-sm bg-blue-50 text-blue-700 px-2 py-0.5 rounded">{loc}</span>)}</div>
            </div>
          )}
        </div>
        <div>
          {data.keywords?.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1">Keywords</h4>
              <div className="flex flex-wrap gap-1">{data.keywords.map(kw => <span key={kw} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{kw}</span>)}</div>
            </div>
          )}
        </div>
      </div>

      {data.functions?.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-100">
          <h4 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-2">Function</h4>
          {data.functions.map((f, fi) => <p key={fi} className="text-sm text-gray-600 leading-relaxed mb-1">{f}</p>)}
        </div>
      )}

      {data.features?.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-100">
          <h4 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-2">Active Sites & Features</h4>
          <div className="space-y-1">
            {data.features.map((f, fi) => (
              <div key={fi} className="text-sm text-gray-600">
                <span className="font-medium">{f.type}:</span> {f.description}
                {(f.begin || f.end) && <span className="text-gray-400"> ({f.begin}–{f.end})</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

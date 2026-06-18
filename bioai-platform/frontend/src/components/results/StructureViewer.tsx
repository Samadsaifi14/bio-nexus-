'use client';

import { ExternalLink } from 'lucide-react';
import type { AlphaFoldResult } from '@/types/pipeline';

interface StructureViewerProps {
  data: AlphaFoldResult;
}

export function StructureViewer({ data }: StructureViewerProps) {
  if (!data.structure_available) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-6">
        <h3 className="font-semibold text-gray-900 mb-2">AlphaFold Structure</h3>
        <p className="text-sm text-gray-500">No AlphaFold prediction available for this protein.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900">AlphaFold Structure</h3>
        {data.confidence && (
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            data.confidence > 90 ? 'bg-teal-50 text-teal-700' :
            data.confidence > 70 ? 'bg-yellow-50 text-yellow-700' :
            'bg-red-50 text-red-700'
          }`}>
            pLDDT: {data.confidence.toFixed(1)}
          </span>
        )}
      </div>

      {data.pdb_url && (
        <div className="aspect-square bg-gray-50 rounded-xl border border-gray-100 flex items-center justify-center mb-4">
          <p className="text-sm text-gray-400 text-center px-4">
            3D viewer coming Phase 1.5<br />
            <span className="text-xs">(3Dmol.js in-browser rendering)</span>
          </p>
        </div>
      )}

      {data.pdb_url && (
        <a
          href={data.pdb_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-teal-600 hover:text-teal-700 flex items-center gap-1"
        >
          Download PDB file <ExternalLink className="w-3.5 h-3.5" />
        </a>
      )}

      {data.model_created_date && (
        <p className="text-xs text-gray-400 mt-1">Model created: {data.model_created_date}</p>
      )}
    </div>
  );
}

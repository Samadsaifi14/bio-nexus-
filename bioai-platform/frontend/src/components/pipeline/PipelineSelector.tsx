'use client';

import { useState } from 'react';
import { Dna, ArrowRight, ChevronRight } from 'lucide-react';

interface PipelineOption {
  id: string;
  name: string;
  description: string;
  icon: typeof Dna;
}

const pipelines: PipelineOption[] = [
  {
    id: 'protein_analysis',
    name: 'Protein Sequence Analysis',
    description: 'BLAST + UniProt + AlphaFold + AI interpretation in one run',
    icon: Dna,
  },
];

interface PipelineSelectorProps {
  onSelect: (pipelineId: string) => void;
}

export default function PipelineSelector({ onSelect }: PipelineSelectorProps) {
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Choose a pipeline</h2>
      <div className="grid gap-4">
        {pipelines.map((p) => {
          const active = selected === p.id;
          return (
            <button
              key={p.id}
              onClick={() => {
                setSelected(p.id);
                onSelect(p.id);
              }}
              className={`w-full text-left p-5 rounded-2xl border-2 transition ${
                active
                  ? 'border-green-500 bg-green-50 shadow-sm'
                  : 'border-gray-200 bg-white hover:border-green-300 hover:shadow-sm'
              }`}
            >
              <div className="flex items-start gap-4">
                <div className={`p-3 rounded-xl ${active ? 'bg-green-100' : 'bg-gray-100'}`}>
                  <p.icon className={`w-6 h-6 ${active ? 'text-green-600' : 'text-gray-500'}`} />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className={`font-semibold ${active ? 'text-green-900' : 'text-gray-900'}`}>{p.name}</h3>
                    <ChevronRight className={`w-4 h-4 ${active ? 'text-green-600' : 'text-gray-300'}`} />
                  </div>
                  <p className="text-sm text-gray-500 mt-1">{p.description}</p>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

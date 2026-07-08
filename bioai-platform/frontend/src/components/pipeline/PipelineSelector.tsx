'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Dna, ArrowRight, ChevronRight } from 'lucide-react';
import { fadeUp, stagger, cardHover } from '@/lib/animations';

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

export function PipelineSelector({ onSelect }: PipelineSelectorProps) {
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Choose a pipeline</h2>
      <motion.div animate="show" variants={stagger} className="grid gap-4">
        {pipelines.map((p) => {
          const active = selected === p.id;
          return (
            <motion.div key={p.id} variants={fadeUp} whileHover={cardHover}>
              <button
                onClick={() => {
                  setSelected(p.id);
                  onSelect(p.id);
                }}
                className={`w-full text-left p-5 rounded-2xl border-2 transition ${
                  active
                    ? 'border-teal-500 bg-teal-50 shadow-sm'
                    : 'border-gray-200 bg-white hover:border-teal-300 hover:shadow-sm'
                }`}
              >
                <div className="flex items-start gap-4">
                  <div className={`p-3 rounded-xl ${active ? 'bg-teal-100' : 'bg-gray-100'}`}>
                    <p.icon className={`w-6 h-6 ${active ? 'text-teal-600' : 'text-gray-500'}`} />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className={`font-semibold ${active ? 'text-teal-900' : 'text-gray-900'}`}>{p.name}</h3>
                      <ChevronRight className={`w-4 h-4 ${active ? 'text-teal-600' : 'text-gray-300'}`} />
                    </div>
                    <p className="text-sm text-gray-500 mt-1">{p.description}</p>
                  </div>
                </div>
              </button>
            </motion.div>
          );
        })}
      </motion.div>
    </div>
  );
}

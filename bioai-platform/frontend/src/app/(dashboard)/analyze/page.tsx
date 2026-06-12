'use client';

import { useRouter } from 'next/navigation';
import { Dna, Layout, Search, Globe, GitBranch, Beaker } from 'lucide-react';

const operations = [
  {
    id: 'blast',
    name: 'BLAST Search',
    description: 'Find similar sequences across organisms. The most common starting point for any protein or DNA analysis.',
    icon: Search,
    active: true,
    badge: null,
  },
  {
    id: 'uniprot',
    name: 'UniProt Lookup',
    description: 'Retrieve detailed annotations, functions, and features for a known protein.',
    icon: Globe,
    active: false,
    badge: 'Coming in Phase 1',
  },
  {
    id: 'msa',
    name: 'Multiple Sequence Alignment',
    description: 'Align three or more sequences to find conserved regions and evolutionary relationships.',
    icon: Layout,
    active: false,
    badge: 'Coming in Phase 1',
  },
  {
    id: 'structure',
    name: 'Structure Lookup',
    description: 'Fetch 3D protein structures from PDB and visualize them in your browser.',
    icon: Dna,
    active: false,
    badge: 'Coming in Phase 1',
  },
  {
    id: 'pathway',
    name: 'Pathway Analysis',
    description: 'Map your genes or proteins to biological pathways from Reactome and WikiPathways.',
    icon: GitBranch,
    active: false,
    badge: 'Coming in Phase 1',
  },
  {
    id: 'tools',
    name: 'Utility Tools',
    description: 'Format conversion, sequence validation, and other everyday bioinformatics utilities.',
    icon: Beaker,
    active: false,
    badge: 'Coming in Phase 1',
  },
];

export default function AnalyzePage() {
  const router = useRouter();

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-1">What do you want to do?</h1>
      <p className="text-gray-500 mb-8">Choose an operation to get started with your analysis.</p>

      <div className="grid md:grid-cols-2 gap-4">
        {operations.map((op) => {
          const Icon = op.icon;
          return (
            <button
              key={op.id}
              onClick={() => op.active && router.push(`/analyze/${op.id}`)}
              disabled={!op.active}
              className={`relative text-left p-5 rounded-2xl border-2 transition ${
                op.active
                  ? 'border-gray-200 bg-white hover:border-teal-400 hover:shadow-md cursor-pointer'
                  : 'border-gray-100 bg-gray-50 cursor-default opacity-70'
              }`}
            >
              <div className="flex items-start gap-4">
                <div className={`p-3 rounded-xl ${op.active ? 'bg-teal-50' : 'bg-gray-100'}`}>
                  <Icon className={`w-6 h-6 ${op.active ? 'text-teal-600' : 'text-gray-400'}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className={`font-semibold ${op.active ? 'text-gray-900' : 'text-gray-500'}`}>
                      {op.name}
                    </h3>
                    {op.badge && (
                      <span className="text-[10px] font-medium text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full whitespace-nowrap">
                        {op.badge}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-500 mt-1 leading-relaxed">
                    {op.description}
                  </p>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

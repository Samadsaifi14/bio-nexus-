'use client';

import { useRouter } from 'next/navigation';
import { Play, Dna, Brain, Zap } from 'lucide-react';

export default function DashboardHome() {
  const router = useRouter();

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Bio Nexus Dashboard</h1>
      <p className="text-gray-600 mb-8">
        Run a pipeline or browse your recent results
      </p>

      <div className="grid md:grid-cols-2 gap-6 mb-8">
        <button
          onClick={() => router.push('/dashboard/analyze')}
          className="bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl p-8 text-left text-white hover:from-green-600 hover:to-emerald-700 transition shadow-sm"
        >
          <Play className="w-10 h-10 mb-4" />
          <h2 className="text-xl font-bold mb-2">New Analysis</h2>
          <p className="text-sm text-green-100">Run a protein analysis pipeline — BLAST, UniProt, AlphaFold, and AI interpretation</p>
        </button>

        <button
          onClick={() => router.push('/dashboard/history')}
          className="bg-white rounded-2xl border border-gray-200 p-8 text-left hover:border-green-300 hover:shadow-sm transition"
        >
          <Dna className="w-10 h-10 text-green-600 mb-4" />
          <h2 className="text-xl font-bold text-gray-900 mb-2">Recent Results</h2>
          <p className="text-sm text-gray-500">View and share your past pipeline runs</p>
        </button>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        {[
          { icon: Zap, title: 'One-click pipeline', desc: 'Submit a sequence, get BLAST + annotations + structure + AI' },
          { icon: Brain, title: 'AI-powered interpretation', desc: 'Full context assembled before AI speaks — grounded, not generic' },
          { icon: Dna, title: 'Shareable results', desc: 'Every result gets a public URL you can share with collaborators' },
        ].map((f) => (
          <div key={f.title} className="bg-white rounded-xl border border-gray-200 p-5">
            <f.icon className="w-8 h-8 text-green-600 mb-3" />
            <h3 className="font-semibold text-gray-900 text-sm mb-1">{f.title}</h3>
            <p className="text-xs text-gray-500">{f.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

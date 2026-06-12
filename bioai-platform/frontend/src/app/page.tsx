'use client';

import Link from 'next/link';
import { Dna, Zap, Brain, Database, ChevronRight } from 'lucide-react';

export default function Home() {

  return (
    <div className="min-h-screen">
      {/* Nav */}
      <nav className="border-b border-green-100 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Dna className="w-8 h-8 text-green-600" />
            <span className="text-xl font-bold text-gray-900">Bio Nexus</span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/auth" className="text-sm text-gray-600 hover:text-gray-900 font-medium">Sign in</Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-20 pb-24">
        <div className="max-w-3xl">
          <h1 className="text-5xl font-bold text-gray-900 leading-tight tracking-tight">
            One interface for every <span className="text-green-600">bioinformatics</span> tool you use.
          </h1>
          <p className="mt-6 text-xl text-gray-600 leading-relaxed text-balance">
            BLAST, UniProt, AlphaFold, docking, MSA, pathway analysis — run from a single dashboard.
            No command line. No juggling 12 browser tabs. Built for researchers who aren't bioinformaticians.
          </p>
        </div>

        {/* CTA */}
        <div className="mt-12">
          <Link
            href="/auth"
            className="inline-flex items-center gap-2 px-8 py-4 bg-green-600 text-white font-semibold rounded-xl hover:bg-green-700 transition text-lg"
          >
            Start analyzing
            <ChevronRight className="w-5 h-5" />
          </Link>
          <p className="mt-3 text-sm text-gray-500">Free for academic researchers. No spam, ever.</p>
        </div>
      </section>

      {/* Features */}
      <section className="border-t border-green-100 bg-white py-24">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center text-gray-900 mb-16">
            Everything you need, nothing you don't
          </h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {[
              { icon: Database, title: 'BLAST + UniProt', desc: 'Run searches and pull annotations in seconds. Cached for speed.' },
              { icon: Brain, title: 'AI Interpretation', desc: 'Every result explained in plain language with citations to primary sources.' },
              { icon: Zap, title: 'AlphaFold Structures', desc: 'Fetch 3D predictions for 200M+ proteins. Interactive 3D viewer built in.' },
              { icon: Dna, title: 'Drug Discovery', desc: 'ChEMBL bioactivity, PubChem compounds, molecular docking — all connected.' },
            ].map((f) => (
              <div key={f.title} className="p-6 rounded-2xl border border-gray-200 hover:border-green-300 hover:shadow-lg transition">
                <f.icon className="w-10 h-10 text-green-600 mb-4" />
                <h3 className="font-semibold text-gray-900 mb-2">{f.title}</h3>
                <p className="text-gray-600 text-sm leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Who it's for */}
      <section className="py-24">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center text-gray-900 mb-16">
            Built for researchers at IITs, IISERs, CSIR labs, NCBS, CCMB, AIIMS
          </h2>
          <div className="grid md:grid-cols-3 gap-8 max-w-4xl mx-auto">
            {[
              { step: '1', text: 'Paste your protein sequence or FASTA file' },
              { step: '2', text: 'Pick a tool — BLAST, structure, docking, anything' },
              { step: '3', text: 'Get results with AI explanation you can cite' },
            ].map((s) => (
              <div key={s.step} className="text-center">
                <div className="w-12 h-12 bg-green-100 text-green-700 rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">{s.step}</div>
                <p className="text-gray-700">{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-200 bg-white py-8">
        <div className="max-w-6xl mx-auto px-6 flex items-center justify-between text-sm text-gray-500">
          <div className="flex items-center gap-2">
            <Dna className="w-5 h-5 text-green-600" />
            <span>Bio Nexus</span>
          </div>
          <span>Made for Indian computational biology researchers</span>
        </div>
      </footer>
    </div>
  );
}
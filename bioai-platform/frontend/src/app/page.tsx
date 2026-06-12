'use client';

import Link from 'next/link';
import { Dna, Zap, Brain, Database, ChevronRight, ArrowRight } from 'lucide-react';
import SequenceTypewriter from '@/components/SequenceTypewriter';

export default function Home() {
  return (
    <div className="min-h-screen">
      <nav className="border-b border-gray-100 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Dna className="w-8 h-8 text-teal-600" />
            <span className="text-xl font-bold text-gray-900 font-display">Bio Nexus</span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/auth" className="text-sm text-gray-600 hover:text-gray-900 font-medium">
              Sign in
            </Link>
            <Link
              href="/analyze"
              className="px-5 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition"
            >
              Get started
            </Link>
          </div>
        </div>
      </nav>

      <section className="max-w-6xl mx-auto px-6 pt-20 pb-24">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          <div className="animate-fadeUp">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-teal-50 border border-teal-200 rounded-full text-xs font-medium text-teal-700 mb-6">
              <span className="w-1.5 h-1.5 rounded-full bg-teal-500" />
              Free for academic researchers
            </div>
            <h1 className="text-5xl font-bold text-gray-900 leading-tight tracking-tight font-display">
              One interface for every{' '}
              <span className="text-teal-600">bioinformatics</span>{' '}
              tool you use.
            </h1>
            <p className="mt-6 text-lg text-gray-600 leading-relaxed">
              BLAST, UniProt, AlphaFold, docking, MSA, pathway analysis — run from a single dashboard.
              No command line. No juggling browser tabs.
            </p>
            <div className="mt-10 flex items-center gap-4">
              <Link
                href="/analyze"
                className="inline-flex items-center gap-2 px-8 py-4 bg-teal-600 text-white font-semibold rounded-xl hover:bg-teal-700 transition text-lg"
              >
                Start analyzing
                <ArrowRight className="w-5 h-5" />
              </Link>
              <Link
                href="/auth"
                className="px-8 py-4 bg-white border border-gray-200 text-gray-700 font-medium rounded-xl hover:border-teal-300 hover:text-teal-700 transition text-lg"
              >
                Sign in
              </Link>
            </div>
            <p className="mt-4 text-sm text-gray-400">
              No credit card required. No spam. Ever.
            </p>
          </div>

          <div className="animate-fadeUp" style={{ animationDelay: '0.2s' }}>
            <SequenceTypewriter />
          </div>
        </div>
      </section>

      <section className="border-t border-gray-100 bg-gray-50 py-24">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center text-gray-900 mb-4 font-display">
            Everything you need, nothing you don't
          </h2>
          <p className="text-gray-500 text-center max-w-2xl mx-auto mb-16">
            From sequence to insight in minutes. Built for wet-lab researchers who need answers, not a terminal.
          </p>
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { icon: Database, title: 'BLAST + UniProt', desc: 'Run searches and pull annotations in seconds. Cached for speed.' },
              { icon: Brain, title: 'AI Interpretation', desc: 'Every result explained in plain language with citations to primary sources.' },
              { icon: Zap, title: 'AlphaFold Structures', desc: 'Fetch 3D predictions for 200M+ proteins. Interactive 3D viewer built in.' },
              { icon: Dna, title: 'Drug Discovery', desc: 'ChEMBL bioactivity, PubChem compounds, molecular docking — all connected.' },
            ].map((f, i) => (
              <div
                key={f.title}
                className="bg-white rounded-2xl border border-gray-200 p-6 hover:border-teal-300 hover:shadow-lg transition animate-fadeUp"
                style={{ animationDelay: `${0.1 * i}s` }}
              >
                <div className="w-10 h-10 bg-teal-50 rounded-xl flex items-center justify-center mb-4">
                  <f.icon className="w-5 h-5 text-teal-600" />
                </div>
                <h3 className="font-semibold text-gray-900 mb-2">{f.title}</h3>
                <p className="text-gray-600 text-sm leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-24">
        <div className="max-w-6xl mx-auto px-6">
          <h2 className="text-3xl font-bold text-center text-gray-900 mb-4 font-display">
            Three clicks. One answer.
          </h2>
          <p className="text-gray-500 text-center max-w-xl mx-auto mb-16">
            No dropdown menus with 50 options. No parameters you've never heard of. Just paste, pick, and learn.
          </p>
          <div className="grid md:grid-cols-3 gap-8 max-w-4xl mx-auto">
            {[
              { step: '1', text: 'Paste your protein sequence or FASTA file' },
              { step: '2', text: 'Pick a tool — BLAST, structure, docking, anything' },
              { step: '3', text: 'Get results with AI explanation you can cite' },
            ].map((s, i) => (
              <div key={s.step} className="text-center animate-fadeUp" style={{ animationDelay: `${0.1 * i}s` }}>
                <div className="w-14 h-14 bg-teal-50 text-teal-700 rounded-2xl flex items-center justify-center text-2xl font-bold mx-auto mb-4 font-display">
                  {s.step}
                </div>
                <p className="text-gray-700 font-medium">{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-gray-900 py-24">
        <div className="max-w-6xl mx-auto px-6 text-center">
          <h2 className="text-3xl font-bold text-white mb-4 font-display">
            Ready to analyze?
          </h2>
          <p className="text-gray-400 max-w-xl mx-auto mb-8">
            No account needed. Paste a sequence and get BLAST results + AI interpretation in under 3 minutes.
          </p>
          <Link
            href="/analyze"
            className="inline-flex items-center gap-2 px-8 py-4 bg-teal-500 text-white font-semibold rounded-xl hover:bg-teal-400 transition text-lg"
          >
            Start your first analysis
            <ChevronRight className="w-5 h-5" />
          </Link>
        </div>
      </section>

      <footer className="border-t border-gray-200 bg-white py-8">
        <div className="max-w-6xl mx-auto px-6 flex items-center justify-between text-sm text-gray-500">
          <div className="flex items-center gap-2">
            <Dna className="w-5 h-5 text-teal-600" />
            <span className="font-medium">Bio Nexus</span>
          </div>
          <span>Built for Indian computational biology researchers</span>
        </div>
      </footer>
    </div>
  );
}

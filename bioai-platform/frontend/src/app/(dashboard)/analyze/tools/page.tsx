'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { ArrowLeft, Beaker, Copy, Check } from 'lucide-react';
import { fadeUp } from '@/lib/animations';

export default function ToolsPage() {
  const router = useRouter();
  const [input, setInput] = useState('');
  const [output, setOutput] = useState('');
  const [tool, setTool] = useState<'reverse' | 'gc' | 'fasta'>('reverse');
  const [copied, setCopied] = useState(false);

  const process = () => {
    const raw = input.replace(/[^A-Za-z]/g, '').toUpperCase();
    if (!raw) return;
    switch (tool) {
      case 'reverse':
        setOutput(raw.split('').reverse().join(''));
        break;
      case 'gc': {
        const gc = raw.replace(/[^CG]/g, '').length;
        const total = raw.length;
        setOutput(`GC content: ${(gc / total * 100).toFixed(1)}% (${gc}/${total})`);
        break;
      }
      case 'fasta': {
        const lines = [];
        for (let i = 0; i < raw.length; i += 60) {
          lines.push(raw.slice(i, i + 60));
        }
        setOutput(`>sequence\n${lines.join('\n')}`);
        break;
      }
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(output);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-2xl">
      <button onClick={() => router.push('/analyze')} className="flex items-center gap-1 text-sm text-text-muted hover:text-text-primary mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Choose a different operation
      </button>

      <motion.div variants={fadeUp} initial="hidden" animate="show" className="mb-8">
        <h1 className="text-2xl font-bold text-text-primary mb-1">Utility Tools</h1>
        <p className="text-sm text-text-secondary">Reverse complement, GC content, FASTA formatting, and more.</p>
      </motion.div>

      <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-5 mb-6 space-y-4">
        <div className="flex gap-2 flex-wrap">
          {([{ id: 'reverse', label: 'Reverse' }, { id: 'gc', label: 'GC Content' }, { id: 'fasta', label: '→ FASTA' }] as const).map((t) => (
            <button key={t.id} onClick={() => { setTool(t.id); setOutput(''); }} className={`px-4 py-2 text-sm font-medium rounded-lg transition ${tool === t.id ? 'btn-primary' : 'glass-card text-text-secondary'}`}>
              {t.label}
            </button>
          ))}
        </div>

        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Paste raw sequence..."
          className="w-full h-32 px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition font-mono text-sm resize-none bg-surface-1 text-text-primary"
        />

        <button onClick={process} disabled={!input.trim()} className="btn-primary px-6 py-2.5 text-sm disabled:opacity-50">
          Process
        </button>
      </motion.div>

      {output && (
        <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-5">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-medium text-text-muted uppercase tracking-wider">Result</p>
            <button onClick={handleCopy} className="text-xs text-accent-cyan hover:underline flex items-center gap-1">
              {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
          <pre className="font-mono text-sm text-text-secondary bg-surface-0 rounded-xl p-4 max-h-48 overflow-auto whitespace-pre-wrap break-all">
            {output}
          </pre>
        </motion.div>
      )}
    </div>
  );
}

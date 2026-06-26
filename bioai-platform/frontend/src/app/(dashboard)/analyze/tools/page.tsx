'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { ArrowLeft, Copy, Check } from 'lucide-react';
import { fadeUp } from '@/lib/animations';
import { useAuditTrail } from '@/hooks/useAuditTrail';

const COMPLEMENT: Record<string, string> = {
  A: 'T', T: 'A', C: 'G', G: 'C',
  U: 'A', R: 'Y', Y: 'R', S: 'S', W: 'W', K: 'M', M: 'K',
  B: 'V', V: 'B', D: 'H', H: 'D', N: 'N',
};

const CODON: Record<string, string> = {
  TTT:'F',TTC:'F',TTA:'L',TTG:'L',TCT:'S',TCC:'S',TCA:'S',TCG:'S',
  TAT:'Y',TAC:'Y',TAA:'*',TAG:'*',TGT:'C',TGC:'C',TGA:'*',TGG:'W',
  CTT:'L',CTC:'L',CTA:'L',CTG:'L',CCT:'P',CCC:'P',CCA:'P',CCG:'P',
  CAT:'H',CAC:'H',CAA:'Q',CAG:'Q',CGT:'R',CGC:'R',CGA:'R',CGG:'R',
  ATT:'I',ATC:'I',ATA:'I',ATG:'M',ACT:'T',ACC:'T',ACA:'T',ACG:'T',
  AAT:'N',AAC:'N',AAA:'K',AAG:'K',AGT:'S',AGC:'S',AGA:'R',AGG:'R',
  GTT:'V',GTC:'V',GTA:'V',GTG:'V',GCT:'A',GCC:'A',GCA:'A',GCG:'A',
  GAT:'D',GAC:'D',GAA:'E',GAG:'E',GGT:'G',GGC:'G',GGA:'G',GGG:'G',
};

const VALID_DNA = new Set('ACGTUN');

// Insulin CDS (human) — complete ORF with stop codon
const SAMPLE_CDS = 'ATGGCCCTGTGGATGCGCCTCCTGCCCCTGCTGGCGCTGCTGGCCCTCTGGGGACCTGACCCAGCCGCAGCCTTTGTGAACCAACACCTGTGCGGCTCACACCTGGTGGAAGCTCTCTACCTAGTGTGCGGGGAACGAGGCTTCTTCTACACACCCAAGACCCGCCGGGAGGCAGAGGACCTGCAGGTGGGGCAGGTGGAGCTGGGCGGGGGCCCTGGTGCAGGCAGCCTGCAGCCCTTGGCCCTGGAGGGGTCCCTGCAGAAGCGTGGCATTGTGGAACAATGCTGTACCAGCATCTGCTCCCTCTACCAGCTGGAGAACTACTGCAACTAG';

const TOOLS = [
  { id: 'translate' as const, label: 'Translate CDS' },
  { id: 'revcomp' as const, label: 'Reverse Complement' },
  { id: 'reverse' as const, label: 'Reverse' },
  { id: 'complement' as const, label: 'Complement' },
  { id: 'gc' as const, label: 'GC Content' },
  { id: 'fasta' as const, label: '→ FASTA' },
];

export default function ToolsPage() {
  const router = useRouter();
  const audit = useAuditTrail();
  const auditedRef = useRef(false);
  const [input, setInput] = useState('');
  const [output, setOutput] = useState('');
  const [tool, setTool] = useState<string>('translate');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const stored = sessionStorage.getItem('cds_sequence');
    if (stored) {
      sessionStorage.removeItem('cds_sequence');
      setInput(stored);
      setTool('translate');
    }
  }, []);

  const process = () => {
    const raw = input.replace(/[^A-Za-z]/g, '').toUpperCase();
    if (!raw) return;
    auditedRef.current = false;
    switch (tool) {
      case 'translate': {
        const chars = raw.split('');
        const invalid = chars.filter(c => !VALID_DNA.has(c));
        if (invalid.length > 0) {
          setOutput(`Error: Invalid DNA character(s): ${Array.from(new Set(invalid)).join(', ')}\nOnly A, C, G, T, U, N allowed.`);
          audit.emitFailed('translate_cds', 'CDStool', `${raw.length}bp`, `invalid chars: ${Array.from(new Set(invalid)).join(',')}`);
          return;
        }
        const seq = raw.replace(/U/g, 'T');
        if (seq.length < 3) {
          setOutput('Error: Sequence too short — need at least 3 bases (1 codon).');
          audit.emitFailed('translate_cds', 'CDStool', `${seq.length}bp`, 'too short');
          return;
        }
        const startIdx = seq.indexOf('ATG');
        const offset = startIdx >= 0 ? startIdx : 0;
        const cdsLen = seq.length - offset;
        const codons: string[] = [];
        for (let i = offset; i + 2 < seq.length; i += 3) {
          codons.push(seq.slice(i, i + 3));
        }
        const aa: string[] = [];
        let stopped = false;
        for (const codon of codons) {
          if (codon.includes('N')) { aa.push('X'); continue; }
          const a = CODON[codon];
          if (!a) { aa.push('X'); continue; }
          if (a === '*') { stopped = true; break; }
          aa.push(a);
        }
        const protein = aa.join('');
        const line1 = `> Translated CDS${startIdx >= 0 ? '' : ' (no start codon — translated from position 0)'}`;
        const lines: string[] = [];
        for (let i = 0; i < protein.length; i += 60) {
          lines.push(protein.slice(i, i + 60));
        }
        const stats =
          `CDS: ${cdsLen} bp → Protein: ${protein.length} aa` +
          (stopped ? ' (complete ORF)' : cdsLen % 3 !== 0 ? ' (incomplete final codon)' : ' (no stop codon — partial CDS)') +
          (offset > 0 ? `\nORF start at position ${offset + 1}` : '');
        setOutput(`${line1}\n${lines.join('\n')}\n\n${stats}`);
        if (!auditedRef.current) { auditedRef.current = true; audit.emitSuccess('translate_cds', 'CDStool', `${raw.length}bp`, `${protein.length}aa`); }
        break;
      }
      case 'revcomp':
        setOutput(raw.split('').reverse().map(c => COMPLEMENT[c] || c).join(''));
        break;
      case 'reverse':
        setOutput(raw.split('').reverse().join(''));
        break;
      case 'complement':
        setOutput(raw.split('').map(c => COMPLEMENT[c] || c).join(''));
        break;
      case 'gc': {
        const gc = raw.replace(/[^CG]/g, '').length;
        const at = raw.replace(/[^AT]/g, '').length;
        const total = raw.length;
        const other = total - gc - at;
        setOutput(
          `GC content: ${(gc / total * 100).toFixed(1)}%  (${gc}/${total})\n` +
          `AT content: ${(at / total * 100).toFixed(1)}%  (${at}/${total})\n` +
          `Length: ${total} bp\n` +
          (other > 0 ? `Other: ${other} (ambiguous bases)\n` : '') +
          `GC skew (G-C)/(G+C): ${raw.includes('G') || raw.includes('C') ? ((raw.replace(/[^G]/g, '').length - raw.replace(/[^C]/g, '').length) / (raw.replace(/[^GC]/g, '').length || 1) * 100).toFixed(1) : 0}%`
        );
        break;
      }
      case 'fasta': {
        const name = raw.slice(0, 20);
        const lines = [];
        for (let i = 0; i < raw.length; i += 60) {
          lines.push(raw.slice(i, i + 60));
        }
        setOutput(`>${name}\n${lines.join('\n')}`);
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
        <p className="text-sm text-text-secondary">Translate CDS, reverse complement, GC content, FASTA formatting, and more.</p>
      </motion.div>

      <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-5 mb-6 space-y-4">
        <div className="flex gap-2 flex-wrap">
          {TOOLS.map((t) => (
            <button key={t.id} onClick={() => { setTool(t.id); setOutput(''); }} className={`px-4 py-2 text-sm font-medium rounded-lg transition ${tool === t.id ? 'btn-primary' : 'glass-card text-text-secondary'}`}>
              {t.label}
            </button>
          ))}
        </div>

        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Paste raw DNA or protein sequence..."
          className="w-full h-32 px-4 py-3 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition font-mono text-sm resize-none bg-surface-1 text-text-primary"
        />

        <div className="flex gap-3">
          <button
            onClick={() => { setInput(SAMPLE_CDS); setOutput(''); }}
            className="text-sm text-accent-cyan hover:text-accent-cyan/80 underline"
          >
            Load sample
          </button>
          <div className="flex-1" />
          <button onClick={process} disabled={!input.trim()} className="btn-primary px-6 py-2.5 text-sm disabled:opacity-50">
            Process
          </button>
        </div>
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

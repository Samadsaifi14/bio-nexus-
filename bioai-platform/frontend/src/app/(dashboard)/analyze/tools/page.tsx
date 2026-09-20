'use client';

import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Check, Copy, Flask, Warning as WarningIcon } from '@phosphor-icons/react';

import { fadeUp } from '@/lib/animations';
import { longApi } from '@/lib/api';
import { BackButton, CriticalButton, FlatTextarea, PageHeader } from '@/components/ui';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import { isScientificResult, type ScientificResult } from '@/types/scientific-result';

const SAMPLE_CDS = 'ATGGCCCTGTGGATGCGCCTCCTGCCCCTGCTGGCGCTGCTGGCCCTCTGGGGACCTGACCCAGCCGCAGCCTTTGTGAACCAACACCTGTGCGGCTCACACCTGGTGGAAGCTCTCTACCTAGTGTGCGGGGAACGAGGCTTCTTCTACACACCCAAGACCCGCCGGGAGGCAGAGGACCTGCAGGTGGGGCAGGTGGAGCTGGGCGGGGGCCCTGGTGCAGGCAGCCTGCAGCCCTTGGCCCTGGAGGGGTCCCTGCAGAAGCGTGGCATTGTGGAACAATGCTGTACCAGCATCTGCTCCCTCTACCAGCTGGAGAACTACTGCAACTAG';

const TOOLS = [
  { id: 'analyze', label: 'Sequence analysis' },
  { id: 'translate_frame', label: 'Translate selected frame' },
  { id: 'find_orfs', label: 'Find ORFs' },
  { id: 'translate_cds', label: 'Translate declared CDS' },
  { id: 'reverse_complement', label: 'Reverse complement' },
  { id: 'complement', label: 'Complement' },
  { id: 'reverse', label: 'Reverse' },
  { id: 'transcribe', label: 'Transcribe DNA → RNA' },
  { id: 'fasta', label: 'Format FASTA' },
] as const;

type Operation = typeof TOOLS[number]['id'];

type OperationResults = Record<string, unknown> & {
  operation: Operation;
  sequence_type: string;
  input_length: number;
  value: unknown;
};

function displayValue(value: unknown): string {
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
}

export default function ToolsPage() {
  const audit = useAuditTrail();
  const [input, setInput] = useState('');
  const [operation, setOperation] = useState<Operation>('translate_frame');
  const [seqType, setSeqType] = useState<'auto' | 'dna' | 'rna' | 'protein'>('auto');
  const [frame, setFrame] = useState(1);
  const [stopAtStop, setStopAtStop] = useState(false);
  const [requireStart, setRequireStart] = useState(false);
  const [requireTerminalStop, setRequireTerminalStop] = useState(false);
  const [minOrfAa, setMinOrfAa] = useState(1);
  const [fastaName, setFastaName] = useState('sequence');
  const [result, setResult] = useState<ScientificResult<OperationResults> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const stored = sessionStorage.getItem('cds_sequence');
    if (stored) {
      sessionStorage.removeItem('cds_sequence');
      setInput(stored);
      setOperation('translate_cds');
      setSeqType('dna');
    }
  }, []);

  const showFrame = operation === 'translate_frame' || operation === 'translate_cds';
  const output = useMemo(() => result ? displayValue(result.results.value) : '', [result]);

  const process = async () => {
    if (!input.trim()) return;
    const summary = `operation:${operation},type:${seqType},frame:${frame}`;
    setRunning(true);
    setError(null);
    setResult(null);
    audit.emitStarted('sequence_utility', 'Validated sequence backend', summary);
    try {
      const response = await longApi.post('/api/seq-tools/operate', {
        sequence: input,
        seq_type: seqType,
        operation,
        frame,
        stop_at_stop: stopAtStop,
        require_start: requireStart,
        require_terminal_stop: requireTerminalStop,
        min_orf_aa: minOrfAa,
        fasta_name: fastaName,
        fasta_width: 60,
      });
      if (!isScientificResult(response.data)) throw new Error('Backend did not emit a valid ScientificResult');
      const scientific = response.data as ScientificResult<OperationResults>;
      setResult(scientific);
      audit.emitSuccess('sequence_utility', 'Validated sequence backend', summary, scientific.output_sha256);
    } catch (cause: unknown) {
      const axiosLike = cause as { response?: { data?: { detail?: string } }; message?: string };
      const message = axiosLike.response?.data?.detail || axiosLike.message || 'Sequence operation failed';
      setError(message);
      audit.emitFailed('sequence_utility', 'Validated sequence backend', summary, message);
    } finally {
      setRunning(false);
    }
  };

  const copy = async () => {
    if (!output) return;
    await navigator.clipboard.writeText(output);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="max-w-4xl">
      <BackButton />
      <PageHeader
        title="Utility Tools"
        subtitle="All scientific sequence operations execute in the same validated backend used by Sequence Utilities. No browser-side sequence biology is performed."
      />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card mb-6 space-y-5 p-5">
        <div className="flex flex-wrap gap-2">
          {TOOLS.map((tool) => (
            <button
              key={tool.id}
              onClick={() => { setOperation(tool.id); setResult(null); setError(null); }}
              className={`rounded-lg border px-3 py-2 text-xs transition ${operation === tool.id ? 'border-accent-cyan/40 bg-accent-cyan/10 text-accent-cyan' : 'border-glass-border bg-surface-1 text-text-secondary hover:text-text-primary'}`}
            >
              {tool.label}
            </button>
          ))}
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <label className="text-xs text-text-muted">
            Sequence type
            <select value={seqType} onChange={(event) => setSeqType(event.target.value as typeof seqType)} className="mt-1 w-full rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-sm text-text-primary">
              <option value="auto">Auto detect</option>
              <option value="dna">DNA</option>
              <option value="rna">RNA</option>
              <option value="protein">Protein</option>
            </select>
          </label>
          {showFrame && (
            <label className="text-xs text-text-muted">
              Frame
              <select value={frame} onChange={(event) => setFrame(Number(event.target.value))} className="mt-1 w-full rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-sm text-text-primary">
                {[1, 2, 3, -1, -2, -3].map((value) => <option key={value} value={value}>{value > 0 ? `+${value}` : value}</option>)}
              </select>
            </label>
          )}
          {operation === 'find_orfs' && (
            <label className="text-xs text-text-muted">
              Minimum ORF length (aa)
              <input type="number" min={1} value={minOrfAa} onChange={(event) => setMinOrfAa(Math.max(1, Number(event.target.value) || 1))} className="mt-1 w-full rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-sm text-text-primary" />
            </label>
          )}
          {operation === 'fasta' && (
            <label className="text-xs text-text-muted">
              FASTA name
              <input value={fastaName} onChange={(event) => setFastaName(event.target.value)} className="mt-1 w-full rounded-lg border border-glass-border bg-surface-1 px-3 py-2 text-sm text-text-primary" />
            </label>
          )}
        </div>

        {operation === 'translate_frame' && (
          <label className="flex items-center gap-2 text-xs text-text-secondary">
            <input type="checkbox" checked={stopAtStop} onChange={(event) => setStopAtStop(event.target.checked)} />
            Stop translation at the first stop codon
          </label>
        )}
        {operation === 'translate_cds' && (
          <div className="flex flex-wrap gap-5 text-xs text-text-secondary">
            <label className="flex items-center gap-2"><input type="checkbox" checked={requireStart} onChange={(event) => setRequireStart(event.target.checked)} /> Require start codon in selected frame</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={requireTerminalStop} onChange={(event) => setRequireTerminalStop(event.target.checked)} /> Require terminal stop</label>
          </div>
        )}

        <FlatTextarea value={input} onChange={(event) => { setInput(event.target.value); setResult(null); setError(null); }} placeholder="Paste a raw sequence or FASTA…" className="h-40 w-full font-mono text-sm" />

        <div className="flex items-center gap-3">
          <button onClick={() => { setInput(SAMPLE_CDS); setSeqType('dna'); setResult(null); }} className="text-xs text-accent-cyan hover:underline">Load sample CDS</button>
          <div className="flex-1" />
          <CriticalButton onClick={process} disabled={running || !input.trim()}>
            <Flask className="h-4 w-4" /> {running ? 'Running…' : 'Run backend operation'}
          </CriticalButton>
        </div>
      </motion.div>

      {error && (
        <div className="mb-6 flex gap-2 rounded-xl border border-error/25 bg-error/5 p-4 text-sm text-error">
          <WarningIcon className="mt-0.5 h-4 w-4 flex-none" />
          <span>{error}</span>
        </div>
      )}

      {result && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-4">
          <div className="data-card p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-text-primary">{result.method}</p>
                <p className="text-xs text-text-muted">{result.engine} · {result.engine_version} · {result.status}</p>
              </div>
              <button onClick={copy} className="flex items-center gap-1.5 text-xs text-accent-cyan hover:underline">
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                {copied ? 'Copied' : 'Copy result'}
              </button>
            </div>
            <pre className="max-h-[34rem] overflow-auto whitespace-pre-wrap break-words rounded-xl bg-surface-0 p-4 font-mono text-xs text-text-secondary">{output}</pre>
          </div>

          <div className="data-card grid gap-3 p-5 text-xs md:grid-cols-2">
            <div><p className="text-text-muted">Input SHA-256</p><p className="break-all font-mono text-text-secondary">{result.input_sha256}</p></div>
            <div><p className="text-text-muted">Output SHA-256</p><p className="break-all font-mono text-text-secondary">{result.output_sha256}</p></div>
          </div>
        </motion.div>
      )}
    </div>
  );
}

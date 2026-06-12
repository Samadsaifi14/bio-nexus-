'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Dna, Search, ChevronRight, Loader2, AlertCircle, CheckCircle } from 'lucide-react';
import toast from 'react-hot-toast';
import { runPipeline, fetchSequence, validateSequence } from '@/lib/api';
import type { SequenceResult, SequenceValidation, SequenceType } from '@/types/pipeline';

const SAMPLES = [
  {
    label: 'p53 (human)',
    seq: `>sp|P04637|P53_HUMAN Cellular tumor antigen p53
MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGP
DEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYPQGLNGTVNLPGRNSFEV
RVCACPHERCTEGRAVKLFSPKELNCEMAQDIINNKFNLNLLPETIPNTIICFVESQPPQGD
SVTTCFSWRGEGNEMYLHTEKEYKALKSTLSEKYMATCLLLSPKKKSLFPEALKLCNQKYS
EEFLLLDEALLSGCFAELACALHLAPAEGRYSGGFNHELYNMMTQQQQHQHHLQMQQHHQQ
HHQQHHQQHHQQQQQQQQQQQQQQQQQH`,
  },
  {
    label: 'Insulin (human)',
    seq: `>sp|P01308|INS_HUMAN Insulin
MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKTRREAED
LQVGQVELGGGPGAGSLQPLALEGSLQKRGIVEQCCTSICSLYQLENYCN`,
  },
];

function detectSequenceType(seq: string): SequenceType {
  const clean = seq.replace(/[^A-Za-z]/g, '').toUpperCase();
  if (!clean) return 'unknown';
  const protein = new Set('ACDEFGHIKLMNPQRSTVWY');
  const extra = new Set(clean.split('').filter(c => !protein.has(c)));
  if (extra.size === 0) return 'protein';
  if (extra.size === 1 && (extra.has('N') || extra.has('B') || extra.has('Z') || extra.has('X'))) return 'protein';
  return 'dna';
}

export default function BlastWizardPage() {
  const router = useRouter();
  const [step, setStep] = useState<2 | 3>(2);
  const [inputMode, setInputMode] = useState<'paste' | 'accession'>('paste');
  const [rawInput, setRawInput] = useState('');
  const [detectedType, setDetectedType] = useState<SequenceType | null>(null);
  const [aaCount, setAaCount] = useState(0);
  const [accessionResult, setAccessionResult] = useState<SequenceResult | null>(null);
  const [accessionLoading, setAccessionLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [advancedDb, setAdvancedDb] = useState('nr');
  const [advancedProgram, setAdvancedProgram] = useState('');

  useEffect(() => {
    if (inputMode === 'paste') {
      const clean = rawInput.split('\n').filter(l => !l.startsWith('>')).join('');
      const alpha = clean.replace(/[^A-Za-z]/g, '');
      setAaCount(alpha.length);
      if (alpha.length > 0) setDetectedType(detectSequenceType(alpha));
    }
  }, [rawInput, inputMode]);

  const handleFetchAccession = async () => {
    if (!rawInput.trim()) return;
    setAccessionLoading(true);
    setAccessionResult(null);
    try {
      const res = await fetchSequence(rawInput.trim());
      if (res.error) {
        toast.error(res.error);
      } else {
        setAccessionResult(res);
        setDetectedType(res.sequence_type);
        toast.success('Sequence retrieved');
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to fetch sequence');
    } finally {
      setAccessionLoading(false);
    }
  };

  const handleSubmit = async () => {
    let seq = '';
    if (inputMode === 'paste') {
      seq = rawInput;
    } else if (accessionResult) {
      seq = `>${accessionResult.accession}\n${accessionResult.sequence}`;
    }

    if (!seq.trim()) {
      toast.error('Enter or fetch a sequence first');
      return;
    }

    const clean = seq.replace(/[^A-Za-z]/g, '');
    if (clean.length < 6) {
      toast.error('Sequence must be at least 6 amino acids');
      return;
    }

    const invalid = clean.split('').filter(c => !'ACDEFGHIKLMNPQRSTVWY'.includes(c.toUpperCase()));
    if (invalid.length > 0) {
      const unique = Array.from(new Set(invalid.map(c => c.toUpperCase())));
      toast.error(`Invalid character(s) in sequence: ${unique.join(', ')}`);
      return;
    }

    if (clean.length > 10000) {
      toast.error('Sequence too long (max 10,000 residues for BLAST)');
      return;
    }

    setSubmitting(true);
    try {
      const result = await runPipeline(seq, 'blast', advancedDb || 'nr', 100);
      router.push(`/jobs/${result.job_id}`);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 429) {
        toast.error(
          typeof detail === 'object'
            ? detail.message || 'Daily limit reached. Resets at midnight.'
            : 'Daily limit reached. Resets at midnight.',
        );
      } else {
        toast.error(detail || 'Failed to start analysis');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const programLabel = detectedType === 'protein' ? 'blastp' : 'blastn';
  const dbLabel = detectedType === 'protein' ? 'nr' : 'nt';

  return (
    <div className="max-w-2xl">
      <button
        onClick={() => router.push('/analyze')}
        className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        Choose a different operation
      </button>

      <div className="flex items-center gap-3 mb-8">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center gap-3">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
              s < step ? 'bg-teal-500 text-white' : s === step ? 'bg-teal-500 text-white' : 'bg-gray-100 text-gray-400'
            }`}>
              {s < step ? '✓' : s}
            </div>
            <span className={`text-sm ${s === step ? 'font-medium text-gray-900' : 'text-gray-400'}`}>
              {s === 1 ? 'Choose' : s === 2 ? 'Input' : 'Confirm'}
            </span>
            {s < 3 && <ChevronRight className="w-4 h-4 text-gray-300" />}
          </div>
        ))}
      </div>

      {step === 2 && (
        <div className="space-y-6">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-1">Enter your sequence</h2>
            <p className="text-sm text-gray-500">
              Paste a protein or DNA sequence, or fetch it by accession number.
            </p>
          </div>

          <div className="flex gap-2">
            {([
              { id: 'paste' as const, label: 'Paste Sequence' },
              { id: 'accession' as const, label: 'Fetch by Accession' },
            ]).map((tab) => (
              <button
                key={tab.id}
                onClick={() => { setInputMode(tab.id); setAccessionResult(null); }}
                className={`px-4 py-2 text-sm font-medium rounded-lg transition ${
                  inputMode === tab.id ? 'bg-teal-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {inputMode === 'paste' ? (
            <div className="bg-white rounded-2xl border border-gray-200 p-5">
              <textarea
                value={rawInput}
                onChange={(e) => setRawInput(e.target.value)}
                placeholder="Paste a FASTA or raw sequence here..."
                className="w-full h-40 px-4 py-3 rounded-xl border border-gray-300 focus:border-teal-500 focus:ring-2 focus:ring-teal-200 outline-none transition font-mono text-sm text-gray-900 resize-none"
              />
              <div className="flex items-center justify-between mt-4">
                <div className="flex items-center gap-3">
                  {SAMPLES.map((s) => (
                    <button
                      key={s.label}
                      type="button"
                      onClick={() => setRawInput(s.seq)}
                      className="text-sm text-teal-600 hover:text-teal-700 underline"
                    >
                      Load {s.label}
                    </button>
                  ))}
                </div>
                {detectedType && (
                  <div className="flex items-center gap-2">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                      detectedType === 'protein'
                        ? 'text-blue-600 bg-blue-50'
                        : 'text-purple-600 bg-purple-50'
                    }`}>
                      {detectedType}
                    </span>
                    <span className="text-xs text-gray-400">{aaCount} aa</span>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-gray-200 p-5 space-y-4">
              <div className="flex gap-3">
                <input
                  type="text"
                  value={rawInput}
                  onChange={(e) => setRawInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleFetchAccession()}
                  placeholder="e.g. NP_000509.1, P04637, 1TIM"
                  className="flex-1 px-4 py-3 rounded-xl border border-gray-300 focus:border-teal-500 focus:ring-2 focus:ring-teal-200 outline-none transition text-sm font-mono"
                />
                <button
                  onClick={handleFetchAccession}
                  disabled={accessionLoading || !rawInput.trim()}
                  className="px-5 py-3 bg-teal-600 text-white font-medium rounded-xl hover:bg-teal-700 transition disabled:opacity-50 flex items-center gap-2"
                >
                  {accessionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                  Fetch
                </button>
              </div>

              {accessionResult && (
                <div className="p-4 bg-teal-50 border border-teal-200 rounded-xl">
                  <div className="flex items-center gap-2 mb-2">
                    <CheckCircle className="w-4 h-4 text-teal-600" />
                    <code className="text-sm font-mono font-semibold text-teal-800">{accessionResult.accession}</code>
                    <span className="text-xs bg-teal-200 text-teal-700 px-2 py-0.5 rounded-full">{accessionResult.sequence_type}</span>
                  </div>
                  <p className="text-sm text-teal-700">{accessionResult.description}</p>
                  <p className="text-xs text-teal-600 mt-1">{accessionResult.organism} · {accessionResult.length} residues</p>
                </div>
              )}
            </div>
          )}

          <div className="border-t border-gray-200 pt-4">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              {showAdvanced ? 'Hide' : 'Show'} advanced settings
            </button>
            {showAdvanced && (
              <div className="mt-3 grid grid-cols-2 gap-4 p-4 bg-gray-50 rounded-xl">
                <div>
                  <label className="text-xs font-medium text-gray-500 block mb-1">Database</label>
                  <select
                    value={advancedDb}
                    onChange={(e) => setAdvancedDb(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm"
                  >
                    <option value="nr">nr (non-redundant)</option>
                    <option value="swissprot">Swiss-Prot</option>
                    <option value="pdbaa">PDB</option>
                    <option value="refseq_protein">RefSeq</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500 block mb-1">Program</label>
                  <select
                    value={advancedProgram || programLabel}
                    onChange={(e) => setAdvancedProgram(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm"
                  >
                    <option value="blastp">blastp</option>
                    <option value="blastn">blastn</option>
                    <option value="blastx">blastx</option>
                  </select>
                </div>
              </div>
            )}
          </div>

          <div className="flex justify-end">
            <button
              onClick={() => setStep(3)}
              disabled={
                (inputMode === 'paste' && !rawInput.trim()) ||
                (inputMode === 'accession' && !accessionResult)
              }
              className="px-6 py-3 bg-teal-600 text-white font-medium rounded-xl hover:bg-teal-700 transition disabled:opacity-50 flex items-center gap-2"
            >
              Continue
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-6">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-1">Confirm and run</h2>
            <p className="text-sm text-gray-500">Review your analysis settings before submitting.</p>
          </div>

          <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-4">
            <div className="flex items-center gap-3 pb-4 border-b border-gray-100">
              <Search className="w-5 h-5 text-teal-600" />
              <div>
                <p className="font-medium text-gray-900">BLAST Search</p>
                <p className="text-sm text-gray-500">
                  We'll run a <strong>{advancedProgram || programLabel}</strong> search of your{' '}
                  <strong>{aaCount || accessionResult?.length}</strong>-{detectedType === 'protein' ? 'aa' : 'bp'}{' '}
                  {detectedType} against the <strong>{advancedDb || dbLabel}</strong> database.
                </p>
              </div>
            </div>

            {inputMode === 'paste' ? (
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Sequence</p>
                <pre className="font-mono text-xs text-gray-700 bg-gray-50 rounded-xl p-4 max-h-24 overflow-auto whitespace-pre-wrap break-all">
                  {rawInput.slice(0, 300)}{rawInput.length > 300 ? '...' : ''}
                </pre>
              </div>
            ) : accessionResult && (
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Sequence</p>
                <div className="p-4 bg-gray-50 rounded-xl">
                  <code className="text-sm font-mono text-teal-700">{accessionResult.accession}</code>
                  <p className="text-sm text-gray-700 mt-1">{accessionResult.description}</p>
                  <p className="text-xs text-gray-500 mt-1">{accessionResult.organism} · {accessionResult.length} residues</p>
                </div>
              </div>
            )}

            <div className="pt-2 text-xs text-gray-500">
              <p>BLAST searches against NCBI nr typically take 30s–5min. Your results will be saved and you can return to them later.</p>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <button
              onClick={() => setStep(2)}
              className="text-sm text-gray-500 hover:text-gray-700 underline"
            >
              &larr; Change input
            </button>
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="px-8 py-3 bg-teal-600 text-white font-medium rounded-xl hover:bg-teal-700 transition disabled:opacity-50 flex items-center gap-2"
            >
              {submitting ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Submitting...</>
              ) : (
                'Run Analysis'
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

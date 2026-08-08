'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { CircleNotch as LoaderCircle } from '@phosphor-icons/react';
import { fadeUp } from '@/lib/animations';
import { fetchMotifPatterns, scanMotifLibrary, scanMotifPattern } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import { BackButton, CriticalButton, ClaySegmented, FlatTextarea, PageHeader } from '@/components/ui';
import { MotifTrack, MatchTable } from '@/components/motifs/MotifTrack';
import type { MotifLibraryPattern, MotifLibraryResult, MotifPatternScanResult } from '@/types/pipeline';

type Mode = 'library' | 'custom';

const SAMPLE = '>kinase\nMKDYQNSTLPVARKTGHMRKNGGGGGPMNSSTLDEIYGKPPASDVAVCGHWMQEVDVCVGVIGRSGYGFRLGFLHSGTAKSVTCTYSPALNKMFCQLAKTCPVQLWVDSTPPPGTRVRAMAIYKQSQHMTEVVRRCPHHERCSDSDGLAPPQHLIRVEGNLRVEYLDDRNTFRHSVVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRNSFEVRVCACPGRDRRTEEENLRKKGEPHHELPPGSTKRALPNNTSSSPQPKKKPLDGEYFTLQIRGRERFEMFRELNEALELKDAQAGKEPGGSRAHSSHLKSKKGQSTSRHKKLMFKTEGPDSD';

function cleanLength(seq: string): number {
  return seq.replace(/[^A-Za-z]/g, '').length;
}

export default function MotifScannerPage() {
  const [sequence, setSequence] = useState('');
  const [mode, setMode] = useState<Mode>('library');
  const [patterns, setPatterns] = useState<MotifLibraryPattern[]>([]);
  const [customPattern, setCustomPattern] = useState('N-{P}-[ST]-{P}');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MotifLibraryResult | null>(null);
  const [patternResult, setPatternResult] = useState<MotifPatternScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const audit = useAuditTrail();

  useEffect(() => {
    fetchMotifPatterns().then(setPatterns).catch(() => {});
  }, []);

  const canRun = cleanLength(sequence) >= 1 && !loading;

  const handleRun = async () => {
    if (!canRun) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setPatternResult(null);
    const summary = `len:${cleanLength(sequence)},mode:${mode}`;
    audit.emitStarted('motif_scanner', 'Motif Scanner', summary);
    try {
      if (mode === 'library') {
        const res = await scanMotifLibrary(sequence);
        setResult(res);
        audit.emitSuccess('motif_scanner', 'Motif Scanner', summary, `motifs:${res.motifs_found}`);
      } else {
        const res = await scanMotifPattern({ sequence, pattern: customPattern });
        setPatternResult(res);
        audit.emitSuccess('motif_scanner', 'Motif Scanner', summary, `matches:${res.count}`);
      }
    } catch (err: unknown) {
      const errMsg = extractErrorMessage(err, 'Motif scan failed');
      setError(errMsg);
      audit.emitFailed('motif_scanner', 'Motif Scanner', summary, errMsg);
    } finally {
      setLoading(false);
    }
  };

  const seqLen = cleanLength(sequence);

  return (
    <div className="max-w-3xl">
      <BackButton />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show">
        <PageHeader
          title="Motif Scanner"
          subtitle="Find short functional motifs in a protein — scan against a curated library of well-known patterns (glycosylation, phosphorylation, zinc fingers, P-loop...) or enter your own PROSITE pattern."
        />
      </motion.div>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-6">
        <div className="data-card p-5 space-y-4">
          <FlatTextarea
            value={sequence}
            onChange={e => setSequence(e.target.value)}
            placeholder="Paste a protein sequence (raw or FASTA)..."
            className="w-full h-36 text-sm"
          />
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <ClaySegmented
              options={[
                { value: 'library', label: 'Curated library' },
                { value: 'custom', label: 'Custom pattern' },
              ]}
              value={mode}
              onChange={setMode}
              size="sm"
            />
            <button
              onClick={() => setSequence(SAMPLE)}
              className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition"
            >
              Load sample protein
            </button>
          </div>

          {mode === 'custom' && (
            <div>
              <label className="block text-[10px] uppercase tracking-wider text-text-muted mb-1.5">
                PROSITE pattern
              </label>
              <div className="flex items-center gap-2">
                <input
                  value={customPattern}
                  onChange={e => setCustomPattern(e.target.value)}
                  placeholder="e.g. N-{P}-[ST]-{P}, [ST]-x-[RK], x(2,4)"
                  className="input-flat font-mono text-sm flex-1"
                />
                <div className="hidden md:block max-w-56">
                  {patterns.length > 0 && (
                    <select
                      onChange={e => { if (e.target.value) setCustomPattern(e.target.value); }}
                      value=""
                      className="input-flat text-xs w-full"
                      aria-label="Choose a preset pattern"
                    >
                      <option value="">Presets…</option>
                      {patterns.map(p => (
                        <option key={p.name} value={p.pattern}>{p.name}</option>
                      ))}
                    </select>
                  )}
                </div>
              </div>
              <p className="mt-1.5 text-[11px] text-text-muted">
                Syntax: <code className="font-mono text-accent-cyan">-</code> separator,{' '}
                <code className="font-mono text-accent-cyan">x</code> any residue,{' '}
                <code className="font-mono text-accent-cyan">[ST]</code> one of,{' '}
                <code className="font-mono text-accent-cyan">{'{ED}'}</code> none of,{' '}
                <code className="font-mono text-accent-cyan">x(2,4)</code> repeats,{' '}
                <code className="font-mono text-accent-cyan">&lt;</code>/<code className="font-mono text-accent-cyan">&gt;</code> anchors.
              </p>
            </div>
          )}
        </div>

        <div className="flex justify-end">
          <CriticalButton onClick={handleRun} disabled={!canRun}>
            {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : null}
            {loading ? 'Scanning...' : mode === 'library' ? 'Scan library' : 'Scan pattern'}
          </CriticalButton>
        </div>

        {error && (
          <div className="rounded-lg bg-error/10 border border-error/30 px-4 py-3 text-sm text-error">
            <strong>Scan failed:</strong> {error}
          </div>
        )}

        {patternResult && !loading && (
          <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-4 mt-8">
            <div className="data-card p-5">
              <div className="flex items-center gap-3 mb-1 flex-wrap">
                <h3 className="text-sm font-semibold text-text-primary">Pattern matches</h3>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-cyan/10 border border-accent-cyan/30 text-accent-cyan font-medium">
                  {patternResult.count} hits
                </span>
                <code className="text-xs font-mono text-text-muted ml-auto">{patternResult.pattern}</code>
              </div>
              <p className="text-[11px] font-mono text-text-muted mb-3">regex: {patternResult.regex}</p>
              {patternResult.count === 0 ? (
                <p className="text-sm text-text-muted">No matches found for this pattern.</p>
              ) : (
                <>
                  <MotifTrack
                    length={seqLen}
                    tracks={[{ name: 'Pattern', matches: patternResult.matches }]}
                  />
                  <div className="mt-3">
                    <MatchTable matches={patternResult.matches} />
                  </div>
                </>
              )}
            </div>
          </motion.div>
        )}

        {result && !loading && (
          <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-4 mt-8">
            <div className="data-card p-5">
              <div className="flex items-center gap-3 mb-1 flex-wrap">
                <h3 className="text-sm font-semibold text-text-primary">Motif library scan</h3>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-purple/10 border border-accent-purple/30 text-accent-purple font-medium">
                  {result.motifs_found} motifs · {result.patterns_scanned} patterns
                </span>
              </div>
              <p className="text-xs text-text-muted mb-3">
                {result.length} residues · {result.sequence_type} sequence
              </p>

              {result.motifs_found === 0 ? (
                <p className="text-sm text-text-muted">No known motifs found in this sequence.</p>
              ) : (
                <div className="space-y-5">
                  <MotifTrack
                    length={result.length}
                    tracks={result.hits.map(h => ({ name: h.name, matches: h.matches }))}
                  />
                  {result.hits.map(hit => (
                    <div key={hit.name} className="rounded-lg bg-surface-0 border border-glass-border p-4">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <h4 className="text-sm font-semibold text-accent-purple">{hit.name}</h4>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-1 border border-glass-border text-text-muted font-medium">
                          {hit.count}×
                        </span>
                        <code className="text-[11px] font-mono text-text-muted ml-auto">{hit.pattern}</code>
                      </div>
                      <p className="text-[11px] text-text-muted mb-2">{hit.description}</p>
                      <MatchTable matches={hit.matches} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}

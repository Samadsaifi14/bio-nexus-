'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import {
  CircleNotch as LoaderCircle,
  DownloadSimple as Download,
  MagnifyingGlass as Search,
  X as Close,
  Atom,
  ArrowsLeftRight as ArrowSwap,
  ChartScatter as Scatter,
} from '@phosphor-icons/react';
import { fadeUp } from '@/lib/animations';
import { fetchMotifCategories, fetchMotifPatterns, fetchSequence, scanMotifLibrary, scanMotifPattern } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import { downloadText, downloadTsv } from '@/lib/export-utils';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import { BackButton, CriticalButton, ClaySegmented, FlatTextarea, PageHeader } from '@/components/ui';
import { setPrefill } from '@/lib/cross-link';
import { MotifTrack, MatchTable, SequenceHighlight, TRACK_COLORS } from '@/components/motifs/MotifTrack';
import type { MotifLibraryHit, MotifLibraryPattern, MotifLibraryResult, MotifPatternScanResult } from '@/types/pipeline';

type Mode = 'library' | 'custom';

const SAMPLE = '>kinase\nMKDYQNSTLPVARKTGHMRKNGGGGGPMNSSTLDEIYGKPPASDVAVCGHWMQEVDVCVGVIGRSGYGFRLGFLHSGTAKSVTCTYSPALNKMFCQLAKTCPVQLWVDSTPPPGTRVRAMAIYKQSQHMTEVVRRCPHHERCSDSDGLAPPQHLIRVEGNLRVEYLDDRNTFRHSVVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRNSFEVRVCACPGRDRRTEEENLRKKGEPHHELPPGSTKRALPNNTSSSPQPKKKPLDGEYFTLQIRGRERFEMFRELNEALELKDAQAGKEPGGSRAHSSHLKSKKGQSTSRHKKLMFKTEGPDSD';

function cleanLength(seq: string): number {
  return seq.replace(/[^A-Za-z]/g, '').length;
}

/** Best-effort UniProt/RefSeq accession from a FASTA header or bare id. */
function extractAccession(seq: string): string | null {
  const trimmed = seq.trim();
  if (!trimmed) return null;
  const firstLine = trimmed.split('\n')[0].trim();
  const re = /[OPQ][0-9][A-Z0-9]{3}[0-9](?:\.[0-9]+)?|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2}(?:\.[0-9]+)?/;
  if (firstLine.startsWith('>')) {
    const m = firstLine.match(re);
    return m ? m[0].split('.')[0] : null;
  }
  // Bare identifier line (no ">"): only trust it when the whole line is the accession.
  const m = firstLine.match(re);
  if (m && m[0] === firstLine && firstLine.length <= 15) {
    return m[0].split('.')[0];
  }
  return null;
}

const SCORING_HINT: Record<string, { color: string; label: string }> = {
  high: { color: 'text-accent-cyan', label: 'High specificity' },
  loose: { color: 'text-accent-amber', label: 'Loose consensus' },
};

function HitExportButtons({ hit, sequence }: { hit: MotifLibraryHit; sequence: string }) {
  const rows = hit.matches.map(m => [
    hit.name, hit.accession, hit.category, hit.specificity,
    String(m.start), String(m.end), m.motif,
  ]);
  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => downloadTsv(
          ['Pattern', 'Accession', 'Category', 'Specificity', 'Start', 'End', 'Match'],
          rows,
          `motif-${hit.name.replace(/\s+/g, '-').toLowerCase()}.tsv`,
        )}
        className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition-colors flex items-center gap-1.5"
      >
        <Download className="w-3.5 h-3.5" /> CSV
      </button>
      <button
        onClick={() => downloadText(
          JSON.stringify({ hit, sequence_length: sequence.length }, null, 2),
          `motif-${hit.name.replace(/\s+/g, '-').toLowerCase()}.json`,
        )}
        className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition-colors flex items-center gap-1.5"
      >
        <Download className="w-3.5 h-3.5" /> JSON
      </button>
    </div>
  );
}

function SpecificityBadge({ specificity }: { specificity: 'high' | 'loose' }) {
  const hint = SCORING_HINT[specificity];
  return (
    <span
      className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${
        specificity === 'high'
          ? 'bg-accent-cyan/10 border-accent-cyan/30 text-accent-cyan'
          : 'bg-accent-amber/10 border-accent-amber/30 text-accent-amber'
      }`}
      title={hint.label}
    >
      {specificity === 'high' ? 'High specificity' : 'Loose'}
    </span>
  );
}

export default function MotifScannerPage() {
  const router = useRouter();
  const [sequence, setSequence] = useState('');
  const [mode, setMode] = useState<Mode>('library');
  const [patterns, setPatterns] = useState<MotifLibraryPattern[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [customPattern, setCustomPattern] = useState('N-{P}-[ST]-{P}');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MotifLibraryResult | null>(null);
  const [patternResult, setPatternResult] = useState<MotifPatternScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [accession, setAccession] = useState<string | null>(null);
  const [accessionQuery, setAccessionQuery] = useState('');
  const [accessionLoading, setAccessionLoading] = useState(false);
  const [accessionError, setAccessionError] = useState<string | null>(null);
  const audit = useAuditTrail();

  useEffect(() => {
    fetchMotifPatterns().then(setPatterns).catch(() => {});
    fetchMotifCategories().then(setCategories).catch(() => {});
  }, []);

  // Prefill the sequence / accession from a deep link
  // (e.g. "scan for motifs" on a BLAST hit carries ?sequence=...&uniprot=...).
  useEffect(() => {
    const params = new URLSearchParams(globalThis.location?.search ?? '');
    const seqParam = params.get('sequence');
    const accParam = params.get('uniprot');
    if (seqParam) setSequence(seqParam);
    if (accParam) {
      const clean = accParam.trim().split('.')[0];
      if (extractAccession(`>${clean}`)) {
        setAccession(clean);
      } else {
        // Non-UniProt identifier (e.g. a RefSeq id) — best-effort resolve.
        fetchSequence(clean, 'uniprot')
          .then(res => {
            if (res.sequence && res.accession) setAccession(res.accession.split('.')[0]);
          })
          .catch(() => {});
      }
    }
  }, []);

  // Extract an accession from a pasted FASTA header so "highlight on
  // structure" works without a separate lookup.
  useEffect(() => {
    if (!sequence.trim()) return;
    if (!accession) setAccession(extractAccession(sequence));
  }, [sequence, accession]);

  const handleAccessionSearch = async () => {
    const acc = accessionQuery.trim();
    if (!acc) return;
    setAccessionLoading(true);
    setAccessionError(null);
    try {
      const res = await fetchSequence(acc, 'uniprot');
      setSequence(res.sequence);
      setAccession(res.accession || acc);
      setAccessionQuery('');
    } catch (err: unknown) {
      setAccessionError(extractErrorMessage(err, `Could not fetch ${acc}`));
    } finally {
      setAccessionLoading(false);
    }
  };

  const toggleCategory = (cat: string) => {
    setSelectedCategories(prev =>
      prev.includes(cat) ? prev.filter(c => c !== cat) : [...prev, cat],
    );
  };

  const canRun = cleanLength(sequence) >= 1 && !loading;

  const handleRun = async () => {
    if (!canRun) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setPatternResult(null);
    const summary = `len:${cleanLength(sequence)},mode:${mode}${selectedCategories.length ? `,cats:${selectedCategories.join('|')}` : ''}`;
    audit.emitStarted('motif_scanner', 'Motif Scanner', summary);
    try {
      if (mode === 'library') {
        const res = await scanMotifLibrary(sequence, selectedCategories.length ? selectedCategories : undefined);
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

  const openOnStructure = useCallback(
    (hit: MotifLibraryHit) => {
      if (!accession || hit.matches.length === 0) return;
      const first = hit.matches[0];
      router.push(`/analyze/structure?uniprot=${encodeURIComponent(accession)}&highlight=${first.start}-${first.end}`);
    },
    [accession, router],
  );

  const goBlast = () => {
    setPrefill(router, 'blast_sequence', sequence, '/analyze/blast');
  };

  const goPairwise = () => {
    setPrefill(router, 'pairwise_sequence_a', sequence, '/analyze/pairwise');
  };

  const goDotPlot = () => {
    router.push(`/analyze/dotplot?seq_a=${encodeURIComponent(sequence.replace(/[^A-Za-z]/g, '').toUpperCase())}&self=1`);
  };

  const groupedPresets = useMemo(() => {
    const groups = new Map<string, MotifLibraryPattern[]>();
    for (const p of patterns) {
      const list = groups.get(p.category) ?? [];
      list.push(p);
      groups.set(p.category, list);
    }
    return Array.from(groups.entries());
  }, [patterns]);

  return (
    <div className="max-w-3xl">
      <BackButton />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show">
        <PageHeader
          title="Motif Scanner"
          subtitle="Find short functional motifs in a protein — scan against a curated library of well-known patterns (glycosylation, phosphorylation, zinc fingers, P-loop...) or enter your own PROSITE pattern. Results can be highlighted directly on the AlphaFold structure."
        />
      </motion.div>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-6">
        {/* Start-from-accession search (same retrieval step as BLAST/UniProt) */}
        <div className="glass p-4 border border-glass-border">
          <div className="flex items-center gap-2">
            <Search className="w-4 h-4 text-text-muted shrink-0" />
            <input
              value={accessionQuery}
              onChange={e => { setAccessionQuery(e.target.value); setAccessionError(null); }}
              onKeyDown={e => e.key === 'Enter' && handleAccessionSearch()}
              placeholder="Start from a UniProt accession, e.g. P04637"
              className="input-flat text-sm flex-1"
            />
            <button
              onClick={handleAccessionSearch}
              disabled={accessionLoading || !accessionQuery.trim()}
              className="text-xs px-3 py-1.5 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition disabled:opacity-40 flex items-center gap-1.5"
            >
              {accessionLoading ? <LoaderCircle className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
              Fetch
            </button>
          </div>
          {accessionError && <p className="mt-2 text-xs text-error">{accessionError}</p>}
          {accession && (
            <div className="mt-2 flex items-center gap-2">
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-cyan/10 border border-accent-cyan/30 text-accent-cyan font-mono">
                {accession}
              </span>
              <button onClick={() => setAccession(null)} className="text-text-muted hover:text-text-primary" aria-label="Clear accession">
                <Close className="w-3 h-3" />
              </button>
            </div>
          )}
        </div>

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
                      {groupedPresets.map(([cat, list]) => (
                        <optgroup key={cat} label={cat}>
                          {list.map(p => (
                            <option key={p.name} value={p.pattern}>
                              {p.name} ({p.accession || 'consensus'})
                            </option>
                          ))}
                        </optgroup>
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

          {mode === 'library' && categories.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[10px] uppercase tracking-wider text-text-muted mr-1">Filter:</span>
              {categories.map(cat => (
                <button
                  key={cat}
                  onClick={() => toggleCategory(cat)}
                  aria-pressed={selectedCategories.includes(cat)}
                  className={`text-xs px-2.5 py-1 rounded-full border transition ${
                    selectedCategories.includes(cat)
                      ? 'bg-accent-purple/15 border-accent-purple/40 text-accent-purple'
                      : 'bg-surface-1 border-glass-border text-text-secondary hover:text-text-primary'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-end">
          <CriticalButton onClick={handleRun} disabled={!canRun}>
            {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : null}
            {loading ? 'Scanning...' : mode === 'library' ? 'Scan library' : 'Scan pattern'}
          </CriticalButton>
        </div>

        {canRun && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] uppercase tracking-wider text-text-muted mr-1">Continue in:</span>
            <button
              onClick={goBlast}
              className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded border border-glass-border bg-surface-1 text-text-secondary hover:text-accent-cyan transition"
            >
              <Search className="w-3.5 h-3.5" /> BLAST
            </button>
            <button
              onClick={goPairwise}
              className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded border border-glass-border bg-surface-1 text-text-secondary hover:text-accent-cyan transition"
            >
              <ArrowSwap className="w-3.5 h-3.5" /> Pairwise align
            </button>
            <button
              onClick={goDotPlot}
              className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded border border-glass-border bg-surface-1 text-text-secondary hover:text-accent-cyan transition"
            >
              <Scatter className="w-3.5 h-3.5" /> Dot plot
            </button>
          </div>
        )}

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
                  <div className="mb-3">
                    <SequenceHighlight
                      sequence={sequence.replace(/[^A-Za-z]/g, '').toUpperCase()}
                      tracks={[{ name: 'Pattern', matches: patternResult.matches }]}
                    />
                  </div>
                  <MotifTrack
                    length={seqLen}
                    tracks={[{ name: 'Pattern', matches: patternResult.matches }]}
                  />
                  <div className="mt-3 flex items-center gap-2">
                    <MatchTable matches={patternResult.matches} />
                    <div className="ml-auto flex items-center gap-2">
                      <button
                        onClick={() => downloadTsv(
                          ['Pattern', 'Start', 'End', 'Match'],
                          patternResult.matches.map(m => [patternResult.pattern, String(m.start), String(m.end), m.motif]),
                          'motif-scan.tsv',
                        )}
                        className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition-colors flex items-center gap-1.5"
                      >
                        <Download className="w-3.5 h-3.5" /> CSV
                      </button>
                      <button
                        onClick={() => downloadText(JSON.stringify(patternResult, null, 2), 'motif-scan.json')}
                        className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition-colors flex items-center gap-1.5"
                      >
                        <Download className="w-3.5 h-3.5" /> JSON
                      </button>
                    </div>
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
                {selectedCategories.length > 0 && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-1 border border-glass-border text-text-muted font-medium">
                    {selectedCategories.join(' + ')}
                  </span>
                )}
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
                  <div className="rounded-lg bg-surface-0 border border-glass-border p-4">
                    <h4 className="text-sm font-semibold text-text-primary mb-2">All hits on sequence</h4>
                    <SequenceHighlight
                      sequence={sequence.replace(/[^A-Za-z]/g, '').toUpperCase()}
                      tracks={result.hits}
                    />
                  </div>
                  {result.hits.map((hit, hi) => (
                    <div key={hit.name} className="rounded-lg bg-surface-0 border border-glass-border p-4">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: TRACK_COLORS[hi % TRACK_COLORS.length] }} />
                        <h4 className="text-sm font-semibold text-accent-purple">{hit.name}</h4>
                        <SpecificityBadge specificity={hit.specificity} />
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-1 border border-glass-border text-text-muted font-mono">
                          {hit.accession || 'consensus'}
                        </span>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-1 border border-glass-border text-text-muted font-medium">
                          {hit.category}
                        </span>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-1 border border-glass-border text-text-muted font-medium">
                          {hit.count}×
                        </span>
                        <code className="text-[11px] font-mono text-text-muted ml-auto">{hit.pattern}</code>
                      </div>
                      <p className="text-[11px] text-text-muted mb-2">{hit.description}</p>
                      <div className="flex items-start gap-3 flex-wrap">
                        <div className="flex-1 min-w-0">
                          <MatchTable matches={hit.matches} />
                        </div>
                        <div className="flex flex-col items-end gap-2 shrink-0">
                          <HitExportButtons hit={hit} sequence={sequence} />
                          {accession ? (
                            <button
                              onClick={() => openOnStructure(hit)}
                              className="text-xs px-2.5 py-1 rounded bg-accent-cyan/10 border border-accent-cyan/30 text-accent-cyan hover:bg-accent-cyan/20 transition-colors flex items-center gap-1.5"
                            >
                              <Atom className="w-3.5 h-3.5" /> Highlight on structure
                            </button>
                          ) : (
                            <span className="max-w-44 text-right text-[10px] text-text-muted">
                              Add a UniProt accession above to highlight these residues on the structure.
                            </span>
                          )}
                        </div>
                      </div>
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

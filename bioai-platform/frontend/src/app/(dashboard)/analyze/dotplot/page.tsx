'use client';

import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  CircleNotch as LoaderCircle,
  DownloadSimple as Download,
  MagnifyingGlass as Search,
} from '@phosphor-icons/react';
import {
  ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis, Tooltip,
  CartesianGrid, ReferenceLine, Brush,
} from 'recharts';
import { fadeUp } from '@/lib/animations';
import { fetchSequence, runDotPlot } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import { downloadText } from '@/lib/export-utils';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import { BackButton, CriticalButton, ClaySlider, ClayToggle, FlatTextarea, PageHeader } from '@/components/ui';
import type { DotPlotResult, DotPlotFeatures } from '@/types/pipeline';

const SCORING_OPTIONS = ['identity', 'blosum62', 'blosum50', 'blosum45', 'pam30', 'pam70', 'pam250'];

const LINE = {
  diagonal: 'rgba(168,85,247,0.55)',
  repeat: '#FBBF24',
  inverted: '#34D399',
};

const SAMPLE_A = '>p53_human\nMEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYQGSYGFRLGFLHSGTAKSVTCTYSPALNKMFCQLAKTCPVQLWVDSTPPPGTRVRAMAIYKQSQHMTEVVRRCPHHERCSDSDGLAPPQHLIRVEGNLRVEYLDDRNTFRHSVVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRNSFEVRVCACPGRDRRTEEENLRKKGEPHHELPPGSTKRALPNNTSSSPQPKKKPLDGEYFTLQIRGRERFEMFRELNEALELKDAQAGKEPGGSRAHSSHLKSKKGQSTSRHKKLMFKTEGPDSD';
const SAMPLE_B = '>p53_mouse\nMEEPQSDPSIEPPLSQETFSDLWKLLPENNVLSPLPSQAVDDLMLSPDDLAQWFTEDPGPDEAPRMSEAAPPAAPAPAAPTPAAPAPAPSWPLSSFVPSQKTYQGNYGFHLGFLQSGTAKSVMCTYSPPLNKLFCQLAKTCPVQLWVSATPPAGSRVRAMAIYKKSQHMTEVVRRCPHHERCSDSSDGLAPPQHLIRVEGNLRAEYLDDRNTFRHSIVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRDSFEVRVCACPGRDRRTEEENFKKKEPCPEPPPGSTRALGSTSTSSPTPKKKPLDGEYFTLKIRGRERFEMFRELNEALELKDAHATEEPFGGSRAHSSHLKSKKGQSTSRHKKFKKTADPSS';

function cleanLength(seq: string): number {
  return seq.replace(/[^A-Za-z]/g, '').length;
}

/** Boundary points of line y = x - offset clipped to the [0,W]x[0,H] rect. */
function diagSegment(offset: number, W: number, H: number): Array<[number, number]> {
  const pts: Array<[number, number]> = [];
  if (offset >= 0 && offset <= W) pts.push([offset, 0]);
  const xTop = H + offset;
  if (xTop >= 0 && xTop <= W) pts.push([xTop, H]);
  const yLeft = -offset;
  if (yLeft >= 0 && yLeft <= H) pts.push([0, yLeft]);
  const yRight = W - offset;
  if (yRight >= 0 && yRight <= H) pts.push([W, yRight]);
  return pts.slice(0, 2);
}

/** Boundary points of anti-diagonal line x + y = sum clipped to the rect. */
function antiSegment(sum: number, W: number, H: number): Array<[number, number]> {
  const pts: Array<[number, number]> = [];
  if (sum >= 0 && sum <= W) pts.push([sum, 0]);
  const xTop = sum - H;
  if (xTop >= 0 && xTop <= W) pts.push([xTop, H]);
  if (sum >= 0 && sum <= H) pts.push([0, sum]);
  const yRight = sum - W;
  if (yRight >= 0 && yRight <= H) pts.push([W, yRight]);
  return pts.slice(0, 2);
}

const tooltipStyle = {
  contentStyle: { background: 'var(--chart-tooltip-bg)', border: '1px solid var(--chart-tooltip-border)', borderRadius: 8, fontSize: 12 },
  labelStyle: { color: 'var(--chart-tooltip-label)' },
  itemStyle: { color: 'var(--chart-tooltip-item)' },
};

function FeatureChip({ label, value, tone = 'text-text-primary' }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex flex-col items-center px-3 py-2 rounded-lg bg-surface-0 border border-glass-border min-w-[84px]">
      <span className="text-[9px] uppercase tracking-wider text-text-muted">{label}</span>
      <span className={`text-sm font-bold font-mono mt-0.5 ${tone}`}>{value}</span>
    </div>
  );
}

export default function DotPlotPage() {
  const [seqA, setSeqA] = useState('');
  const [seqB, setSeqB] = useState('');
  const [selfCompare, setSelfCompare] = useState(false);
  const [window, setWindow] = useState(10);
  const [stringency, setStringency] = useState(80);
  const [scoring, setScoring] = useState('identity');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DotPlotResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [accA, setAccA] = useState('');
  const [accB, setAccB] = useState('');
  const [accLoading, setAccLoading] = useState<'A' | 'B' | null>(null);
  const [accError, setAccError] = useState<string | null>(null);
  const audit = useAuditTrail();

  // Deep-link support: /analyze/dotplot?seq_a=...&seq_b=...&self=1&scoring=...
  useEffect(() => {
    const params = new URLSearchParams(globalThis.location?.search ?? '');
    const a = params.get('seq_a');
    const b = params.get('seq_b');
    const score = params.get('scoring');
    const w = params.get('window');
    const s = params.get('stringency');
    if (a) setSeqA(decodeURIComponent(a));
    if (b) setSeqB(decodeURIComponent(b));
    if (params.get('self') === '1') setSelfCompare(true);
    if (score && SCORING_OPTIONS.includes(score)) setScoring(score);
    if (w && Number(w) >= 1 && Number(w) <= 50) setWindow(Number(w));
    if (s && Number(s) >= 40 && Number(s) <= 100) setStringency(Number(s));
  }, []);

  const effectiveB = selfCompare ? seqA : seqB;
  const canRun = cleanLength(seqA) >= 1 && cleanLength(effectiveB) >= 1 && !loading;

  const data = useMemo(
    () => (result ? result.dots.map(([y, x], i) => ({ x, y, idx: i })) : []),
    [result],
  );

  const handleAccessionSearch = async (target: 'A' | 'B') => {
    const acc = (target === 'A' ? accA : accB).trim();
    if (!acc) return;
    setAccLoading(target);
    setAccError(null);
    try {
      const res = await fetchSequence(acc, 'uniprot');
      if (target === 'A') { setSeqA(res.sequence); setAccA(''); }
      else { setSeqB(res.sequence); setAccB(''); }
      if (selfCompare) setSelfCompare(false);
    } catch (err: unknown) {
      setAccError(extractErrorMessage(err, `Could not fetch ${acc}`));
    } finally {
      setAccLoading(null);
    }
  };

  const handleRun = async () => {
    if (!canRun) return;
    setLoading(true);
    setError(null);
    setResult(null);
    const summary = `lenA:${cleanLength(seqA)},lenB:${cleanLength(effectiveB)},w:${window},s:${stringency},scoring:${scoring},self:${selfCompare}`;
    audit.emitStarted('dot_plot', 'Dot Plot', summary);
    try {
      const res = await runDotPlot({
        seq_a: seqA,
        seq_b: effectiveB,
        window,
        stringency,
        scoring,
      });
      setResult(res);
      audit.emitSuccess('dot_plot', 'Dot Plot', summary, `dots:${res.dot_count}`);
    } catch (err: unknown) {
      const errMsg = extractErrorMessage(err, 'Dot plot failed');
      setError(errMsg);
      audit.emitFailed('dot_plot', 'Dot Plot', summary, errMsg);
    } finally {
      setLoading(false);
    }
  };

  const toggleSelf = (value: boolean) => {
    setSelfCompare(value);
    if (value) setSeqB(seqA);
  };

  const exportPng = () => {
    if (!result) return;
    const W = 1000;
    const H = Math.max(400, Math.round((result.seq_a_length / result.seq_b_length) * W));
    const canvas = document.createElement('canvas');
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.fillStyle = '#0B0C14';
    ctx.fillRect(0, 0, W, H);
    const sx = W / result.seq_b_length;
    const sy = H / result.seq_a_length;
    ctx.fillStyle = 'rgba(34,211,238,0.55)';
    for (const [y, x] of result.dots) {
      ctx.fillRect(x * sx, H - (y + 1) * sy, Math.max(1, sx), Math.max(1, sy));
    }
    const a = document.createElement('a');
    a.download = `dotplot-${result.seq_a_length}x${result.seq_b_length}.png`;
    a.href = canvas.toDataURL('image/png');
    a.click();
  };

  const exportSvg = () => {
    if (!result) return;
    const W = result.seq_b_length;
    const H = result.seq_a_length;
    const dots = result.dots.slice(0, 20000)
      .map(([y, x]) => `<circle cx="${x}" cy="${H - y}" r="0.35" fill="#22D3EE" opacity="0.55"/>`)
      .join('');
    const svg =
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${Math.max(600, W * 2)}" height="${Math.max(600, H * 2)}">` +
      `<rect width="100%" height="100%" fill="#0B0C14"/>${dots}</svg>`;
    downloadText(svg, `dotplot-${result.seq_a_length}x${result.seq_b_length}.svg`);
  };

  const features: DotPlotFeatures | null = result?.features ?? null;
  const W = result?.seq_b_length ?? 0;
  const H = result?.seq_a_length ?? 0;
  const diagEnd = Math.min(W, H);

  const accessionInput = (target: 'A' | 'B') => (
    <div className="flex items-center gap-2">
      <Search className="w-3.5 h-3.5 text-text-muted shrink-0" />
      <input
        value={target === 'A' ? accA : accB}
        onChange={e => { if (target === 'A') setAccA(e.target.value); else setAccB(e.target.value); setAccError(null); }}
        onKeyDown={e => e.key === 'Enter' && handleAccessionSearch(target)}
        placeholder="or UniProt accession"
        className="input-flat text-xs flex-1"
      />
      <button
        onClick={() => handleAccessionSearch(target)}
        disabled={accLoading !== null || !(target === 'A' ? accA : accB).trim()}
        className="text-xs px-2 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition disabled:opacity-40"
      >
        {accLoading === target ? <LoaderCircle className="w-3 h-3 animate-spin" /> : 'Fetch'}
      </button>
    </div>
  );

  return (
    <div className="max-w-4xl">
      <BackButton />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show">
        <PageHeader
          title="Dot Plot"
          subtitle="Compare two sequences visually — every dot marks a window of similar residues. Identical sequences trace the main diagonal; repeats and rearranged segments appear as off-diagonal lines; inverted repeats as anti-diagonal lines. Optionally score protein windows with a BLOSUM/PAM matrix."
        />
      </motion.div>

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-6">
        <div className="data-card p-5 space-y-4">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h3 className="text-sm font-semibold text-text-primary">Sequence A (vertical axis)</h3>
            <button
              onClick={() => setSeqA(SAMPLE_A)}
              className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition"
            >
              Load p53 human
            </button>
          </div>
          <FlatTextarea
            value={seqA}
            onChange={e => setSeqA(e.target.value)}
            placeholder="Paste first sequence (raw or FASTA)..."
            className="w-full h-24 text-sm"
          />
          {accessionInput('A')}

          <div className="flex items-center gap-3 flex-wrap">
            <h3 className="text-sm font-semibold text-text-primary">Sequence B (horizontal axis)</h3>
            <ClayToggle
              checked={selfCompare}
              onChange={toggleSelf}
              label={selfCompare ? 'Self-comparison' : 'Compare to self'}
            />
            {!selfCompare && (
              <button
                onClick={() => setSeqB(SAMPLE_B)}
                className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition"
              >
                Load p53 mouse
              </button>
            )}
          </div>
          <FlatTextarea
            value={effectiveB}
            onChange={e => setSeqB(e.target.value)}
            disabled={selfCompare}
            placeholder="Paste second sequence (raw or FASTA)..."
            className="w-full h-24 text-sm"
          />
          {!selfCompare && accessionInput('B')}
          {accError && <p className="text-xs text-error">{accError}</p>}
        </div>

        <div className="glass p-4 border border-glass-border grid grid-cols-1 sm:grid-cols-3 gap-5 items-end">
          <ClaySlider
            label="Window size"
            value={window}
            min={1}
            max={50}
            unit="residues"
            onChange={setWindow}
          />
          <ClaySlider
            label="Stringency"
            value={stringency}
            min={40}
            max={100}
            unit="% match"
            onChange={setStringency}
          />
          <div className="flex flex-col gap-1.5">
            <label className="text-sm text-text-primary" htmlFor="dotplot-scoring">Scoring</label>
            <select
              id="dotplot-scoring"
              value={scoring}
              onChange={e => setScoring(e.target.value)}
              className="input-flat text-sm"
            >
              <option value="identity">Identity (nucleotides)</option>
              <option value="blosum62">BLOSUM62 (protein)</option>
              <option value="blosum50">BLOSUM50 (protein)</option>
              <option value="blosum45">BLOSUM45 (protein)</option>
              <option value="pam30">PAM30 (protein)</option>
              <option value="pam70">PAM70 (protein)</option>
              <option value="pam250">PAM250 (protein)</option>
            </select>
            <p className="text-[10px] text-text-muted">
              Matrices require both inputs to be protein; otherwise scoring falls back to identity.
            </p>
          </div>
        </div>

        <div className="flex justify-end">
          <CriticalButton onClick={handleRun} disabled={!canRun}>
            {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : null}
            {loading ? 'Computing...' : 'Compute dot plot'}
          </CriticalButton>
        </div>

        {error && (
          <div className="rounded-lg bg-error/10 border border-error/30 px-4 py-3 text-sm text-error">
            <strong>Dot plot failed:</strong> {error}
          </div>
        )}

        {result && !loading && (
          <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="space-y-4 mt-8">
            <div className="data-card p-5">
              <div className="flex items-center gap-3 mb-4 flex-wrap">
                <h3 className="text-sm font-semibold text-text-primary">Dot plot</h3>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent-cyan/10 border border-accent-cyan/30 text-accent-cyan font-medium">
                  {result.dot_count.toLocaleString()} dots
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-1 border border-glass-border text-text-muted font-medium">
                  A: {result.seq_a_length} · B: {result.seq_b_length}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-1 border border-glass-border text-text-muted font-medium">
                  {result.sequence_type_a}{result.sequence_type_b && result.sequence_type_a !== result.sequence_type_b ? ` × ${result.sequence_type_b}` : ''}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface-1 border border-glass-border text-text-muted font-medium">
                  {result.scoring_used}{result.scoring !== result.scoring_used ? ' (requested ' + result.scoring + ')' : ''} · window {result.window} · ≥{result.stringency}% match
                </span>
                <div className="ml-auto flex items-center gap-2">
                  <button
                    onClick={exportPng}
                    className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition-colors flex items-center gap-1.5"
                  >
                    <Download className="w-3.5 h-3.5" /> PNG
                  </button>
                  <button
                    onClick={exportSvg}
                    className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition-colors flex items-center gap-1.5"
                  >
                    <Download className="w-3.5 h-3.5" /> SVG
                  </button>
                  <button
                    onClick={() => setResult({ ...result })}
                    className="text-xs px-2.5 py-1 rounded bg-surface-1 border border-glass-border text-text-secondary hover:text-accent-cyan transition"
                  >
                    Reset zoom
                  </button>
                </div>
              </div>

              {result.downsampled && (
                <p className="mb-3 text-xs text-accent-amber">
                  Downsampled: {result.total_matches.toLocaleString()} raw matches, showing a uniform subset.
                </p>
              )}

              {features && (
                <div className="mb-4 flex flex-wrap gap-2">
                  <FeatureChip
                    label="Main diag."
                    value={`${features.main_diagonal_pct}%`}
                    tone={features.main_diagonal_pct >= 70 ? 'text-accent-purple' : 'text-accent-amber'}
                  />
                  <FeatureChip label="Repeats" value={String(features.off_diagonal.length)} tone="text-accent-amber" />
                  <FeatureChip label="Inverted" value={String(features.anti_diagonal.length)} tone="text-accent-cyan" />
                  <FeatureChip label="Indel gaps" value={`${features.gaps.count}`} tone={features.gaps.largest > 0 ? 'text-accent-amber' : 'text-text-primary'} />
                  <div className="ml-auto flex flex-col justify-center gap-1 text-[10px] text-text-muted">
                    <span className="flex items-center gap-1.5"><span className="w-4 h-0.5" style={{ background: LINE.diagonal }} /> main diagonal</span>
                    <span className="flex items-center gap-1.5"><span className="w-4 h-0.5" style={{ background: LINE.repeat }} /> repeat / duplication</span>
                    <span className="flex items-center gap-1.5"><span className="w-4 h-0.5" style={{ background: LINE.inverted }} /> inverted repeat</span>
                  </div>
                </div>
              )}

              <div className="w-full h-[520px]">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 10, right: 20, bottom: 24, left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis
                      type="number"
                      dataKey="x"
                      name="Position in B"
                      domain={[0, W]}
                      tick={{ fontSize: 10, fill: '#64748B' }}
                      label={{ value: 'Sequence B position', position: 'insideBottom', offset: -12, fill: '#94A3B8', fontSize: 11 }}
                    />
                    <YAxis
                      type="number"
                      dataKey="y"
                      name="Position in A"
                      domain={[H, 0]}
                      tick={{ fontSize: 10, fill: '#64748B' }}
                      label={{ value: 'Sequence A position', angle: -90, position: 'insideLeft', offset: 4, fill: '#94A3B8', fontSize: 11 }}
                    />
                    <ReferenceLine segment={[{ x: 0, y: 0 }, { x: diagEnd, y: diagEnd }]} stroke={LINE.diagonal} strokeDasharray="5 5" />
                    {features?.off_diagonal.map(f => {
                      const seg = diagSegment(f.offset, W, H);
                      if (seg.length < 2) return null;
                      return (
                        <ReferenceLine
                          key={`off-${f.offset}`}
                          segment={[{ x: seg[0][0], y: seg[0][1] }, { x: seg[1][0], y: seg[1][1] }]}
                          stroke={LINE.repeat}
                          strokeDasharray="4 4"
                          strokeWidth={1.5}
                        />
                      );
                    })}
                    {features?.anti_diagonal.map(f => {
                      const seg = antiSegment(f.sum, W, H);
                      if (seg.length < 2) return null;
                      return (
                        <ReferenceLine
                          key={`anti-${f.sum}`}
                          segment={[{ x: seg[0][0], y: seg[0][1] }, { x: seg[1][0], y: seg[1][1] }]}
                          stroke={LINE.inverted}
                          strokeDasharray="4 4"
                          strokeWidth={1.5}
                        />
                      );
                    })}
                    <Tooltip {...tooltipStyle} />
                    <Scatter data={data} fill="#22D3EE" fillOpacity={0.55} stroke="none" shape="circle" isAnimationActive={false} />
                    <Brush dataKey="x" height={18} travellerWidth={8} stroke="#22D3EE" fill="rgba(34,211,238,0.08)" />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </div>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}

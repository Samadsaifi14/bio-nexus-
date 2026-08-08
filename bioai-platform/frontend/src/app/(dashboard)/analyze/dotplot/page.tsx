'use client';

import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { CircleNotch as LoaderCircle } from '@phosphor-icons/react';
import {
  ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis, Tooltip,
  CartesianGrid, ReferenceLine, Brush,
} from 'recharts';
import { fadeUp } from '@/lib/animations';
import { runDotPlot } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import { BackButton, CriticalButton, ClaySlider, ClayToggle, FlatTextarea, PageHeader } from '@/components/ui';
import type { DotPlotResult } from '@/types/pipeline';

const SAMPLE_A = '>p53_human\nMEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYQGSYGFRLGFLHSGTAKSVTCTYSPALNKMFCQLAKTCPVQLWVDSTPPPGTRVRAMAIYKQSQHMTEVVRRCPHHERCSDSDGLAPPQHLIRVEGNLRVEYLDDRNTFRHSVVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRNSFEVRVCACPGRDRRTEEENLRKKGEPHHELPPGSTKRALPNNTSSSPQPKKKPLDGEYFTLQIRGRERFEMFRELNEALELKDAQAGKEPGGSRAHSSHLKSKKGQSTSRHKKLMFKTEGPDSD';
const SAMPLE_B = '>p53_mouse\nMEEPQSDPSIEPPLSQETFSDLWKLLPENNVLSPLPSQAVDDLMLSPDDLAQWFTEDPGPDEAPRMSEAAPPAAPAPAAPTPAAPAPAPSWPLSSFVPSQKTYQGNYGFHLGFLQSGTAKSVMCTYSPPLNKLFCQLAKTCPVQLWVSATPPAGSRVRAMAIYKKSQHMTEVVRRCPHHERCSDSSDGLAPPQHLIRVEGNLRAEYLDDRNTFRHSIVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRDSFEVRVCACPGRDRRTEEENFKKKEPCPEPPPGSTRALGSTSTSSPTPKKKPLDGEYFTLKIRGRERFEMFRELNEALELKDAHATEEPFGGSRAHSSHLKSKKGQSTSRHKKFKKTADPSS';

function cleanLength(seq: string): number {
  return seq.replace(/[^A-Za-z]/g, '').length;
}

const tooltipStyle = {
  contentStyle: { background: '#0E1521', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8, fontSize: 12 },
  labelStyle: { color: '#94A3B8' },
  itemStyle: { color: '#E2E8F0' },
};

export default function DotPlotPage() {
  const [seqA, setSeqA] = useState('');
  const [seqB, setSeqB] = useState('');
  const [selfCompare, setSelfCompare] = useState(false);
  const [window, setWindow] = useState(10);
  const [stringency, setStringency] = useState(80);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DotPlotResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const audit = useAuditTrail();

  const effectiveB = selfCompare ? seqA : seqB;
  const canRun = cleanLength(seqA) >= 1 && cleanLength(effectiveB) >= 1 && !loading;

  const data = useMemo(
    () => (result ? result.dots.map(([y, x], i) => ({ x, y, idx: i })) : []),
    [result],
  );

  const handleRun = async () => {
    if (!canRun) return;
    setLoading(true);
    setError(null);
    setResult(null);
    const summary = `lenA:${cleanLength(seqA)},lenB:${cleanLength(effectiveB)},w:${window},s:${stringency},self:${selfCompare}`;
    audit.emitStarted('dot_plot', 'Dot Plot', summary);
    try {
      const res = await runDotPlot({
        seq_a: seqA,
        seq_b: effectiveB,
        window,
        stringency,
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

  return (
    <div className="max-w-4xl">
      <BackButton />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show">
        <PageHeader
          title="Dot Plot"
          subtitle="Compare two sequences visually — every dot marks a window of matching residues. Identical sequences trace the main diagonal; repeats and rearranged segments appear as off-diagonal lines."
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
            className="w-full h-28 text-sm"
          />

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
            className="w-full h-28 text-sm"
          />
        </div>

        <div className="glass p-4 border border-glass-border grid grid-cols-1 sm:grid-cols-2 gap-5">
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
            unit="% identity"
            onChange={setStringency}
          />
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
                  window {result.window} · {result.stringency}% (≥{result.threshold})
                </span>
                <div className="ml-auto flex items-center gap-2">
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

              <div className="w-full h-[520px]">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 10, right: 20, bottom: 24, left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                    <XAxis
                      type="number"
                      dataKey="x"
                      name="Position in B"
                      domain={[0, result.seq_b_length]}
                      tick={{ fontSize: 10, fill: '#64748B' }}
                      label={{ value: 'Sequence B position', position: 'insideBottom', offset: -12, fill: '#94A3B8', fontSize: 11 }}
                    />
                    <YAxis
                      type="number"
                      dataKey="y"
                      name="Position in A"
                      domain={[0, result.seq_a_length]}
                      tick={{ fontSize: 10, fill: '#64748B' }}
                      label={{ value: 'Sequence A position', angle: -90, position: 'insideLeft', offset: 4, fill: '#94A3B8', fontSize: 11 }}
                    />
                    {result.seq_a_length === result.seq_b_length && (
                      <ReferenceLine segment={[{ x: 0, y: 0 }, { x: result.seq_b_length, y: result.seq_a_length }]} stroke="rgba(168,85,247,0.5)" strokeDasharray="4 4" />
                    )}
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

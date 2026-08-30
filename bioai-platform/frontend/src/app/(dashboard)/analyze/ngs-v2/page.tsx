'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Dna, CircleNotch, TestTube, MapTrifold, Warning, Database, FileText } from '@phosphor-icons/react';
import { fadeUp } from '@/lib/animations';
import { runNgs2Analyze } from '@/lib/api';
import type { Ngs2AnalyzeResult } from '@/lib/api';
import { BackButton, CriticalButton, FlatInput, PageHeader } from '@/components/ui';
import ScientificResultsWorkspace from '@/components/results/ScientificResultsWorkspace';
import StageEvidenceTable from '@/components/results/StageEvidenceTable';
import { ProvenancePanel, RawEvidence } from '@/components/results/ProvenancePanel';
import GenomeViewer from '@/components/GenomeViewer';

const ASSAY_OPTIONS = [
  { value: '', label: 'Auto-detect assay' },
  { value: 'WGS', label: 'Whole Genome Sequencing (WGS)' },
  { value: 'WES', label: 'Whole Exome Sequencing (WES)' },
  { value: 'RNA-seq', label: 'RNA-seq' },
  { value: 'Amplicon', label: 'Targeted Amplicon' },
];

const DEMOS = [
  { id: 'wgs-clean', title: 'Clean WGS', subtitle: '2×150 bp · high-quality paired reads', assay: 'WGS' },
  { id: 'wgs-mixed-quality', title: 'Mixed-quality WGS', subtitle: 'low-quality tails + duplicates', assay: 'WGS' },
  { id: 'wes-small', title: 'Compact WES', subtitle: 'small paired-end exome-style run', assay: 'WES' },
] as const;

type DemoMeta = { profile: string; label: string; description: string; synthetic: boolean; read_pairs: number };
type ExtendedResult = Ngs2AnalyzeResult & { demo?: DemoMeta | null; requested: Ngs2AnalyzeResult['requested'] & { demo_profile?: string | null } };

export default function NgsV2Page() {
  const [filePaths, setFilePaths] = useState('');
  const [assay, setAssay] = useState('');
  const [reference, setReference] = useState('grch38');
  const [synthetic, setSynthetic] = useState(true);
  const [loading, setLoading] = useState(false);
  const [runningDemo, setRunningDemo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExtendedResult | null>(null);

  const run = async (demoProfile?: string) => {
    const files = filePaths.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean);
    if (!demoProfile && files.length === 0) return;
    setLoading(true); setRunningDemo(demoProfile ?? null); setError(null); setResult(null);
    try {
      const payload = {
        file_paths: demoProfile ? [] : files,
        reference: reference || undefined,
        assay: demoProfile ? undefined : (assay || undefined),
        metadata: { platform: 'illumina', source: demoProfile ? 'bionexus-demo' : 'user' },
        synthetic_reference: demoProfile ? true : synthetic,
        demo_profile: demoProfile,
      };
      const res = await runNgs2Analyze(payload as Parameters<typeof runNgs2Analyze>[0] & { demo_profile?: string });
      setResult(res as ExtendedResult);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to run analysis');
    } finally { setLoading(false); setRunningDemo(null); }
  };

  const verdict = result?.pipeline.pipeline_status ?? 'INFO';
  const status = verdict === 'PASS' ? 'PASS' : verdict === 'WARN' ? 'WARN' : verdict === 'FAIL' ? 'FAIL' : 'INFO';
  const gate = result?.pipeline.stages[result.pipeline.stages.length - 1];
  const passed = result?.pipeline.stages.filter(s => s.qc?.status === 'PASS').length ?? 0;
  const warned = result?.pipeline.stages.filter(s => s.qc?.status === 'WARN').length ?? 0;
  const failed = result?.pipeline.stages.filter(s => s.qc?.status === 'FAIL').length ?? 0;
  const totalReads = result ? Object.values(result.requested.reads_loaded).reduce((a, b) => a + b, 0) : 0;

  return <div className="scientific-page max-w-6xl space-y-6 pb-12">
    <BackButton />
    <PageHeader title="NGS Analysis" subtitle="Raw FASTQ to auditable QC, alignment, variant evidence, IGV tracks and a final analysis-readiness decision." />

    <motion.section variants={fadeUp} initial={{ y: 18 }} animate="show" className="data-card overflow-hidden">
      <div className="border-b border-glass-border p-5"><div className="flex items-center gap-2"><TestTube className="h-4 w-4 text-accent-cyan"/><h2 className="text-sm font-semibold text-text-primary">Try a complete analysis</h2></div><p className="mt-1 text-xs leading-5 text-text-muted">These are deterministic synthetic FASTQ pairs. They run through the same validation and 21-stage analysis DAG as supplied files and are clearly marked as demonstration data.</p></div>
      <div className="grid gap-px bg-glass-border md:grid-cols-3">{DEMOS.map(demo => <button key={demo.id} disabled={loading} onClick={() => run(demo.id)} className="bg-surface-0 p-4 text-left transition hover:bg-surface-1 disabled:opacity-50"><div className="flex items-center justify-between"><span className="text-sm font-semibold text-text-primary">{demo.title}</span><span className="rounded border border-accent-cyan/20 bg-accent-cyan/5 px-1.5 py-0.5 font-mono text-[9px] text-accent-cyan">DEMO</span></div><p className="mt-1 text-xs text-text-muted">{demo.subtitle}</p><p className="mt-3 text-[11px] font-medium text-accent-cyan">{runningDemo === demo.id ? 'Running…' : 'Run demo →'}</p></button>)}</div>
    </motion.section>

    <section className="data-card p-5 space-y-4">
      <div><label className="mb-1.5 block text-sm font-medium text-text-primary">Or analyze server-local FASTQ files</label><FlatInput type="text" value={filePaths} onChange={(e) => { setFilePaths(e.target.value); setResult(null); setError(null); }} onKeyDown={(e) => e.key === 'Enter' && run()} placeholder="/data/SAMPLE_001_R1.fastq.gz, /data/SAMPLE_001_R2.fastq.gz" className="w-full px-4 py-3 text-sm font-mono"/><p className="mt-1.5 text-[11px] text-text-muted">Separate paired paths with commas. Public deployments can use the demos above without filesystem access.</p></div>
      <div className="grid gap-4 md:grid-cols-2"><div><label className="mb-1.5 block text-xs text-text-muted">Assay</label><select value={assay} onChange={e => setAssay(e.target.value)} className="scientific-select">{ASSAY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</select></div><div><label className="mb-1.5 block text-xs text-text-muted">Reference build</label><select value={reference} onChange={e => setReference(e.target.value)} className="scientific-select"><option value="grch38">GRCh38</option><option value="grch37">GRCh37</option></select></div></div>
      <label className="flex items-start gap-2 rounded-lg border border-glass-border bg-surface-1 p-3"><input type="checkbox" checked={synthetic} onChange={e => setSynthetic(e.target.checked)} className="mt-0.5 accent-cyan-500"/><span><span className="block text-xs font-medium text-text-primary">Synthetic demonstration reference</span><span className="mt-0.5 block text-[11px] leading-4 text-text-muted">For local test reads, derive a deterministic non-clinical reference so alignment-dependent stages can execute. Do not use this mode for biological interpretation.</span></span></label>
      <CriticalButton onClick={() => run()} disabled={loading || !filePaths.trim()} className="w-full py-3 flex items-center justify-center gap-2 disabled:opacity-50">{loading && !runningDemo ? <CircleNotch className="h-4 w-4 animate-spin"/> : <Dna className="h-4 w-4"/>}{loading && !runningDemo ? 'Running 21-stage pipeline…' : 'Run FASTQ analysis'}</CriticalButton>
    </section>

    {error && <div className="rounded-xl border border-error/25 bg-error/8 p-4 text-sm text-error">{error}</div>}

    {result && <ScientificResultsWorkspace
      title={result.demo ? result.demo.label : `${result.detection.assay} sequencing result`}
      subtitle={`${result.pipeline.pipeline} · ${result.requested.reference}${result.demo ? ' · SYNTHETIC DEMONSTRATION DATA' : ''}`}
      status={status}
      statusLabel={verdict === 'PASS' ? 'ANALYSIS READY' : verdict === 'WARN' ? 'READY WITH WARNINGS' : verdict === 'FAIL' ? 'NOT ANALYSIS READY' : verdict}
      metadata={[{ label: 'Assay', value: result.detection.assay }, { label: 'Library', value: result.detection.library_type }, { label: 'Sample type', value: result.detection.sample_type }, { label: 'Reference', value: result.requested.reference }, { label: 'Pipeline', value: result.pipeline.pipeline }, { label: 'Final gate', value: gate?.qc?.status ?? '—' }]}
      metrics={[{ label: 'Reads loaded', value: totalReads.toLocaleString() }, { label: 'Stages', value: result.pipeline.stages.length }, { label: 'PASS', value: passed, status: 'PASS' }, { label: 'WARN', value: warned, status: warned ? 'WARN' : 'PASS' }, { label: 'FAIL', value: failed, status: failed ? 'FAIL' : 'PASS' }, { label: 'Mapped reads', value: result.visualization.n_mapped.toLocaleString() }, { label: 'Variants', value: result.visualization.n_variants.toLocaleString() }, { label: 'Detection confidence', value: `${(result.detection.confidence * 100).toFixed(0)}%` }]}
      overview={<div className="space-y-5">{result.demo && <div className="rounded-lg border border-info/20 bg-info/5 p-4 text-xs leading-5 text-text-secondary"><strong className="text-text-primary">Demonstration dataset:</strong> {result.demo.description} It is synthetic and intended to test execution, QC visualization and result handling—not biological or clinical conclusions.</div>}<div className="grid gap-3 md:grid-cols-3"><div className="result-callout"><Database/><div><b>Assay routing</b><p>{result.detection.assay} · {result.detection.library_type} · {(result.detection.confidence*100).toFixed(0)}% detection confidence.</p></div></div><div className="result-callout"><FileText/><div><b>Evidence chain</b><p>{result.pipeline.stages.length} stages preserve tool, version, metrics, outputs and decisions.</p></div></div><div className="result-callout"><MapTrifold/><div><b>Visualization</b><p>{result.visualization.n_mapped} mapped reads and {result.visualization.n_variants} variants serialized for inspection.</p></div></div></div>{result.pipeline.warnings.length > 0 && <div className="rounded-lg border border-warn/20 bg-warn/5 p-4"><div className="flex items-center gap-2 text-xs font-semibold text-warn"><Warning/>Warnings ({result.pipeline.warnings.length})</div><ul className="mt-2 space-y-1 font-mono text-[11px] text-text-muted">{result.pipeline.warnings.map((w,i)=><li key={i}>• {w}</li>)}</ul></div>}</div>}
      qc={<StageEvidenceTable stages={result.pipeline.stages}/>} 
      results={<div className="space-y-5">{(result.visualization.sam || result.visualization.vcf) ? <div><div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-semibold text-text-primary">Genome evidence viewer</h3><span className="font-mono text-[10px] text-text-muted">{result.visualization.n_mapped} mapped · {result.visualization.n_variants} variants</span></div><GenomeViewer samText={result.visualization.sam} vcfText={result.visualization.vcf} locus={result.visualization.locus ?? undefined}/></div> : <p className="text-sm text-text-muted">No alignment/variant visualization was emitted.</p>}<div><h3 className="mb-2 text-sm font-semibold text-text-primary">Complete stage evidence</h3><StageEvidenceTable stages={result.pipeline.stages}/></div></div>}
      raw={<div className="space-y-5"><RawEvidence label="Pipeline report" value={result.pipeline}/>{result.visualization.vcf && <RawEvidence label="VCF" value={result.visualization.vcf}/>} {result.visualization.sam && <RawEvidence label="SAM" value={result.visualization.sam}/>}</div>}
      methods={<ProvenancePanel provenance={result.pipeline.provenance}/>} 
      ai={<div className="rounded-lg border border-info/20 bg-info/5 p-4 text-sm leading-6 text-text-secondary">AI interpretation is intentionally separated from the deterministic NGS evidence. The current v2 result prioritizes stage QC, raw artifacts, provenance and the final readiness gate. Any future AI summary should cite these emitted metrics and never override a blocking QC decision.</div>}
    />}
  </div>;
}

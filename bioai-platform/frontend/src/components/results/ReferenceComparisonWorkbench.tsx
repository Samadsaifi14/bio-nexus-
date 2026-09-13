'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { UploadSimple as Upload, Scales, CircleNotch as LoaderCircle } from '@phosphor-icons/react';
import { compareWithReference, getReferenceComparators, type ComparatorDefinition, type ScientificComparison } from '@/lib/scientificComparisonApi';
import { parseReferenceInput } from '@/lib/referenceInput';
import { ScientificComparisonResult } from './ScientificComparisonResult';
import { FlatInput, FlatTextarea, CriticalButton } from '@/components/ui';

const SAMPLE_HINTS: Record<string, string> = {
  blast: 'Paste NCBI BLAST JSON2, or normalized JSON with a hits array.',
  msa: 'Paste aligned FASTA from the reference tool, or JSON containing aln_fasta.',
  phylo: 'Paste a reference Newick tree or JSON containing newick/phylotree_newick.',
  rnaseq: 'Paste DESeq2 TSV/CSV or JSON with gene, log2FoldChange and padj fields.',
  pathway: 'Paste Reactome enrichment JSON or normalized pathway rows.',
  docking: 'Paste standalone Vina JSON/normalized pose records for the same receptor, ligand, box, seed and settings.',
};

interface Props {
  analysisType: string;
  bionexusResult?: Record<string, unknown> | null;
  title?: string;
  defaultTopN?: number;
}

export function ReferenceComparisonWorkbench({ analysisType, bionexusResult, title = 'Reference-tool comparison', defaultTopN = 10 }: Props) {
  const [definition, setDefinition] = useState<ComparatorDefinition | null>(null);
  const [bioText, setBioText] = useState(bionexusResult ? JSON.stringify(bionexusResult, null, 2) : '');
  const [referenceText, setReferenceText] = useState('');
  const [referenceTool, setReferenceTool] = useState('');
  const [referenceVersion, setReferenceVersion] = useState('');
  const [referenceDatabase, setReferenceDatabase] = useState('');
  const [topN, setTopN] = useState(defaultTopN);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<ScientificComparison | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (bionexusResult) setBioText(JSON.stringify(bionexusResult, null, 2));
  }, [bionexusResult]);

  useEffect(() => {
    let active = true;
    getReferenceComparators()
      .then(reg => { if (active) setDefinition(reg.comparators[analysisType] ?? null); })
      .catch(() => { if (active) setDefinition(null); });
    return () => { active = false; };
  }, [analysisType]);

  const canRun = useMemo(() => Boolean((bionexusResult || bioText.trim()) && referenceText.trim()), [bionexusResult, bioText, referenceText]);

  async function runComparison() {
    setLoading(true); setError(''); setResult(null);
    try {
      const bio = bionexusResult ?? parseReferenceInput(analysisType, bioText);
      const reference = parseReferenceInput(analysisType, referenceText);
      const compared = await compareWithReference({
        analysis_type: analysisType,
        bionexus: bio,
        reference,
        top_n: topN,
        reference_metadata: {
          tool: referenceTool || definition?.reference || 'User-supplied reference result',
          version: referenceVersion || null,
          database_or_reference: referenceDatabase || null,
          input_match_asserted: true,
          parameter_match_asserted: true,
        },
      });
      setResult(compared);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Comparison failed');
    } finally {
      setLoading(false);
    }
  }

  async function loadFile(file: File | undefined) {
    if (!file) return;
    const text = await file.text();
    setReferenceText(text);
    setResult(null);
    setError('');
  }

  return (
    <div className="space-y-4">
      <div className="data-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h3 className="flex items-center gap-2 text-base font-semibold text-text-primary"><Scales className="h-5 w-5 text-accent-cyan" />{title}</h3>
            <p className="mt-1 max-w-3xl text-xs text-text-muted">Run the same scientific workload in an independent reference tool, export its result, then compare the two here. BioNexus reports concordance and deltas—not an automatic “winner”.</p>
          </div>
          {definition && <a href={definition.reference_url} target="_blank" rel="noreferrer" className="text-xs text-accent-cyan hover:underline">Reference: {definition.reference}</a>}
        </div>

        <div className="mt-4 rounded-lg border border-accent-amber/25 bg-accent-amber/5 p-3 text-xs text-text-secondary">
          Required for a defensible comparison: same biological input, same database/reference build, same relevant parameters, and a recorded tool/version. If these differ, treat the output as a methodological comparison rather than exact concordance.
        </div>

        {!bionexusResult && (
          <div className="mt-4">
            <label className="mb-1 block text-xs font-medium text-text-secondary">BioNexus result JSON / TSV / supported scientific text</label>
            <FlatTextarea value={bioText} onChange={e => setBioText(e.target.value)} rows={7} className="w-full font-mono text-xs" placeholder="Paste the BioNexus result to compare..." />
          </div>
        )}

        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div><label className="mb-1 block text-xs text-text-muted">Reference tool</label><FlatInput value={referenceTool} onChange={e => setReferenceTool(e.target.value)} placeholder={definition?.reference ?? 'e.g. NCBI BLAST'} /></div>
          <div><label className="mb-1 block text-xs text-text-muted">Tool version / release</label><FlatInput value={referenceVersion} onChange={e => setReferenceVersion(e.target.value)} placeholder="Record exactly if available" /></div>
          <div><label className="mb-1 block text-xs text-text-muted">Database / reference build</label><FlatInput value={referenceDatabase} onChange={e => setReferenceDatabase(e.target.value)} placeholder="e.g. Swiss-Prot release / GRCh38" /></div>
        </div>

        <div className="mt-4">
          <div className="mb-1 flex items-center justify-between gap-2"><label className="text-xs font-medium text-text-secondary">Independent reference result</label><button type="button" onClick={() => fileRef.current?.click()} className="btn-ghost inline-flex items-center gap-1 px-2 py-1 text-xs"><Upload className="h-3.5 w-3.5" /> Upload result file</button></div>
          <input ref={fileRef} type="file" className="hidden" accept=".json,.txt,.tsv,.csv,.fa,.fasta,.aln,.nwk,.newick" onChange={e => void loadFile(e.target.files?.[0])} />
          <FlatTextarea value={referenceText} onChange={e => { setReferenceText(e.target.value); setResult(null); }} rows={9} className="w-full font-mono text-xs" placeholder={SAMPLE_HINTS[analysisType] ?? 'Paste normalized JSON, TSV/CSV, or a supported reference format...'} />
        </div>

        <div className="mt-4 flex flex-wrap items-end gap-3">
          <div><label className="mb-1 block text-xs text-text-muted">Top-N / comparison depth</label><FlatInput type="number" min={1} max={100} value={topN} onChange={e => setTopN(Math.max(1, Math.min(100, Number(e.target.value) || 10)))} className="w-24" /></div>
          <CriticalButton onClick={() => void runComparison()} disabled={!canRun || loading}>{loading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Scales className="h-4 w-4" />}{loading ? 'Comparing...' : 'Compare scientifically'}</CriticalButton>
        </div>
        {error && <p className="mt-3 text-sm text-error">{error}</p>}
      </div>

      {result && <ScientificComparisonResult result={result} />}
    </div>
  );
}

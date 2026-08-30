'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import dynamic from 'next/dynamic'
import { DownloadSimple, TreeStructure, ChartBar, FileText, Dna } from '@phosphor-icons/react'
import { useAuditTrail } from '@/hooks/useAuditTrail'
import { BackButton, CriticalButton, FlatTextarea, PageHeader } from '@/components/ui'
import { AIResultSummary } from '@/components/results/AIResultSummary'
import ScientificResultsWorkspace, { MetricGrid } from '@/components/results/ScientificResultsWorkspace'
import { RawEvidence } from '@/components/results/ProvenancePanel'
import { parseFasta } from '@/lib/sequence-utils'

const PhyloTreeViewer = dynamic(() => import('@/components/phylo/PhyloTreeViewer'), { ssr: false })

type Method = 'nj' | 'ml' | 'upgma'
type SeqType = 'protein' | 'dna'
type JobPhase = 'queued' | 'msa_running' | 'msa_done' | 'tree_running' | 'complete' | 'error'

interface PhyloJobStatus {
  job_id: string
  method: Method
  seq_type: SeqType
  model: string | null
  bootstrap: number | null
  phase: JobPhase
  aln_fasta: string | null
  newick: string | null
  stats: string | null
  error: string | null
  created_at: number
  msa_done_at: number | null
  done_at: number | null
}

const PROTEIN_MODELS = ['LG', 'WAG', 'JTT', 'Blosum62', 'MtREV', 'Dayhoff']
const DNA_MODELS = ['GTR', 'HKY85', 'K80', 'F81', 'TN93', 'SYM']

const METHOD_INFO: Record<Method, { label: string; desc: string; note: string }> = {
  nj: { label: 'Neighbor-Joining', desc: 'Distance-based tree reconstruction for fast exploratory analysis.', note: 'Fast and useful for exploration; support values are not automatically equivalent to ML bootstrap support.' },
  upgma: { label: 'UPGMA', desc: 'Ultrametric clustering under a molecular-clock assumption.', note: 'Interpret cautiously when evolutionary rates differ among lineages.' },
  ml: { label: 'Maximum Likelihood', desc: 'Model-based phylogenetic inference with optional bootstrap replicates.', note: 'Preferred here when model-based inference and branch support are required.' },
}

const PHASE_LABELS: Record<JobPhase, string> = {
  queued: 'Waiting to start…', msa_running: 'Running multiple sequence alignment…', msa_done: 'Alignment complete — building tree…',
  tree_running: 'Inferring phylogenetic tree…', complete: 'Complete', error: 'Error',
}

const DEMOS: Record<string, { label: string; type: SeqType; fasta: string }> = {
  globins: {
    label: 'Globins · 5 proteins', type: 'protein', fasta: `>Human_HBA
MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHGKKVADALTNAVAHVDDMPNALSALSDLHAHKLRVDPVNFKLLSHCLLVTLAAHLPAEFTPAVHASLDKFLASVSTVLTSKYR
>Chimp_HBA
MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHGKKVADALTNAVAHVDDMPNALSALSDLHAHKLRVDPVNFKLLSHCLLVTLAAHLPAEFTPAVHASLDKFLASVSTVLTSKYR
>Mouse_HBA
MVLSGEDKSNVKAAWGKIGGHAGEYGAEALERMFASFPTTKTYFPHFDVSHGSAQVKGHGKKVADALTNAVGHLDDLPGALSDLSNLHAHKLRVDPVNFKLLSHCLLVTLANHLPDFTPAVHASLDKFLANVSTVLTSKYR
>Human_HBB
MVHLTPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRFFESFGDLSTPDAVMGNPKVKAHGKKVLGAFSDGLAHLDNLKGTFATLSELHCDKLHVDPENFRLLGNVLVCVLAHHFGKEFTPPVQAAYQKVVAGVANALAHKYH
>Myoglobin
MGLSDGEWQLVLNVWGKVEADIPGHGQEVLIRLFKGHPETLEKFDKFKHLKSEDEMKASEDLKKHGATVLTALGGILKKKGHHEAEIKPLAQSHATKHKIPVKYLEFISECIIQVLQSKHPGDFGADAQGAMNKALELFRKDMASNYKELGFQG`,
  },
  primates: {
    label: 'Primate mtDNA · 4 sequences', type: 'dna', fasta: `>Human
ATGACCCCAATACGCAAAATTAACCCCCTAATAAAATTAATTAACCACTCATTCATCGACCTCCCCACCCCATCCAACATCTCCGCATGATGAAACTTCGGCTCACTCCTTGGCGCCTGCCTGATCCTCCAAATCACCACAGGACTATTCCTAGCCATACACTACACATCAGACACAACAAACCTTATCCACCTTCCCTCACCAAAGCCCATAAAATAGACCTACG
>Chimpanzee
ATGACCCCAATACGCAAAATTAACCCCCTAATAAAATTAATTAACCACTCATTCATCGACCTCCCCACCCCATCCAACATCTCCGCATGATGAAACTTCGGCTCACTCCTTGGCGCCTGCCTGATCCTCCAAATCACCACAGGACTATTCCTAGCCATACACTACACATCAGACACAACAAACCTTATCCACCTTCCCTCACCAAAGCCCATAAAATAGATCTACG
>Gorilla
ATGACCCCAATACGCAAAATTAACCCCCTAATAAAATTAATTAACCACTCATTCATCGACCTCCCCACCCCATCCAACATCTCCGCATGATGAAACTTCGGCTCACTCCTTGGCGCCTGCCTGATCCTCCAAATCACCACAGGACTATTCCTAGCCATACACTACACATCAGACACAACAAACCTTATCCACCTTCCCTCACCAAAGCCCATAAAATAGATTTACG
>Orangutan
ATGACCCCAATACGCAAAATTAACCCCCTAATAAAATTAATTAACCACTCATTCATCGACCTCCCCACCCCATCCAACATCTCCGCATGATGAAACTTCGGCTCACTCCTTGGCGCCTGCCTGATCCTCCAAATCACCACAGGACTATTCCTAGCCATACACTACACATCAGACACAACAAACCTTATCCACCTTCCCTCACCAAAGCCCATAAAATAGACTTACG`,
  },
}

function elapsed(from: number): string {
  const s = Math.max(0, Math.round(Date.now() / 1000 - from))
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`
}

function downloadText(name: string, text: string) {
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url)
}

function alignmentMetrics(alignment?: string | null) {
  if (!alignment) return null
  const sequences = parseFasta(alignment)
  if (!sequences.length) return null
  const alignedLength = Math.max(...sequences.map(s => s.sequence.length))
  let gapCharacters = 0, variableSites = 0, conservedSites = 0
  for (let i = 0; i < alignedLength; i++) {
    const column = sequences.map(s => s.sequence[i] ?? '-').filter(c => c !== '-')
    gapCharacters += sequences.length - column.length
    const unique = new Set(column.map(c => c.toUpperCase()))
    if (unique.size <= 1 && column.length) conservedSites++
    if (unique.size > 1) variableSites++
  }
  const identities: number[] = []
  for (let i = 0; i < sequences.length; i++) for (let j = i + 1; j < sequences.length; j++) {
    let compared = 0, same = 0
    for (let p = 0; p < alignedLength; p++) {
      const a = sequences[i].sequence[p], b = sequences[j].sequence[p]
      if (!a || !b || a === '-' || b === '-') continue
      compared++; if (a.toUpperCase() === b.toUpperCase()) same++
    }
    if (compared) identities.push((same / compared) * 100)
  }
  return {
    sequenceCount: sequences.length,
    alignedLength,
    gapFraction: (gapCharacters / Math.max(1, alignedLength * sequences.length)) * 100,
    variableSites,
    conservedSites,
    meanPairwiseIdentity: identities.length ? identities.reduce((a, b) => a + b, 0) / identities.length : 100,
  }
}

function ProgressTracker({ job }: { job: PhyloJobStatus }) {
  const order: JobPhase[] = ['queued', 'msa_running', 'msa_done', 'tree_running', 'complete']
  const idx = order.indexOf(job.phase)
  return <div className="data-card p-5">
    <div className="flex items-center justify-between"><div><p className="text-sm font-medium text-text-primary">{PHASE_LABELS[job.phase]}</p><p className="mt-1 font-mono text-[10px] text-text-muted">Job {job.job_id}</p></div><span className="font-mono text-xs text-text-muted">{elapsed(job.created_at)}</span></div>
    <div className="mt-4 grid grid-cols-3 gap-2">{['Alignment', 'Inference', 'Result'].map((label, i) => <div key={label} className={`rounded-md border px-3 py-2 text-center text-[11px] font-medium ${idx > i + 1 || job.phase === 'complete' ? 'border-good/25 bg-good/8 text-good' : idx === i + 1 ? 'border-accent-cyan/30 bg-accent-cyan/8 text-accent-cyan' : 'border-glass-border bg-surface-1 text-text-muted'}`}>{label}</div>)}</div>
  </div>
}

export default function PhyloPage() {
  const [fasta, setFasta] = useState('')
  const [method, setMethod] = useState<Method>('nj')
  const [seqType, setSeqType] = useState<SeqType>('protein')
  const [model, setModel] = useState('LG')
  const [bootstrap, setBootstrap] = useState(100)
  const [submitError, setSubmitError] = useState('')
  const [loading, setLoading] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [job, setJob] = useState<PhyloJobStatus | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const audit = useAuditTrail()

  useEffect(() => setModel(seqType === 'protein' ? 'LG' : 'GTR'), [seqType])
  const stopPoll = useCallback(() => { if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null } }, [])
  useEffect(() => () => stopPoll(), [stopPoll])

  const fetchStatus = useCallback(async (id: string) => {
    try {
      const res = await fetch(`/api/backend/phylo/status/${id}`)
      if (!res.ok) return
      const data: PhyloJobStatus = await res.json(); setJob(data)
      if (data.phase === 'complete' || data.phase === 'error') stopPoll()
    } catch { /* polling retries naturally */ }
  }, [stopPoll])

  async function handleSubmit() {
    const sequences = parseFasta(fasta)
    if (sequences.length < 2) return setSubmitError('Enter at least 2 sequences in FASTA format.')
    if (sequences.length > 50) return setSubmitError('Maximum 50 sequences per run.')
    if (sequences.some(s => s.sequence.length < 10)) return setSubmitError('Each sequence must be at least 10 residues/bases.')
    const inputSummary = `method:${method},seqType:${seqType},seqs:${sequences.length}`
    audit.emitStarted('phylo_run', 'PhyML/QuickTree', inputSummary)
    setSubmitError(''); setLoading(true); setJob(null); setJobId(null)
    try {
      const res = await fetch('/api/backend/phylo/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sequences, method, seq_type: seqType, model: method === 'ml' ? model : null, bootstrap: method === 'ml' ? bootstrap : 0 }) })
      if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(typeof d.detail === 'string' ? d.detail : `HTTP ${res.status}`) }
      const { job_id } = await res.json(); setJobId(job_id); await fetchStatus(job_id); intervalRef.current = setInterval(() => fetchStatus(job_id), 3000)
      audit.emitSuccess('phylo_run', 'PhyML/QuickTree', inputSummary, `job_id:${job_id}`)
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Failed to start job'; setSubmitError(message); audit.emitFailed('phylo_run', 'PhyML/QuickTree', inputSummary, message)
    } finally { setLoading(false) }
  }

  function handleReset() { stopPoll(); setJob(null); setJobId(null); setSubmitError(''); setFasta('') }
  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) { const file = e.target.files?.[0]; if (!file) return; const reader = new FileReader(); reader.onload = ev => setFasta((ev.target?.result as string) ?? ''); reader.readAsText(file); e.target.value = '' }

  const seqCount = parseFasta(fasta).length
  const models = seqType === 'protein' ? PROTEIN_MODELS : DNA_MODELS
  const isRunning = Boolean(job && job.phase !== 'complete' && job.phase !== 'error')
  const isDone = job?.phase === 'complete'
  const aln = useMemo(() => alignmentMetrics(job?.aln_fasta), [job?.aln_fasta])

  return <div className="scientific-page max-w-6xl space-y-6 pb-12">
    <BackButton />
    <PageHeader title="Phylogenetic Analysis" subtitle="Alignment-aware evolutionary inference with inspectable tree, support settings, raw Newick and run provenance." />

    {!jobId && <div className="data-card p-6 space-y-5">
      <div className="flex flex-wrap items-center gap-2"><span className="text-xs text-text-muted">Test datasets</span>{Object.entries(DEMOS).map(([key, d]) => <button key={key} onClick={() => { setFasta(d.fasta); setSeqType(d.type) }} className="scientific-chip">{d.label}</button>)}</div>
      <div className="flex gap-2">{(['protein', 'dna'] as SeqType[]).map(t => <button key={t} onClick={() => setSeqType(t)} className={`scientific-segment ${seqType === t ? 'active' : ''}`}>{t.toUpperCase()}</button>)}</div>
      <div><div className="mb-2 flex items-center justify-between"><label className="text-sm font-medium text-text-primary">Input sequences <span className="font-normal text-text-muted">FASTA · 2–50</span></label><button onClick={() => fileRef.current?.click()} className="text-xs text-accent-cyan hover:underline">Upload FASTA</button></div><FlatTextarea rows={9} value={fasta} onChange={e => { setFasta(e.target.value); setSubmitError('') }} placeholder=">Sequence_1\nMVLSPADKTNVKAAWGK...\n>Sequence_2\nMVLSGEDKSNVKAAWGK..." spellCheck={false} className="w-full font-mono"/><div className="mt-2 flex justify-between text-xs text-text-muted"><span>{seqCount} sequences detected</span><span>{seqType.toUpperCase()}</span></div><input ref={fileRef} type="file" accept=".fasta,.fa,.faa,.fna,.txt" className="hidden" onChange={handleFileUpload}/></div>
      <div><label className="mb-2 block text-sm font-medium text-text-primary">Inference method</label><div className="grid gap-3 md:grid-cols-3">{(Object.entries(METHOD_INFO) as [Method, typeof METHOD_INFO[Method]][]).map(([m, info]) => <button key={m} onClick={() => setMethod(m)} className={`scientific-option ${method === m ? 'active' : ''}`}><div className="text-sm font-semibold text-text-primary">{info.label}</div><p className="mt-1 text-xs leading-5 text-text-muted">{info.desc}</p></button>)}</div></div>
      {method === 'ml' && <div className="grid gap-4 rounded-xl border border-glass-border bg-surface-1 p-4 md:grid-cols-2"><div><label className="mb-1.5 block text-xs text-text-muted">Substitution model</label><select value={model} onChange={e => setModel(e.target.value)} className="scientific-select">{models.map(m => <option key={m}>{m}</option>)}</select></div><div><label className="mb-1.5 block text-xs text-text-muted">Bootstrap replicates</label><select value={bootstrap} onChange={e => setBootstrap(Number(e.target.value))} className="scientific-select"><option value={0}>None</option><option value={100}>100</option><option value={500}>500</option><option value={1000}>1000</option></select></div></div>}
      <div className="rounded-lg border border-info/20 bg-info/5 px-4 py-3 text-xs leading-5 text-text-secondary"><strong className="text-text-primary">Interpretation note:</strong> {METHOD_INFO[method].note} A tree is an inference from the selected alignment, model and assumptions; method choice alone does not guarantee biological correctness.</div>
      {submitError && <div className="rounded-lg border border-error/25 bg-error/8 px-4 py-3 text-sm text-error">{submitError}</div>}
      <CriticalButton onClick={handleSubmit} disabled={loading || seqCount < 2} className="w-full py-3">{loading ? 'Starting analysis…' : `Build ${METHOD_INFO[method].label} tree`}</CriticalButton>
    </div>}

    {job && isRunning && <ProgressTracker job={job} />}
    {job?.phase === 'error' && <div className="data-card p-6"><p className="font-semibold text-error">Pipeline error</p><p className="mt-2 text-sm text-text-muted">{job.error}</p><button onClick={handleReset} className="mt-4 scientific-chip">Start over</button></div>}

    {isDone && job && <ScientificResultsWorkspace
      title="Phylogenetic result"
      subtitle={`${METHOD_INFO[job.method].label} · ${job.seq_type.toUpperCase()} · job ${job.job_id}`}
      status="PASS"
      statusLabel="INFERENCE COMPLETE"
      metadata={[{ label: 'Method', value: METHOD_INFO[job.method].label }, { label: 'Model', value: job.model || 'distance method' }, { label: 'Bootstrap', value: job.bootstrap ? `${job.bootstrap} replicates` : 'not requested' }, { label: 'Runtime', value: job.done_at ? `${Math.round(job.done_at - job.created_at)}s` : '—' }]}
      metrics={[
        { label: 'Sequences', value: aln?.sequenceCount ?? seqCount }, { label: 'Alignment length', value: aln ? `${aln.alignedLength} ${job.seq_type === 'dna' ? 'bp' : 'aa'}` : '—' },
        { label: 'Variable sites', value: aln?.variableSites ?? '—' }, { label: 'Conserved sites', value: aln?.conservedSites ?? '—' },
        { label: 'Mean pairwise identity', value: aln ? `${aln.meanPairwiseIdentity.toFixed(1)}%` : '—' }, { label: 'Gap fraction', value: aln ? `${aln.gapFraction.toFixed(1)}%` : '—' },
        { label: 'Bootstrap', value: job.bootstrap ? job.bootstrap : 'N/A', detail: job.method === 'ml' ? 'Replicates requested' : 'Not used for this run' }, { label: 'Tree format', value: job.newick ? 'Newick' : '—' },
      ]}
      overview={<div className="space-y-5">
        <div className="flex flex-wrap gap-2"><button onClick={handleReset} className="scientific-chip">New analysis</button>{job.newick && <button onClick={() => downloadText(`phylogeny-${job.job_id}.nwk`, job.newick!)} className="scientific-chip"><DownloadSimple className="mr-1 inline"/>Newick</button>}{job.aln_fasta && <button onClick={() => downloadText(`alignment-${job.job_id}.fasta`, job.aln_fasta!)} className="scientific-chip"><DownloadSimple className="mr-1 inline"/>Alignment</button>}</div>
        {job.newick && <div className="rounded-xl border border-glass-border bg-surface-1 p-3"><PhyloTreeViewer newick={job.newick} method={job.method} alignment={job.aln_fasta ?? undefined} sequenceType={job.seq_type}/></div>}
        <div className="grid gap-3 md:grid-cols-3"><div className="result-callout"><TreeStructure/><div><b>Inference</b><p>{METHOD_INFO[job.method].label} using {job.model || 'distance-based settings'}.</p></div></div><div className="result-callout"><ChartBar/><div><b>Support</b><p>{job.bootstrap ? `${job.bootstrap} bootstrap replicates requested.` : 'No bootstrap support requested.'}</p></div></div><div className="result-callout"><Dna/><div><b>Alignment</b><p>{aln ? `${aln.sequenceCount} sequences across ${aln.alignedLength} columns.` : 'Alignment metadata unavailable.'}</p></div></div></div>
      </div>}
      qc={<div className="space-y-4"><MetricGrid metrics={[{ label: 'Gap fraction', value: aln ? `${aln.gapFraction.toFixed(2)}%` : '—', detail: 'Alignment gaps across all cells' }, { label: 'Variable sites', value: aln?.variableSites ?? '—' }, { label: 'Conserved sites', value: aln?.conservedSites ?? '—' }, { label: 'Pairwise identity', value: aln ? `${aln.meanPairwiseIdentity.toFixed(2)}%` : '—' }]}/><div className="rounded-lg border border-warn/20 bg-warn/5 p-4 text-xs leading-5 text-text-secondary"><strong className="text-text-primary">Scientific QC:</strong> inspect alignment quality, taxon sampling, rooting, model suitability and branch support before drawing evolutionary conclusions. Bio Nexus reports the evidence; it does not convert tree completion into a biological validation claim.</div></div>}
      results={<div className="space-y-4">{job.newick && <><h3 className="text-sm font-semibold text-text-primary">Interactive tree</h3><PhyloTreeViewer newick={job.newick} method={job.method} alignment={job.aln_fasta ?? undefined} sequenceType={job.seq_type}/></>}{job.stats && <div><h3 className="mb-2 text-sm font-semibold text-text-primary">Engine statistics</h3><pre className="max-h-80 overflow-auto rounded-xl border border-glass-border bg-surface-1 p-4 font-mono text-[11px] leading-5 text-text-secondary">{job.stats}</pre></div>}</div>}
      raw={<div className="space-y-5">{job.newick && <RawEvidence label="Newick tree" value={job.newick}/>} {job.aln_fasta && <RawEvidence label="Multiple sequence alignment · FASTA" value={job.aln_fasta}/>} {job.stats && <RawEvidence label="Phylogeny engine statistics" value={job.stats}/>}</div>}
      methods={<div className="space-y-3"><div className="provenance-grid"><span>Job ID</span><code>{job.job_id}</code><span>Sequence type</span><code>{job.seq_type}</code><span>Inference method</span><code>{METHOD_INFO[job.method].label}</code><span>Substitution model</span><code>{job.model || 'N/A'}</code><span>Bootstrap</span><code>{job.bootstrap || 0}</code><span>Alignment engine</span><code>Clustal Omega pipeline stage</code><span>Tree engine</span><code>{job.method === 'ml' ? 'PhyML' : 'QuickTree/distance workflow'}</code><span>Created</span><code>{new Date(job.created_at * 1000).toISOString()}</code></div></div>}
      ai={<AIResultSummary toolName="phylo" result={{ method: job.method, seq_type: job.seq_type, model: job.model, bootstrap: job.bootstrap, alignment_metrics: aln, newick: job.newick } as unknown as Record<string, unknown>}/>} />}
  </div>
}

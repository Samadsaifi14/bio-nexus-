'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import dynamic from 'next/dynamic'
import { useAuditTrail } from '@/hooks/useAuditTrail'

const PhyloTreeViewer = dynamic(
  () => import('@/components/phylo/PhyloTreeViewer'),
  { ssr: false },
)

type Method   = 'nj' | 'ml' | 'upgma'
type SeqType  = 'protein' | 'dna'
type JobPhase = 'queued' | 'msa_running' | 'msa_done' | 'tree_running' | 'complete' | 'error'

interface PhyloJobStatus {
  job_id:      string
  method:      Method
  seq_type:    SeqType
  model:       string | null
  bootstrap:   number | null
  phase:       JobPhase
  aln_fasta:   string | null
  newick:      string | null
  stats:       string | null
  error:       string | null
  created_at:  number
  msa_done_at: number | null
  done_at:     number | null
}

const PROTEIN_MODELS = ['LG', 'WAG', 'JTT', 'Blosum62', 'MtREV', 'Dayhoff']
const DNA_MODELS     = ['GTR', 'HKY85', 'K80', 'F81', 'TN93', 'SYM']

const METHOD_INFO: Record<Method, { label: string; desc: string; time: string }> = {
  nj:    { label: 'Neighbor-Joining',   desc: 'Fast tree from pairwise distances. Good for exploration and coursework.', time: '~1 min' },
  upgma: { label: 'UPGMA',              desc: 'Ultrametric clustering. Assumes constant evolutionary rate (molecular clock).', time: '~1 min' },
  ml:    { label: 'Maximum Likelihood', desc: 'Statistically rigorous. Returns bootstrap support values. Publication-quality.', time: '3-6 min' },
}

const PHASE_LABELS: Record<JobPhase, string> = {
  queued:      'Waiting to start...',
  msa_running: 'Running Multiple Sequence Alignment (Clustal Omega)...',
  msa_done:    'Alignment complete — building tree...',
  tree_running: 'Building phylogenetic tree...',
  complete:    'Complete',
  error:       'Error',
}

const DEMOS: Record<string, { label: string; type: SeqType; fasta: string }> = {
  globins: {
    label: 'Globins (5 sequences)',
    type: 'protein',
    fasta: `>Human_HBA
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
}

function parseFasta(raw: string): Array<{ id: string; sequence: string }> {
  const seqs: Array<{ id: string; sequence: string }> = []
  let cur: { id: string; seq: string[] } | null = null
  for (const line of raw.split('\n')) {
    const t = line.trim()
    if (t.startsWith('>')) {
      if (cur) seqs.push({ id: cur.id, sequence: cur.seq.join('') })
      cur = { id: t.slice(1).split(/\s+/)[0] || 'Seq', seq: [] }
    } else if (cur && t && !t.startsWith(';')) {
      cur.seq.push(t)
    }
  }
  if (cur) seqs.push({ id: cur.id, sequence: cur.seq.join('') })
  return seqs
}

function elapsed(from: number): string {
  const s = Math.round(Date.now() / 1000 - from)
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`
}

function ProgressTracker({ job }: { job: PhyloJobStatus }) {
  const phaseOrder: JobPhase[] = ['queued', 'msa_running', 'msa_done', 'tree_running', 'complete']
  const currentIdx = phaseOrder.indexOf(job.phase)

  return (
    <div className="glass-card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-text-primary text-sm font-medium">
          {PHASE_LABELS[job.phase]}
        </p>
        <span className="text-text-secondary text-xs">{elapsed(job.created_at)} elapsed</span>
      </div>

      <div className="flex gap-2">
        {(['MSA', 'Tree', 'Done'] as const).map((label, i) => {
          const done   = currentIdx > i + 1 || job.phase === 'complete'
          const active = (i === 0 && job.phase === 'msa_running')
            || (i === 1 && (job.phase === 'msa_done' || job.phase === 'tree_running'))
            || (i === 2 && job.phase === 'complete')
          const cls = job.phase === 'error'
            ? 'border-red-500/40 bg-red-500/10 text-red-400'
            : done
              ? 'border-accent-cyan bg-accent-cyan/10 text-accent-cyan'
              : active
                ? 'border-accent-cyan/50 bg-accent-cyan/5 text-accent-cyan animate-pulse'
                : 'border-glass-border bg-surface-1 text-text-secondary opacity-50'
          return (
            <div key={label}
              className={`flex-1 rounded-lg border px-3 py-2 text-center text-xs font-medium transition-all ${cls}`}>
              {done ? '✓ ' : active ? '⟳ ' : ''}{label}
            </div>
          )
        })}
      </div>

      {job.aln_fasta && job.phase !== 'complete' && (
        <p className="text-emerald-400 text-xs">
          ✓ Alignment ready — {job.aln_fasta.split('\n').filter(l => l.startsWith('>')).length} sequences aligned
        </p>
      )}
    </div>
  )
}

export default function PhyloPage() {
  const [fasta, setFasta]         = useState('')
  const [method, setMethod]       = useState<Method>('nj')
  const [seqType, setSeqType]     = useState<SeqType>('protein')
  const [model, setModel]         = useState('LG')
  const [bootstrap, setBootstrap] = useState(100)
  const [submitError, setSubmitError] = useState('')
  const [loading, setLoading]     = useState(false)
  const [jobId, setJobId]         = useState<string | null>(null)
  const [job, setJob]             = useState<PhyloJobStatus | null>(null)
  const intervalRef               = useRef<ReturnType<typeof setInterval> | null>(null)
  const fileRef                   = useRef<HTMLInputElement>(null)
  const audit                     = useAuditTrail()

  useEffect(() => {
    setModel(seqType === 'protein' ? 'LG' : 'GTR')
  }, [seqType])

  const stopPoll = useCallback(() => {
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null }
  }, [])

  useEffect(() => () => stopPoll(), [stopPoll])

  const fetchStatus = useCallback(async (id: string) => {
    try {
      const res = await fetch(`/api/backend/phylo/status/${id}`)
      if (!res.ok) return
      const data: PhyloJobStatus = await res.json()
      setJob(data)
      if (data.phase === 'complete' || data.phase === 'error') stopPoll()
    } catch { }
  }, [stopPoll])

  async function handleSubmit() {
    const sequences = parseFasta(fasta)
    if (sequences.length < 2) { setSubmitError('Enter at least 2 sequences in FASTA format.'); return }
    if (sequences.length > 50) { setSubmitError('Maximum 50 sequences per run.'); return }
    if (sequences.some(s => s.sequence.length < 10)) { setSubmitError('Each sequence must be at least 10 residues.'); return }

    const inputSummary = `method:${method},seqType:${seqType},seqs:${sequences.length}`
    audit.emitStarted('phylo_run', 'PhyML/QuickTree', inputSummary)

    setSubmitError('')
    setLoading(true)
    setJob(null)
    setJobId(null)

    try {
      const res = await fetch('/api/backend/phylo/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sequences,
          method,
          seq_type: seqType,
          model: method === 'ml' ? model : 'LG',
          bootstrap: method === 'ml' ? bootstrap : 0,
        }),
      })

      if (!res.ok) {
        const d = await res.json().catch(() => ({}))
        const det = d.detail
        throw new Error(
          Array.isArray(det) ? det.map((e: {msg?:string}) => e.msg).join('; ')
          : typeof det === 'string' ? det : `HTTP ${res.status}`
        )
      }

      const { job_id } = await res.json()
      setJobId(job_id)
      await fetchStatus(job_id)
      intervalRef.current = setInterval(() => fetchStatus(job_id), 3000)
      audit.emitSuccess('phylo_run', 'PhyML/QuickTree', inputSummary, `job_id:${job_id}`)
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : 'Failed to start job'
      audit.emitFailed('phylo_run', 'PhyML/QuickTree', inputSummary, errMsg)
      setSubmitError(errMsg)
    } finally {
      setLoading(false)
    }
  }

  function handleReset() {
    stopPoll(); setJob(null); setJobId(null); setSubmitError(''); setFasta('')
  }

  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => setFasta((ev.target?.result as string) ?? '')
    reader.readAsText(file)
    e.target.value = ''
  }

  const seqCount = parseFasta(fasta).length
  const models   = seqType === 'protein' ? PROTEIN_MODELS : DNA_MODELS
  const isRunning = job && job.phase !== 'complete' && job.phase !== 'error'
  const isDone    = job?.phase === 'complete'

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-12">

      <div>
        <h1 className="text-text-primary text-2xl font-bold">Phylogenetic Tree</h1>
        <p className="text-text-secondary text-sm mt-1">
          Build evolutionary trees from protein or DNA sequences — Neighbor-Joining, UPGMA, or Maximum Likelihood.
        </p>
      </div>

      {!jobId && (
        <div className="glass-card p-6 space-y-5">

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-text-secondary text-xs">Demo:</span>
            {Object.entries(DEMOS).map(([key, { label }]) => (
              <button key={key}
                onClick={() => { const d = DEMOS[key]; setFasta(d.fasta); setSeqType(d.type) }}
                className="text-xs px-3 py-1.5 rounded-lg border border-glass-border
                  text-text-secondary hover:text-accent-cyan hover:border-accent-cyan/40 transition-colors">
                {label}
              </button>
            ))}
          </div>

          <div className="flex gap-2">
            {(['protein', 'dna'] as SeqType[]).map(t => (
              <button key={t} onClick={() => setSeqType(t)}
                className={`text-sm px-4 py-1.5 rounded-lg border transition-colors capitalize ${
                  seqType === t
                    ? 'border-accent-cyan text-accent-cyan bg-accent-cyan/10'
                    : 'border-glass-border text-text-secondary hover:text-text-primary'
                }`}>
                {t}
              </button>
            ))}
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-text-secondary text-sm">Sequences (FASTA, 2–50)</label>
              <button onClick={() => fileRef.current?.click()}
                className="text-xs text-text-secondary hover:text-text-primary transition-colors">
                ↑ Upload FASTA
              </button>
            </div>
            <textarea rows={8} value={fasta} onChange={e => setFasta(e.target.value)}
              placeholder={`>Sequence_1\nMVLSPADKTNVKAAWGK...\n>Sequence_2\nMVLSGEDKSNVKAAWGK...`}
              spellCheck={false}
              className="w-full rounded-lg px-3 py-2 text-sm font-mono
                bg-surface-1 border border-glass-border
                focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10
                text-text-primary placeholder-text-secondary/40 outline-none resize-y" />
            {seqCount > 0 && (
              <p className="text-text-secondary text-xs mt-1">
                {seqCount} sequence{seqCount !== 1 ? 's' : ''} detected
                {seqCount < 2 && <span className="text-amber-400 ml-2">— need at least 2</span>}
              </p>
            )}
            <input ref={fileRef} type="file" accept=".fasta,.fa,.faa,.fna,.txt"
              className="hidden" onChange={handleFileUpload} />
          </div>

          <div>
            <label className="block text-text-secondary text-sm mb-2">Method</label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {(Object.entries(METHOD_INFO) as [Method, typeof METHOD_INFO[Method]][]).map(([m, info]) => (
                <button key={m} onClick={() => setMethod(m)}
                  className={`text-left p-3 rounded-xl border transition-all ${
                    method === m
                      ? 'border-accent-cyan bg-accent-cyan/5'
                      : 'border-glass-border bg-surface-1 hover:border-glass-border/80'
                  }`}>
                  <div className={`text-sm font-medium mb-1 ${method === m ? 'text-accent-cyan' : 'text-text-primary'}`}>
                    {info.label}
                  </div>
                  <div className="text-text-secondary text-xs leading-snug">{info.desc}</div>
                  <div className="text-text-secondary text-xs mt-1.5 opacity-60">Est. {info.time}</div>
                </button>
              ))}
            </div>
          </div>

          {method === 'ml' && (
            <div className="grid grid-cols-2 gap-4 p-4 rounded-xl bg-surface-1 border border-glass-border">
              <div>
                <label className="block text-text-secondary text-xs mb-1.5">Substitution model</label>
                <select value={model} onChange={e => setModel(e.target.value)}
                  className="w-full rounded-lg px-3 py-2 text-sm bg-bg border border-glass-border
                    focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10
                    text-text-primary outline-none transition">
                  {models.map(m => (
                    <option key={m} value={m}>
                      {m}{m === (seqType === 'protein' ? 'LG' : 'GTR') ? ' (recommended)' : ''}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-text-secondary text-xs mb-1.5">Bootstrap replicates</label>
                <select value={bootstrap} onChange={e => setBootstrap(Number(e.target.value))}
                  className="w-full rounded-lg px-3 py-2 text-sm bg-bg border border-glass-border
                    focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10
                    text-text-primary outline-none transition">
                  <option value={0}>None (fast)</option>
                  <option value={100}>100 (standard)</option>
                  <option value={500}>500 (thorough)</option>
                  <option value={1000}>1000 (publication)</option>
                </select>
              </div>
              <p className="col-span-2 text-text-secondary text-xs opacity-60">
                LG = best-fit model for most proteins (Le &amp; Gascuel 2008). GTR = most general DNA model.
                Bootstrap ≥ 70 = supported; ≥ 95 = strongly supported.
              </p>
            </div>
          )}

          {submitError && (
            <p className="text-red-400 text-sm bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
              {submitError}
            </p>
          )}

          <button onClick={handleSubmit} disabled={loading || seqCount < 2}
            className="btn-primary w-full py-3 text-sm font-semibold
              disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2">
            {loading
              ? <><span className="animate-spin">⟳</span> Starting...</>
              : `▶ Build ${METHOD_INFO[method].label} Tree`}
          </button>
        </div>
      )}

      {job && isRunning && <ProgressTracker job={job} />}

      {job?.phase === 'error' && (
        <div className="glass-card p-6 space-y-4">
          <p className="text-red-400 font-medium">Pipeline error</p>
          <p className="text-text-secondary text-sm">{job.error}</p>
          <button onClick={handleReset} className="btn-primary text-sm px-4 py-2">← Try again</button>
        </div>
      )}

      {isDone && job && (
        <div className="space-y-5">
          <div className="glass-card p-4 flex flex-wrap gap-4 items-center">
            <div className="flex gap-4 text-sm flex-wrap flex-1">
              <span className="text-text-secondary">
                Method: <span className="text-text-primary font-medium">{METHOD_INFO[job.method].label}</span>
              </span>
              {job.model && (
                <span className="text-text-secondary">
                  Model: <span className="text-text-primary font-medium">{job.model}</span>
                </span>
              )}
              {job.bootstrap != null && job.bootstrap > 0 && (
                <span className="text-text-secondary">
                  Bootstrap: <span className="text-text-primary font-medium">{job.bootstrap} replicates</span>
                </span>
              )}
              {job.done_at && (
                <span className="text-text-secondary">
                  Time: <span className="text-text-primary font-medium">{Math.round(job.done_at - job.created_at)}s</span>
                </span>
              )}
            </div>
            <button onClick={handleReset}
              className="text-sm px-4 py-1.5 rounded-lg border border-glass-border
                text-text-secondary hover:text-text-primary transition-colors">
              New analysis
            </button>
          </div>

          {job.newick && (
            <div className="glass-card p-5">
              <PhyloTreeViewer
                newick={job.newick}
                method={job.method}
                alignment={job.aln_fasta ?? undefined}
                sequenceType={job.seq_type}
              />
            </div>
          )}

          {job.stats && (
            <div className="border border-glass-border rounded-xl overflow-hidden">
              <details>
                <summary className="px-4 py-3 text-sm text-text-secondary hover:text-text-primary cursor-pointer">
                  PhyML statistics
                </summary>
                <pre className="overflow-auto p-4 text-xs font-mono text-text-secondary bg-surface-1 max-h-60">
                  {job.stats}
                </pre>
              </details>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

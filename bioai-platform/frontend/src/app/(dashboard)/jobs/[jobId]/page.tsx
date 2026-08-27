'use client';

import { useEffect, useState, useRef, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { CircleNotch as LoaderCircle, Dna, WarningCircle as AlertCircle, ShareNetwork, Download, MagnifyingGlass as Search, Clock, WifiSlash as WifiOff, TestTube as FlaskConical } from '@phosphor-icons/react';
import toast from 'react-hot-toast';
import type { JobStatus, JobStepStatus } from '@/types/pipeline';
import { STEP_LABELS } from '@/types/pipeline';
import { AIInterpretation } from '@/components/results/AIInterpretation';
import { BlastPanel } from '@/components/results/BlastPanel';
import { ScoreBars } from '@/components/results/ScoreBars';
import { UniprotPanel } from '@/components/results/UniprotPanel';
import { DeNovoPanel } from '@/components/results/DeNovoPanel';
import { ConfidenceBadge } from '@/components/results/ConfidenceBadge';
import { FinalReport } from '@/components/results/FinalReport';
import { AlphaFoldViewer } from '@/components/AlphaFoldViewer';
import { PathwayEnrichment } from '@/components/results/PathwayEnrichment';
import { getJob, createShareLink } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import { buildShareUrl, buildShareMessage, buildShareDetails, type ShareDetails } from '@/lib/share';
import { ShareDialog } from '@/components/share/ShareDialog';
import { motion } from 'framer-motion';
import { fadeUp, stagger, cardHover } from '@/lib/animations';
import { DomainArchitecture } from '@/components/domains/DomainArchitecture';
import { StringDBViewer } from '@/components/interactions/StringDBViewer';
import PhyloTreeViewer from '@/components/phylo/PhyloTreeViewer';
import { AlignmentStatsBar } from '@/components/alignment/AlignmentStatsBar';
import { AlignmentBlock } from '@/components/alignment/AlignmentBlock';
import { computeAlignmentStats, parseAlignedFasta } from '@/lib/alignment-stats';
import { SecondaryStructureViewer } from '@/components/structure/SecondaryStructure';
import { RamachandranPlot } from '@/components/structure/RamachandranPlot';
import { StructureComparison } from '@/components/structure/StructureComparison';
import { BackButton, CriticalButton } from '@/components/ui';
import { setPrefill } from '@/lib/cross-link';
import { downloadText } from '@/lib/export-utils';
import { JobGraph } from '@/components/pipeline/JobGraph';
import { branchFromJob } from '@/lib/api';

const STEP_ORDER = ['blast', 'uniprot', 'msa', 'phylo', 'domains', 'pathway_enrichment', 'alphafold', 'interpret'];

const STATUS_ORDER: JobStepStatus[] = [
  'queued', 'running', 'submitted_to_ncbi', 'polling_ncbi', 'parsing', 'fetching_uniprot', 'running_msa', 'interpreting', 'pathway_enrichment', 'fetching_alphafold', 'complete',
];
const POLL_TIMEOUT_MS = 65 * 60 * 1000;

export default function JobPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.jobId as string;
  const [job, setJob] = useState<JobStatus | null>(null);
  const [shareOpen, setShareOpen] = useState(false);
  const [shareCreating, setShareCreating] = useState(false);
  const [shareLink, setShareLink] = useState('');
  const [shareDetails, setShareDetails] = useState<ShareDetails | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [pollError, setPollError] = useState<string | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const [activeAnalysisTab, setActiveAnalysisTab] = useState<string | null>(null);
  const startRef = useRef(Date.now());

  // Full-length subject sequences from the MSA (headers may carry a `_aln`
  // suffix or a versioned accession), used by BLAST "Dot plot vs query" links
  // so the comparison runs against the whole protein, not just the aligned hit.
  const fullHitSequences = useMemo(() => {
    const map: Record<string, string> = {};
    const fasta = job?.context_json?.msa?.aln_fasta;
    if (!fasta) return map;
    const { headers, seqs } = parseAlignedFasta(fasta);
    headers.forEach((header, i) => {
      const clean = seqs[i].replace(/[^A-Za-z]/g, '');
      const id = header.trim();
      map[id] = clean;
      map[id.replace(/_aln$/, '')] = clean;
      map[id.replace(/\.\d+$/, '')] = clean;
    });
    return map;
  }, [job?.context_json?.msa?.aln_fasta]);

  useEffect(() => {
    let cancelled = false;
    let pollTimer: ReturnType<typeof setTimeout>;
    startRef.current = Date.now();

    const poll = async () => {
      if (Date.now() - startRef.current > POLL_TIMEOUT_MS) {
        if (!cancelled) setTimedOut(true);
        setLoading(false);
        return;
      }
      try {
        const data = await getJob(jobId);
        if (!cancelled) {
          setPollError(null);
          setJob(data);
          const terminal = ['complete', 'failed'];
          if (terminal.includes(data.status)) {
            setLoading(false);
            return;
          }
        }
      } catch {
        if (!cancelled) {
          setPollError('Connection lost — retrying...');
          setLoading(false);
        }
      }
      if (!cancelled) pollTimer = setTimeout(poll, 3000);
    };
    poll();
    return () => { cancelled = true; clearTimeout(pollTimer); };
  }, [jobId]);

  if (loading && !job && !timedOut) {
    return (
      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="flex items-center justify-center py-20">
        <div className="text-center">
          <LoaderCircle className="w-8 h-8 text-accent-cyan animate-spin mx-auto mb-4" />
          <p className="text-sm text-text-secondary">Loading job...</p>
        </div>
      </motion.div>
    );
  }

  if (!job && timedOut) {
    return (
      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="max-w-xl mx-auto py-12">
        <div className="glass-card p-8 text-center">
          <Clock className="w-12 h-12 text-accent-amber mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-text-primary mb-2">Still processing</h3>
          <p className="text-sm text-text-secondary mb-6">
            This job is taking longer than expected. It&apos;s still running — your results will be saved.
            Check back later at this URL.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="btn-critical text-sm"
          >
            Refresh
          </button>
        </div>
      </motion.div>
    );
  }

  if (!job) {
    return (
      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-16 text-center">
        <Dna className="w-16 h-16 text-text-muted mx-auto mb-6" />
        <h3 className="text-xl font-semibold text-text-primary mb-2">Job not found</h3>
        <p className="text-sm text-text-secondary">This job does not exist or has been deleted.</p>
      </motion.div>
    );
  }

  const isActive = ['queued', 'running', 'submitted_to_ncbi', 'polling_ncbi', 'parsing', 'fetching_uniprot', 'running_msa', 'interpreting', 'pathway_enrichment', 'fetching_alphafold'].includes(job.status);
  const currentIdx = STATUS_ORDER.indexOf(job.status as JobStepStatus);

  if (isActive) {
    return (
      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="max-w-xl mx-auto py-12">
        <div className="glass-card p-8 text-center">
          {pollError ? (
            <div className="mb-6">
              <div className="w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                <WifiOff className="w-10 h-10 text-accent-amber" />
              </div>
              <p className="text-sm text-accent-amber font-medium mb-1">{pollError}</p>
              <p className="text-xs text-text-muted">Still processing — your results will be saved.</p>
            </div>
          ) : (
            <>
              <div className="relative w-16 h-16 mx-auto mb-6">
                <div className="absolute inset-0 rounded-full bg-accent-cyan/20 animate-ping" />
                <div className="relative w-16 h-16 rounded-full bg-accent-cyan flex items-center justify-center">
                  <Dna className="w-8 h-8 text-void" />
                </div>
              </div>
              <p className="text-lg font-semibold text-text-primary mb-2">
                {job.current_step_label || STEP_LABELS[job.status as JobStepStatus] || 'Processing...'}
              </p>
            </>
          )}
          <p className="text-sm text-text-secondary mb-8">
            Usually 30s–3min depending on NCBI load. You can close this tab and come back later.
          </p>

          <div className="max-w-sm mx-auto space-y-3">
            {STATUS_ORDER.map((s, i) => {
              const isActiveStep = currentIdx === i;
              const isDone = currentIdx > i;
              return (
                <div key={s} className="flex items-center gap-3">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
                    isDone ? 'bg-accent-cyan' : isActiveStep ? 'bg-accent-cyan/20 border-2 border-accent-cyan' : 'bg-surface-1'
                  }`}>
                    {isDone && <span className="text-void text-xs">✓</span>}
                    {isActiveStep && <div className="w-2 h-2 rounded-full bg-accent-cyan animate-pulse" />}
                  </div>
                  <span className={`text-sm ${isActiveStep ? 'font-medium text-text-primary' : isDone ? 'text-text-secondary' : 'text-text-muted'}`}>
                    {STEP_LABELS[s]}
                  </span>
                </div>
              );
            })}
          </div>

          <div className="mt-8 glass p-4 text-left border border-accent-amber/20">
            <p className="text-xs text-accent-amber">
              <strong>This result is saved.</strong> You can close this tab and return to this URL later.
            </p>
            <p className="text-xs text-accent-amber/80 mt-2">
              Saved for 24 hours. Create a free account to keep it forever.
            </p>
          </div>
        </div>
      </motion.div>
    );
  }

  if (job.status === 'failed') {
    const errorMsg = job.error_message || job.error || 'An unknown error occurred';
    const failedStepMatch = errorMsg.match(/Pipeline failed at (\w+):/);
    const failedStep = failedStepMatch ? failedStepMatch[1] : null;
    const isTimeout = errorMsg.toLowerCase().includes('timed out') || errorMsg.toLowerCase().includes('timeout');
    const isNcbiError = errorMsg.toLowerCase().includes('ncbi') || errorMsg.toLowerCase().includes('blast');
    const isParseError = errorMsg.toLowerCase().includes('parse');
    const isUniProtError = errorMsg.toLowerCase().includes('uniprot') || errorMsg.toLowerCase().includes('mapping');
    return (
      <div className="max-w-xl mx-auto py-12">
        <div className="glass-card p-8 text-center border border-error/20">
          <AlertCircle className="w-12 h-12 text-error mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-text-primary mb-2">Analysis Failed</h3>
          <div className="glass bg-error/5 p-4 mb-6 text-left">
            <p className="text-xs text-error font-mono leading-relaxed">{errorMsg}</p>
          </div>
          <div className="space-y-2">
            {isTimeout && (
              <p className="text-sm text-accent-amber bg-accent-amber/5 rounded-lg p-3 border border-accent-amber/20">
                External servers are slow right now. Wait a moment and try again.
              </p>
            )}
            {isNcbiError && (
              <p className="text-sm text-accent-amber bg-accent-amber/5 rounded-lg p-3 border border-accent-amber/20">
                The BLAST service returned an error. This is usually temporary — please try again.
              </p>
            )}
            {isParseError && (
              <p className="text-sm text-accent-amber bg-accent-amber/5 rounded-lg p-3 border border-accent-amber/20">
                We couldn&apos;t read the results from the BLAST service. The data may have been in an unexpected format.
              </p>
            )}
          </div>
          <div className="flex items-center justify-center gap-3 mt-6">
            <CriticalButton onClick={() => router.push('/analyze')}>
              New Analysis
            </CriticalButton>
            <button
              onClick={() => window.location.reload()}
              className="glass-card px-6 py-2.5 text-sm text-text-secondary hover:bg-surface-2 transition"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  const context = job.context_json;

  if (!context) {
    return (
      <div className="glass-card p-8 text-center">
        <h3 className="text-lg font-semibold text-text-primary mb-2">No results data</h3>
        <p className="text-sm text-text-secondary">This job has no result data.</p>
      </div>
    );
  }

  const hasHits = context.blast && context.blast.hits && context.blast.hits.length > 0;
  const confidence = context.query?.confidence;
  const isDeNovo = context.uniprot?._de_novo === true || confidence === 'de_novo';

  return (
    <motion.div variants={stagger} initial={{ y: 24 }} animate="show" className="space-y-6">
      <BackButton href="/jobs" label="Back to Jobs" />

      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary mb-1">Analysis Results</h1>
          <p className="text-sm text-text-secondary">
            {context.query?.accession
              ? <>Query: <code className="font-mono text-accent-cyan">{context.query.accession}</code></>
              : <>Query: {context.query?.sequence?.slice(0, 80) ?? ''}...</>
            } ({context.query?.length ?? '?'} {context.query?.sequence_type === 'dna' ? 'bp' : 'aa'})
          </p>
        </div>
        <CriticalButton
          onClick={async () => {
            setShareCreating(true);
            try {
              const { url } = await createShareLink(jobId);
              const link = buildShareUrl(url);
              setShareLink(link);
              setShareDetails(buildShareDetails(context));
              setShareOpen(true);
            } catch (err) {
              toast.error(extractErrorMessage(err, 'Failed to create share link'));
            } finally {
              setShareCreating(false);
            }
          }}
          disabled={shareCreating}
          className="flex items-center gap-2"
        >
          {shareCreating ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <ShareNetwork className="w-4 h-4" />}
          Share
        </CriticalButton>
      </motion.div>

      <motion.div variants={fadeUp} className="glass-card p-4">
        <JobGraph
          jobId={jobId}
          onNodeClick={(id) => router.push(`/jobs/${id}`)}
          onBranch={async (sourceId) => {
            try {
              const { job_id } = await branchFromJob(sourceId, STEP_ORDER);
              toast.success('Branched — new job started');
              router.push(`/jobs/${job_id}`);
            } catch (err) {
              toast.error(extractErrorMessage(err, 'Failed to branch'));
            }
          }}
        />
      </motion.div>

      <motion.div variants={fadeUp} whileHover={cardHover}>
        {context.final_report && <FinalReport data={context.final_report} />}
        <AIInterpretation context={context} pipelineType={job.pipeline_type} />
      </motion.div>

      {!hasHits && !isDeNovo ? (
        <motion.div variants={fadeUp} whileHover={cardHover} className="glass-card p-10 text-center">
          <Search className="w-12 h-12 text-text-muted mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-text-primary mb-2">No significant similarity found</h3>
          <p className="text-sm text-text-secondary max-w-md mx-auto">
            BLAST completed but found no statistically significant matches in the database.
            This could mean your sequence is novel, highly divergent, or the database doesn&apos;t contain close relatives.
          </p>
          <div className="mt-6 glass p-4 text-left text-sm text-text-secondary">
            <p className="font-medium text-text-primary mb-2">What this can mean:</p>
            <ul className="space-y-1.5 list-disc pl-5">
              <li>Your sequence may be from a poorly characterized organism</li>
              <li>The protein could be a novel family member with low sequence conservation</li>
              <li>Try searching against a different database (e.g., nr instead of Swiss-Prot)</li>
              <li>Consider checking your sequence for frame-shift errors if it&apos;s a nucleotide translation</li>
            </ul>
          </div>
          <CriticalButton onClick={() => router.push('/analyze')} className="mt-6">
            New Analysis
          </CriticalButton>
        </motion.div>
      ) : (
        <>
          {(confidence || isDeNovo) && (
            <motion.div variants={fadeUp} className="flex items-center gap-3 flex-wrap">
              <ConfidenceBadge confidence={isDeNovo ? 'de_novo' : confidence} />
              {isDeNovo && (
                <span className="text-xs text-text-muted">
                  No homolog found — annotations below are predictions computed from your sequence.
                </span>
              )}
            </motion.div>
          )}

          {!isDeNovo && (
            <motion.div variants={fadeUp} whileHover={cardHover}>
              <div className="grid lg:grid-cols-2 gap-6">
                <BlastPanel
                  hits={context.blast.hits}
                  count={context.blast.count}
                  source={context.blast?.source ?? 'NCBI BLAST'}
                  querySequence={context.query?.sequence}
                  fullSequences={fullHitSequences}
                />
                {context.uniprot && !context.uniprot._de_novo && <UniprotPanel data={context.uniprot} />}
              </div>
            </motion.div>
          )}

          {isDeNovo && context.uniprot?._de_novo && (
            <motion.div variants={fadeUp} whileHover={cardHover}>
              <DeNovoPanel data={context.uniprot} />
            </motion.div>
          )}

          {!isDeNovo && hasHits && (
            <motion.div variants={fadeUp} whileHover={cardHover}>
              <ScoreBars hits={context.blast.hits} />
            </motion.div>
          )}

          {context.msa?.aln_fasta && (
            <motion.div variants={fadeUp} whileHover={cardHover} className="data-card p-4">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <h3 className="text-sm font-semibold text-text-primary">Multiple Sequence Alignment</h3>
                  <p className="text-xs text-text-muted mt-0.5">{context.msa.sequence_count ?? 0} sequences aligned via Clustal Omega</p>
                </div>
                <button
                  onClick={() => {
                    const fasta = context.msa?.aln_fasta;
                    if (!fasta) return;
                    downloadText(fasta, `msa-${jobId.slice(0, 8)}.fasta`);
                  }}
                  className="px-3 py-1.5 rounded-lg border border-glass-border text-xs text-text-secondary hover:bg-surface-1 transition"
                >
                  <Download className="w-3.5 h-3.5 inline mr-1" />FASTA
                </button>
              </div>
              <AlignmentStatsBar
                stats={computeAlignmentStats(parseAlignedFasta(context.msa.aln_fasta).seqs)}
                className="mb-2"
              />
              <AlignmentBlock alnFasta={context.msa.aln_fasta} className="max-h-80" />
            </motion.div>
          )}

          {(() => {
            const newick = context.phylo?.phylotree_newick || context.phylo_data?.phylotree_newick || context.msa?.phylotree;
            return newick ? (
              <motion.div variants={fadeUp} whileHover={cardHover} className="data-card p-4">
                <h3 className="text-sm font-semibold text-text-primary mb-2">Phylogenetic Tree</h3>
                <PhyloTreeViewer newick={newick} />
              </motion.div>
            ) : null;
          })()}

          {context.alphafold && context.alphafold.structure_available && (
            <motion.div variants={fadeUp} whileHover={cardHover}>
              <AlphaFoldViewer
                pdbUrl={context.alphafold.pdb_url}
                pdbData={context.alphafold.pdb_text}
                uniprotId={context.alphafold.uniprot_accession ?? undefined}
              />
              <div className="mt-2 flex items-center justify-end">
                {context.alphafold.pdb_url ? (
                  <button
                    onClick={() => {
                      const url = context.alphafold?.pdb_url;
                      if (url) router.push(`/analyze/docking?pdb_url=${encodeURIComponent(url)}`);
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-cyan/10 text-accent-cyan text-xs font-medium hover:bg-accent-cyan/20 transition border border-accent-cyan/20"
                  >
                    <FlaskConical className="w-3.5 h-3.5" />
                    Dock with this structure
                  </button>
                ) : (
                  isDeNovo && (
                    <span className="text-xs text-text-muted">
                      Predicted structure (ESMFold) — docking requires an experimentally determined receptor.
                    </span>
                  )
                )}
              </div>
            </motion.div>
          )}

          {context.pathway_enrichment ? (
            <motion.div variants={fadeUp} whileHover={cardHover}>
              <PathwayEnrichment data={context.pathway_enrichment} />
            </motion.div>
          ) : isDeNovo ? (
            <motion.div variants={fadeUp} className="data-card p-5 border border-dashed border-glass-border">
              <h3 className="text-sm font-semibold text-text-primary">Pathway enrichment</h3>
              <p className="text-xs text-text-muted mt-1">
                Unavailable for de novo sequences — pathway databases require an identified organism or gene.
              </p>
            </motion.div>
          ) : null}

          <div className="flex items-center gap-3 pt-2 flex-wrap">
            {!isDeNovo && (
              <button
                onClick={() => {
                  const csv = [['Accession', 'Description', 'E-value', '% Identity', 'Bit Score'].join(',')]
                    .concat((context.blast?.hits || []).map((h: import('@/types/pipeline').BlastHitSummary) => [h.accession, `"${h.description}"`, h.evalue_raw ?? h.evalue, h.identity_pct, h.bit_score].join(',')))
                    .join('\n');
                  const blob = new Blob([csv], { type: 'text/csv' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `blast-results-${jobId.slice(0, 8)}.csv`;
                  a.click();
                  URL.revokeObjectURL(url);
                  toast.success('Downloaded as CSV');
                }}
                className="btn-critical text-sm flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                Download CSV
              </button>
            )}
            {(() => {
              const uniprotAcc = context.uniprot?.accession;
              const geneName = context.uniprot?.gene_names?.[0] ?? null;
              const pdbId = context.uniprot?.pdb_ids?.[0] ?? null;
              return (
                <>
                  {uniprotAcc && (
                    <button onClick={() => setPrefill(router, 'domains_accession', uniprotAcc, '/analyze/domains')}
                      className="glass-card px-4 py-2.5 text-xs text-text-secondary flex items-center gap-2 hover:bg-surface-2 hover:text-accent-cyan transition">
                      Domains
                    </button>
                  )}
                  {uniprotAcc && (
                    <button onClick={() => setPrefill(router, 'structure_query', uniprotAcc, '/analyze/structure')}
                      className="glass-card px-4 py-2.5 text-xs text-text-secondary flex items-center gap-2 hover:bg-surface-2 hover:text-accent-cyan transition">
                      Structure
                    </button>
                  )}
                  {geneName && (
                    <button onClick={() => setPrefill(router, 'interaction_gene', geneName, '/analyze/interactions')}
                      className="glass-card px-4 py-2.5 text-xs text-text-secondary flex items-center gap-2 hover:bg-surface-2 hover:text-accent-cyan transition">
                      Interactions
                    </button>
                  )}
                  {pdbId && (
                    <button onClick={() => setPrefill(router, 'docking_pdb_id', pdbId, '/analyze/docking')}
                      className="glass-card px-4 py-2.5 text-xs text-text-secondary flex items-center gap-2 hover:bg-surface-2 hover:text-accent-cyan transition">
                      Docking
                    </button>
                  )}
                  {pdbId && (
                    <button onClick={() => setPrefill(router, 'md_pdb_id', pdbId, '/analyze/md')}
                      className="glass-card px-4 py-2.5 text-xs text-text-secondary flex items-center gap-2 hover:bg-surface-2 hover:text-accent-cyan transition">
                      MD
                    </button>
                  )}
                  {pdbId && (
                    <button onClick={() => setPrefill(router, 'function_pdb_id', pdbId, '/analyze/function')}
                      className="glass-card px-4 py-2.5 text-xs text-text-secondary flex items-center gap-2 hover:bg-surface-2 hover:text-accent-cyan transition">
                      Function
                    </button>
                  )}
                </>
              );
            })()}
          </div>

          {/* Advanced Analysis section */}
          {(() => {
            const uniprotAcc = context.uniprot?.accession;
            const geneName = context.uniprot?.gene_names?.[0] ?? null;
            const pdbId = context.uniprot?.pdb_ids?.[0] ?? null;

            const analysisTabs: { id: string; label: string; available: boolean; component: React.ReactNode }[] = [
              { id: "doms", label: "Domains",     available: !!uniprotAcc, component: uniprotAcc ? <>
                <DomainArchitecture accession={uniprotAcc} />
                {pdbId && <div className="mt-3 pt-3 border-t border-glass-border flex items-center justify-end">
                  <button onClick={() => router.push(`/analyze/docking?pdb_id=${pdbId}`)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-cyan/10 text-accent-cyan text-xs font-medium hover:bg-accent-cyan/20 transition">
                    <FlaskConical className="w-3.5 h-3.5" /> Dock at binding site (F5)
                  </button>
                </div>}
              </> : null },
              { id: "net",  label: "Interactions", available: !!geneName,   component: geneName ? <StringDBViewer geneName={geneName} initialData={context.interactions ?? null} /> : null },
              { id: "ss",   label: "2° Structure", available: !!uniprotAcc, component: uniprotAcc ? <SecondaryStructureViewer identifier={uniprotAcc} /> : null },
              { id: "rama", label: "Ramachandran", available: !!uniprotAcc, component: uniprotAcc ? <RamachandranPlot pdbId={pdbId} /> : null },
              { id: "comp", label: "Comparison",   available: !!pdbId,     component: pdbId ? <>
                <StructureComparison pdbId={pdbId} />
                <div className="mt-3 pt-3 border-t border-glass-border flex items-center justify-end">
                  <button onClick={() => router.push(`/analyze/docking?pdb_id=${pdbId}`)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-cyan/10 text-accent-cyan text-xs font-medium hover:bg-accent-cyan/20 transition">
                    <FlaskConical className="w-3.5 h-3.5" /> Use top match as docking receptor (F7)
                  </button>
                </div>
              </> : null },
            ];

            const available = analysisTabs.filter(t => t.available);
            if (available.length === 0) return null;

            return (
              <motion.div variants={fadeUp} className="data-card p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-text-primary">Advanced Analysis</h3>
                  <div className="flex gap-2 flex-wrap">
                    {available.map(tab => (
                      <button key={tab.id}
                        onClick={() => setActiveAnalysisTab(activeAnalysisTab === tab.id ? null : tab.id)}
                        className={`px-3 py-1 rounded-full text-xs border transition ${
                          activeAnalysisTab === tab.id
                            ? "border-accent-cyan bg-accent-cyan/10 text-accent-cyan"
                            : "border-glass-border text-text-muted hover:border-white/20"
                        }`}>
                        {tab.label}
                      </button>
                    ))}
                  </div>
                </div>
                {activeAnalysisTab && (
                  <motion.div
                    key={activeAnalysisTab}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                    className="border-t border-glass-border pt-4"
                  >
                    {analysisTabs.find(t => t.id === activeAnalysisTab)?.component}
                  </motion.div>
                )}
              </motion.div>
            );
          })()}
        </>
      )}

      <ShareDialog
        open={shareOpen}
        onClose={() => setShareOpen(false)}
        url={shareLink}
        message={buildShareMessage(shareLink, shareDetails)}
      />
    </motion.div>
  );
}

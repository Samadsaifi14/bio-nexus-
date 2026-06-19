'use client';

import { useEffect, useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { LoaderCircle, Dna, AlertCircle, Copy, Download, Search, Clock, WifiOff } from 'lucide-react';
import toast from 'react-hot-toast';
import type { JobStatus, JobStepStatus } from '@/types/pipeline';
import { STEP_LABELS } from '@/types/pipeline';
import { AIInterpretation } from '@/components/results/AIInterpretation';
import { BlastPanel } from '@/components/results/BlastPanel';
import { ScoreBars } from '@/components/results/ScoreBars';
import { UniprotPanel } from '@/components/results/UniprotPanel';
import { AlphaFoldViewer } from '@/components/AlphaFoldViewer';
import { PathwayEnrichment } from '@/components/results/PathwayEnrichment';
import { getJob } from '@/lib/api';
import { motion } from 'framer-motion';
import { fadeUp, stagger, cardHover } from '@/lib/animations';

const STATUS_ORDER: JobStepStatus[] = [
  'queued', 'submitted_to_ncbi', 'polling_ncbi', 'parsing', 'interpreting', 'fetching_alphafold', 'complete',
];
const POLL_TIMEOUT_MS = 10 * 60 * 1000;

export default function JobPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.jobId as string;
  const [job, setJob] = useState<JobStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [pollError, setPollError] = useState<string | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const startRef = useRef(Date.now());

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
        if (!cancelled) setPollError('Connection lost — retrying...');
      }
      if (!cancelled) pollTimer = setTimeout(poll, 3000);
    };
    poll();
    return () => { cancelled = true; clearTimeout(pollTimer); };
  }, [jobId]);

  if (loading && !job && !timedOut) {
    return (
      <motion.div variants={fadeUp} initial="hidden" animate="show" className="flex items-center justify-center py-20">
        <div className="text-center">
          <LoaderCircle className="w-8 h-8 text-accent-cyan animate-spin mx-auto mb-4" />
          <p className="text-sm text-text-secondary">Loading job...</p>
        </div>
      </motion.div>
    );
  }

  if (!job && timedOut) {
    return (
      <motion.div variants={fadeUp} initial="hidden" animate="show" className="max-w-xl mx-auto py-12">
        <div className="glass-card p-8 text-center">
          <Clock className="w-12 h-12 text-accent-amber mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-text-primary mb-2">Still processing</h3>
          <p className="text-sm text-text-secondary mb-6">
            This job is taking longer than expected. It's still running — your results will be saved.
            Check back later at this URL.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="btn-primary px-6 py-2.5 text-sm"
          >
            Refresh
          </button>
        </div>
      </motion.div>
    );
  }

  if (!job) {
    return (
      <motion.div variants={fadeUp} initial="hidden" animate="show" className="glass-card p-16 text-center">
        <Dna className="w-16 h-16 text-text-muted mx-auto mb-6" />
        <h3 className="text-xl font-semibold text-text-primary mb-2">Job not found</h3>
        <p className="text-sm text-text-secondary">This job does not exist or has been deleted.</p>
      </motion.div>
    );
  }

  const isActive = ['queued', 'submitted_to_ncbi', 'polling_ncbi', 'parsing', 'interpreting'].includes(job.status);
  const currentIdx = STATUS_ORDER.indexOf(job.status as JobStepStatus);

  if (isActive) {
    return (
      <motion.div variants={fadeUp} initial="hidden" animate="show" className="max-w-xl mx-auto py-12">
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
                  <Dna className="w-8 h-8 text-white" />
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
                    {isDone && <span className="text-white text-xs">✓</span>}
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
    const isTimeout = errorMsg.toLowerCase().includes('timed out') || errorMsg.toLowerCase().includes('timeout');
    const isNcbiError = errorMsg.toLowerCase().includes('ncbi') || errorMsg.toLowerCase().includes('blast');
    const isParseError = errorMsg.toLowerCase().includes('parse');
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
                NCBI returned an error. This is usually temporary — please try again.
              </p>
            )}
            {isParseError && (
              <p className="text-sm text-accent-amber bg-accent-amber/5 rounded-lg p-3 border border-accent-amber/20">
                We couldn't read the results from NCBI. The data may have been in an unexpected format.
              </p>
            )}
          </div>
          <div className="flex items-center justify-center gap-3 mt-6">
            <button
              onClick={() => router.push('/analyze')}
              className="btn-primary px-6 py-2.5 text-sm"
            >
              New Analysis
            </button>
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

  return (
    <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-6">
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary mb-1">Analysis Results</h1>
          <p className="text-sm text-text-secondary">
            Query: {context.query?.sequence?.slice(0, 80) ?? ''}... ({context.query?.length ?? '?'} aa)
          </p>
        </div>
        <button
          onClick={() => { navigator.clipboard.writeText(window.location.href); toast.success('Link copied!'); }}
          className="btn-primary px-4 py-2 text-sm flex items-center gap-2"
        >
          <Copy className="w-4 h-4" />
          Share
        </button>
      </motion.div>

      <motion.div variants={fadeUp} whileHover={cardHover}>
        <AIInterpretation context={context} pipelineType={job.pipeline_type} />
      </motion.div>

      {!hasHits ? (
        <motion.div variants={fadeUp} whileHover={cardHover} className="glass-card p-10 text-center">
          <Search className="w-12 h-12 text-text-muted mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-text-primary mb-2">No significant similarity found</h3>
          <p className="text-sm text-text-secondary max-w-md mx-auto">
            BLAST completed but found no statistically significant matches in the database.
            This could mean your sequence is novel, highly divergent, or the database doesn't contain close relatives.
          </p>
          <div className="mt-6 glass p-4 text-left text-sm text-text-secondary">
            <p className="font-medium text-text-primary mb-2">What this can mean:</p>
            <ul className="space-y-1.5 list-disc pl-5">
              <li>Your sequence may be from a poorly characterized organism</li>
              <li>The protein could be a novel family member with low sequence conservation</li>
              <li>Try searching against a different database (e.g., nr instead of Swiss-Prot)</li>
              <li>Consider checking your sequence for frame-shift errors if it's a nucleotide translation</li>
            </ul>
          </div>
          <button
            onClick={() => router.push('/analyze')}
            className="mt-6 btn-primary px-6 py-2.5 text-sm"
          >
            New Analysis
          </button>
        </motion.div>
      ) : (
        <>
          <motion.div variants={fadeUp} whileHover={cardHover}>
            <div className="grid lg:grid-cols-2 gap-6">
              <BlastPanel
                hits={context.blast.hits}
                count={context.blast.count}
                source={context.blast?.source ?? 'NCBI BLAST'}
              />
              {context.uniprot && <UniprotPanel data={context.uniprot} />}
            </div>
          </motion.div>

          <motion.div variants={fadeUp} whileHover={cardHover}>
            <ScoreBars hits={context.blast.hits} />
          </motion.div>

          {context.alphafold && context.alphafold.structure_available && (
            <motion.div variants={fadeUp} whileHover={cardHover}>
              <AlphaFoldViewer
                pdbUrl={context.alphafold.pdb_url}
                uniprotId={context.alphafold.uniprot_accession}
              />
            </motion.div>
          )}

          {context.pathway_enrichment && (
            <motion.div variants={fadeUp} whileHover={cardHover}>
              <PathwayEnrichment data={context.pathway_enrichment} />
            </motion.div>
          )}

          <div className="flex items-center gap-3 pt-2">
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
              className="glass-card px-4 py-2.5 text-sm text-text-secondary flex items-center gap-2 hover:bg-surface-2 transition"
            >
              <Download className="w-4 h-4" />
              Download CSV
            </button>
          </div>
        </>
      )}
    </motion.div>
  );
}

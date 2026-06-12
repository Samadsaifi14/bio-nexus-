'use client';

import { useEffect, useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2, Dna, AlertCircle, Copy, Download, Search, Clock, WifiOff } from 'lucide-react';
import toast from 'react-hot-toast';
import type { JobStatus, JobStepStatus } from '@/types/pipeline';
import { STEP_LABELS } from '@/types/pipeline';
import AIInterpretation from '@/components/results/AIInterpretation';
import BlastPanel from '@/components/results/BlastPanel';
import ScoreBars from '@/components/results/ScoreBars';
import UniprotPanel from '@/components/results/UniprotPanel';
import AlphaFoldViewer from '@/components/AlphaFoldViewer';

const STATUS_ORDER: JobStepStatus[] = [
  'queued', 'submitted_to_ncbi', 'polling_ncbi', 'parsing', 'interpreting', 'complete',
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
        const res = await fetch(`/api/backend/api/jobs/${jobId}`);
        if (res.ok) {
          const data = await res.json();
          if (!cancelled) {
            setPollError(null);
            setJob(data);
            const terminal = ['complete', 'failed'];
            if (terminal.includes(data.status)) {
              setLoading(false);
              return;
            }
          }
        } else {
          setPollError(`Server returned ${res.status}`);
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
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-teal-500 animate-spin mx-auto mb-4" />
          <p className="text-sm text-gray-500">Loading job...</p>
        </div>
      </div>
    );
  }

  if (!job && timedOut) {
    return (
      <div className="max-w-xl mx-auto py-12">
        <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center">
          <Clock className="w-12 h-12 text-amber-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Still processing</h3>
          <p className="text-sm text-gray-500 mb-6">
            This job is taking longer than expected. It's still running — your results will be saved.
            Check back later at this URL.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="px-6 py-2.5 bg-teal-600 text-white text-sm font-medium rounded-xl hover:bg-teal-700 transition"
          >
            Refresh
          </button>
        </div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-16 text-center">
        <Dna className="w-16 h-16 text-gray-200 mx-auto mb-6" />
        <h3 className="text-xl font-semibold text-gray-900 mb-2">Job not found</h3>
        <p className="text-sm text-gray-500">This job does not exist or has been deleted.</p>
      </div>
    );
  }

  const isActive = ['queued', 'submitted_to_ncbi', 'polling_ncbi', 'parsing', 'interpreting'].includes(job.status);
  const currentIdx = STATUS_ORDER.indexOf(job.status as JobStepStatus);

  if (isActive) {
    return (
      <div className="max-w-xl mx-auto py-12">
        <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center">
          {pollError ? (
            <div className="mb-6">
              <div className="w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                <WifiOff className="w-10 h-10 text-amber-500" />
              </div>
              <p className="text-sm text-amber-700 font-medium mb-1">{pollError}</p>
              <p className="text-xs text-gray-500">Still processing — your results will be saved.</p>
            </div>
          ) : (
            <>
              <div className="relative w-16 h-16 mx-auto mb-6">
                <div className="absolute inset-0 rounded-full bg-teal-500/20 animate-ping" />
                <div className="relative w-16 h-16 rounded-full bg-teal-500 flex items-center justify-center">
                  <Dna className="w-8 h-8 text-white" />
                </div>
              </div>
              <p className="text-lg font-semibold text-gray-900 mb-2">
                {job.current_step_label || STEP_LABELS[job.status as JobStepStatus] || 'Processing...'}
              </p>
            </>
          )}
          <p className="text-sm text-gray-500 mb-8">
            Usually 30s–3min depending on NCBI load. You can close this tab and come back later.
          </p>

          <div className="max-w-sm mx-auto space-y-3">
            {STATUS_ORDER.map((s, i) => {
              const isActiveStep = currentIdx === i;
              const isDone = currentIdx > i;
              return (
                <div key={s} className="flex items-center gap-3">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
                    isDone ? 'bg-teal-500' : isActiveStep ? 'bg-teal-500/20 border-2 border-teal-500' : 'bg-gray-100'
                  }`}>
                    {isDone && <span className="text-white text-xs">✓</span>}
                    {isActiveStep && <div className="w-2 h-2 rounded-full bg-teal-500 animate-pulse" />}
                  </div>
                  <span className={`text-sm ${isActiveStep ? 'font-medium text-gray-900' : isDone ? 'text-gray-500' : 'text-gray-400'}`}>
                    {STEP_LABELS[s]}
                  </span>
                </div>
              );
            })}
          </div>

          <div className="mt-8 bg-amber-50 border border-amber-200 rounded-xl p-4 text-left">
            <p className="text-xs text-amber-700">
              <strong>This result is saved.</strong> You can close this tab and return to this URL later.
            </p>
            <p className="text-xs text-amber-600 mt-2">
              Saved for 24 hours. Create a free account to keep it forever.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (job.status === 'failed') {
    const errorMsg = job.error_message || job.error || 'An unknown error occurred';
    const isTimeout = errorMsg.toLowerCase().includes('timed out') || errorMsg.toLowerCase().includes('timeout');
    const isNcbiError = errorMsg.toLowerCase().includes('ncbi') || errorMsg.toLowerCase().includes('blast');
    const isParseError = errorMsg.toLowerCase().includes('parse');
    return (
      <div className="max-w-xl mx-auto py-12">
        <div className="bg-white rounded-2xl border border-red-200 p-8 text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-red-900 mb-2">Analysis Failed</h3>
          <div className="bg-red-50 rounded-xl p-4 mb-6 text-left">
            <p className="text-xs text-red-700 font-mono leading-relaxed">{errorMsg}</p>
          </div>
          <div className="space-y-2">
            {isTimeout && (
              <p className="text-sm text-amber-700 bg-amber-50 rounded-lg p-3">
                External servers are slow right now. Wait a moment and try again.
              </p>
            )}
            {isNcbiError && (
              <p className="text-sm text-amber-700 bg-amber-50 rounded-lg p-3">
                NCBI returned an error. This is usually temporary — please try again.
              </p>
            )}
            {isParseError && (
              <p className="text-sm text-amber-700 bg-amber-50 rounded-lg p-3">
                We couldn't read the results from NCBI. The data may have been in an unexpected format.
              </p>
            )}
          </div>
          <div className="flex items-center justify-center gap-3 mt-6">
            <button
              onClick={() => router.push('/analyze')}
              className="px-6 py-2.5 bg-teal-600 text-white text-sm font-medium rounded-xl hover:bg-teal-700 transition"
            >
              New Analysis
            </button>
            <button
              onClick={() => window.location.reload()}
              className="px-6 py-2.5 bg-white border border-gray-200 text-gray-700 text-sm font-medium rounded-xl hover:bg-gray-50 transition"
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
      <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">No results data</h3>
        <p className="text-sm text-gray-500">This job has no result data.</p>
      </div>
    );
  }

  const hasHits = context.blast && context.blast.hits && context.blast.hits.length > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 mb-1">Analysis Results</h1>
          <p className="text-sm text-gray-500">
            Query: {context.query.sequence.slice(0, 80)}... ({context.query.length} aa)
          </p>
        </div>
        <button
          onClick={() => { navigator.clipboard.writeText(window.location.href); toast.success('Link copied!'); }}
          className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition"
        >
          Share
        </button>
      </div>

      <AIInterpretation context={context} pipelineType={job.pipeline_type} />

      {!hasHits ? (
        <div className="bg-white rounded-2xl border border-gray-200 p-10 text-center">
          <Search className="w-12 h-12 text-gray-200 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">No significant similarity found</h3>
          <p className="text-sm text-gray-500 max-w-md mx-auto">
            BLAST completed but found no statistically significant matches in the database.
            This could mean your sequence is novel, highly divergent, or the database doesn't contain close relatives.
          </p>
          <div className="mt-6 bg-gray-50 rounded-xl p-4 text-left text-sm text-gray-600">
            <p className="font-medium text-gray-900 mb-2">What this can mean:</p>
            <ul className="space-y-1.5 list-disc pl-5">
              <li>Your sequence may be from a poorly characterized organism</li>
              <li>The protein could be a novel family member with low sequence conservation</li>
              <li>Try searching against a different database (e.g., nr instead of Swiss-Prot)</li>
              <li>Consider checking your sequence for frame-shift errors if it's a nucleotide translation</li>
            </ul>
          </div>
          <button
            onClick={() => router.push('/analyze')}
            className="mt-6 px-6 py-2.5 bg-teal-600 text-white text-sm font-medium rounded-xl hover:bg-teal-700 transition"
          >
            New Analysis
          </button>
        </div>
      ) : (
        <>
          <div className="grid lg:grid-cols-2 gap-6">
            <BlastPanel
              hits={context.blast.hits}
              count={context.blast.count}
              source={context.blast.source}
            />
            {context.uniprot && <UniprotPanel data={context.uniprot} />}
          </div>

          <ScoreBars hits={context.blast.hits} />

          {context.alphafold && context.alphafold.structure_available && (
            <AlphaFoldViewer
              pdbUrl={context.alphafold.pdb_url}
              uniprotId={context.alphafold.uniprot_accession}
            />
          )}

          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={() => {
                const csv = [['Accession', 'Description', 'E-value', '% Identity', 'Bit Score'].join(',')]
                  .concat((context.blast?.hits || []).map((h: any) => [h.accession, `"${h.description}"`, h.evalue, h.identity_pct, h.bit_score].join(',')))
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
              className="flex items-center gap-2 px-4 py-2.5 bg-white border border-gray-200 text-gray-700 text-sm font-medium rounded-xl hover:bg-gray-50 transition"
            >
              <Download className="w-4 h-4" />
              Download CSV
            </button>
          </div>
        </>
      )}
    </div>
  );
}

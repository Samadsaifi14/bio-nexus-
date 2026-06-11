'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { Loader2, Dna } from 'lucide-react';
import toast from 'react-hot-toast';
import type { JobStatus } from '@/types/pipeline';
import AIInterpretation from '@/components/results/AIInterpretation';
import BlastPanel from '@/components/results/BlastPanel';
import UniprotPanel from '@/components/results/UniprotPanel';
import AlphaFoldViewer from '@/components/AlphaFoldViewer';

export default function ResultsPage() {
  const params = useParams();
  const jobId = params.jobId as string;
  const [job, setJob] = useState<JobStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await fetch(`/api/backend/api/jobs/${jobId}`);
        if (res.ok) {
          const data = await res.json();
          if (!cancelled) {
            setJob(data);
            if (data.status === 'complete' || data.status === 'failed') {
              setLoading(false);
              return;
            }
          }
        }
      } catch {}
      if (!cancelled) setTimeout(poll, 2000);
    };
    poll();
    return () => { cancelled = true; };
  }, [jobId]);

  if (loading && !job) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-green-600 animate-spin mx-auto mb-4" />
          <p className="text-sm text-gray-500">Loading results...</p>
        </div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-16 text-center">
        <Dna className="w-16 h-16 text-gray-200 mx-auto mb-6" />
        <h3 className="text-xl font-semibold text-gray-900 mb-2">Result not found</h3>
        <p className="text-sm text-gray-500">This job does not exist or has been deleted.</p>
      </div>
    );
  }

  if (job.status === 'running' || job.status === 'pending' || job.status === 'queued') {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-green-600 animate-spin mx-auto mb-4" />
          <p className="text-sm text-gray-500">Pipeline is running...</p>
          {job.steps_completed && job.steps_completed.length > 0 && (
            <p className="text-xs text-gray-400 mt-1">Completed: {job.steps_completed.join(', ')}</p>
          )}
        </div>
      </div>
    );
  }

  if (job.status === 'failed') {
    return (
      <div className="bg-white rounded-2xl border border-red-200 p-8 text-center">
        <h3 className="text-lg font-semibold text-red-900 mb-2">Pipeline Failed</h3>
        <p className="text-sm text-red-600">{job.error || 'An unknown error occurred'}</p>
      </div>
    );
  }

  const context = job.context_json;
  if (!context) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">No context data</h3>
        <p className="text-sm text-gray-500">This job has no context data. It may have been created with an older version.</p>
      </div>
    );
  }

  const handleShare = async () => {
    // Copy result URL
    const url = `${window.location.origin}/shared/${jobId}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success('Share link copied!');
    } catch {
      toast.error('Failed to copy link');
    }
  };

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
          onClick={handleShare}
          className="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 transition"
        >
          Share
        </button>
      </div>

      <AIInterpretation context={context} pipelineType={job.pipeline_type} />

      <div className="grid lg:grid-cols-2 gap-6">
        {context.blast && context.blast.hits && context.blast.hits.length > 0 && (
          <BlastPanel
            hits={context.blast.hits}
            count={context.blast.count}
            source={context.blast.source}
          />
        )}

        {context.uniprot && (
          <UniprotPanel data={context.uniprot} />
        )}
      </div>

      {context.alphafold && context.alphafold.structure_available && (
        <AlphaFoldViewer
          pdbUrl={context.alphafold.pdb_url}
          uniprotId={context.alphafold.uniprot_accession}
        />
      )}
    </div>
  );
}

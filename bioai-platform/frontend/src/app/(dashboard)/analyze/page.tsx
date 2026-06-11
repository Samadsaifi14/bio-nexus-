'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import toast from 'react-hot-toast';
import PipelineSelector from '@/components/pipeline/PipelineSelector';
import SequenceInput from '@/components/pipeline/SequenceInput';
import JobProgress from '@/components/pipeline/JobProgress';
import { runPipeline } from '@/lib/api';
import type { JobStatus } from '@/types/pipeline';

export default function AnalyzePage() {
  const router = useRouter();
  const [pipelineType, setPipelineType] = useState<string | null>(null);
  const [sequence, setSequence] = useState('');
  const [loading, setLoading] = useState(false);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [pollInterval, setPollInterval] = useState<ReturnType<typeof setInterval> | null>(null);

  const handleRunPipeline = async () => {
    if (!sequence.trim()) {
      toast.error('Enter a sequence first');
      return;
    }
    if (!pipelineType) {
      toast.error('Select a pipeline type');
      return;
    }

    setLoading(true);
    setJob(null);
    if (pollInterval) clearInterval(pollInterval);

    try {
      const result = await runPipeline(sequence, pipelineType);
      setJob({
        id: result.job_id,
        tool: 'pipeline',
        query_preview: sequence.slice(0, 100),
        status: 'running',
        pipeline_type: pipelineType as any,
        steps_completed: [],
        context_json: null,
        progress_pct: 0,
        created_at: new Date().toISOString(),
        completed_at: null,
        error: null,
        share_token: null,
      });
      toast.success('Pipeline started!');

      const interval = setInterval(async () => {
        try {
          const res = await fetch(`/api/backend/api/jobs/${result.job_id}`);
          if (res.ok) {
            const data = await res.json();
            setJob(data);
            if (data.status === 'complete' || data.status === 'failed') {
              clearInterval(interval);
              setPollInterval(null);
              if (data.status === 'complete') {
                toast.success('Pipeline complete!');
                router.push(`/results/${result.job_id}`);
              } else {
                toast.error(data.error || 'Pipeline failed');
              }
            }
          }
        } catch {}
      }, 2000);
      setPollInterval(interval);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to start pipeline');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Run Analysis</h1>
      <p className="text-gray-600 mb-8">
        Select a pipeline, paste your sequence, and get a complete analysis with AI interpretation
      </p>

      {!pipelineType ? (
        <PipelineSelector onSelect={setPipelineType} />
      ) : (
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => { setPipelineType(null); if (pollInterval) clearInterval(pollInterval); }}
              className="text-sm text-gray-500 hover:text-gray-700 underline"
            >
              &larr; Change pipeline
            </button>
            <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
              Protein Sequence Analysis
            </span>
          </div>

          <SequenceInput
            value={sequence}
            onChange={setSequence}
            onSubmit={handleRunPipeline}
            loading={loading}
          />

          {job && (
            <JobProgress stepsCompleted={job.steps_completed || []} status={job.status} />
          )}
        </div>
      )}
    </div>
  );
}

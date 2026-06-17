import axios from 'axios';
import type { JobStatus, PipelineDefinition, AssembledContext, BlastSummary, UniprotSummary, AlphaFoldResult, SequenceResult, SequenceValidation, SequenceSearchResponse } from '@/types/pipeline';

const api = axios.create({
  baseURL: '/api/backend',
});

export async function runPipeline(
  sequence: string,
  pipelineType: string = 'protein_analysis',
  database: string = 'uniprotkb_swissprot',
  maxHits: number = 10,
): Promise<{ job_id: string; status: string }> {
  const res = await api.post('/api/pipelines/run', {
    sequence,
    pipeline_type: pipelineType,
    database,
    max_hits: maxHits,
  });
  return res.data;
}

export async function getPipelineDefinitions(): Promise<PipelineDefinition[]> {
  const res = await api.get('/api/pipelines/definitions');
  return res.data.pipelines;
}

export async function getJob(jobId: string): Promise<JobStatus> {
  const res = await api.get(`/api/jobs/${jobId}`);
  return res.data;
}

export async function getJobs(): Promise<JobStatus[]> {
  const res = await api.get('/api/jobs');
  return res.data.jobs || [];
}

export async function deleteJob(jobId: string): Promise<void> {
  await api.delete(`/api/jobs/${jobId}`);
}

export async function getJobCount(): Promise<{ count: number; limit: number; remaining: number }> {
  const res = await api.get('/api/jobs/count');
  return res.data;
}

export async function getSharedResult(token: string): Promise<JobStatus> {
  const res = await api.get(`/api/share/${token}`);
  return res.data;
}

export function createJobPollingUrl(jobId: string): string {
  return `/api/backend/api/jobs/${jobId}`;
}

export async function interpretStream(payload: {
  pipeline_type: string;
  context: unknown;
}): Promise<Response> {
  const res = await fetch('/api/backend/api/ai/interpret/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return res;
}

export async function fetchSequence(accession: string, dbPreference?: string): Promise<SequenceResult> {
  const res = await api.post('/api/sequences/fetch', {
    accession,
    db_preference: dbPreference,
  });
  return res.data;
}

export async function validateSequence(sequence: string): Promise<SequenceValidation> {
  const res = await api.post('/api/sequences/validate', { sequence });
  return res.data;
}

export async function searchSequences(query: string, db: string = 'protein', maxResults: number = 10): Promise<SequenceSearchResponse> {
  const res = await api.post('/api/sequences/search', {
    query,
    db,
    max_results: maxResults,
  });
  return res.data;
}

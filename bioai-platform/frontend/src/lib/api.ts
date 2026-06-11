import axios from 'axios';
import type { JobStatus, PipelineDefinition, AssembledContext, BlastSummary, UniprotSummary, AlphaFoldResult } from '@/types/pipeline';

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

export function createInterpretStreamUrl(): string {
  return '/api/backend/api/ai/interpret/stream';
}

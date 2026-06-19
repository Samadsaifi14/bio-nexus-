import axios from 'axios';
import type { JobStatus, UniprotSummary, SequenceResult, SequenceValidation, SequenceSearchResponse } from '@/types/pipeline';
import { getSupabase } from './supabase';

const api = axios.create({
  baseURL: '/api/backend',
  timeout: 30_000,
});

api.interceptors.request.use(async (config) => {
  try {
    const supabase = getSupabase();
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`;
    }
  } catch {
    // Session fetch failed silently — requests will be anonymous
  }
  return config;
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

export async function getJob(jobId: string): Promise<JobStatus> {
  const res = await api.get(`/api/jobs/${jobId}`);
  return res.data;
}

export async function getJobs(): Promise<JobStatus[]> {
  const res = await api.get('/api/jobs');
  return res.data.jobs || [];
}

export async function getJobCount(): Promise<{ count: number; limit: number; remaining: number }> {
  const res = await api.get('/api/jobs/count');
  return res.data;
}

export async function getSharedResult(token: string): Promise<JobStatus> {
  const res = await api.get(`/api/share/${token}`);
  return res.data;
}

export async function interpretStream(payload: {
  pipeline_type: string;
  context: unknown;
}): Promise<Response> {
  const supabase = getSupabase();
  const { data: { session } } = await supabase.auth.getSession();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`;
  }
  const res = await fetch('/api/backend/api/ai/interpret/stream', {
    method: 'POST',
    headers,
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

export async function searchUniprot(query: string, maxResults: number = 20): Promise<{ results: UniprotSearchResult[]; count: number }> {
  const res = await api.post('/api/uniprot/search', { query, max_results: maxResults });
  return res.data;
}

export async function getUniprotDetail(accession: string): Promise<UniprotSummary> {
  const res = await api.post('/api/uniprot/detail', { accession });
  return res.data;
}

export type UniprotSearchResult = {
  accession: string;
  name: string;
  gene_names: string[];
  organism: string;
  length: number;
};
export async function searchSequences(query: string, db: string = 'protein', maxResults: number = 10): Promise<SequenceSearchResponse> {
  const res = await api.post('/api/sequences/search', {
    query,
    db,
    max_results: maxResults,
  });
  return res.data;
}

export type AlignmentResult = {
  job_id: string;
  aln_fasta: string;
  aln_clustal: string;
  phylotree: string;
  stype: string;
};

export async function runAlignment(sequence: string, stype: string = 'protein'): Promise<AlignmentResult> {
  const res = await api.post('/api/alignment/run', { sequence, stype });
  return res.data;
}

export type StructureResult = {
  source: string;
  pdb_id?: string;
  title?: string;
  method?: string;
  resolution?: number;
  deposited?: string;
  pdb_url?: string;
  cif_url?: string;
  uniprot_accession?: string;
  confidence?: number;
  model_created_date?: string;
};

export async function fetchStructure(query: string): Promise<StructureResult> {
  const res = await api.post('/api/structures/fetch', { query });
  return res.data;
}

/** @deprecated Unused — search is handled by fetchStructure */
export async function searchStructures(query: string): Promise<{ results: { pdb_id: string; score: number }[]; count: number }> {
  const res = await api.post('/api/structures/search', { query });
  return res.data;
}

export type PathwayResult = {
  pathway_id: string;
  name: string;
  species: string;
  url: string;
};

export async function searchPathways(query: string, species: string = 'Homo sapiens'): Promise<{ results: PathwayResult[]; count: number }> {
  const res = await api.post('/api/pathways/search', { query, species });
  return res.data;
}

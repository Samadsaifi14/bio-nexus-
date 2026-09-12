import { getSupabase } from './supabase';

const BASE = '/api/backend';

export type ProductionProfile = 'docker' | 'singularity' | 'apptainer' | 'slurm' | 'awsbatch';

export type RnaSeqProductionPlanRequest = {
  samplesheet_path: string;
  outdir: string;
  genome?: string | null;
  fasta?: string | null;
  gtf?: string | null;
  execution_profile: ProductionProfile;
  aligner: 'star_salmon' | 'star_rsem' | 'hisat2' | 'bowtie2_salmon';
  pseudo_aligner?: 'salmon' | null;
  strandedness: 'auto' | 'unstranded' | 'forward' | 'reverse';
  custom_config?: string | null;
  trim_nextseq?: number | null;
  skip_trimming: boolean;
  save_trimmed: boolean;
  differential_expression_requested: boolean;
  fusion_detection_requested: boolean;
};

export type ProductionPlan = {
  schema_version: string;
  workflow: Record<string, string>;
  state: 'PLANNED' | 'BLOCKED';
  ready_to_launch: boolean;
  blockers: string[];
  warnings: string[];
  command_argv: string[];
  command_display: string;
  required_artifacts: Array<{ id: string; required: boolean; description: string; patterns: string[] }>;
  provenance_requirements: string[];
  clinical_boundary: Record<string, unknown>;
};

export type ProductionCapabilities = {
  workflows?: Array<{ name: string; revision: string; assays: string[] }>;
  executors: Record<'local' | 'slurm' | 'awsbatch', { available: boolean; enabled: boolean; missing: string[]; requirements: string[] }>;
  fallback: null;
  note: string;
};

export type ProductionRun = {
  run_id: string;
  state: 'SUBMITTED' | 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'UNKNOWN';
  executor: 'local' | 'slurm' | 'awsbatch';
  executor_job_id: string;
  workflow: string;
  revision: string;
  outdir: string;
  submitted_at: string;
  updated_at: string;
  exit_code?: number | null;
  message?: string | null;
};

export type ProductionArtifacts = {
  run_id: string;
  workflow: string;
  revision: string;
  source: string;
  observed_file_count: number;
  groups: Record<string, string[]>;
  required_groups_complete: boolean;
  missing_groups: string[];
  claim: string;
};

async function authHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  try {
    const { data: { session } } = await getSupabase().auth.getSession();
    if (session?.access_token) headers.Authorization = `Bearer ${session.access_token}`;
  } catch {
    // Anonymous planning remains available; submission will fail closed at the API.
  }
  return headers;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = { ...(await authHeaders()), ...(init?.headers ?? {}) };
  const response = await fetch(`${BASE}${path}`, { ...init, headers });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    const message = typeof detail === 'string'
      ? detail
      : typeof detail?.message === 'string'
        ? `${detail.message}${Array.isArray(detail.blockers) ? `: ${detail.blockers.join(' ')}` : ''}`
        : `Request failed (${response.status})`;
    const error = new Error(message) as Error & { status?: number };
    error.status = response.status;
    throw error;
  }
  return body as T;
}

export function getProductionCapabilities(): Promise<ProductionCapabilities> {
  return requestJson('/api/ngs/v2/production/capabilities');
}

export function buildRnaSeqProductionPlan(payload: RnaSeqProductionPlanRequest): Promise<ProductionPlan> {
  return requestJson('/api/ngs/v2/rnaseq/production/plan', { method: 'POST', body: JSON.stringify(payload) });
}

export function submitRnaSeqProductionRun(payload: RnaSeqProductionPlanRequest): Promise<{ run_id: string; state: string; executor: string; executor_job_id?: string; message: string }> {
  return requestJson('/api/ngs/v2/rnaseq/production/submit', { method: 'POST', body: JSON.stringify(payload) });
}

export function getProductionRun(runId: string): Promise<ProductionRun> {
  return requestJson(`/api/ngs/v2/production/runs/${encodeURIComponent(runId)}`);
}

export function getProductionArtifacts(runId: string): Promise<ProductionArtifacts> {
  return requestJson(`/api/ngs/v2/production/runs/${encodeURIComponent(runId)}/artifacts`);
}

import { getSupabase } from './supabase';

const BASE = '/api/backend';

export type NextflowCapabilities = {
  workflow_id: string;
  workflow: {
    name: string;
    revision: string;
    definition: string;
    processes: string[];
    truth_control: boolean;
  };
  engine: {
    name: string;
    version: string | null;
    tool_versions: Record<string, string>;
    container_image: string;
    container_digest: string | null;
    executor: string;
  };
  fixtures: Array<{
    id: string;
    label: string;
    description: string;
    expected_snp: string;
    classification: string;
  }>;
  parameters: Record<string, { default: number; minimum: number; maximum: number }>;
  executor: {
    name: string;
    available: boolean;
    missing: string[];
    requirements: string[];
    reason: string | null;
  };
  claim: string;
};

export type NextflowProcess = {
  task_id: string | null;
  name: string | null;
  status: string | null;
  exit: string | null;
  realtime: string | null;
};

export type NextflowRun = {
  run_id: string;
  state: 'SUBMITTED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | string;
  workflow_id: string;
  workflow: string;
  revision: string;
  engine: string;
  engine_version: string | null;
  container_image: string;
  container_digest: string | null;
  executor: string;
  fixture: string;
  sample_name: string;
  parameters: Record<string, number>;
  outdir: string;
  submitted_at: string;
  updated_at: string;
  exit_code: number | null;
  message: string | null;
  command_sha256: string;
  nextflow_executed: boolean;
  processes?: NextflowProcess[];
  process_count?: number;
  artifacts_ready?: boolean;
};

export type NextflowArtifact = {
  id: string;
  label: string;
  category: string;
  media_type: string;
  required: boolean;
  path: string;
  present: boolean;
  bytes: number | null;
  sha256: string | null;
  download_url: string | null;
};

export type NextflowArtifactManifest = {
  run_id: string;
  workflow: string;
  revision: string;
  state: string;
  nextflow_executed: boolean;
  source: string;
  observed_file_count: number;
  artifacts: NextflowArtifact[];
  required_complete: boolean;
  missing_required: string[];
  claim: string;
};

export type NextflowEvidenceFile = {
  label: string;
  media_type: string;
  bytes: number;
  sha256: string;
  download_url: string;
};

export type NextflowEvidence = {
  available: boolean;
  reason?: string;
  workflow_id: string;
  workflow: string;
  revision: string;
  generated_at: string;
  execution: {
    engine: string;
    engine_version: string;
    executor: string;
    container_image: string;
    container_digest: string;
    state: string;
    exit_code: number;
    nextflow_executed: boolean;
    command_sha256: string;
    command?: string[];
    evidence_note: string;
  };
  fixture: {
    id: string;
    label: string;
    classification: string;
    expected_snp: string;
  };
  parameters: Record<string, number>;
  result: {
    called_variants: number;
    mean_depth: number;
    mapped_reads: number;
    reference_length: number;
    tp: number;
    fp: number;
    fn: number;
    precision: number;
    recall: number;
    f1: number;
    normalized_calls_sha256: string;
  };
  tool_versions: Record<string, string>;
  processes: NextflowProcess[];
  files: Record<string, NextflowEvidenceFile>;
  claim: string;
  inline?: {
    'metrics.json'?: Record<string, unknown>;
    'benchmark.json'?: Record<string, unknown>;
    'calls.tsv'?: string;
  };
};

async function authHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  try {
    const { data: { session } } = await getSupabase().auth.getSession();
    if (session?.access_token) headers.Authorization = `Bearer ${session.access_token}`;
  } catch {
    // Public capability/evidence reads do not require a token.
  }
  return headers;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = { ...(await authHeaders()), ...(init?.headers ?? {}) };
  const response = await fetch(`${BASE}${path}`, { ...init, headers });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    const message = typeof detail === 'string' ? detail : `Request failed (${response.status})`;
    const error = new Error(message) as Error & { status?: number };
    error.status = response.status;
    throw error;
  }
  return body as T;
}

export function getNextflowCapabilities(): Promise<NextflowCapabilities> {
  return requestJson('/api/ngs/v2/nextflow/capabilities');
}

export function getNextflowEvidence(): Promise<NextflowEvidence> {
  return requestJson('/api/ngs/v2/nextflow/evidence');
}

export function getNextflowRun(runId: string): Promise<NextflowRun> {
  return requestJson(`/api/ngs/v2/nextflow/runs/${encodeURIComponent(runId)}`);
}

export function getNextflowArtifacts(runId: string): Promise<NextflowArtifactManifest> {
  return requestJson(`/api/ngs/v2/nextflow/runs/${encodeURIComponent(runId)}/artifacts`);
}

export function submitNextflowRun(payload: {
  fixture: string;
  min_qual: number;
  min_dp: number;
  threads: number;
  sample_name?: string;
}): Promise<{ run_id: string; state: string; workflow: string; engine: string; message: string }> {
  return requestJson('/api/ngs/v2/nextflow/runs', { method: 'POST', body: JSON.stringify(payload) });
}

export function evidenceFileUrl(name: string): string {
  return `${BASE}/api/ngs/v2/nextflow/evidence/files/${encodeURIComponent(name)}`;
}

export async function downloadNextflowArtifact(runId: string, artifactId: string, filename: string): Promise<void> {
  const { Authorization } = await authHeaders();
  const response = await fetch(
    `${BASE}/api/ngs/v2/nextflow/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactId)}`,
    { headers: Authorization ? { Authorization } : {} },
  );
  if (!response.ok) throw new Error(`Artifact download failed (${response.status})`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

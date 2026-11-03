import axios from 'axios';
import type { JobStatus, UniprotSummary, SequenceResult, SequenceValidation, SequenceSearchResponse, PairwiseAlignResult, SequenceUtilitiesResult, MotifPatternScanResult, MotifLibraryResult, MotifLibraryPattern, DotPlotResult } from '@/types/pipeline';
import { getSupabase } from './supabase';

/**
 * Resolve the backend base URL.
 * Deployed builds bypass Vercel's /api/backend rewrite (Vercel blocks proxying
 * to the hf.space hostname with a DNS-hostname-resolved-private edge error) and
 * call the Space directly cross-origin — the CORS middleware allows it. Local
 * dev keeps the same-origin proxy so requests stay cookie/header friendly.
 */
function resolveApiBase(): string {
  const explicit = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, '');
  if (explicit) return explicit;
  if (typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    return 'https://samad14-bio-nexus-api.hf.space';
  }
  return '/api/backend';
}

export function apiUrl(path: string): string {
  return `${resolveApiBase()}${path}`;
}

const api = axios.create({
  baseURL: resolveApiBase(),
  timeout: 30_000,
});

export const longApi = axios.create({
  baseURL: resolveApiBase(),
  timeout: 660_000,
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

longApi.interceptors.request.use(async (config) => {
  try {
    const supabase = getSupabase();
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`;
    }
  } catch {
    // Session fetch failed silently
  }
  
…[1 chars truncated — re-run with head/grep/tail for full output]…
bos: Record<string, string[]>;
  defaults: { forcefield: string; solvent: string };
  probe?: { system: string; forcefields_tested: number; solvents_tested: number };
};

export async function getMDForceFields(): Promise<MDForceFieldsMenu> {
  const res = await api.get('/api/md/forcefields');
  return res.data;
}

export async function runMD(pdbId: string, mode: string = 'minimize', options?: MDRunOptions): Promise<{ job_id: string; status: string }> {
  const res = await longApi.post('/api/md/run', { pdb_id: pdbId, mode, ...options });
  return res.data;
}

export async function getMDStatus(jobId: string): Promise<{ job_id: string; status: string; result?: MDSimulationResult; error?: string }> {
  const res = await longApi.get(`/api/md/status/${jobId}`);
  return res.data;
}

// ---------------------------------------------------------------------------
// Function hints (InterProScan and InterPro2GO evidence)
// ---------------------------------------------------------------------------

export type FunctionPredictionResult = {
  pdb_id: string;
  sequence_length: number;
  go_terms: { go_id: string; name: string; namespace: string; confidence: number | null }[];
  ec_numbers: { number: string; confidence: number }[];
  saliency: number[];
  composition?: { aa: string; fractions: Record<string, number> };
  method: string;
  note: string;
};

export async function predictFunction(pdbId: string): Promise<{ job_id: string; status: string }> {
  const res = await longApi.post('/api/function/predict', { pdb_id: pdbId });
  return res.data;
}

export async function getFunctionStatus(jobId: string): Promise<{ job_id: string; status: string; result?: FunctionPredictionResult; error?: string }> {
  const res = await longApi.get(`/api/function/status/${jobId}`);
  return res.data;
}

// ─── CASTp ──────────────────────────────────────────────────────────────────

export interface PocketInfo {
  id: number;
  area_sa: number;
  volume_sa: number;
  num_residues: number;
  residues: string[];
  centroid: number[];
  radius: number;
}

export interface CastpPipelineStep {
  step: string;
  status: string;
  detail: string;
}

export interface CastpUniProt {
  accession: string;
  name: string;
  organism: string;
  gene_names: string[];
  sequence_length: number;
}

export interface CastpChainGap {
  start: number;
  end: number;
  count: number;
}

export interface CastpChain {
  id: string;
  residue_count: number;
  sequence: string;
  gaps: CastpChainGap[];
}

export interface CastpPocketResidue {
  chain: string;
  residue_number: number;
  residue_name: string;
  one: string;
  label: string;
  coordinate_present: boolean;
}

export interface CastpPocketGap {
  chain: string;
  gaps: CastpChainGap[];
}

export interface CastpChainSpan {
  chain: string;
  min: number;
  max: number;
  count: number;
}

export interface CastpActiveSiteResidue {
  chain: string;
  residue_number: number;
  residue_name: string;
  one?: string;
  role: string;
  source: string;
}

export interface CastpPocket {
  id: number;
  druggability_score?: number | null;
  score?: number | null;
  area_sa: number | null;
  volume_sa: number | null;
  num_residues: number;
  residues: string[];
  centroid: number[] | null;
  radius: number | null;
  residue_details: CastpPocketResidue[];
  gap_ranges: CastpPocketGap[];
  chain_spans: CastpChainSpan[];
  active_site_hits: CastpActiveSiteResidue[];
}

export interface CastpResult {
  pdb_id: string;
  probe_radius: number | null;
  total_residues: number;
  pockets: CastpPocket[];
  method?: string;
  methods_tried?: Array<{ method: string; status: string }>;
  fallback_used?: boolean;
  status?: string;
  error?: string;
  note?: string;
  sequence_source?: string;
  structure_source?: string;
  structure_pdb?: string;
  pipeline?: CastpPipelineStep[];
  uniprot?: CastpUniProt | null;
  chains?: CastpChain[];
  active_sites?: CastpActiveSiteResidue[];
  contacts?: IntramolecularContacts;
}

export type PocketMethod = 'fpocket' | 'sasa_heuristic';

function unwrapPocketResult(data: Record<string, unknown>): CastpResult {
  const nested = data.results;
  const source = nested && typeof nested === 'object'
    ? nested as Record<string, unknown>
    : data;
  const pockets = Array.isArray(source.pockets) ? source.pockets as CastpPocket[] : [];
  const activeSites = Array.isArray(source.active_sites)
    ? source.active_sites as CastpActiveSiteResidue[]
    : [];
  const chains = Array.isArray(source.chains) ? source.chains as CastpChain[] : [];
  const pipeline = Array.isArray(source.pipeline) ? source.pipeline as CastpPipelineStep[] : [];
  const methodsTried = Array.isArray(source.methods_tried)
    ? source.methods_tried as Array<{ method: string; status: string }> : [];
  // Provider payloads can omit optional nested collections. Normalize them once
  // at the API boundary so result components never dereference undefined arrays.
  const normalizedPockets = pockets.map((pocket) => ({
    ...pocket, residues: Array.isArray(pocket.residues) ? pocket.residues : [],
    residue_details: Array.isArray(pocket.residue_details) ? pocket.residue_details : [],
    gap_ranges: Array.isArray(pocket.gap_ranges) ? pocket.gap_ranges : [],
    chain_spans: Array.isArray(pocket.chain_spans) ? pocket.chain_spans : [],
    active_site_hits: Array.isArray(pocket.active_site_hits) ? pocket.active_site_hits : [],
  }));
  return {
    ...source,
    pdb_id: typeof source.pdb_id === 'string' ? source.pdb_id : 'unknown',
    total_residues: Number.isFinite(Number(source.total_residues)) ? Number(source.total_residues) : 0,
    pockets: normalizedPockets,
    active_sites: activeSites,
    chains,
    pipeline,
    methods_tried: methodsTried,
    method: (source.method ?? data.method) as string | undefined,
    status: (source.status ?? data.status) as string | undefined,
    fallback_used: (source.fallback_used ?? data.fallback_used) as boolean | undefined,
    error: ((source.validation as Record<string, unknown> | undefined)?.reason
      ?? source.error
      ?? data.error) as string | undefined,
  } as CastpResult;
}

export async function runCastp(pdbId: string, probeRadius = 1.4, method: PocketMethod = 'fpocket'): Promise<CastpResult> {
  return submitPocketJob({ pdb_id: pdbId, probe_radius: probeRadius, method });
}

export async function runCastpSequence(sequence: string, probeRadius = 1.4, method: PocketMethod = 'fpocket'): Promise<CastpResult> {
  return submitPocketJob({ sequence, probe_radius: probeRadius, method });
}

async function submitPocketJob(payload: Record<string, unknown>): Promise<CastpResult> {
  // Background + poll: structure resolution and fpocket/CASTp can exceed the
  // platform proxy budget, which previously surfaced as 502/504.
  const submitted = await api.post('/api/castp/jobs', payload);
  const jobId = String(submitted.data.job_id);
  const state = await waitForToolJob(() =>
    api.get(`/api/castp/jobs/${encodeURIComponent(jobId)}`).then((res) => res.data),
  );
  const result = (state.result as Record<string, unknown> | undefined) ?? state;
  return unwrapPocketResult(result);
}

// ─── SWISS-MODEL ────────────────────────────────────────────────────────────

export interface SwissModelTemplate {
  template: string | null;
  provider: string | null;
  method: string | null;
  coverage: number | null;
  oligo_state: string | null;
  from_res: number | null;
  to_res: number | null;
  created_date: string | null;
  coordinates_url: string | null;
  qmean_score: number | null;
  qmean_discovery_score: number | null;
  gmqe_score: number | null;
  ligands: { hetid: string; description: string }[];
  complex_with: { chain: string; uniprot_ac: string; description: string }[];
}

export interface SwissModelResult {
  accession: string;
  sequence: string;
  sequence_length: number;
  models: SwissModelTemplate[];
  experimental: SwissModelTemplate[];
}

export async function querySwissModel(accession: string): Promise<SwissModelResult> {
  const res = await api.post('/api/swissmodel/repository', { accession });
  return res.data;
}

export async function getSwissModelCoordinates(accession: string): Promise<{ accession: string; pdb: string }> {
  const res = await api.get(`/api/swissmodel/coordinates/${accession}`);
  return res.data;
}

// ─── Structure Prediction (ESMFold) ─────────────────────────────────────────

export interface PredictionJob {
  job_id: string;
  status: string;
}

export interface PredictionResult {
  job_id: string;
  status: string;
  pdb: string | null;
  mean_plddt: number | null;
  ptm: number | null;
  error: string | null;
}

export async function predictStructure(sequence: string, jobTitle = ''): Promise<PredictionJob> {
  const res = await longApi.post('/api/structure-predict/predict', { sequence, job_title: jobTitle });
  return res.data;
}

export async function getPredictionStatus(jobId: string): Promise<PredictionResult> {
  const res = await longApi.get(`/api/structure-predict/status/${jobId}`);
  return res.data;
}

// ─── Structure Preparation Pipeline ──────────────────────────────────────────

export interface StructurePrepJob {
  job_id: string;
  status: string;
}

export type ContactCategory = {
  items: {
    donor?: string;
    donor_atom?: string;
    donor_chain?: string;
    donor_residue_seq?: number;
    acceptor?: string;
    acceptor_atom?: string;
    acceptor_chain?: string;
    acceptor_residue_seq?: number;
    partner_residue?: string;
    partner_residue_seq?: number;
    partner_chain?: string;
    partner_atom?: string;
    distance: number;
    geometry?: string;
    charge_pair?: string;
  }[];
  count: number;
  total: number;
  truncated: boolean;
};

export type IntramolecularContacts = {
  status?: 'error';
  error?: string;
  hbonds: ContactCategory;
  salt_bridges: ContactCategory;
  hydrophobic: ContactCategory;
  disulfides: ContactCategory;
  method?: {
    name: string;
    kind: string;
    explicit_hydrogens: boolean | null;
    criteria: Record<string, Record<string, unknown>>;
    excludes: string;
  };
  limitation?: string;
};

export interface StructurePrepResult {
  job_id: string;
  status: string;
  step: string;
  chain_health: {
    has_missing_residues: boolean;
    missing_residue_count: number;
    missing_ranges: string[];
    has_chain_breaks: boolean;
    chain_break_count: number;
    chain_breaks: { chain: string; from_resnum: number; to_resnum: number; distance: number }[];
    is_broken: boolean;
    chains: string[];
    total_residues: number;
  } | null;
  fpocket_pockets: { id: number; druggability_score: number | null; volume: number | null; area: number | null; score: number | null; num_residues: number }[];
  castp_pockets: { id: number; area_sa: number; volume_sa: number }[];
  fpocket_engine?: 'fpocket' | 'sasa_concave_packing_fallback' | string;
  fpocket_engine_note?: string;
  fpocket_status?: string;
  castp_status?: string;
  contacts?: IntramolecularContacts;
  operations: { step: string; engine: string; status: string; duration_s: number; note: string }[];
  cleaned_pdb: string;
  error: string | null;
}

// The hosted backend (HF Space) recycles/restarts under load; its router then
// answers 502 to the browser for a moment. The run POST is fast and arrives at
// the app or the router's restart window — retry once on 502 before failing.
async function postWithGatewayRetry<T>(fn: () => Promise<{ data: T }>): Promise<T> {
  const isGatewayFailure = (err: unknown) =>
    !!err && typeof err === 'object' && 'response' in err &&
    (err as { response?: { status?: number } }).response?.status === 502;
  try {
    const res = await fn();
    return res.data;
  } catch (err) {
    if (!isGatewayFailure(err)) throw err;
    await new Promise((resolve) => setTimeout(resolve, 1500));
    const res = await fn();
    return res.data;
  }
}

export async function runStructurePrep(pdbId: string, probeRadius = 1.4): Promise<StructurePrepJob> {
  return postWithGatewayRetry(() => longApi.post('/api/structure-prep/run', { pdb_id: pdbId, probe_radius: probeRadius }));
}

export async function runStructurePrepSequence(sequence: string, probeRadius = 1.4): Promise<StructurePrepJob> {
  return postWithGatewayRetry(() => longApi.post('/api/structure-prep/run', { sequence, probe_radius: probeRadius }));
}

export async function getStructurePrepStatus(jobId: string): Promise<StructurePrepResult> {
  const res = await longApi.get(`/api/structure-prep/status/${jobId}`);
  return res.data;
}

// --- History DAG -----------------------------------------------------------

export interface JobNode {
  id: string;
  tool: string;
  query_preview: string;
  status: string;
  parent_job_id: string | null;
  created_at: string;
  completed_at: string | null;
  error: string | null;
}

export interface JobGraph {
  nodes: JobNode[];
  edges: Array<{ from: string; to: string }>;
  focus: string;
}

export async function getJobGraph(jobId: string): Promise<JobGraph> {
  const res = await api.get(`/api/history/graph/${jobId}`);
  return res.data;
}

export async function getJobChildren(jobId: string): Promise<{ children: JobNode[] }> {
  const res = await api.get(`/api/history/children/${jobId}`);
  return res.data;
}

export async function branchFromJob(
  sourceJobId: string,
  steps: string[],
  parameters?: Record<string, unknown>
): Promise<{ job_id: string; parent_job_id: string }> {
  const res = await api.post('/api/history/branch', {
    source_job_id: sourceJobId,
    steps,
    parameters,
  });
  return res.data;
}

// --- Pipeline Templates ----------------------------------------------------

export interface PipelineTemplate {
  id: string;
  name: string;
  description: string;
  steps: string[];
  parameters: Record<string, unknown>;
  share_token: string | null;
  user_id: string | null;
  created_at: string;
  updated_at: string;
}

export async function getTemplates(): Promise<PipelineTemplate[]> {
  const res = await api.get('/api/templates');
  return res.data.templates || [];
}

export async function createTemplate(
  name: string,
  description: string,
  steps: string[],
  parameters?: Record<string, unknown>
): Promise<PipelineTemplate> {
  const res = await api.post('/api/templates', { name, description, steps, parameters });
  return res.data;
}

export async function updateTemplate(
  templateId: string,
  updates: Partial<Pick<PipelineTemplate, 'name' | 'description' | 'steps' | 'parameters'>>
): Promise<PipelineTemplate> {
  const res = await api.put(`/api/templates/${templateId}`, updates);
  return res.data;
}

export async function deleteTemplate(templateId: string): Promise<void> {
  await api.delete(`/api/templates/${templateId}`);
}

export async function shareTemplate(
  templateId: string
): Promise<{ token: string; url: string }> {
  const res = await api.post(`/api/templates/${templateId}/share`);
  return res.data;
}

export async function getSharedTemplate(token: string): Promise<PipelineTemplate> {
  const res = await api.get(`/api/templates/shared/${token}`);
  return res.data;
}

// --- Tool Cards ------------------------------------------------------------

export interface ToolCard {
  id: string;
  name: string;
  category: string;
  inputs: Record<string, string>;
  outputs: Record<string, string>;
  external: string;
  version: string;
  cli_binary: string | null;
  api_endpoint: string | null;
}

export async function getToolCards(): Promise<ToolCard[]> {
  const res = await api.get('/api/tools');
  return res.data.tools || [];
}

export async function getToolCard(toolId: string): Promise<ToolCard> {
  const res = await api.get(`/api/tools/${toolId}`);
  return res.data;
}

/** Stored scientific workflow evidence; export does not execute or translate tools. */
export async function getWorkflowEvidenceManifest(jobId: string): Promise<Record<string, unknown>> {
  const res = await api.get(`/api/experiments/${encodeURIComponent(jobId)}/workflow-manifest`);
  return res.data;
}


export async function exportWorkflowRecipe(jobId: string): Promise<Record<string, unknown>> {
  const res = await api.get(`/api/experiments/${encodeURIComponent(jobId)}/workflow-recipe`);
  return res.data;
}
export async function validateWorkflowRecipe(recipe: unknown): Promise<Record<string, unknown>> {
  const res = await api.post('/api/pipelines/recipes/validate', recipe);
  return res.data;
}
export async function replayWorkflow(jobId: string, sequence: string): Promise<{ job_id: string; status: string }> {
  const res = await api.post(`/api/experiments/${encodeURIComponent(jobId)}/replay`, { sequence });
  return res.data;
}

export async function runWorkflowRecipe(recipe: unknown, sequence: string): Promise<{ job_id: string; status: string }> {
  const res = await api.post('/api/pipelines/run', { sequence, pipeline_type: 'protein_analysis', workflow_recipe: recipe });
  return res.data;
}

export interface WorkflowCollectionItem { identifier: string; job_id: string | null; status: string; error?: string }
export async function runWorkflowCollection(recipe: unknown, fasta: string, submissionId: string): Promise<{ items: WorkflowCollectionItem[]; total: number }> {
  const res = await api.post('/api/pipelines/collections/run', { recipe, fasta, submission_id: submissionId });
  return res.data;
}

export interface AlignmentTrimResult {
  trimmed_fasta: string;
  mask: { kept_columns: number[]; dropped_columns: number[]; input_width: number; output_width: number; record_count: number; residues_removed: number; input_sha256: string; output_sha256: string; coordinate_convention: string };
  warning: string;
}
export async function trimAlignmentColumns(fasta: string, molecule: 'dna' | 'rna' | 'protein', mode: 'all_gap' | 'any_gap' | 'gap_percent', gap_percent: number) {
  const { data } = await longApi.post<{ results: AlignmentTrimResult }>('/api/seq-tools/alignment-trim', { fasta, molecule, mode, gap_percent });
  return data;
}

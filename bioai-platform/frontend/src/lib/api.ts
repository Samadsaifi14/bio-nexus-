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
  queryAccession?: string,
): Promise<{ job_id: string; status: string }> {
  const res = await api.post('/api/pipelines/run', {
    sequence,
    pipeline_type: pipelineType,
    database,
    max_hits: maxHits,
    query_accession: queryAccession ?? '',
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

export async function createShareLink(jobId: string): Promise<{ token: string; url: string }> {
  const res = await api.post('/api/share', { job_id: jobId });
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

export type UniprotCDSResult = {
  uniprot_accession: string;
  embl_accession: string;
  sequence: string;
  length: number;
  description: string;
  organism: string;
};

export async function fetchUniprotCds(accession: string, emblAccession: string): Promise<UniprotCDSResult> {
  const res = await api.post('/api/uniprot/cds', { accession, embl_accession: emblAccession });
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

export async function runPipelineV2(sequence: string, steps?: string[]): Promise<{ job_id: string }> {
  const res = await api.post('/api/pipeline/v2/run', { sequence, steps: steps || undefined });
  return res.data;
}

export async function getPipelineStatusV2(jobId: string): Promise<any> {
  const res = await api.get(`/api/pipeline/v2/status/${jobId}`);
  return res.data;
}

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

export type StructureInventory = {
  pdb_id: string;
  chains: Array<{ id: string; residue_count: number }>;
  ligands: Array<{ id: string; chain: string; residue_count: number }>;
};

export async function getStructureInventory(pdbId: string): Promise<StructureInventory> {
  const res = await api.post('/api/structures/inventory', { pdb_id: pdbId });
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

export type PathwayDetail = {
  pathway_id: string;
  name: string;
  species: string;
  description: string;
  url: string;
};

export async function fetchPathwayDetail(pathwayId: string): Promise<PathwayDetail> {
  const res = await api.post('/api/pathways/detail', { pathway_id: pathwayId });
  return res.data;
}

export type KEGGPathwayResult = {
  pathway_id: string;
  name: string;
  organism: string;
  url: string;
  image_url: string;
};

export async function searchKEGGPathways(query: string): Promise<{ results: KEGGPathwayResult[]; count: number }> {
  const res = await api.post('/api/pathways/kegg/search', { query });
  return res.data;
}

export type EnrichmentResult = {
  token: string;
  pathways: Array<{
    stId: string;
    name: string;
    species: string;
    entitiesFound: number;
    entitiesTotal: number;
    entitiesFDR: number;
  }>;
};

export type ApiKey = {
  id: string;
  name: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
};

export async function getApiKeys(): Promise<ApiKey[]> {
  const res = await api.get('/api/keys');
  return res.data.keys || [];
}

export async function createApiKey(name: string): Promise<{ key: string; key_prefix: string; name: string }> {
  const res = await api.post('/api/keys', { name });
  return res.data;
}

export async function deleteApiKey(id: string): Promise<void> {
  await api.delete(`/api/keys/${id}`);
}

export function getExportUrl(jobId: string, format: 'pdf' | 'json'): string {
  return `/api/backend/api/export/job/${jobId}?format=${format}`;
}

export async function runEnrichment(identifiers: string[]): Promise<EnrichmentResult> {
  const res = await api.post('/api/pathways/enrichment', { identifiers });
  return res.data;
}

export type DockingAtom = {
  x: number;
  y: number;
  z: number;
  element: string;
  atom_type: string;
};

export type DockingPose = {
  model: number;
  atoms: number;
  coords?: DockingAtom[];
  affinity: number | null;
};

export type DockingInteraction = {
  hbonds: Array<{
    type: string;
    ligand_atom: string;
    ligand_coords: [number, number, number];
    protein_residue: string;
    protein_residue_seq: number;
    protein_chain: string;
    protein_atom: string;
    protein_coords: [number, number, number];
    distance: number;
    confidence: string;
  }>;
  hydrophobic: Array<{
    type: string;
    ligand_atom: string;
    ligand_coords: [number, number, number];
    protein_residue: string;
    protein_residue_seq: number;
    protein_chain: string;
    protein_atom: string;
    protein_coords: [number, number, number];
    distance: number;
  }>;
  pi_stacking: Array<{
    type: string;
    protein_residue: string;
    protein_residue_seq: number;
    protein_chain: string;
    ring_centroid: [number, number, number];
    ring_normal: [number, number, number];
    ligand_centroid: [number, number, number];
    distance: number;
    angle: number;
    stacking_type: string;
    confidence: string;
  }>;
  salt_bridges: Array<{
    type: string;
    ligand_atom: string;
    ligand_coords: [number, number, number];
    protein_residue: string;
    protein_residue_seq: number;
    protein_chain: string;
    protein_atom: string;
    protein_coords: [number, number, number];
    distance: number;
    charge_pair: string;
  }>;
};

export type DockingPoseInteractions = {
  model: number;
  hbonds: number;
  hydrophobic: number;
  pi_stacking: number;
  salt_bridges: number;
};

export type DockingResult = {
  job_id: string;
  status: string;
  result?: {
    pdb_id: string;
    smiles: string;
    poses: DockingPose[];
    num_poses: number;
    box_center: { x: number; y: number; z: number };
    box_size: { x: number; y: number; z: number };
    vina_log?: string;
    from_cache?: boolean;
    interactions?: DockingInteraction;
    pose_interactions?: DockingPoseInteractions[];
    ligand_pdb?: string;
  };
  error?: string;
};

export async function runDocking(pdbId: string, smiles: string, pdbUrl?: string): Promise<{ job_id: string; status: string }> {
  const res = await api.post('/api/docking/run', { pdb_id: pdbId, smiles, pdb_url: pdbUrl || '' });
  return res.data;
}

export async function getDockingStatus(jobId: string): Promise<DockingResult> {
  const res = await api.get(`/api/docking/status/${jobId}`);
  return res.data;
}

export function getDockingPdbUrl(jobId: string): string {
  return `/api/backend/docking/result/${jobId}/pdb`;
}

export type SequencingQC = {
  total_reads: number;
  total_bases: number;
  avg_read_length: number;
  min_read_length: number;
  max_read_length: number;
  gc_percent: number;
  mean_quality: number;
  min_quality: number;
  max_quality: number;
  q20_percent: number;
  q30_percent: number;
  overrepresented_sequences: { sequence: string; count: number; percent: number }[];
};

export type SequencingAlignment = {
  mapped_reads: number;
  unmapped_reads: number;
  total_alignments: number;
};

export type SequencingVariant = {
  pos: number;
  ref: string;
  alt: string;
  depth: number;
  alt_count: number;
  freq: number;
};

export type SequencingResult = {
  job_id: string;
  status: string;
  result?: {
    reference: string;
    qc: SequencingQC;
    alignment: SequencingAlignment;
    variants: SequencingVariant[];
    consensus_sequence?: string;
    report: {
      reference: string;
      qc_summary: { total_reads: number; total_bases: number; mean_quality: number; q30_percent: number; gc_percent: number };
      variant_summary: { total_variants: number; snv_count: number; avg_depth: number };
      variants: SequencingVariant[];
    };
    steps_completed: string[];
  };
  error?: string;
};

export type SequencingReference = {
  id: string;
  name: string;
};

export async function runSequencing(fastqUrl: string, reference: string = 'sars-cov-2'): Promise<{ job_id: string; status: string }> {
  const res = await api.post('/api/sequencing/run', { fastq_url: fastqUrl, reference });
  return res.data;
}

export async function getSequencingStatus(jobId: string): Promise<SequencingResult> {
  const res = await api.get(`/api/sequencing/status/${jobId}`);
  return res.data;
}

export async function listSequencingReferences(): Promise<SequencingReference[]> {
  const res = await api.get('/api/sequencing/references');
  return res.data.references || [];
}

// ---------------------------------------------------------------------------
// ADMET descriptors
// ---------------------------------------------------------------------------

export type ADMETResult = {
  smiles: string;
  formula: string;
  heavy_atoms: number;
  molecular_weight: number;
  logp: number;
  tpsa: number;
  hbd: number;
  hba: number;
  rotatable_bonds: number;
  qed_score: number;
  lipinski: { pass: boolean; violations: string[]; violation_count: number };
  veber: { pass: boolean; violations: string[]; violation_count: number };
};

export async function computeADMET(smiles: string): Promise<{ result: ADMETResult }> {
  const res = await api.post('/api/admet/descriptors', { smiles });
  return res.data;
}

// ---------------------------------------------------------------------------
// MD Simulation
// ---------------------------------------------------------------------------

export type MDSimulationResult = {
  pdb_id: string;
  mode: string;
  engine: string;
  forcefield: string;
  implicit_solvent: string;
  temperature_k: number;
  timestep_fs: number;
  minimization_steps: number;
  equilibration_steps: number;
  production_steps: number;
  final_energy_kj_mol: number;
  energy: { minimization: { step: number; energy: number }[]; production: { step: number; energy: number }[] };
  rmsd: { frame: number; rmsd: number }[];
  rmsf: { residue: string; rmsf_angstrom: number }[];
  atom_count: number;
  residue_count: number;
  elapsed_seconds: number;
  status: string;
  note?: string;
  chain_count?: number;
  radius_of_gyration_angstrom?: number;
  avg_bfactor?: number;
  secondary_structure?: { helix: number; sheet: number; coil: number };
};

export async function runMD(pdbId: string, mode: string = 'minimize'): Promise<{ job_id: string; status: string }> {
  const res = await api.post('/api/md/run', { pdb_id: pdbId, mode });
  return res.data;
}

export async function getMDStatus(jobId: string): Promise<{ job_id: string; status: string; result?: MDSimulationResult; error?: string }> {
  const res = await api.get(`/api/md/status/${jobId}`);
  return res.data;
}

// ---------------------------------------------------------------------------
// Function Prediction (DeepFRI-inspired)
// ---------------------------------------------------------------------------

export type FunctionPredictionResult = {
  pdb_id: string;
  sequence_length: number;
  go_terms: { go_id: string; name: string; namespace: string; confidence: number }[];
  ec_numbers: { number: string; confidence: number }[];
  saliency: number[];
  method: string;
  note: string;
};

export async function predictFunction(pdbId: string): Promise<{ job_id: string; status: string }> {
  const res = await api.post('/api/function/predict', { pdb_id: pdbId });
  return res.data;
}

export async function getFunctionStatus(jobId: string): Promise<{ job_id: string; status: string; result?: FunctionPredictionResult; error?: string }> {
  const res = await api.get(`/api/function/status/${jobId}`);
  return res.data;
}

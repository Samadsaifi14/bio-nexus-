import axios from 'axios';
import type { JobStatus, UniprotSummary, SequenceResult, SequenceValidation, SequenceSearchResponse, PairwiseAlignResult, SequenceUtilitiesResult, MotifPatternScanResult, MotifLibraryResult, MotifLibraryPattern, DotPlotResult } from '@/types/pipeline';
import { getSupabase } from './supabase';

const api = axios.create({
  baseURL: '/api/backend',
  timeout: 30_000,
});

export const longApi = axios.create({
  baseURL: '/api/backend',
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
  return config;
});

export async function runPipeline(
  sequence: string,
  pipelineType: string = 'protein_analysis',
  database: string = 'uniprotkb_swissprot',
  maxHits: number = 10,
  queryAccession?: string,
  fastMode: boolean = false,
): Promise<{ job_id: string; status: string }> {
  const res = await longApi.post('/api/pipelines/run', {
    sequence,
    pipeline_type: pipelineType,
    database,
    max_hits: maxHits,
    query_accession: queryAccession ?? '',
    fast_mode: fastMode,
  });
  return res.data;
}

export async function getJob(jobId: string): Promise<JobStatus> {
  const res = await longApi.get(`/api/jobs/${jobId}`);
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

export type AIInterpretation = {
  headline: string;
  summary: string;
  findings: string[];
  caveats: string[];
};

export async function interpretToolResult(
  toolName: string,
  result: Record<string, unknown>,
): Promise<AIInterpretation> {
  const supabase = getSupabase();
  const { data: { session } } = await supabase.auth.getSession();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`;
  }
  const res = await fetch('/api/backend/api/ai/tool-interpret', {
    method: 'POST',
    headers,
    body: JSON.stringify({ tool_name: toolName, result }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const msg = (body && typeof body.detail === 'string' && body.detail) || 'Could not generate AI summary';
    throw new Error(msg);
  }
  return res.json();
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

export type UniprotSearchOptions = {
  reviewed?: boolean;
  organism?: string;
};

export async function searchUniprot(query: string, maxResults: number = 20, opts: UniprotSearchOptions = {}): Promise<{ results: UniprotSearchResult[]; count: number }> {
  const res = await api.post('/api/uniprot/search', {
    query,
    max_results: maxResults,
    reviewed: opts.reviewed ?? false,
    organism: opts.organism ?? '',
  });
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
  reviewed: boolean;
};

export type ScanPrositeMatch = {
  signature_ac: string;
  name: string;
  start: number;
  stop: number;
  level_tag: string;
};

export type ScanPrositeResult = {
  sequence_length: number;
  count: number;
  matches: ScanPrositeMatch[];
};

export async function scanPrositeSequence(sequence: string): Promise<ScanPrositeResult> {
  const res = await api.post('/api/domains/scan', { sequence });
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

export type PrimerSearchHit = {
  accession: string;
  title: string;
  organism: string;
  length: number;
  record_type: string;
  suggested_use: string;
};

export type PrimerSearchResponse = {
  query: string;
  db: string;
  count: number;
  results: PrimerSearchHit[];
  error?: string;
};

export type PrimerStructure = {
  dg: number;
  stem_length: number;
  stem: string;
  loop?: string;
  involves_a3?: boolean;
  involves_b3?: boolean;
  risk: string;
  note: string;
};

export type PrimerQC = {
  sequence: string;
  length: number;
  gc: number;
  tm_50mM: number;
  hairpin: PrimerStructure;
  self_dimer: PrimerStructure;
};

export type PrimerAnalyzeResponse = {
  qc: {
    left: PrimerQC;
    right: PrimerQC;
    hetero_dimer: PrimerStructure;
  };
  pcr?: {
    template_length: number;
    forward_binding_sites: number;
    reverse_binding_sites: number;
    forward_positions: number[];
    reverse_positions: number[];
    specific: boolean;
    amplicons: { start: number; end: number; length: number }[];
    primer3_consistent: boolean | null;
    matches_product_size: boolean | null;
    note: string | null;
  };
};

export async function searchPrimerTargets(query: string, maxResults: number = 12): Promise<PrimerSearchResponse> {
  const res = await api.post('/api/primers/search', { query, max_results: maxResults });
  return res.data;
}

export async function analyzePrimer(payload: {
  left_seq: string;
  right_seq: string;
  template?: string;
  left_pos?: number;
  right_pos?: number;
  expected_product?: number;
}): Promise<PrimerAnalyzeResponse> {
  const res = await api.post('/api/primers/analyze', payload);
  return res.data;
}

export type AlignmentResult = {
  job_id: string;
  aln_fasta: string;
  aln_clustal: string;
  phylotree: string;
  stype: string;
  method?: string;
};

export async function runPipelineV2(sequence: string, steps?: string[], alignmentMode?: 'global' | 'local'): Promise<{ job_id: string }> {
  const res = await longApi.post('/api/pipeline/v2/run', { sequence, steps: steps || undefined, alignment_mode: alignmentMode || 'global' });
  return res.data;
}

export async function getPipelineStatusV2(jobId: string): Promise<any> {
  const res = await longApi.get(`/api/pipeline/v2/status/${jobId}`);
  return res.data;
}

export type AlignmentMethod = 'clustalo' | 'muscle' | 'kalign' | 'mafft' | 'tcoffee';

export async function runAlignment(sequence: string, stype: string = 'protein', method: AlignmentMethod = 'clustalo'): Promise<AlignmentResult> {
  const res = await api.post('/api/alignment/run', { sequence, stype, method });
  return res.data;
}

export type PairwiseAlignOptions = {
  hit_accession?: string;
  subject_sequence?: string;
  query_sequence?: string;
  query_accession?: string;
  mode?: 'global' | 'local';
  matrix?: 'blosum62' | 'pam250';
};

export async function runPairwiseAlignment(options: PairwiseAlignOptions): Promise<PairwiseAlignResult> {
  const res = await api.post('/api/alignment/pairwise', {
    hit_accession: options.hit_accession ?? '',
    subject_sequence: options.subject_sequence ?? '',
    query_sequence: options.query_sequence ?? '',
    query_accession: options.query_accession ?? '',
    mode: options.mode ?? 'global',
    matrix: options.matrix ?? 'blosum62',
  });
  return res.data;
}

export async function analyzeSequence(payload: {
  sequence: string;
  seq_type?: 'auto' | 'dna' | 'rna' | 'protein';
}): Promise<SequenceUtilitiesResult> {
  const res = await api.post('/api/seq-tools/analyze', {
    sequence: payload.sequence,
    seq_type: payload.seq_type ?? 'auto',
  });
  return res.data;
}

export async function scanMotifPattern(payload: {
  sequence: string;
  pattern: string;
}): Promise<MotifPatternScanResult> {
  const res = await api.post('/api/seq-tools/motif-scan', payload);
  return res.data;
}

export async function scanMotifLibrary(
  sequence: string,
  categories?: string[],
): Promise<MotifLibraryResult> {
  const res = await api.post('/api/seq-tools/motif-library', { sequence, categories });
  return res.data;
}

export async function fetchMotifPatterns(): Promise<MotifLibraryPattern[]> {
  const res = await api.get('/api/seq-tools/motif-library/patterns');
  return res.data;
}

export async function fetchMotifCategories(): Promise<string[]> {
  const res = await api.get('/api/seq-tools/motif-library/categories');
  return res.data;
}

export async function runDotPlot(payload: {
  seq_a: string;
  seq_b: string;
  window: number;
  stringency: number;
  scoring?: string;
}): Promise<DotPlotResult> {
  const res = await api.post('/api/seq-tools/dotplot', {
    seq_a: payload.seq_a,
    seq_b: payload.seq_b,
    window: payload.window,
    stringency: payload.stringency,
    scoring: payload.scoring ?? 'identity',
  });
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
    geneRatio: number;
    entitiesFDR: number;
    entitiesPValue: number;
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

export function getExportUrl(jobId: string, format: 'pdf' | 'json' | 'ro-crate'): string {
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
  hydrogens?: number;
  coords?: DockingAtom[];
  affinity: number | null;
  rmsd_lb?: number | null;
  rmsd_ub?: number | null;
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
    ligand_properties?: {
      molecular_formula: string;
      molecular_weight: number;
      heavy_atoms: number;
      hydrogen_count: number;
      total_atoms: number;
      rotatable_bonds: number;
      tpsa: number;
      hbd: number;
      hba: number;
      logp: number;
    };
    box_center: { x: number; y: number; z: number };
    box_size: { x: number; y: number; z: number };
    vina_log?: string;
    vina_version?: string;
    vina_seed?: number | null;
    vina_exhaustiveness?: number | null;
    from_cache?: boolean;
    interactions?: DockingInteraction;
    pose_interactions?: DockingPoseInteractions[];
    ligand_pdb?: string;
  };
  error?: string;
};

export async function runDocking(
  pdbId: string,
  smiles: string,
  pdbUrl?: string,
  gridCenter?: number[],
): Promise<{ job_id: string; status: string }> {
  const res = await longApi.post('/api/docking/run', {
    pdb_id: pdbId,
    smiles,
    pdb_url: pdbUrl || '',
    ...(gridCenter && gridCenter.length === 3 ? { grid_center: gridCenter } : {}),
  });
  return res.data;
}

export async function getDockingStatus(jobId: string): Promise<DockingResult> {
  const res = await longApi.get(`/api/docking/status/${jobId}`);
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
// NGS Pipeline
// ---------------------------------------------------------------------------

export type NGSQC = {
  tool: string;
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
  quality_by_position?: { position: number; mean: number; q10: number; q90: number }[];
  gc_by_window?: number[];
  read_length_distribution?: { length: number; count: number }[];
  overrepresented_sequences: { sequence: string; count: number; percent: number }[];
};

export type NGSTrimming = {
  tool: string;
  reads_before: number;
  reads_after: number;
  reads_discarded: number;
};

export type NGSAlignment = {
  tool: string;
  mapped_reads: number;
  unmapped_reads: number;
  total_alignments: number;
  read_region?: string;
};

export type NGSAnnotation = {
  tool: string;
  reference: string;
  annotations: { pos: number; ref: string; alt: string; gene: string; mutation: string; significance: string; depth: number; freq: number; protein_change?: string }[];
  total_annotated: number;
  known_variants_found: number;
};

export type NGSResult = {
  job_id: string;
  status: string;
  result?: {
    reference: string;
    reference_size: number;
    fastq_source: string;
    qc: NGSQC;
    trimming: NGSTrimming;
    alignment: NGSAlignment;
    variants: { pos: number; ref: string; alt: string; depth: number; alt_count: number; freq: number }[];
    annotation: NGSAnnotation;
    consensus_sequence?: string;
    file_urls?: { bam?: string; bai?: string; sam?: string; vcf?: string; reference?: string };
    report: {
      reference: string;
      qc_summary: { total_reads: number; total_bases: number; mean_quality: number; q30_percent: number; gc_percent: number };
      trimming_summary: { reads_before: number; reads_after: number };
      alignment_summary: { mapped_reads: number; unmapped_reads: number; mapping_rate: number };
      variant_summary: { total_variants: number; snv_count: number; known_variants: number; novel_variants: number };
    };
    steps_completed: string[];
    progress: Record<string, string>;
    tools_used: Record<string, string>;
  };
  error?: string;
};

export type NGSReference = {
  id: string;
  name: string;
};

export async function runNGS(fastqUrl: string, reference: string = 'sars-cov-2'): Promise<{ job_id: string; status: string }> {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const res = await api.post('/api/ngs/run', { fastq_url: fastqUrl, reference });
      return res.data;
    } catch (err: any) {
      if (err?.response?.status === 503 && attempt === 0) {
        await new Promise((r) => setTimeout(r, 5000));
        continue;
      }
      throw err;
    }
  }
  throw new Error('Server is waking up — please try again in a moment');
}

export async function getNGSStatus(jobId: string): Promise<NGSResult> {
  const res = await longApi.get(`/api/ngs/status/${jobId}`);
  return res.data;
}

export async function listNGSReferences(): Promise<NGSReference[]> {
  const res = await api.get('/api/ngs/references');
  return res.data.references || [];
}

// ---------------------------------------------------------------------------
// Multi-assay NGS Platform (v2): assay router + QC contract engine + readiness gate
// ---------------------------------------------------------------------------

export type Ngs2Detection = {
  assay: string;
  sample_type: string;
  library_type: string;
  confidence: number;
  evidence: string[];
  pairs: string[][];
};

export type Ngs2StageContract = {
  step: string;
  tool: string;
  inputs: string[];
  outputs: string[];
  fail_blocks: boolean;
  expectation: string;
};

export type Ngs2Metric = {
  name: string;
  value: number | null;
  status: string;
  expected: string | null;
  detail: string | null;
};

export type Ngs2Stage = {
  step: string;
  tool: string;
  version: string;
  inputs: string[];
  outputs: string[];
  qc: {
    status: string;
    decision: string;
    metrics: Ngs2Metric[];
  } | null;
  decision: string;
  data: Record<string, unknown>;
};

export type Ngs2AnalyzeResult = {
  detection: Ngs2Detection;
  requested: {
    assay: string;
    reference: string;
    synthetic_reference: boolean;
    reads_loaded: Record<string, number>;
  };
  pipeline: {
    pipeline: string;
    pipeline_status: string;
    pipeline_decision: string;
    stopped_at: string | null;
    warnings: string[];
    stages: Ngs2Stage[];
    provenance: Record<string, unknown>;
  };
  visualization: Ngs2Visualization;
};

export type Ngs2Visualization = {
  sam: string;
  vcf: string;
  locus: string | null;
  n_reads: number;
  n_mapped: number;
  n_variants: number;
};

export async function runNgs2Analyze(payload: {
  file_paths: string[];
  reference?: string;
  assay?: string;
  sample_type?: string;
  metadata?: Record<string, unknown>;
  synthetic_reference?: boolean;
}): Promise<Ngs2AnalyzeResult> {
  const res = await longApi.post('/api/ngs/v2/analyze', payload);
  return res.data;
}

export async function listNgs2Stages(): Promise<Ngs2StageContract[]> {
  const res = await api.get('/api/ngs/v2/stages');
  return res.data.stages || [];
}

export async function detectNgs2Assay(payload: {
  file_paths: string[];
  reference?: string;
  assay?: string;
  metadata?: Record<string, unknown>;
}): Promise<Ngs2Detection> {
  const res = await api.post('/api/ngs/v2/detect', payload);
  return res.data;
}

// ---------------------------------------------------------------------------
// Staged Molecular Dynamics (v2): in-process MD DAG + QC contract engine
// ---------------------------------------------------------------------------

export type Md2Metric = {
  name: string;
  value: number | null;
  status: string;
  expected: string | null;
  detail: string | null;
};

export type Md2Stage = {
  step: string;
  tool: string;
  version: string;
  inputs: string[];
  outputs: string[];
  qc: {
    status: string;
    decision: string;
    metrics: Md2Metric[];
  } | null;
  decision: string;
  data: Record<string, unknown>;
};

export type Md2EngineStatus = {
  primary: string;
  engines: Record<string, { available: boolean; version?: string; note?: string }>;
};

export type Md2StageContract = {
  step: string;
  tool: string;
  inputs: string[];
  outputs: string[];
  fail_blocks: boolean;
  expectation: string;
};

export type Md2AnalyzeResult = {
  requested: {
    pdb_id: string;
    forcefield: string;
    solvent: string;
    production_ps: number | null;
    source: string;
  };
  pipeline: {
    pipeline: string;
    pipeline_status: string;
    pipeline_decision: string;
    stopped_at: string | null;
    warnings: string[];
    stages: Md2Stage[];
    provenance: Record<string, unknown>;
  };
};

export async function runMd2Analyze(payload: {
  pdb_id: string;
  forcefield?: string;
  solvent?: string;
  production_ps?: number;
  nvt_ps?: number;
}): Promise<Md2AnalyzeResult> {
  const res = await longApi.post('/api/md/v2/analyze', payload);
  return res.data;
}

export async function listMd2Stages(): Promise<Md2StageContract[]> {
  const res = await api.get('/api/md/v2/stages');
  return res.data.stages || [];
}

export async function getMd2EngineStatus(): Promise<Md2EngineStatus> {
  const res = await api.get('/api/md/v2/engine');
  return res.data;
}


// ---------------------------------------------------------------------------
// ADMET descriptors
// ---------------------------------------------------------------------------

export type ADMETSwissADME = {
  physicochemical: {
    formula: string;
    molecular_weight: number;
    fraction_csp3: number;
    rotatable_bonds: number;
    hba: number;
    hbd: number;
    tpsa: number;
  };
  lipophilicity: {
    ilogp: number | null;
    xlogp3: number | null;
    wlogp: number;
    mlogp: number | null;
    silicos_it: number | null;
    consensus_log_p: number;
    note: string;
  };
  water_solubility: {
    esol_log_s: number;
    esol_class: string;
    esol_mol_per_l: number;
    esol_mg_per_ml: number;
    note: string;
  };
  pharmacokinetics: {
    gi_absorption: string;
    bbb_permeant: string;
    pgp_substrate: string;
    cyp1a2_inhibitor: string;
    cyp2c19_inhibitor: string;
    cyp2c9_inhibitor: string;
    cyp2d6_inhibitor: string;
    cyp3a4_inhibitor: string;
    log_kp_skin: number;
    boiled_egg: {
      tpsa: number;
      wlogp: number;
      in_white_gia: boolean;
      in_yolk_bbb: boolean;
      region: string;
      polygons: { white: [number, number][]; yolk: [number, number][] };
    };
  };
  drug_likeness: {
    lipinski: { pass: boolean; violations: string[]; violation_count: number };
    ghose: { pass: boolean; violations: string[]; violation_count: number };
    veber: { pass: boolean; violations: string[]; violation_count: number };
    egan: { pass: boolean; violations: string[]; violation_count: number };
    muegge: { pass: boolean; violations: string[]; violation_count: number };
    bioavailability_score: number;
  };
  medicinal_chemistry: {
    pains_alerts: { pass: boolean; alerts: string[]; alert_count: number };
    brenk_alerts: { pass: boolean; alerts: string[]; alert_count: number };
    lead_likeness_violations: number;
    synthetic_accessibility: number | null;
  };
  bioavailability_radar: {
    axes: { axis: string; label: string; value: number; min: number; max: number; note: string }[];
    all_optimal: boolean;
  };
};

export type ADMETResult = {
  smiles: string;
  chemical_name?: string;
  pubchem_cid?: number;
  formula: string;
  swissadme?: ADMETSwissADME;
  heavy_atoms: number;
  molecular_weight: number;
  logp: number;
  tpsa: number;
  hbd: number;
  hba: number;
  rotatable_bonds: number;
  qed_score: number;
  molar_refractivity: number;
  molecular_volume: number;
  fsp3: number;
  labute_asa: number;
  estate_sum: number;
  wiener_index: number;
  zagreb_index: number;
  ring_count: number;
  aromatic_ring_count: number;
  aliphatic_ring_count: number;
  num_heteroatoms: number;
  num_amide_bonds: number;
  num_atom_stereocenters: number;
  num_unspecified_stereocenters: number;
  functional_groups: Record<string, number>;
  _methodology?: Record<string, { tier: string; confidence: string; method: string; note: string }>;
  drug_likeness: {
    overall_score: number;
    qed_score: number;
    lipinski: { pass: boolean; violations: string[]; violation_count: number };
    veber: { pass: boolean; violations: string[]; violation_count: number };
    ghose: { pass: boolean; violations: string[]; violation_count: number };
    egan: { pass: boolean; violations: string[]; violation_count: number };
    mddr: { pass: boolean; violations: string[]; violation_count: number };
  };
  structural_alerts: {
    pains: { pass: boolean; alerts: string[]; alert_count: number };
    brenk: { pass: boolean; alerts: string[]; alert_count: number };
    total_alert_count: number;
  };
  absorption: {
    oral_bioavailability: number;
    caco2_permeability: string;
    pgp_substrate: string;
    pgp_inhibitor: string;
    hia: string;
  };
  distribution: {
    volume_of_distribution: number;
    bbb_permeability: string;
    plasma_protein_binding: string;
    cns_penetration: string;
  };
  metabolism: {
    cyp_inhibition: Record<string, string>;
    cyp_substrate_risk: string;
    half_life_class: string;
    lipophilic_efficiency: number;
  };
  toxicity: {
    _disclaimer?: string;
    ames_mutagenicity: string;
    ames_alerts: string[];
    herg_liability: string;
    hepatotoxicity_dili: string;
    skin_sensitization: string;
    skin_sensitization_factors: string[];
    acute_toxicity_ld50: string;
    ld50_estimate_log: number;
    risk_score: number;
  };
  clearance: {
    clearance_class: string;
    half_life_class: string;
  };
};

export type ADMETInput = {
  smiles?: string;
  name?: string;
  cid?: number;
};

export async function computeADMET(input: ADMETInput): Promise<{ result: ADMETResult }> {
  const res = await api.post('/api/admet/descriptors', input);
  return res.data;
}

export type ADMETSearchHit = {
  cid: number;
  name: string;
  formula?: string;
  smiles?: string;
};

export async function searchCompounds(query: string, limit = 10): Promise<ADMETSearchHit[]> {
  if (!query.trim()) return [];
  const res = await api.get('/api/admet/search', { params: { q: query, limit } });
  return res.data.results || [];
}

export type ProToxResult = {
  task_id: string;
  input: string;
  input_type: string;
  requested_models: string;
  chemical_name?: string;
  pubchem_cid?: number;
  acute_toxicity: Record<string, string>;
  model_results: Record<string, string>[];
  toxicity_targets: Record<string, string>[];
  methodology?: { tier: string; confidence: string; method: string; note: string };
};

export async function computeProTox(input: { smiles?: string; name?: string; models?: string }): Promise<{ result: ProToxResult }> {
  const res = await longApi.post('/api/admet/protox', input);
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
  production_ps?: number;
  final_energy_kj_mol: number;
  energy: { minimization: { step: number; energy: number }[]; production: { step: number; energy: number }[] };
  temperature?: { step: number; temperature_k: number; kinetic_kj_mol: number }[];
  radius_of_gyration?: { step: number; rg_angstrom: number }[];
  sasa?: { step: number; sasa_angstrom2: number }[];
  sasa_avg_angstrom2?: number;
  rmsd: { frame: number; rmsd: number }[];
  rmsd_basis?: string;
  rmsd_avg_angstrom?: number;
  minimization_drift_angstrom?: number;
  rmsd_source?: string;
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

export type MDRunOptions = {
  forcefield?: string;
  solvent?: string;
  run_length_ps?: number;
};

export type MDForceFieldsMenu = {
  forcefields: { value: string; label: string }[];
  solvents: { value: string; label: string }[];
  combos: Record<string, string[]>;
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
// Function Prediction (DeepFRI-inspired)
// ---------------------------------------------------------------------------

export type FunctionPredictionResult = {
  pdb_id: string;
  sequence_length: number;
  go_terms: { go_id: string; name: string; namespace: string; confidence: number }[];
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
  area_sa: number;
  volume_sa: number;
  num_residues: number;
  residues: string[];
  centroid: number[];
  radius: number;
  residue_details: CastpPocketResidue[];
  gap_ranges: CastpPocketGap[];
  chain_spans: CastpChainSpan[];
  active_site_hits: CastpActiveSiteResidue[];
}

export interface CastpResult {
  pdb_id: string;
  probe_radius: number;
  total_residues: number;
  pockets: CastpPocket[];
  sequence_source?: string;
  structure_source?: string;
  structure_pdb?: string;
  pipeline?: CastpPipelineStep[];
  uniprot?: CastpUniProt | null;
  chains?: CastpChain[];
  active_sites?: CastpActiveSiteResidue[];
}

export async function runCastp(pdbId: string, probeRadius = 1.4): Promise<CastpResult> {
  const res = await longApi.post('/api/castp/analyze', { pdb_id: pdbId, probe_radius: probeRadius });
  return res.data;
}

export async function runCastpSequence(sequence: string, probeRadius = 1.4): Promise<CastpResult> {
  const res = await longApi.post('/api/castp/analyze', { sequence, probe_radius: probeRadius });
  return res.data;
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
  fpocket_pockets: { id: number; druggability_score: number; volume: number; area: number; score: number; num_residues: number }[];
  castp_pockets: { id: number; area_sa: number; volume_sa: number }[];
  cleaned_pdb: string;
  error: string | null;
}

export async function runStructurePrep(pdbId: string, probeRadius = 1.4): Promise<StructurePrepJob> {
  const res = await longApi.post('/api/structure-prep/run', { pdb_id: pdbId, probe_radius: probeRadius });
  return res.data;
}

export async function runStructurePrepSequence(sequence: string, probeRadius = 1.4): Promise<StructurePrepJob> {
  const res = await longApi.post('/api/structure-prep/run', { sequence, probe_radius: probeRadius });
  return res.data;
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

export type SequenceType = 'protein' | 'dna' | 'rna' | 'unknown';

export interface SequenceResult {
  accession: string;
  db_source: string;
  sequence_type: SequenceType;
  sequence: string;
  length: number;
  organism: string;
  description: string;
  gene_names?: string[];
  functions?: string[];
  keywords?: string[];
  go_terms?: string[];
  features?: Array<{
    type: string;
    description: string;
    begin: number | null;
    end: number | null;
  }>;
  pdb_ids?: string[];
  from_cache: boolean;
  error?: string;
}

export interface SequenceValidation {
  valid: boolean;
  sequence_type: SequenceType;
  format: string;
  length: number;
  issues: string[];
}

export interface SequenceSearchResult {
  accession: string;
  title: string;
  organism: string;
  length: number;
}

export interface SequenceSearchResponse {
  results: SequenceSearchResult[];
  count: number;
  query: string;
  error?: string;
}

export type PipelineType = 'protein_analysis';

export interface PipelineDefinition {
  id: PipelineType;
  name: string;
  description: string;
  input_type: string;
  input_label: string;
  steps: string[];
  default_database: string;
  default_max_hits: number;
}

export type JobStepStatus = 'queued' | 'running' | 'submitted_to_ncbi' | 'polling_ncbi' | 'parsing' | 'interpreting' | 'pathway_enrichment' | 'fetching_alphafold' | 'complete' | 'failed';

export const STEP_LABELS: Record<JobStepStatus, string> = {
  queued: 'Queued',
  running: 'Running BLAST pipeline',
  submitted_to_ncbi: 'Submitted to NCBI BLAST',
  polling_ncbi: 'NCBI is searching — this can take a minute',
  parsing: 'Reading results',
  interpreting: 'Writing your explanation',
  pathway_enrichment: 'Running pathway enrichment',
  fetching_alphafold: 'Fetching AlphaFold structure',
  complete: 'Complete',
  failed: 'Failed',
};

export interface JobStatus {
  id: string;
  tool: string;
  query_preview: string;
  status: JobStepStatus;
  pipeline_type: PipelineType;
  steps_completed: string[];
  context_json: AssembledContext | null;
  progress_pct: number;
  current_step_label?: string;
  created_at: string;
  completed_at: string | null;
  error: string | null;
  error_message?: string | null;
  share_token: string | null;
}

export interface PathwayEnrichmentPathway {
  stId: string;
  name: string;
  species: string;
  entitiesFound: number;
  entitiesTotal: number;
  entitiesFDR: number;
}

export interface PathwayEnrichment {
  token: string;
  pathways: PathwayEnrichmentPathway[];
}

export interface InteractionPartner {
  partner_gene: string;
  partner_protein: string;
  combined_score: number;
  nscore: number;
  fscore: number;
  pscore: number;
  ascore: number;
  escore: number;
  dscore: number;
  tscore: number;
}

export interface InteractionsResult {
  gene: string;
  species: number;
  interactions: InteractionPartner[];
}

export interface AssembledContext {
  query: {
    sequence: string;
    length: number;
    sequence_type?: 'protein' | 'dna' | 'rna';
    accession?: string;
  };
  blast: BlastSummary;
  uniprot: UniprotSummary | null;
  alphafold: AlphaFoldResult | null;
  pathway_enrichment?: PathwayEnrichment | null;
  interactions?: InteractionsResult | null;
}

export interface BlastSummary {
  count: number;
  source: string;
  database: string;
  top_hit: {
    accession: string;
    description: string;
    evalue: number;
    identity_pct: number;
    bit_score: number;
    alignment_length: number;
  } | null;
  hits: BlastHitSummary[];
}

export interface BlastHitSummary {
  accession: string;
  description: string;
  organism?: string;
  evalue: number;
  evalue_raw?: string;
  identity_pct: number;
  bit_score: number;
  alignment_length?: number;
  query_coverage_pct?: number;
  query_from?: number;
  query_to?: number;
  hit_from?: number;
  hit_to?: number;
  positive?: number;
  gaps?: number;
  query_alignment?: string;
  hit_alignment?: string;
  midline?: string;
}

export interface UniprotSummary {
  accession: string;
  full_name: string;
  organism: string;
  gene_names: string[];
  functions: string[];
  keywords: string[];
  subcellular_locations: string[];
  pdb_ids: string[];
  features: UniprotFeature[];
  go_terms: string[];
  sequence_length: number;
  sequence: string;
  cds_accessions?: CdsCrossRef[];
}

export interface CdsCrossRef {
  database: string;
  accession: string;
  protein_sequence_id: string;
  nucleotide_sequence_id: string;
}

export interface UniprotFeature {
  type: string;
  description: string;
  begin: number | null;
  end: number | null;
}

export interface AlphaFoldResult {
  uniprot_accession: string;
  structure_available: boolean;
  pdb_url: string | null;
  cif_url: string | null;
  confidence: number | null;
  model_created_date: string;
}

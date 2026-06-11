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

export interface JobStatus {
  id: string;
  tool: string;
  query_preview: string;
  status: 'pending' | 'running' | 'complete' | 'failed';
  pipeline_type: PipelineType;
  steps_completed: string[];
  context_json: AssembledContext | null;
  progress_pct: number;
  created_at: string;
  completed_at: string | null;
  error: string | null;
  share_token: string | null;
}

export interface AssembledContext {
  query: {
    sequence: string;
    length: number;
  };
  blast: BlastSummary;
  uniprot: UniprotSummary | null;
  alphafold: AlphaFoldResult | null;
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
  evalue: number;
  identity_pct: number;
  bit_score: number;
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

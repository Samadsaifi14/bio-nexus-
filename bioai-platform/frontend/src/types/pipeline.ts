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

export type JobStepStatus = 'queued' | 'running' | 'submitted_to_ncbi' | 'polling_ncbi' | 'parsing' | 'fetching_uniprot' | 'running_msa' | 'interpreting' | 'pathway_enrichment' | 'fetching_alphafold' | 'complete' | 'failed';

export const STEP_LABELS: Record<JobStepStatus, string> = {
  queued: 'Queued',
  running: 'Running BLAST pipeline',
  submitted_to_ncbi: 'Submitted to NCBI BLAST',
  polling_ncbi: 'NCBI is searching — this can take a minute',
  parsing: 'Parsing BLAST results',
  fetching_uniprot: 'Fetching UniProt annotations',
  running_msa: 'Running multiple sequence alignment',
  interpreting: 'Writing AI interpretation',
  pathway_enrichment: 'Running pathway enrichment',
  fetching_alphafold: 'Resolving protein structure',
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
  parent_job_id: string | null;
}

export interface PathwayEnrichmentPathway {
  stId: string;
  name: string;
  species: string;
  entitiesFound: number;
  entitiesTotal: number;
  geneRatio: number;
  entitiesFDR: number | null;
  entitiesPValue: number | null;
  adjustedPValue?: number | null;
  significance_source?: string;
  provider?: string;
}

export interface PathwayEnrichment {
  token: string;
  pathways: PathwayEnrichmentPathway[];
  method?: string;
  provider?: string;
  provider_label?: string;
  correction_method?: string;
  significance_note?: string;
  projection?: {
    identifiers_found?: number | null;
    identifiers_not_found?: number | null;
    identifiers_total?: number | null;
    found_note?: string;
  };
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

export interface PipelineDomainHit {
  accession?: string;
  name?: string;
  source_db?: string;
  start?: number;
  end?: number;
  score?: number | null;
  description?: string;
}

export interface PipelineDomainEvidence {
  uniprot_accession?: string;
  sequence_length?: number;
  confidence?: string;
  domains: PipelineDomainHit[];
  error?: string;
}

export interface AssembledContext {
  sequence?: string;
  length?: number;
  query: {
    sequence: string;
    length: number;
    sequence_type?: 'protein' | 'dna' | 'rna';
    accession?: string;
    confidence?: QueryConfidence;
  };
  blast: BlastSummary;
  uniprot: UniprotSummary | null;
  alphafold: AlphaFoldResult | null;
  pathway_enrichment?: PathwayEnrichment | null;
  interactions?: InteractionsResult | null;
  domains?: PipelineDomainEvidence | null;
  msa?: {
    aln_fasta?: string | null;
  phylotree?: string | null;
  phylotree_method?: string | null;
  method?: string | null;
  sequence_count?: number;
  engine?: string | null;
    msa_stats?: MsaStats | null;
  };
  phylo?: { phylotree_newick?: string; method?: string | null; source_alignment_method?: string | null };
  phylo_data?: { phylotree_newick?: string };
  final_report?: FinalSynthesisReport | null;
}

export interface SynthesisFinding {
  claim: string;
  confidence_tier: QueryConfidence;
  source_tool: string;
  page_url?: string | null;
}

export interface FinalSynthesisReport {
  headline: string;
  summary: string;
  findings: SynthesisFinding[];
  caveats: string[];
  _mode?: 'llm_polished' | 'deterministic';
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
  query_coverage_pct?: number | null;
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

export interface PairwiseAlignResult {
  mode: 'global' | 'local';
  matrix: string;
  open_gap_score: number;
  extend_gap_score: number;
  score: number;
  aligned_query: string;
  aligned_hit: string;
  alignment_length: number;
  identity: number;
  pct_identity: number;
  mismatches: number;
  similarity: number;
  pct_similarity: number;
  gaps_total: number;
  gap_positions: Array<{ seq: 'query' | 'subject'; inserted_after: number; length: number }>;
  query_start: number;
  query_end: number;
  hit_start: number;
  hit_end: number;
  query_length: number;
  hit_length: number;
  hit_source?: string;
}

export interface MsaStats {
  length: number;
  matched: number;
  mismatched: number;
  gapped: number;
  total_gaps: number;
  identity_pct: number;
}

export interface MsaStepResult {
  aln_fasta?: string | null;
  phylotree?: string | null;
  phylotree_method?: string | null;
  method?: string | null;
  sequence_count?: number;
  alignment_mode?: 'global' | 'local';
  engine?: string | null;
  engine_version?: string | null;
  input_sha256?: string;
  output_sha256?: string;
  msa_stats?: MsaStats | null;
  fallback_used?: boolean;
  pairwise?: PairwiseAlignResult | null;
  pairwise_subject?: string | null;
  error?: string | null;
}

export interface UniprotSummary {
  accession: string;
  reviewed?: boolean;
  release?: string;
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
  /** Tier-6 de novo annotation bundle (stored in the uniprot slot when no homolog was identified) */
  _de_novo?: boolean;
  composition?: Record<string, unknown> & { sequence_type?: string };
  function_hints?: { go_terms?: string[]; _note?: string; source?: string };
}

export type QueryConfidence = 'identified' | 'homolog' | 'de_novo';

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
  evidence?: string[];
}

export interface AlphaFoldResult {
  uniprot_accession?: string | null;
  structure_available: boolean;
  pdb_url?: string | null;
  cif_url?: string | null;
  confidence?: number | null;
  model_created_date?: string | null;
  latest_version?: number | null;
  /** Inline PDB text (tier-6 ESMFold predictions carry the model directly, no URL) */
  pdb_text?: string | null;
  mean_plddt?: number | null;
  source?: string;
  structure_type?: 'experimental' | 'predicted' | string;
  pdb_id?: string | null;
  evidence_class?: string;
  message?: string;
}


// --- Sequence utilities toolkit -------------------------------------------

export interface SeqTranslationFrames {
  frames: Record<string, string>;
  best: {
    frame: number;
    strand: 'forward' | 'reverse';
    protein: string;
    start: number;
    length: number;
    has_stop: boolean;
    starts_with_m: boolean;
  } | null;
}

export interface SeqRestrictionSite {
  name: string;
  recognition: string;
  count: number;
  positions: number[];
}

export interface SeqAaComposition {
  aa: string;
  count: number;
  pct: number;
}

export interface SequenceUtilitiesResult {
  sequence_type: 'dna' | 'rna' | 'protein' | 'unknown';
  detected_type: string;
  length: number;
  gc_content: number | null;
  molecular_weight: number | null;
  reverse_complement: string | null;
  transcription: string | null;
  translation: SeqTranslationFrames | null;
  aa_composition: SeqAaComposition[] | null;
  restriction_sites: SeqRestrictionSite[] | null;
  issues: string[];
}

// --- Motif scanner --------------------------------------------------------

export interface MotifMatch {
  start: number;
  end: number;
  motif: string;
}

export interface MotifPatternScanResult {
  sequence_type: string;
  pattern: string;
  regex: string;
  count: number;
  matches: MotifMatch[];
}

export interface MotifLibraryHit {
  name: string;
  accession: string;
  category: string;
  specificity: 'high' | 'loose';
  description: string;
  pattern: string;
  count: number;
  matches: MotifMatch[];
}

export interface MotifLibraryResult {
  sequence_type: string;
  length: number;
  patterns_scanned: number;
  motifs_found: number;
  hits: MotifLibraryHit[];
}

export interface MotifLibraryPattern {
  name: string;
  accession: string;
  category: string;
  specificity: 'high' | 'loose';
  description: string;
  pattern: string;
}

// --- Dot plot -------------------------------------------------------------

export interface DotPlotFeatures {
  main_diagonal_pct: number;
  gaps: { count: number; largest: number };
  off_diagonal: Array<{ offset: number; count: number }>;
  anti_diagonal: Array<{ sum: number; count: number }>;
}

export interface DotPlotResult {
  sequence_type: string;
  sequence_type_a?: string;
  sequence_type_b?: string;
  seq_a_length: number;
  seq_b_length: number;
  window: number;
  stringency: number;
  scoring: string;
  scoring_used: string;
  threshold: number;
  match_rule?: 'window_identity' | 'percent_of_perfect_self_match';
  total_matches: number;
  dot_count: number;
  downsampled: boolean;
  features: DotPlotFeatures;
  dots: Array<[number, number]>;
}

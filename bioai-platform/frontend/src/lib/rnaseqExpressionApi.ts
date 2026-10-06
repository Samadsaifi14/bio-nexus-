import { longApi } from '@/lib/api';

export type RnaSeqArtifact = {
  name: string;
  kind: string;
  content_type: string;
  bytes: number;
  sha256: string;
  url: string;
};

export type RnaSeqExpressionSummary = {
  enrichment?: {
    status: string; message: string; organism: string; gene_id_type?: string;
    database?: string; method?: string; method_key?: string; background?: string;
    direction_conflicts?: number; aliases_recovered?: number; mapping_coverage?: number; annotation_coverage?: number;
    coverage_warning?: string; interpretation_note?: string;
    background_genes?: number; genes_eligible?: number; genes_uniquely_mapped?: number;
    genes_unmapped?: number; genes_ambiguous?: number; terms_tested?: number; significant_terms?: number;
  };
  genes_input: number;
  genes_kept: number;
  genes_removed: number;
  samples: number;
  reference_level: string;
  test_level: string;
  condition_column: string;
  covariates: string[];
  design: string;
  min_count: number;
  min_samples_requested?: number;
  min_samples: number;
  replicate_counts?: Record<string, number>;
  design_full_rank?: boolean;
  design_rank?: number;
  design_columns?: number;
  design_warnings?: string[];
  experimental_unit_status?: string;
  technical_covariates_detected?: string[];
  technical_covariates_in_model?: string[];
  library_size_min?: number;
  library_size_max?: number;
  library_size_fold_range?: number;
  size_factor_library_correlation?: number | null;
  alpha: number;
  lfc_threshold: number;
  significant: number;
  up: number;
  down: number;
  pca_percent_variance: { PC1: number; PC2: number };
  size_factor_min: number;
  size_factor_max: number;
  lfc_shrinkage: string;
  expression_heatmap_generated: boolean;
  expression_heatmap_basis: 'significant_DE_genes' | 'top_variable_genes_QC' | 'none';
  expression_heatmap_genes: number;
  package_versions: Record<string, string>;
};

export type RnaSeqExpressionResult = {
  run_id: string;
  state: 'SUCCEEDED';
  summary: RnaSeqExpressionSummary;
  provenance: Record<string, unknown>;
  artifacts: RnaSeqArtifact[];
  manifest_url: string;
};

export type RnaSeqExpressionUpload = {
  counts: File;
  metadata: File;
  conditionColumn: string;
  referenceLevel: string;
  testLevel: string;
  covariates?: string;
  alpha?: number;
  lfcThreshold?: number;
  minCount?: number;
  minSamples?: number;
  topHeatmapGenes?: number;
  organism?: string;
};

export async function runRnaSeqExpression(payload: RnaSeqExpressionUpload): Promise<RnaSeqExpressionResult> {
  const form = new FormData();
  form.append('organism', payload.organism ?? 'auto');
  form.append('counts', payload.counts);
  form.append('metadata', payload.metadata);
  form.append('condition_column', payload.conditionColumn);
  form.append('reference_level', payload.referenceLevel);
  form.append('test_level', payload.testLevel);
  form.append('covariates', payload.covariates ?? '');
  form.append('alpha', String(payload.alpha ?? 0.05));
  form.append('lfc_threshold', String(payload.lfcThreshold ?? 1));
  form.append('min_count', String(payload.minCount ?? 10));
  form.append('min_samples', String(payload.minSamples ?? 0));
  form.append('top_heatmap_genes', String(payload.topHeatmapGenes ?? 40));
  const response = await longApi.post('/api/ngs/v2/rnaseq/expression/run', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export async function runCerSalsDemo(): Promise<RnaSeqExpressionResult> {
  const response = await longApi.post('/api/ngs/v2/rnaseq/expression/demo');
  return response.data;
}

export async function getRnaSeqExpressionRun(runId: string): Promise<RnaSeqExpressionResult> {
  const response = await longApi.get(`/api/ngs/v2/rnaseq/expression/runs/${encodeURIComponent(runId)}`);
  return response.data;
}

export type EnrichmentRetryOptions = {
  organism: string; database: string; method: string; idType: string; aliases: boolean;
  databaseLabel?: string; namespace?: string; gmt?: File | null; mapping?: File | null;
};

export async function rerunRnaSeqEnrichment(runId: string, options: EnrichmentRetryOptions): Promise<RnaSeqExpressionResult> {
  const form = new FormData();
  form.append('organism', options.organism);
  form.append('database', options.database);
  form.append('method', options.method);
  form.append('id_type', options.idType);
  form.append('aliases', String(options.aliases));
  form.append('database_label', options.databaseLabel ?? '');
  form.append('namespace', options.namespace ?? '');
  if (options.gmt) form.append('gmt', options.gmt);
  if (options.mapping) form.append('mapping', options.mapping);
  const response = await longApi.post(`/api/ngs/v2/rnaseq/expression/runs/${encodeURIComponent(runId)}/enrichment`, form,
    { headers: { 'Content-Type': 'multipart/form-data' } });
  return response.data;
}

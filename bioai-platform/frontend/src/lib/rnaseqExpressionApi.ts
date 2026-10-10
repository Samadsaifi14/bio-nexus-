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
  input_kind?: string;
  normalization_method?: string;
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
  countOrigin: { kind: 'raw_counts'; normalization: 'none'; evidence: string; method: string; annotation: string; reviewed: boolean };
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

export async function runRnaSeqExpression(payload: RnaSeqExpressionUpload): Promise<{ job_id: string; state: string }> {
  const form = new FormData();
  form.append('organism', payload.organism ?? 'auto');
  form.append('counts', payload.counts);
  form.append('count_origin', JSON.stringify(payload.countOrigin));
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
  if (typeof response.data?.job_id !== 'string') throw new Error('Invalid queued expression job');
  return response.data;
}

export async function runCerSalsDemo(): Promise<RnaSeqExpressionResult> {
  const response = await longApi.post('/api/ngs/v2/rnaseq/expression/demo');
  return parseExpressionResult(response.data);
}

export async function getRnaSeqExpressionRun(runId: string): Promise<RnaSeqExpressionResult> {
  const response = await longApi.get(`/api/ngs/v2/rnaseq/expression/runs/${encodeURIComponent(runId)}`);
  return parseExpressionResult(response.data);
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
  return parseExpressionResult(response.data);
}


export function parseExpressionResult(value: unknown): RnaSeqExpressionResult {
  if (!value || typeof value !== 'object') throw new Error('Invalid expression result');
  const result = value as Record<string, unknown>;
  const summary = result.summary as Record<string, unknown> | undefined;
  if (result.state !== 'SUCCEEDED' || typeof result.run_id !== 'string' || !summary || !Array.isArray(result.artifacts)) throw new Error('Incomplete expression result');
  const arrays = ['covariates', 'design_warnings', 'technical_covariates_detected', 'technical_covariates_in_model'];
  const normalized = { ...summary };
  for (const key of arrays) {
    const entry = summary[key];
    if (entry === null || entry === undefined) normalized[key] = [];
    else if (typeof entry === 'string') normalized[key] = [entry]; // historical jsonlite singleton
    else if (Array.isArray(entry) && entry.every(item => typeof item === 'string')) normalized[key] = entry;
    else throw new Error(`Invalid list field: ${key}`);
  }
  for (const key of ['genes_input', 'genes_kept', 'samples', 'significant', 'up', 'down', 'alpha', 'lfc_threshold']) {
    if (typeof summary[key] !== 'number' || !Number.isFinite(summary[key])) throw new Error(`Invalid numeric result: ${key}`);
  }
  const pca = summary.pca_percent_variance as Record<string, unknown> | undefined;
  if (!pca || typeof pca.PC1 !== 'number' || typeof pca.PC2 !== 'number') throw new Error('Missing PCA variance');
  for (const item of result.artifacts) {
    if (!item || typeof item !== 'object' || typeof item.name !== 'string' || typeof item.url !== 'string' || typeof item.sha256 !== 'string') throw new Error('Invalid artifact manifest');
  }
  return { ...result, summary: normalized } as RnaSeqExpressionResult;
}

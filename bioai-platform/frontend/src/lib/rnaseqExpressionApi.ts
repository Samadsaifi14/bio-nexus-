import { longApi } from '@/lib/api';

export type RnaSeqArtifact = {
  name: string;
  kind: string;
  content_type: string;
  bytes: number;
  url: string;
};

export type RnaSeqExpressionSummary = {
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
  min_samples: number;
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
};

export async function runRnaSeqExpression(payload: RnaSeqExpressionUpload): Promise<RnaSeqExpressionResult> {
  const form = new FormData();
  form.append('counts', payload.counts);
  form.append('metadata', payload.metadata);
  form.append('condition_column', payload.conditionColumn);
  form.append('reference_level', payload.referenceLevel);
  form.append('test_level', payload.testLevel);
  form.append('covariates', payload.covariates ?? '');
  form.append('alpha', String(payload.alpha ?? 0.05));
  form.append('lfc_threshold', String(payload.lfcThreshold ?? 1));
  form.append('min_count', String(payload.minCount ?? 10));
  form.append('min_samples', String(payload.minSamples ?? 2));
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

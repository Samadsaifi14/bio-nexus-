export type ScientificStatus = 'VALID' | 'DEGRADED' | 'NOT_EVALUATED' | 'FAILED';

export type ScientificArtifact = {
  name: string;
  media_type?: string;
  url?: string;
  sha256?: string;
  available?: boolean;
  role?: string;
  reason?: string;
  [key: string]: unknown;
};

export type ScientificPlot = {
  id: string;
  title: string;
  data: unknown;
  [key: string]: unknown;
};

export type ScientificResult<TResults extends Record<string, unknown> = Record<string, unknown>> = {
  status: ScientificStatus;
  method: string;
  engine: string;
  engine_version: string;
  database: string | null;
  database_version: string | null;
  parameters: Record<string, unknown>;
  input_sha256: string;
  output_sha256: string;
  fallback_used: boolean;
  fallback_method: string | null;
  results: TResults;
  plots: ScientificPlot[];
  artifacts: ScientificArtifact[];
  evidence_class: string;
  validation: Record<string, unknown>;
  citations: unknown[];
};

/**
 * The frontend is deliberately presentation-only for scientific values.
 * Never normalize, infer, rename, backfill, or recalculate ScientificResult
 * fields here.  If a field is absent, render it as unavailable and fix the
 * scientific backend if the field should exist.
 */
export function isScientificResult(value: unknown): value is ScientificResult {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Record<string, unknown>;
  return (
    ['VALID', 'DEGRADED', 'NOT_EVALUATED', 'FAILED'].includes(String(candidate.status)) &&
    typeof candidate.method === 'string' &&
    typeof candidate.engine === 'string' &&
    typeof candidate.engine_version === 'string' &&
    typeof candidate.input_sha256 === 'string' &&
    typeof candidate.output_sha256 === 'string' &&
    !!candidate.results && typeof candidate.results === 'object' &&
    Array.isArray(candidate.plots) &&
    Array.isArray(candidate.artifacts)
  );
}

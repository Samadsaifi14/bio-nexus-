export type ComparatorDefinition = {
  reference: string;
  reference_url: string;
  kind: string;
  metrics: string[];
  plots: string[];
};

export type ComparisonMetric = {
  id: string;
  label: string;
  value: unknown;
  reference_value?: unknown;
  unit?: string | null;
  note?: string | null;
};

export type ComparisonSeries = {
  id: string;
  kind: string;
  points: Array<Record<string, unknown>>;
  x_label?: string;
  y_label?: string;
};

export type ScientificComparison = {
  schema: string;
  analysis_type: string;
  comparator: ComparatorDefinition;
  reference_metadata: Record<string, unknown>;
  concordance: {
    score: number | null;
    status: string;
    meaning: string;
  };
  metrics: ComparisonMetric[];
  series: ComparisonSeries[];
  matched_entities: string[];
  claim_boundary: {
    same_input_required: boolean;
    same_reference_or_database_required: boolean;
    same_parameters_required: boolean;
    missing_measurements_are_not_zero: boolean;
    superiority_claim_allowed: boolean;
    note: string;
  };
};

export type ComparatorRegistry = {
  schema: string;
  policy: string;
  comparators: Record<string, ComparatorDefinition>;
};

const API = '/api/backend/api/benchmarks';

export async function getReferenceComparators(): Promise<ComparatorRegistry> {
  const res = await fetch(`${API}/reference-comparators`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Could not load reference comparators (${res.status})`);
  return res.json();
}

export async function compareWithReference(args: {
  analysis_type: string;
  bionexus: Record<string, unknown>;
  reference: Record<string, unknown>;
  top_n?: number;
  reference_metadata?: Record<string, unknown>;
}): Promise<ScientificComparison> {
  const res = await fetch(`${API}/reference-comparators/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(args),
  });
  if (!res.ok) {
    let detail = `Reference comparison failed (${res.status})`;
    try {
      const body = await res.json();
      detail = typeof body?.detail === 'string' ? body.detail : detail;
    } catch {
      // Preserve status-based fallback.
    }
    throw new Error(detail);
  }
  return res.json();
}

export type ScientificStatus =
  | 'VALID'
  | 'DEGRADED'
  | 'NOT_EVALUATED'
  | 'FAILED';

export interface ScientificPlot {
  name: string;
  kind?: string;
  title?: string;
  xlabel?: string;
  ylabel?: string;
  /** Plot payload emitted by the backend. Rendered as-is, never recalculated. */
  data?: unknown;
  /** SVG/PNG inline or a reference to a generated artifact. */
  image?: string;
  artifact_id?: string;
}

export interface ScientificArtifact {
  name: string;
  kind?: string;
  format?: string;
  url?: string;
  sha256?: string;
}

export interface Citation {
  source: string;
  accession?: string;
  version?: string;
  url?: string;
}

/**
 * Canonical ScientificResult envelope produced by every BioNexus backend.
 *
 * The frontend rendering rule is NON-NEGOTIABLE: components render exactly the
 * fields the backend emitted. They never invent, recalculate, rename or
 * silently substitute scientific values. Absent fields render as absent.
 */
export interface ScientificResult {
  status: ScientificStatus;
  method: string;
  engine: string;
  engine_version?: string | null;
  database?: string | null;
  database_version?: string | null;
  parameters?: Record<string, unknown>;
  input_sha256?: string;
  output_sha256?: string;
  fallback_used?: boolean;
  fallback_method?: string | null;
  results: Record<string, unknown>;
  plots?: ScientificPlot[];
  artifacts?: ScientificArtifact[];
  evidence_class?: string;
  validation?: Record<string, unknown>;
  citations?: Citation[];
}

/** True only when the backend actually emitted a usable value for `key`. */
export function hasValue(
  source: Record<string, unknown> | undefined | null,
  key: string,
): boolean {
  if (!source) return false;
  const v = source[key];
  return v !== undefined && v !== null;
}

/** Read a value the backend emitted; absent fields yield `undefined`. */
export function emitted<T>(
  source: Record<string, unknown> | undefined | null,
  key: string,
): T | undefined {
  if (!source) return undefined;
  const v = source[key];
  return v === undefined || v === null ? undefined : (v as T);
}
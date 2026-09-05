import { getSupabase } from './supabase';

async function scientificFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const supabase = getSupabase();
  const { data: { session } } = await supabase.auth.getSession();
  const headers = new Headers(init?.headers);
  headers.set('Content-Type', 'application/json');
  if (session?.access_token) headers.set('Authorization', `Bearer ${session.access_token}`);
  const response = await fetch(`/api/backend${path}`, { ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(typeof detail === 'string' ? detail : `Scientific API request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export type AlignmentColumnInsight = {
  alignment_position: number;
  consensus: string;
  conservation: number;
  entropy_bits: number;
  gap_fraction: number;
  logo: Array<{ symbol: string; frequency: number; information_bits: number }>;
};

export type AlignmentInsights = {
  sequence_type: 'dna' | 'protein';
  sequence_count: number;
  alignment_length: number;
  consensus: string;
  mean_conservation: number;
  mean_entropy_bits: number;
  columns: AlignmentColumnInsight[];
  variant_mapping: Array<Record<string, unknown>>;
};

export function getAlignmentInsights(payload: {
  aligned_sequences: string[];
  reference_index?: number;
  variants?: Array<Record<string, unknown>>;
}): Promise<AlignmentInsights> {
  return scientificFetch('/api/seq-tools/alignment-insights', {
    method: 'POST',
    body: JSON.stringify({ reference_index: 0, variants: [], ...payload }),
  });
}

export type MultiplexCompatibility = {
  pair_count: number;
  tm_range: [number, number] | null;
  tm_spread_c: number;
  medium_or_high_cross_dimers: number;
  compatible_screen: boolean;
  evidence_class: 'Heuristic';
  limitation: string;
  cross_dimers: Array<Record<string, unknown>>;
};

export function screenPrimerMultiplex(
  pairs: Array<Record<string, unknown>>,
  maxTmSpreadC = 3,
): Promise<MultiplexCompatibility> {
  return scientificFetch('/api/primers/multiplex', {
    method: 'POST',
    body: JSON.stringify({ pairs, max_tm_spread_c: maxTmSpreadC }),
  });
}

export type StructuralContactResult = {
  cutoff_angstrom: number;
  residue_count: number;
  contact_count: number;
  contacts: Array<Record<string, unknown>>;
};

export function getStructuralContacts(pdbId: string, chain?: string, cutoff = 8): Promise<StructuralContactResult> {
  const query = new URLSearchParams({ cutoff: String(cutoff) });
  if (chain) query.set('chain', chain);
  return scientificFetch(`/api/structure_insights/${encodeURIComponent(pdbId)}/contacts?${query}`);
}

export function getStructuralInterfaces(pdbId: string, cutoff = 5): Promise<Record<string, unknown>> {
  return scientificFetch(`/api/structure_insights/${encodeURIComponent(pdbId)}/interfaces?cutoff=${cutoff}`);
}

export function getStructuralSurface(pdbId: string, chain?: string): Promise<Record<string, unknown>> {
  const query = chain ? `?chain=${encodeURIComponent(chain)}` : '';
  return scientificFetch(`/api/structure_insights/${encodeURIComponent(pdbId)}/surface${query}`);
}

export function mapStructuralMutation(payload: {
  pdb_id: string;
  chain: string;
  residue_number: number;
  alternate: string;
}): Promise<Record<string, unknown>> {
  return scientificFetch('/api/structure_insights/mutation', { method: 'POST', body: JSON.stringify(payload) });
}

export type PhyloRootResult = {
  newick: string;
  rooting: string;
  terminal_count: number;
  scientific_boundary: string;
};

export function rootPhylogeny(payload: { newick: string; method: 'midpoint' | 'outgroup'; outgroup?: string }): Promise<PhyloRootResult> {
  return scientificFetch('/api/phylo/insights/root', { method: 'POST', body: JSON.stringify(payload) });
}

export function consensusPhylogeny(trees: string[], cutoff = 0.5): Promise<Record<string, unknown>> {
  return scientificFetch('/api/phylo/insights/consensus', { method: 'POST', body: JSON.stringify({ trees, cutoff }) });
}

export function overlayPhylogenyMetadata(newick: string, metadata: Record<string, Record<string, unknown>>): Promise<Record<string, unknown>> {
  return scientificFetch('/api/phylo/insights/metadata-overlay', { method: 'POST', body: JSON.stringify({ newick, metadata }) });
}

export function analyzeDockingPoses(payload: {
  result_pdbqt: string;
  cluster_cutoff_angstrom?: number;
  pdb_id?: string;
  original_pdb_text?: string;
}): Promise<Record<string, unknown>> {
  return scientificFetch('/api/docking/analytics/poses', { method: 'POST', body: JSON.stringify(payload) });
}

export type RnaSeqProductionPlan = {
  schema_version: string;
  workflow: Record<string, string>;
  state: 'PLANNED' | 'BLOCKED';
  ready_to_launch: boolean;
  blockers: string[];
  warnings: string[];
  command_argv: string[];
  command_display: string;
  required_artifacts: Array<Record<string, unknown>>;
  provenance_requirements: string[];
  clinical_boundary: Record<string, unknown>;
};

export function planRnaSeqProduction(payload: Record<string, unknown>): Promise<RnaSeqProductionPlan> {
  return scientificFetch('/api/ngs/v2/rnaseq/production/plan', { method: 'POST', body: JSON.stringify(payload) });
}

export function figureExportUrl(jobId: string, format: 'svg' | 'png' | 'pdf' | 'tiff', dpi = 300): string {
  return `/api/backend/api/figures/${encodeURIComponent(jobId)}/export?format=${format}&dpi=${dpi}`;
}

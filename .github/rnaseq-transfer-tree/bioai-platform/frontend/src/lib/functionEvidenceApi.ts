import { longApi } from './api';

export type FunctionGoEvidence = {
  go_id: string;
  name: string;
  namespace: 'MF' | 'BP' | 'CC' | string;
  supporting_interpro_entries: string[];
  supporting_domain_hits: number;
  support_count: number;
  evidence_type: 'interpro2go_mapping' | string;
  source: string;
  source_url?: string;
  confidence: null;
  confidence_note: string;
};

export type FunctionDomainHit = {
  accession: string;
  name: string;
  database: string;
  start: number;
  end: number;
  score: number | null;
};

export type FunctionEvidenceResult = {
  pdb_id: string;
  sequence_length: number;
  status: 'inferred' | 'insufficient_evidence' | string;
  go_terms: FunctionGoEvidence[];
  ec_numbers: never[];
  ec_scope_note: string;
  domain_hits: FunctionDomainHit[];
  saliency: never[];
  residue_chemistry_scores: number[];
  residue_chemistry_note: string;
  composition: { aa: string; fractions: Record<string, number> };
  method: string;
  method_version: string;
  provenance: {
    sequence_source: string;
    domain_source: string;
    go_mapping_source: string;
    retrieval_is_live: boolean;
  };
  note: string;
};

export async function predictFunctionEvidence(pdbId: string): Promise<{ job_id: string; status: string }> {
  const res = await longApi.post('/api/function/predict', { pdb_id: pdbId });
  return res.data;
}

export async function getFunctionEvidenceStatus(jobId: string): Promise<{
  job_id: string;
  status: string;
  result?: FunctionEvidenceResult;
  error?: string;
}> {
  const res = await longApi.get(`/api/function/status/${jobId}`);
  return res.data;
}

import { longApi } from './api';

export type BlastProgram = 'blastp' | 'blastn' | 'blastx' | 'tblastn' | 'tblastx';

export async function runBlastPipeline(payload: {
  sequence: string;
  database: string;
  program: BlastProgram;
  sequenceType: 'protein' | 'dna' | 'rna';
  maxHits?: number;
  queryAccession?: string;
  fastMode?: boolean;
}): Promise<{ job_id: string; status: string }> {
  const response = await longApi.post('/api/pipelines/run', {
    sequence: payload.sequence,
    pipeline_type: 'blast',
    database: payload.database,
    program: payload.program,
    sequence_type: payload.sequenceType,
    max_hits: payload.maxHits ?? 100,
    query_accession: payload.queryAccession ?? '',
    fast_mode: payload.fastMode ?? false,
  });
  return response.data;
}

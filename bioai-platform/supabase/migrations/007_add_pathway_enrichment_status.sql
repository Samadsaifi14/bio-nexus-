-- Add pathway_enrichment to the jobs.status CHECK constraint

ALTER TABLE jobs DROP CONSTRAINT IF EXISTS jobs_status_check;

ALTER TABLE jobs ADD CONSTRAINT jobs_status_check
  CHECK (status IN (
    'queued', 'running', 'complete', 'failed',
    'submitted_to_ncbi', 'polling_ncbi', 'parsing',
    'interpreting', 'pathway_enrichment', 'fetching_alphafold'
  ));

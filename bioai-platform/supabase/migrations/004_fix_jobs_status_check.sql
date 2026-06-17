-- Fix jobs.status CHECK constraint to allow pipeline step statuses
-- Drop the old constraint and recreate with all valid statuses

ALTER TABLE jobs DROP CONSTRAINT IF EXISTS jobs_status_check;

ALTER TABLE jobs ADD CONSTRAINT jobs_status_check
  CHECK (status IN (
    'queued', 'running', 'complete', 'failed',
    'submitted_to_ncbi', 'polling_ncbi', 'parsing',
    'interpreting', 'fetching_alphafold'
  ));

-- Add columns used by the frontend JobStatus interface
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS current_step_label TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS error_message TEXT;

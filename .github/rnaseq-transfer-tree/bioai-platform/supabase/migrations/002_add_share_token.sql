-- Add share_token to jobs table for public share links

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS share_token text UNIQUE;
CREATE INDEX IF NOT EXISTS idx_jobs_share_token ON jobs(share_token) WHERE share_token IS NOT NULL;

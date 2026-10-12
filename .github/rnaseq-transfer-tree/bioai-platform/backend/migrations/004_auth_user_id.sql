-- Phase 0a: Add user_id to docking_jobs and sequencing_jobs for ownership enforcement.

ALTER TABLE docking_jobs
  ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES profiles(id) ON DELETE CASCADE;

ALTER TABLE sequencing_jobs
  ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES profiles(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_docking_jobs_user ON docking_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_sequencing_jobs_user ON sequencing_jobs(user_id);

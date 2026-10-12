-- Structure Prep: durable job store (replaces in-memory _jobs dict)
-- Pattern-match: docking_jobs / sequencing_jobs / ngs_jobs.
-- Run this in Supabase SQL Editor.

CREATE TABLE IF NOT EXISTS structure_prep_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES profiles(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'running'
      CHECK (status IN ('running', 'complete', 'failed')),
    step text NOT NULL DEFAULT '',
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    result jsonb NOT NULL DEFAULT '{}'::jsonb,
    chain_integrity text NOT NULL DEFAULT 'unknown'
      CHECK (chain_integrity IN ('unknown', 'intact', 'repaired', 'broken_unrepaired')),
    castp_status text NOT NULL DEFAULT 'pending'
      CHECK (castp_status IN ('pending', 'skipped', 'running', 'complete', 'timed_out', 'error')),
    fpocket_status text NOT NULL DEFAULT 'pending'
      CHECK (fpocket_status IN ('pending', 'running', 'complete', 'unavailable', 'error')),
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_structure_prep_jobs_user
  ON structure_prep_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_structure_prep_jobs_created
  ON structure_prep_jobs(created_at DESC);

ALTER TABLE structure_prep_jobs ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  CREATE POLICY "Users can view own structure prep jobs"
    ON structure_prep_jobs FOR SELECT USING (auth.uid() = user_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE POLICY "Users can insert own structure prep jobs"
    ON structure_prep_jobs FOR INSERT WITH CHECK (auth.uid() = user_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

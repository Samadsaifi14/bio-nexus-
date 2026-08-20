-- NGS Pipeline: fix ngs_jobs table + create claim RPC
-- Run this in Supabase SQL Editor if the table was created manually

-- 1. Add missing columns
ALTER TABLE ngs_jobs ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();
ALTER TABLE ngs_jobs ADD COLUMN IF NOT EXISTS updated_at timestamptz;

-- 2. Ensure RLS is enabled
ALTER TABLE ngs_jobs ENABLE ROW LEVEL SECURITY;

-- 3. RLS policies
DO $$ BEGIN
  CREATE POLICY "Users can view own NGS jobs"
    ON ngs_jobs FOR SELECT USING (auth.uid() = user_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE POLICY "Users can insert own NGS jobs"
    ON ngs_jobs FOR INSERT WITH CHECK (auth.uid() = user_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 4. Claim RPC (atomic FOR UPDATE SKIP LOCKED)
CREATE OR REPLACE FUNCTION claim_next_ngs_job(worker_id text)
RETURNS ngs_jobs
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  job ngs_jobs;
BEGIN
  SELECT * INTO job
  FROM ngs_jobs
  WHERE status = 'queued'
    AND attempts < max_attempts
  ORDER BY created_at ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED;

  IF job.id IS NOT NULL THEN
    UPDATE ngs_jobs
    SET status     = 'running',
        claimed_at = now(),
        claimed_by = worker_id,
        attempts   = attempts + 1,
        updated_at = now()
    WHERE id = job.id
    RETURNING * INTO job;
  END IF;

  RETURN job;
END;
$$;

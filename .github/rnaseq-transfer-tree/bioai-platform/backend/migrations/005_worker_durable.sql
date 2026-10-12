-- Phase 0b: Durable worker columns + claim RPCs for docking_jobs, sequencing_jobs, jobs.

-- ---------------------------------------------------------------------------
-- 1. Add worker tracking columns
-- ---------------------------------------------------------------------------
ALTER TABLE docking_jobs
  ADD COLUMN IF NOT EXISTS claimed_at   timestamptz,
  ADD COLUMN IF NOT EXISTS claimed_by   text,
  ADD COLUMN IF NOT EXISTS attempts     integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS max_attempts integer NOT NULL DEFAULT 3,
  ADD COLUMN IF NOT EXISTS updated_at   timestamptz,
  ADD COLUMN IF NOT EXISTS payload      jsonb;

ALTER TABLE sequencing_jobs
  ADD COLUMN IF NOT EXISTS claimed_at   timestamptz,
  ADD COLUMN IF NOT EXISTS claimed_by   text,
  ADD COLUMN IF NOT EXISTS attempts     integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS max_attempts integer NOT NULL DEFAULT 3,
  ADD COLUMN IF NOT EXISTS updated_at   timestamptz,
  ADD COLUMN IF NOT EXISTS payload      jsonb;

ALTER TABLE jobs
  ADD COLUMN IF NOT EXISTS claimed_at   timestamptz,
  ADD COLUMN IF NOT EXISTS claimed_by   text,
  ADD COLUMN IF NOT EXISTS attempts     integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS max_attempts integer NOT NULL DEFAULT 3;

-- ---------------------------------------------------------------------------
-- 2. Claim RPCs  (FOR UPDATE SKIP LOCKED — atomic, no double-processing)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION claim_next_docking_job(worker_id text)
RETURNS docking_jobs
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  job docking_jobs;
BEGIN
  SELECT * INTO job
  FROM docking_jobs
  WHERE status = 'queued'
    AND attempts < max_attempts
  ORDER BY created_at ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED;

  IF job.id IS NOT NULL THEN
    UPDATE docking_jobs
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


CREATE OR REPLACE FUNCTION claim_next_sequencing_job(worker_id text)
RETURNS sequencing_jobs
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  job sequencing_jobs;
BEGIN
  SELECT * INTO job
  FROM sequencing_jobs
  WHERE status = 'queued'
    AND attempts < max_attempts
  ORDER BY created_at ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED;

  IF job.id IS NOT NULL THEN
    UPDATE sequencing_jobs
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


CREATE OR REPLACE FUNCTION claim_next_pipeline_job(worker_id text)
RETURNS jobs
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  job jobs;
BEGIN
  SELECT * INTO job
  FROM jobs
  WHERE status = 'queued'
    AND attempts < max_attempts
  ORDER BY created_at ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED;

  IF job.id IS NOT NULL THEN
    UPDATE jobs
    SET status     = 'running',
        claimed_at = now(),
        claimed_by = worker_id,
        attempts   = attempts + 1
    WHERE id = job.id
    RETURNING * INTO job;
  END IF;

  RETURN job;
END;
$$;

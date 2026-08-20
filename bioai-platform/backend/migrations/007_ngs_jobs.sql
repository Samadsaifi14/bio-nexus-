-- NGS Pipeline: ngs_jobs table + claim RPC

CREATE TABLE IF NOT EXISTS ngs_jobs (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references profiles(id) on delete cascade,
  fastq_url   text,
  reference   text,
  status      text,
  result      jsonb,
  error       text,
  done_at     timestamptz,
  storage_url text,
  payload     jsonb,
  claimed_at  timestamptz,
  claimed_by  text,
  attempts    integer not null default 0,
  max_attempts integer not null default 3,
  updated_at  timestamptz
);

ALTER TABLE ngs_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own NGS jobs"
  ON ngs_jobs FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own NGS jobs"
  ON ngs_jobs FOR INSERT
  WITH CHECK (auth.uid() = user_id);

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

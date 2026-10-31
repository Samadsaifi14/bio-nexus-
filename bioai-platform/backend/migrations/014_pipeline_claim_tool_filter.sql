-- Keep the pipeline claim RPC out of tool-registry mirror rows.
--
-- `jobs` stores both durable pipeline runs (tool = 'pipeline') and best-effort
-- mirror rows written by app.services.job_registry for other tools (docking,
-- MSA, phylo, ...). Only pipeline runs are executed by app.worker, so a queued
-- tool mirror must never be claimed as a pipeline job. The sweep also relies on
-- this distinction when it closes out orphaned mirror rows.
--
-- Idempotent: safe to re-run.

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
    AND tool = 'pipeline'
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

-- 012_transient_jobs.sql — durable state for background jobs that are executed
-- in-process rather than by the claim-based durable worker.
--
-- Scope: phylo, pipeline_v2 and structure_predict keep their working state in a
-- module-level dict, so a container restart (a deploy, a scale-down, or a crash)
-- erased every job and its results: clients then got a 404 for a job that had
-- really only been interrupted.
--
-- The existing `jobs` table is deliberately NOT reused here. It is owner-scoped
-- (user_id references profiles) and backs history, dashboards and benchmarks;
-- these three routers serve unauthenticated/anonymous requests, so writing there
-- would either invent a system user or break ownership enforcement.
--
-- Semantics: this table is a mirror of the in-memory state, not a work queue.
-- There is no claiming: a job interrupted by a restart is *not* silently resumed,
-- because the subprocess that was computing it died with the container. Rows are
-- instead reconciled at startup into a terminal `interrupted` state so the record
-- survives and the user can re-run, which is the honest outcome.
--
-- `state` holds the serialisable job payload; `phase` is denormalised so startup
-- reconciliation can find non-terminal rows without deserialising every payload.

CREATE TABLE IF NOT EXISTS transient_jobs (
  job_id     uuid PRIMARY KEY,
  kind       text        NOT NULL,
  status     text        NOT NULL DEFAULT 'running',
  phase      text,
  state      jsonb       NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Startup reconciliation scans for non-terminal rows only.
CREATE INDEX IF NOT EXISTS idx_transient_jobs_status ON transient_jobs(status);

-- The per-kind job list endpoint reads recent jobs newest-first.
CREATE INDEX IF NOT EXISTS idx_transient_jobs_kind_created
  ON transient_jobs(kind, created_at DESC);

-- A job that finished a while ago is of no interest to anybody, and the mirror
-- exists only to survive restarts, so let it be reclaimed by the vacuum job.
CREATE INDEX IF NOT EXISTS idx_transient_jobs_updated
  ON transient_jobs(updated_at);

-- Keep updated_at honest without making every writer remember to set it.
CREATE OR REPLACE FUNCTION touch_transient_job_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS transient_jobs_touch_updated_at ON transient_jobs;
CREATE TRIGGER transient_jobs_touch_updated_at
  BEFORE UPDATE ON transient_jobs
  FOR EACH ROW
  EXECUTE FUNCTION touch_transient_job_updated_at();

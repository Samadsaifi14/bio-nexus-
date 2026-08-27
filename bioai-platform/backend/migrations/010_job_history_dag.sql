-- 010_job_history_dag.sql — DAG job history
-- Adds parent_job_id to enable branching: each job can point to the
-- job whose results it was derived from, forming a directed acyclic graph.

ALTER TABLE IF EXISTS jobs
  ADD COLUMN IF NOT EXISTS parent_job_id uuid REFERENCES jobs(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_jobs_parent ON jobs(parent_job_id)
  WHERE parent_job_id IS NOT NULL;

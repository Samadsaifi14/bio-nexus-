-- Durable ownership and execution state for real nf-core/sarek runs.
CREATE TABLE IF NOT EXISTS ngs_production_runs (
  run_id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  state text NOT NULL CHECK (state IN ('SUBMITTED','PENDING','RUNNING','SUCCEEDED','FAILED','UNKNOWN')),
  executor text NOT NULL CHECK (executor IN ('local','slurm','awsbatch')),
  executor_job_id text NOT NULL,
  workflow text NOT NULL,
  revision text NOT NULL,
  outdir text NOT NULL,
  submitted_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL,
  exit_code integer,
  message text
);

CREATE INDEX IF NOT EXISTS idx_ngs_production_runs_user_updated
  ON ngs_production_runs(user_id, updated_at DESC);

ALTER TABLE ngs_production_runs ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  CREATE POLICY "Users can view own production NGS runs"
    ON ngs_production_runs FOR SELECT USING (auth.uid() = user_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

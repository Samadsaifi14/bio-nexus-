ALTER TABLE jobs
  ADD COLUMN IF NOT EXISTS pipeline_type TEXT NOT NULL DEFAULT 'protein_analysis',
  ADD COLUMN IF NOT EXISTS context_json JSONB,
  ADD COLUMN IF NOT EXISTS steps_completed TEXT[] DEFAULT '{}';

ALTER TABLE ai_interpretations
  ADD COLUMN IF NOT EXISTS context_snapshot JSONB;

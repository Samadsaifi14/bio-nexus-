-- Phase 0c: Add storage_url columns for large artifact offloading to Supabase Storage.

-- docking_jobs: result_sdf moves to Storage; DB keeps only the URL.
ALTER TABLE docking_jobs
  ADD COLUMN IF NOT EXISTS storage_url text;

-- jobs: context_json / result moves to Storage for large payloads.
ALTER TABLE jobs
  ADD COLUMN IF NOT EXISTS storage_url text;

-- sequencing_jobs: consensus_sequence and large result sub-objects move to Storage.
ALTER TABLE sequencing_jobs
  ADD COLUMN IF NOT EXISTS storage_url text;

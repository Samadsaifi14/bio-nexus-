-- Run this in Supabase SQL Editor to ensure all docking_jobs columns exist.
-- Safe to run multiple times (uses IF NOT EXISTS).

ALTER TABLE IF EXISTS docking_jobs
  ADD COLUMN IF NOT EXISTS protein_name text DEFAULT '',
  ADD COLUMN IF NOT EXISTS protein_sequence text DEFAULT '',
  ADD COLUMN IF NOT EXISTS grid_center jsonb DEFAULT '[0,0,0]',
  ADD COLUMN IF NOT EXISTS grid_size jsonb DEFAULT '[20,20,20]',
  ADD COLUMN IF NOT EXISTS exhaustiveness integer DEFAULT 8,
  ADD COLUMN IF NOT EXISTS num_modes integer DEFAULT 9,
  ADD COLUMN IF NOT EXISTS affinity double precision,
  ADD COLUMN IF NOT EXISTS rmsd_lb double precision,
  ADD COLUMN IF NOT EXISTS rmsd_ub double precision,
  ADD COLUMN IF NOT EXISTS result_sdf text DEFAULT '',
  ADD COLUMN IF NOT EXISTS error text DEFAULT '',
  ADD COLUMN IF NOT EXISTS created_at text DEFAULT '',
  ADD COLUMN IF NOT EXISTS updated_at text DEFAULT '';

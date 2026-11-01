-- Allow castp_status = 'unavailable' on structure_prep_jobs.
--
-- The pipeline records 'unavailable' when the remote CASTpFold service does not
-- accept a submission (no job id). The original 008 migration omitted that value
-- from the CHECK constraint, so the final status write raised Postgres 23514 and
-- failed an otherwise successful prep run (live evidence: job
-- 99e1239d-8ac4-4d4b-a6ae-17346c69d87f, step running_castp, fpocket complete).
--
-- Safe to run multiple times. The application also applies this idempotently via
-- exec_sql before the first structure-prep run (app/routers/structure_prep.py).

ALTER TABLE IF EXISTS structure_prep_jobs
  DROP CONSTRAINT IF EXISTS structure_prep_jobs_castp_status_check;

ALTER TABLE IF EXISTS structure_prep_jobs
  ADD CONSTRAINT structure_prep_jobs_castp_status_check
  CHECK (castp_status IN (
    'pending', 'skipped', 'running', 'complete', 'timed_out', 'error', 'unavailable'
  ));

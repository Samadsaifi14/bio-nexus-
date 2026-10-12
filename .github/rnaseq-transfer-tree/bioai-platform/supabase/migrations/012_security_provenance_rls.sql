-- Phase 15 hardening: repair experiment provenance RLS ownership joins and
-- add immutable audit indexes. Existing service-role writes continue to bypass
-- RLS; authenticated users receive read access only to records owned via jobs.

-- The original experiment_steps policy compared text experiment_id against the
-- UUID primary key of experiments. Recreate it against the human-readable ID.
drop policy if exists "Users can view own experiment steps" on experiment_steps;
create policy "Users can view own experiment steps" on experiment_steps for select
  using (experiment_id in (
    select e.experiment_id from experiments e
    where e.job_id in (select j.id from jobs j where j.user_id = auth.uid())
  ));

drop policy if exists "Users can view own benchmark runs" on benchmark_runs;
create policy "Users can view own benchmark runs" on benchmark_runs for select
  using (experiment_id in (
    select e.experiment_id from experiments e
    where e.job_id in (select j.id from jobs j where j.user_id = auth.uid())
  ));

-- Prevent ordinary authenticated clients from mutating scientific audit tables.
-- There are intentionally no INSERT/UPDATE/DELETE policies on these tables;
-- trusted backend service-role operations are responsible for writes.
revoke insert, update, delete on experiments from authenticated;
revoke insert, update, delete on experiment_steps from authenticated;
revoke insert, update, delete on benchmark_runs from authenticated;
revoke insert, update, delete on experiment_audit_events from authenticated;

create index if not exists idx_exp_steps_node on experiment_steps(experiment_id, node_id);
create index if not exists idx_exp_audit_event_type on experiment_audit_events(event_type, created_at desc);

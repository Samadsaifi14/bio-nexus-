-- Phase 1 hardening: experiment versioning, lineage, archive and DOI metadata.
-- Existing immutable fingerprint columns remain write-once by application policy.

alter table experiments
  add column if not exists version integer not null default 1,
  add column if not exists parent_experiment_id text,
  add column if not exists output_hash text,
  add column if not exists archive_manifest jsonb,
  add column if not exists archived_at timestamptz,
  add column if not exists doi_metadata jsonb;

do $$ begin
  alter table experiments
    add constraint experiments_parent_experiment_fk
    foreign key (parent_experiment_id) references experiments(experiment_id) on delete set null;
exception when duplicate_object then null;
end $$;

do $$ begin
  alter table experiments add constraint experiments_version_positive check (version >= 1);
exception when duplicate_object then null;
end $$;

create index if not exists idx_experiments_parent on experiments(parent_experiment_id);
create index if not exists idx_experiments_pipeline on experiments(pipeline);
create index if not exists idx_experiments_input_hash on experiments(input_hash);
create index if not exists idx_experiments_created_at on experiments(created_at desc);
create index if not exists idx_experiments_git_commit on experiments(git_commit);

-- A compact immutable audit event stream for export/provenance actions that are
-- not naturally represented as scientific computation nodes.
create table if not exists experiment_audit_events (
  id uuid primary key default gen_random_uuid(),
  experiment_id text not null references experiments(experiment_id) on delete cascade,
  event_type text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_experiment_audit_events_experiment
  on experiment_audit_events(experiment_id, created_at);

alter table experiment_audit_events enable row level security;
create policy "Users can view own experiment audit events" on experiment_audit_events for select
  using (experiment_id in (
    select e.experiment_id from experiments e
    where e.job_id in (select id from jobs where user_id = auth.uid())
  ));

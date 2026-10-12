-- Phase 1: Additional tables for full feature support

-- Guest sessions tracking
create table if not exists guest_sessions (
  id uuid primary key default gen_random_uuid(),
  session_id text unique not null,
  user_id uuid references profiles(id) on delete set null,
  created_at timestamptz default now(),
  expires_at timestamptz default (now() + interval '24 hours'),
  last_active_at timestamptz default now()
);

-- Pipeline steps log
create table if not exists pipeline_steps (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references jobs(id) on delete cascade,
  step_name text not null,
  status text not null default 'queued',
  started_at timestamptz,
  completed_at timestamptz,
  error_message text,
  output_json jsonb,
  created_at timestamptz default now()
);

-- Raw API response storage
create table if not exists raw_api_responses (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references jobs(id) on delete cascade,
  source text not null,
  endpoint text,
  response_body text,
  response_format text default 'xml',
  stored_at timestamptz default now()
);

-- Processed/parsed results
create table if not exists processed_results (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references jobs(id) on delete cascade,
  result_type text not null,
  result_data jsonb not null,
  created_at timestamptz default now()
);

-- Saved analyses (user bookmarks)
create table if not exists saved_analyses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id) on delete cascade not null,
  job_id uuid references jobs(id) on delete cascade,
  title text,
  notes text,
  created_at timestamptz default now()
);

-- Sequence cache (UniProt/NCBI)
create table if not exists sequence_cache (
  id uuid primary key default gen_random_uuid(),
  accession text unique not null,
  source text not null,
  result_json jsonb not null,
  cached_at timestamptz default now(),
  expires_at timestamptz default (now() + interval '7 days')
);

-- Structure cache
create table if not exists structure_cache (
  id uuid primary key default gen_random_uuid(),
  pdb_id text,
  uniprot_accession text,
  source text not null,
  result_json jsonb not null,
  cached_at timestamptz default now(),
  expires_at timestamptz default (now() + interval '30 days')
);

-- Indexes
create index if not exists idx_pipeline_steps_job on pipeline_steps(job_id);
create index if not exists idx_raw_api_job on raw_api_responses(job_id);
create index if not exists idx_processed_results_job on processed_results(job_id);
create index if not exists idx_saved_analyses_user on saved_analyses(user_id);
create index if not exists idx_sequence_cache_acc on sequence_cache(accession);
create index if not exists idx_structure_cache_pdb on structure_cache(pdb_id);
create index if not exists idx_structure_cache_uniprot on structure_cache(uniprot_accession);
create index if not exists idx_guest_sessions_id on guest_sessions(session_id);

-- RLS
alter table pipeline_steps enable row level security;
alter table raw_api_responses enable row level security;
alter table processed_results enable row level security;
alter table saved_analyses enable row level security;
alter table sequence_cache enable row level security;
alter table structure_cache enable row level security;
alter table guest_sessions enable row level security;

-- Policies
create policy "Users can view own pipeline steps" on pipeline_steps for select
  using (job_id in (select id from jobs where user_id = auth.uid()));
create policy "Users can view own raw responses" on raw_api_responses for select
  using (job_id in (select id from jobs where user_id = auth.uid()));
create policy "Users can view own processed results" on processed_results for select
  using (job_id in (select id from jobs where user_id = auth.uid()));
create policy "Users can manage own saved analyses" on saved_analyses for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Update profiles with additional columns from schema.md
alter table profiles add column if not exists username text;
alter table profiles add column if not exists display_name text;
alter table profiles add column if not exists avatar_url text;
alter table profiles add column if not exists onboarding_complete boolean default false;
alter table profiles add column if not exists tooltips_enabled boolean default true;
alter table profiles add column if not exists jobs_this_month int default 0;
alter table profiles add column if not exists blast_calls_today int default 0;
alter table profiles add column if not exists quota_reset_at timestamptz;

-- Add title, description columns to jobs for richer display
alter table jobs add column if not exists title text;
alter table jobs add column if not exists description text;

-- Add cleanup function for expired data
create or replace function public.cleanup_expired_data()
returns void as $$
begin
  delete from sequence_cache where expires_at < now();
  delete from structure_cache where expires_at < now();
  delete from guest_sessions where expires_at < now();
end;
$$ language plpgsql security definer;

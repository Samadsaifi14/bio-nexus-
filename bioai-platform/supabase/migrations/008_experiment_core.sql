-- Milestone 1+2: Research Core — Experiment Manager, Provenance Graph, Benchmark Registry
-- Run: supabase db push
-- Services are written to degrade gracefully until these tables are applied
-- (they catch table-missing exceptions and log a warning, never fail a run).

-- 1. Experiments — one immutable row per analysis run.
--    The fingerprint columns (git_commit, software_versions, container_hash,
--    environment, parameters, ...) are written ONCE at creation and never
--    updated; only status/finished_at change. The experiment_id is the
--    human-readable immutable identifier referenced in figures/papers.
create table if not exists experiments (
  id uuid primary key default gen_random_uuid(),
  experiment_id text unique not null,
  job_id uuid references jobs(id) on delete cascade,
  pipeline text not null,
  input_hash text not null,
  git_commit text,
  software_versions jsonb,
  container_hash text,
  database_versions jsonb,
  environment jsonb,
  random_seed bigint,
  parameters jsonb,
  status text not null default 'running',
  started_at timestamptz default now(),
  finished_at timestamptz,
  created_at timestamptz default now()
);

-- 2. Provenance graph edges. Each recorded step is a node; `deps` lists the
--    node_ids it consumed, so a full clickable DAG
--    Sequence -> BLAST -> UniProt -> InterPro -> GO -> Reactome -> AI
--    can be reconstructed from (experiment_id, deps).
create table if not exists experiment_steps (
  id uuid primary key default gen_random_uuid(),
  experiment_id uuid references experiments(id) on delete cascade,
  node_id text not null,
  tool text,
  tool_version text,
  database text,
  database_version text,
  params jsonb,
  deps text[] default '{}',
  input_ref text,
  output_ref text,
  evidence jsonb,
  status text not null default 'complete',
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz default now(),
  unique (experiment_id, node_id)
);

-- 3. Benchmark catalog (BBS-1 expansion repository).
--    Each row carries ground truth + accepted tolerance + citation so every
--    figure/result produced from a benchmark is defensible.
create table if not exists benchmarks (
  id uuid primary key default gen_random_uuid(),
  category text not null,
  name text not null,
  description text,
  input jsonb not null,
  expected_output jsonb,
  tolerance jsonb,
  ground_truth text,
  citation text,
  source text,
  stage text not null default 'draft',
  created_at timestamptz default now()
);

-- 4. Benchmark runs — measured vs expected outcomes for an experiment.
create table if not exists benchmark_runs (
  id uuid primary key default gen_random_uuid(),
  benchmark_id uuid references benchmarks(id) on delete cascade,
  experiment_id uuid references experiments(id) on delete set null,
  status text not null default 'running',
  metrics jsonb,
  passed_checks jsonb,
  runtime_s numeric(12,3),
  run_at timestamptz default now()
);

-- Indexes
create index if not exists idx_experiments_job on experiments(job_id);
create index if not exists idx_experiments_status on experiments(status);
create index if not exists idx_exp_steps_experiment on experiment_steps(experiment_id);
create index if not exists idx_benchmarks_category on benchmarks(category);
create index if not exists idx_benchmark_runs_benchmark on benchmark_runs(benchmark_id);

-- RLS
alter table experiments enable row level security;
alter table experiment_steps enable row level security;
alter table benchmark_runs enable row level security;
-- benchmarks are reference data: world-readable, never user-written
alter table benchmarks enable row level security;

-- Policies: users may read experiments/steps/runs they own (via their job)
create policy "Users can view own experiments" on experiments for select
  using (job_id in (select id from jobs where user_id = auth.uid()));
create policy "Users can view own experiment steps" on experiment_steps for select
  using (experiment_id in (select id from experiments e where e.job_id in
    (select id from jobs where user_id = auth.uid())));
create policy "Users can view own benchmark runs" on benchmark_runs for select
  using (experiment_id in (select id from experiments e where e.job_id in
    (select id from jobs where user_id = auth.uid())));

-- Benchmarks readable by any authenticated user
create policy "Benchmarks are public reference data" on benchmarks for select
  using (true);
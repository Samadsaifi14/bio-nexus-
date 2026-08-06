# Bio Nexus — Database Schema

**Version:** 2.0
**Database:** Supabase (PostgreSQL 15)
**Storage:** Supabase Storage (public bucket) for large artifacts · Redis (optional) for TTL caching
**Last Updated:** August 2026

> Canonical source of truth: migrations in `bioai-platform/supabase/migrations/` (`001`–`007`) plus backend-side `bioai-platform/backend/migrations/` (`001_docking_jobs_columns`, `004_auth_user_id`, `005_worker_durable`, `006_artifact_storage`). Run with `supabase db push`.

---

## Design Decisions

### Jobs are tool-scoped rows, not multi-step DAG rows
`jobs` is one row per analysis with a `tool` column and a `status` CHECK constraint that enumerates the live intermediate states (`submitted_to_ncbi`, `polling_ncbi`, `parsing`, `interpreting`, `pathway_enrichment`, `fetching_alphafold`). The pipeline wizard (`tool = 'wizard_v2'`) persists a lightweight `jobs` row for history/share while the heavy step payload lives in-memory in the API process (see `pipeline_v2`).

### Long-running jobs are their own tables + a durable worker
Docking, MD simulation, function prediction, and sequencing are not rows in `jobs` — they live in `docking_jobs` and `sequencing_jobs` and are executed by `app/worker.py`, which claims them atomically (`FOR UPDATE SKIP LOCKED`), retries up to `max_attempts`, and sweeps stuck rows. `claimed_at / claimed_by / attempts / max_attempts` columns enable this without a separate queue (see `durable-worker-design.md`).

### Large artifacts go to Supabase Storage, not inline
`result_sdf` (docking), `consensus_sequence`/large result JSON (sequencing), and large `jobs.result / context_json` payloads are offloaded to a Supabase Storage bucket via `services/artifact_storage.py`; the row keeps only a `storage_url`. `_read` hydrates the payload back from storage when the inline column is empty.

### Caching is Redis-first, database-backed where useful
Hot external lookups are wrapped with `@ttl_cache` (`services/cache.py`). Redis is optional — if unreachable the cache silently no-ops. `cached_queries` and `sequence_cache`/`structure_cache` are DB-side caches for deterministic inputs.

---

## Table Reference

```
auth.users (Supabase-managed)
  └── profiles                 (auto-created by handle_new_user trigger)
        ├── jobs               (tool-scoped rows; share_token for public links)
        ├── api_keys           (sk_bio_ keys, SHA-256 hashed)
        ├── guest_sessions     (guest session link)
        ├── saved_analyses     (bookmarks)
        └── usage_log          (tokens / cost per tool)

docking_jobs   (docking + MD + function prediction via payload.tool_type)
sequencing_jobs
cached_queries · sequence_cache · structure_cache   (DB caches)
ai_interpretations · pipeline_steps · raw_api_responses · processed_results
waitlist
```

---

## Full Schema (SQL)

```sql
-- ============================================================
-- PROFILES — extends Supabase auth.users (trigger-created on signup)
-- ============================================================
create table if not exists profiles (
  id            uuid primary key references auth.users(id) on delete cascade,
  email         text,
  full_name     text,
  institution   text,
  role          text default 'researcher',
  username      text,                    -- added by 005_phase1_tables
  display_name  text,
  avatar_url    text,
  onboarding_complete boolean default false,
  tooltips_enabled   boolean default true,
  jobs_this_month    int  default 0,
  blast_calls_today  int  default 0,
  quota_reset_at     timestamptz,
  created_at    timestamptz default now()
);

-- ============================================================
-- JOBS — one row per analysis request
-- ============================================================
create table if not exists jobs (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid references profiles(id) on delete cascade,
  tool            text not null,         -- 'blast', 'wizard_v2', 'pairwise', ...
  query_preview   text,                  -- truncated query for list views
  status          text default 'queued' check (status in (
                    'queued','running','complete','failed',
                    'submitted_to_ncbi','polling_ncbi','parsing',
                    'interpreting','pathway_enrichment','fetching_alphafold'
                  )),
  progress_pct    int default 0,
  result          jsonb,                 -- may be NULL when offloaded to storage_url
  error           text,
  created_at      timestamptz default now(),
  completed_at    timestamptz,

  -- added by 002_add_share_token
  share_token     text unique,           -- token for public /share/{token} links

  -- added by 003_pipeline_engine
  pipeline_type   text not null default 'protein_analysis',
  context_json    jsonb,
  steps_completed text[] default '{}',

  -- added by 004_fix_jobs_status_check
  current_step_label text,
  error_message      text,

  -- added by 005_phase1_tables
  title         text,
  description   text,

  -- added by 005_worker_durable (backend migrations)
  claimed_at    timestamptz,
  claimed_by    text,
  attempts      integer not null default 0,
  max_attempts  integer not null default 3,

  -- added by 006_artifact_storage
  storage_url   text
);

-- ============================================================
-- CACHING
-- ============================================================
create table if not exists cached_queries (
  id          uuid primary key default gen_random_uuid(),
  query_hash  text unique not null,
  tool        text not null,
  result      jsonb not null,
  created_at  timestamptz default now(),
  expires_at  timestamptz default (now() + interval '24 hours')
);

create table if not exists sequence_cache (
  id          uuid primary key default gen_random_uuid(),
  accession   text unique not null,
  source      text not null,             -- 'ncbi' | 'uniprot' | 'pdb'
  result_json jsonb not null,
  cached_at   timestamptz default now(),
  expires_at  timestamptz default (now() + interval '7 days')
);

create table if not exists structure_cache (
  id                uuid primary key default gen_random_uuid(),
  pdb_id            text,
  uniprot_accession text,
  source            text not null,
  result_json       jsonb not null,
  cached_at         timestamptz default now(),
  expires_at        timestamptz default (now() + interval '30 days')
);

-- ============================================================
-- AI + AUDIT + GUESTS
-- ============================================================
create table if not exists ai_interpretations (
  id              uuid primary key default gen_random_uuid(),
  job_id          uuid references jobs(id) on delete cascade,
  tool            text not null,
  prompt_version  text,
  model           text,
  response        text,
  tokens_used     int,
  context_snapshot jsonb,                 -- added by 003
  created_at      timestamptz default now()
);

create table if not exists usage_log (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references profiles(id),
  tool        text not null,
  tokens      int default 0,
  model       text,
  cost_usd    numeric(10,6) default 0,
  created_at  timestamptz default now()
);

create table if not exists guest_sessions (
  id             uuid primary key default gen_random_uuid(),
  session_id     text unique not null,
  user_id        uuid references profiles(id) on delete set null,
  created_at     timestamptz default now(),
  expires_at     timestamptz default (now() + interval '24 hours'),
  last_active_at timestamptz default now()
);

create table if not exists waitlist (
  id         uuid primary key default gen_random_uuid(),
  email      text unique not null,
  created_at timestamptz default now()
);

-- ============================================================
-- PIPELINE STEP LOGGING (diagnostics; step payloads live in jobs)
-- ============================================================
create table if not exists pipeline_steps (
  id            uuid primary key default gen_random_uuid(),
  job_id        uuid references jobs(id) on delete cascade,
  step_name     text not null,
  status        text not null default 'queued',
  started_at    timestamptz,
  completed_at  timestamptz,
  error_message text,
  output_json   jsonb,
  created_at    timestamptz default now()
);

create table if not exists raw_api_responses (
  id              uuid primary key default gen_random_uuid(),
  job_id          uuid references jobs(id) on delete cascade,
  source          text not null,
  endpoint        text,
  response_body   text,
  response_format text default 'xml',
  stored_at       timestamptz default now()
);

create table if not exists processed_results (
  id          uuid primary key default gen_random_uuid(),
  job_id      uuid references jobs(id) on delete cascade,
  result_type text not null,
  result_data jsonb not null,
  created_at  timestamptz default now()
);

create table if not exists saved_analyses (
  id      uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id) on delete cascade not null,
  job_id  uuid references jobs(id) on delete cascade,
  title   text,
  notes   text,
  created_at timestamptz default now()
);

-- ============================================================
-- API KEYS  (006_api_keys) — sk_bio_ prefix, SHA-256 hashed
-- ============================================================
create table if not exists api_keys (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null,
  name        text not null,
  key_hash    text not null,
  key_prefix  text not null,
  created_at  timestamptz default now(),
  last_used_at timestamptz
);

-- ============================================================
-- DOCKING JOBS  (docking + MD + function prediction)
-- `payload` jsonb carries tool_type ("docking" | "md" | "function_predict")
-- plus run params (pdb_id, smiles, grid_center, grid_size, exhaustiveness,
-- num_modes, forcefield, solvent, run_length_ps, ...)
-- ============================================================
create table if not exists docking_jobs (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid references profiles(id) on delete cascade,   -- 004
  ligand_smiles   text,
  status          text,                  -- queued | running | complete | failed
  result_sdf      text default '',       -- superseded by storage_url
  storage_url     text,                  -- 006: offloaded result JSON
  error           text default '',
  created_at      timestamptz,
  updated_at      timestamptz,
  done_at         timestamptz,
  payload         jsonb,                 -- 005
  claimed_at      timestamptz,           -- 005 worker columns
  claimed_by      text,
  attempts        integer not null default 0,
  max_attempts    integer not null default 3
);

-- ============================================================
-- SEQUENCING JOBS  (FASTQ QC → variant calling)
-- ============================================================
create table if not exists sequencing_jobs (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references profiles(id) on delete cascade,       -- 004
  fastq_url   text,
  reference   text,                  -- 'sars-cov-2' default
  status      text,                  -- queued | downloading | ... | complete | failed
  result      jsonb,
  error       text,
  done_at     timestamptz,
  storage_url text,                  -- 006
  payload     jsonb,                 -- 005
  claimed_at  timestamptz,           -- 005 worker columns
  claimed_by  text,
  attempts    integer not null default 0,
  max_attempts integer not null default 3
);
```

---

## Row Level Security (RLS)

```sql
alter table profiles enable row level security;
alter table jobs enable row level security;
alter table ai_interpretations enable row level security;
alter table usage_log enable row level security;
alter table pipeline_steps enable row level security;
alter table raw_api_responses enable row level security;
alter table processed_results enable row level security;
alter table saved_analyses enable row level security;
alter table sequence_cache enable row level security;
alter table structure_cache enable row level security;
alter table guest_sessions enable row level security;
alter table api_keys enable row level security;

create policy "Users can view own profile"      on profiles for select using (auth.uid() = id);
create policy "Users can update own profile"    on profiles for update using (auth.uid() = id);
create policy "Users can view own jobs"         on jobs for select using (auth.uid() = user_id);
create policy "Users can create own jobs"       on jobs for insert with check (auth.uid() = user_id);
create policy "Users can delete own jobs"       on jobs for delete using (auth.uid() = user_id);
create policy "Users can view own AI results"   on ai_interpretations for select
  using (job_id in (select id from jobs where user_id = auth.uid()));
create policy "Users can view own usage"        on usage_log for select using (auth.uid() = user_id);

create policy "Users can view own pipeline steps" on pipeline_steps for select
  using (job_id in (select id from jobs where user_id = auth.uid()));
create policy "Users can view own raw responses"  on raw_api_responses for select
  using (job_id in (select id from jobs where user_id = auth.uid()));
create policy "Users can view own processed results" on processed_results for select
  using (job_id in (select id from jobs where user_id = auth.uid()));
create policy "Users can manage own saved analyses" on saved_analyses for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "Users can manage own API keys" on api_keys for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);
```

The backend uses the **service-role key** (`SUPABASE_SERVICE_ROLE_KEY`), bypassing RLS — job ownership is enforced in application code via `user_id` filters (`require_user_id` → `.eq("user_id", user_id)`), and shared results are read through the `share_token` endpoints instead of RLS.

---

## Functions & Triggers

```sql
-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, email, full_name)
  values (new.id, new.email, new.raw_user_meta_data->>'full_name');
  return new;
end;
$$ language plpgsql security definer;

create or replace trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- Expire caches and guest sessions (schedule via pg_cron)
create or replace function public.cleanup_expired_data()
returns void as $$
begin
  delete from sequence_cache where expires_at < now();
  delete from structure_cache where expires_at < now();
  delete from guest_sessions where expires_at < now();
end;
$$ language plpgsql security definer;
```

---

## Durable Worker RPCs (005_worker_durable)

Atomic claim using `FOR UPDATE SKIP LOCKED` — PostgREST cannot express this through the normal REST interface, so it is exposed as `SECURITY DEFINER` functions called via `/rest/v1/rpc/{name}`:

- `claim_next_docking_job(worker_id text)` → `docking_jobs`
- `claim_next_sequencing_job(worker_id text)` → `sequencing_jobs`
- `claim_next_pipeline_job(worker_id text)` → `jobs`

Each returns the oldest row with `status = 'queued' AND attempts < max_attempts`, flips it to `running`, stamps `claimed_at/claimed_by`, and increments `attempts`. The worker requeues on failure (`status → 'queued'`, clear claim) and permanently fails once `attempts >= max_attempts`. A periodic sweep resets rows stuck in `running` for > 90 min.

---

## Storage Conventions

Large results are offloaded to a Supabase Storage bucket (`artifact_storage.py`, bucket auto-created, public).

```
{dockseq}/{job_id}/{kind}.json        # upload_json(job_id, 'result', payload)
  e.g. {bucket}/docking-abc123/result.json
```

`storage_url` on the row stores the public object URL; readers hydrate with `download_json(storage_url)`. The old `result_sdf` inline column is deprecated in favor of `storage_url`.

Redis keys (optional cache): `{prefix}:{sha256_first_16}` with TTLs — BLAST 24h, UniProt 24h, AlphaFold 30d, pathway enrichment 12h, NCBI sequence/search 24h. Cache stats tracked in-process and served at `/api/admin/cache-stats`.

---

## Input Params Conventions

Tool inputs are stored in `jobs.result` / `jobs.context_json` / `payload` as JSONB. Representative shapes:

```jsonc
// docking_jobs.payload
{ "tool_type": "docking", "pdb_id": "1TIM", "smiles": "CCO",
  "grid_center": [0,0,0], "grid_size": [20,20,20],
  "exhaustiveness": 8, "num_modes": 9 }

// md payload
{ "tool_type": "md", "pdb_id": "1TIM", "mode": "minimize",
  "forcefield": "ff14SB", "solvent": "OBC1", "run_length_ps": 1000 }

// function_predict payload
{ "tool_type": "function_predict", "pdb_id": "1TIM" }

// sequencing_jobs row
{ "fastq_url": "https://.../reads.fastq", "reference": "sars-cov-2" }

// jobs row for wizard_v2
{ "tool": "wizard_v2", "pipeline_type": "wizard_v2",
  "query_preview": "MKTAY...", "status": "running", "share_token": null }
```

---

## Migration Notes

- Migrations run in order via `supabase db push` (canonical copy in `bioai-platform/supabase/migrations/`).
- `jobs.status` uses an explicit CHECK constraint — extending it requires drop + recreate (see `004` and `007`). Do not append statuses ad hoc; add a migration.
- Backend `migrations/` SQL (`001`, `004`, `005`, `006`) is applied manually via the Supabase SQL editor and is idempotent (`IF NOT EXISTS`).
- Never modify enum/CHECK values after data exists without a migration that recreates the constraint.

# BioFlow AI — Database Schema

**Version:** 1.0  
**Database:** Supabase (PostgreSQL 15)  
**Storage:** Cloudflare R2 (large binary/text responses)  
**Last Updated:** June 2026

---

## Design Decisions

### Why fine-grained step-level tracking?
Every bioinformatics pipeline is a chain of operations. A BLAST→MSA→Tree workflow
has three distinct steps, each of which can succeed, fail, or be retried independently.
Step-level tracking means:
- Users see exactly which step is running ("Running ClustalOmega alignment...")
- A failed step can be retried without re-running the whole pipeline
- Results for each step are stored and accessible independently
- The platform can resume mid-pipeline on service recovery

### Why store raw API responses?
NCBI BLAST returns XML. PDB returns JSON. AlphaFold returns mmCIF/JSON.
Storing the raw response means:
- We can reparse and reprocess without re-calling the external API
- Database schema changes do not invalidate past analyses
- Debugging API parser bugs is possible after the fact
- Large responses (BLAST XML can be 10MB+) go to Cloudflare R2; small ones inline

### Why separate cache tables?
Sequence data and BLAST results are expensive to fetch (rate-limited, slow).
Dedicated cache tables with TTL-based expiry and deterministic cache keys
allow cache-first architecture without polluting job tables.

---

## Table Reference

```
users (Supabase Auth managed)
  └── profiles
        └── jobs
              └── pipeline_steps
                    ├── raw_api_responses
                    └── processed_results

guest_sessions
  └── jobs (guest_session_id link)

sequence_cache (global, keyed by accession)
blast_cache (global, keyed by MD5 of inputs)
structure_cache (global, keyed by PDB ID)
```

---

## Full Schema (SQL)

```sql
-- ============================================================
-- EXTENSIONS
-- ============================================================
create extension if not exists "uuid-ossp";
create extension if not exists "pg_trgm"; -- for text search on sequences


-- ============================================================
-- PROFILES
-- Extends Supabase auth.users. Created automatically on signup.
-- ============================================================
create table profiles (
  id                    uuid primary key references auth.users(id) on delete cascade,
  username              text unique,
  display_name          text,
  institution           text,
  onboarding_complete   boolean not null default false,
  tooltips_enabled      boolean not null default true,
  -- quota tracking
  jobs_this_month       int not null default 0,
  blast_calls_today     int not null default 0,
  quota_reset_at        timestamptz not null default (now() + interval '1 month'),
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

comment on table profiles is 'User profile data extending Supabase auth';


-- ============================================================
-- GUEST SESSIONS
-- Anonymous users get one session token (stored in cookie).
-- They can run 1 job before being prompted to create an account.
-- ============================================================
create table guest_sessions (
  id            text primary key,            -- UUID v4, stored in browser cookie
  job_count     int not null default 0,      -- max 1 for guests
  ip_hash       text,                        -- hashed for abuse prevention
  created_at    timestamptz not null default now(),
  expires_at    timestamptz not null default (now() + interval '24 hours')
);

comment on table guest_sessions is 'Anonymous session tracking for guest users (1 job limit)';


-- ============================================================
-- JOBS
-- One row per analysis request. Parent of all pipeline steps.
-- ============================================================
create type workflow_type as enum (
  'blast',
  'pairwise_alignment',
  'msa',
  'phylogenetics',
  'msa_phylogenetics',   -- combined MSA + tree pipeline
  'structure_retrieval',
  'structure_prediction',
  'structural_comparison',
  'structural_analysis',
  'homology_modeling',
  'pathway_analysis',
  'compound_search',
  'admet_screening',
  'docking',
  'custom'               -- multi-step user-defined pipeline
);

create type job_status as enum (
  'queued',
  'running',
  'completed',
  'failed',
  'partial',             -- some steps succeeded, some failed
  'cancelled'
);

create table jobs (
  id                uuid primary key default uuid_generate_v4(),
  -- ownership: either user or guest, never both null
  user_id           uuid references profiles(id) on delete cascade,
  guest_session_id  text references guest_sessions(id) on delete cascade,
  -- job metadata
  workflow_type     workflow_type not null,
  title             text not null,            -- auto-generated: "BLAST search: NP_000509.1"
  description       text,                     -- user-facing summary of what was requested
  status            job_status not null default 'queued',
  -- progress tracking
  total_steps       int not null default 1,
  completed_steps   int not null default 0,
  current_step_label text,                    -- "Running BLAST search..." shown in UI
  -- input parameters (what the user asked for)
  input_params      jsonb not null default '{}',
  -- error info
  error_message     text,
  error_step        int,                      -- which step number failed
  -- timing
  created_at        timestamptz not null default now(),
  started_at        timestamptz,
  completed_at      timestamptz,
  expires_at        timestamptz not null default (now() + interval '30 days'),
  -- constraints
  constraint job_has_owner check (
    (user_id is not null and guest_session_id is null) or
    (user_id is null and guest_session_id is not null)
  )
);

create index idx_jobs_user_id on jobs(user_id) where user_id is not null;
create index idx_jobs_guest_session on jobs(guest_session_id) where guest_session_id is not null;
create index idx_jobs_status on jobs(status);
create index idx_jobs_created_at on jobs(created_at desc);

comment on table jobs is 'Parent job record for every analysis request';
comment on column jobs.input_params is 'User-provided inputs: sequences, accession numbers, settings, etc.';
comment on column jobs.expires_at is 'Guest jobs expire in 24h; user jobs in 30 days';


-- ============================================================
-- PIPELINE STEPS
-- One row per tool execution within a job.
-- E.g. a BLAST job has 2 steps: sequence_fetch → blast_search
-- ============================================================
create type step_type as enum (
  'sequence_fetch',        -- NCBI Entrez / UniProt retrieval
  'format_convert',        -- FASTA ↔ GenBank ↔ raw conversion
  'blast_search',          -- NCBI BLAST or EMBL-EBI BLAST
  'pairwise_align',        -- NW or SW alignment
  'msa',                   -- ClustalOmega / MUSCLE
  'phylotree',             -- PHYLIP / IQ-TREE
  'conservation_analysis', -- per-position conservation from MSA
  'primer_design',         -- degenerate primer from nucleotide alignment
  'structure_fetch',       -- PDB retrieval
  'alphafold_predict',     -- AlphaFold EBI prediction
  'secondary_struct',      -- PSIPred prediction
  'structural_align',      -- DALI / TM-Align / PDBeFold
  'dssp_analysis',         -- H-bonds, secondary structure assignment
  'ramachandran',          -- phi/psi angle computation
  'homology_model',        -- SWISS-MODEL submission
  'pathway_fetch',         -- Reactome / WikiPathways / KEGG
  'compound_fetch',        -- PubChem / ChEMBL
  'admet_screen',          -- SwissADME / pkCSM
  'docking',               -- SwissDock / AutoDock Vina
  'ai_interpret'           -- Groq/Claude interpretation generation
);

create type step_status as enum (
  'pending',
  'running',
  'completed',
  'failed',
  'skipped',
  'retrying'
);

create table pipeline_steps (
  id                  uuid primary key default uuid_generate_v4(),
  job_id              uuid not null references jobs(id) on delete cascade,
  step_number         int not null,           -- 1-indexed order within the job
  step_type           step_type not null,
  step_label          text not null,          -- "Fetching sequence from NCBI"
  status              step_status not null default 'pending',
  -- external job tracking (for async external APIs like EMBL-EBI)
  external_job_id     text,                   -- job ID returned by EMBL-EBI, NCBI, etc.
  external_service    text,                   -- 'ncbi_blast', 'embl_ebi_clustalo', 'alphafold_ebi'
  poll_url            text,                   -- URL to poll for async job status
  poll_attempts       int not null default 0,
  -- step-level input (may differ from job.input_params for chained pipelines)
  step_input          jsonb not null default '{}',
  -- retry logic
  retry_count         int not null default 0,
  max_retries         int not null default 3,
  -- error
  error_message       text,
  error_code          text,                   -- machine-readable: 'rate_limit', 'timeout', 'parse_error'
  -- timing
  created_at          timestamptz not null default now(),
  started_at          timestamptz,
  completed_at        timestamptz,
  duration_ms         int,                    -- computed on completion
  unique(job_id, step_number)
);

create index idx_steps_job_id on pipeline_steps(job_id);
create index idx_steps_status on pipeline_steps(status);
create index idx_steps_external_job on pipeline_steps(external_job_id) where external_job_id is not null;

comment on table pipeline_steps is 'Individual tool execution steps within a pipeline job';
comment on column pipeline_steps.external_job_id is 'ID from external async service (EMBL-EBI, NCBI). Used for status polling.';


-- ============================================================
-- RAW API RESPONSES
-- Stores unprocessed responses from external APIs.
-- Large responses (>50KB) stored in Cloudflare R2; small ones inline.
-- ============================================================
create type response_format as enum (
  'json', 'xml', 'fasta', 'pdb', 'mmcif', 'newick',
  'clustal', 'phylip', 'text', 'tsv', 'csv'
);

create table raw_api_responses (
  id              uuid primary key default uuid_generate_v4(),
  step_id         uuid not null references pipeline_steps(id) on delete cascade,
  service         text not null,              -- 'ncbi_entrez', 'embl_ebi_blast', 'pdb_rest', etc.
  endpoint        text,                       -- the actual URL called
  response_format response_format not null,
  -- storage: one of these two is populated, never both
  response_data   jsonb,                      -- inline storage for small JSON responses (<50KB)
  storage_key     text,                       -- Cloudflare R2 object key for large responses
  -- metadata
  size_bytes      int,
  http_status     int,
  response_time_ms int,
  created_at      timestamptz not null default now(),
  constraint raw_response_storage check (
    (response_data is not null and storage_key is null) or
    (response_data is null and storage_key is not null)
  )
);

create index idx_raw_responses_step_id on raw_api_responses(step_id);

comment on table raw_api_responses is 'Raw unprocessed API responses. Large files stored in R2, small JSON inline.';
comment on column raw_api_responses.storage_key is 'R2 key format: raw/{step_id}/{service}.{ext}';


-- ============================================================
-- PROCESSED RESULTS
-- Parsed, structured output from a pipeline step.
-- This is what the frontend reads to render visualizations.
-- ============================================================
create type result_type as enum (
  'sequence_data',        -- retrieved sequence with annotations
  'blast_hits',           -- parsed BLAST hit list
  'pairwise_alignment',   -- formatted alignment with scores
  'msa_result',           -- multiple sequence alignment
  'phylo_tree',           -- Newick tree + metadata
  'conservation_scores',  -- per-position conservation array
  'primer_data',          -- designed primer with properties
  'structure_metadata',   -- PDB metadata (resolution, method, chains)
  'structure_coordinates',-- 3D coordinates (stored in R2 as PDB/mmCIF)
  'alphafold_result',     -- AlphaFold prediction + pLDDT scores
  'secondary_struct',     -- per-residue helix/strand/coil prediction
  'structural_alignment', -- TM-score, RMSD, aligned pairs
  'dssp_analysis',        -- H-bonds, salt bridges, DSSP assignment
  'ramachandran_data',    -- phi/psi angles per residue
  'homology_model',       -- model quality scores + structure key
  'pathway_data',         -- pathway name, genes, reactions
  'compound_data',        -- PubChem/ChEMBL compound info
  'admet_properties',     -- ADMET screening results
  'docking_result',       -- binding poses + energies
  'ai_interpretation'     -- AI-generated natural language explanation
);

create table processed_results (
  id                  uuid primary key default uuid_generate_v4(),
  step_id             uuid not null references pipeline_steps(id) on delete cascade,
  job_id              uuid not null references jobs(id) on delete cascade,
  result_type         result_type not null,
  -- structured result data (always stored here — parsed and typed)
  result_data         jsonb not null default '{}',
  -- for large binary data (3D structures, large alignments)
  storage_key         text,                   -- R2 key if result is also stored as file
  -- AI interpretation
  ai_interpretation   text,
  ai_model            text,                   -- 'groq/llama-3.1-8b-instant', 'claude-sonnet-4-6'
  ai_generated_at     timestamptz,
  -- metadata
  is_cached           boolean not null default false,
  created_at          timestamptz not null default now()
);

create index idx_results_step_id on processed_results(step_id);
create index idx_results_job_id on processed_results(job_id);
create index idx_results_type on processed_results(result_type);

comment on table processed_results is 'Parsed, structured results ready for frontend rendering';


-- ============================================================
-- SEQUENCE CACHE
-- Global cache for sequence lookups. Keyed by accession + database.
-- Prevents redundant NCBI Entrez API calls.
-- ============================================================
create table sequence_cache (
  id              uuid primary key default uuid_generate_v4(),
  cache_key       text unique not null,       -- MD5(accession + ':' + db_source)
  accession       text not null,
  db_source       text not null,              -- 'ncbi', 'uniprot', 'pdb'
  sequence_type   text,                       -- 'protein', 'dna', 'rna'
  sequence_data   jsonb not null,             -- { sequence, length, organism, description, ... }
  raw_fasta       text,                       -- original FASTA string
  raw_genbank     text,                       -- original GenBank record (if fetched)
  hit_count       int not null default 0,     -- cache hit counter
  created_at      timestamptz not null default now(),
  expires_at      timestamptz not null default (now() + interval '24 hours'),
  last_accessed   timestamptz not null default now()
);

create index idx_seq_cache_key on sequence_cache(cache_key);
create index idx_seq_cache_expires on sequence_cache(expires_at);

comment on table sequence_cache is 'TTL cache for sequence data from NCBI/UniProt. 24-hour expiry.';


-- ============================================================
-- BLAST CACHE
-- Global cache for BLAST results. Keyed by MD5 of inputs.
-- BLAST is expensive and slow — cache aggressively.
-- ============================================================
create table blast_cache (
  id              uuid primary key default uuid_generate_v4(),
  cache_key       text unique not null,       -- MD5(sequence + db + program + evalue + matrix)
  blast_program   text not null,              -- 'blastp', 'blastn', 'blastx', etc.
  database        text not null,              -- 'nr', 'swissprot', 'pdbaa', etc.
  hit_count       int not null default 0,
  top_hit_accession text,                     -- quick preview for cache listing
  storage_key     text not null,              -- R2 key for raw XML response
  created_at      timestamptz not null default now(),
  expires_at      timestamptz not null default (now() + interval '24 hours')
);

create index idx_blast_cache_key on blast_cache(cache_key);
create index idx_blast_cache_expires on blast_cache(expires_at);


-- ============================================================
-- STRUCTURE CACHE
-- Global cache for PDB structure metadata.
-- PDB structures change rarely — longer TTL.
-- ============================================================
create table structure_cache (
  id              uuid primary key default uuid_generate_v4(),
  pdb_id          text unique not null,       -- e.g. '1TIM', '6LU7'
  metadata        jsonb not null,             -- resolution, method, chains, organism, etc.
  structure_key   text,                       -- R2 key for .pdb / .mmcif file
  created_at      timestamptz not null default now(),
  expires_at      timestamptz not null default (now() + interval '7 days')
);

create index idx_structure_cache_pdb_id on structure_cache(pdb_id);


-- ============================================================
-- SAVED ANALYSES
-- Users can pin/save any job result for long-term access.
-- Saved jobs do not expire.
-- ============================================================
create table saved_analyses (
  id          uuid primary key default uuid_generate_v4(),
  user_id     uuid not null references profiles(id) on delete cascade,
  job_id      uuid not null references jobs(id) on delete cascade,
  title       text,                           -- user-editable title
  notes       text,                           -- user notes
  tags        text[],                         -- e.g. ['coursework', 'assignment-3']
  is_pinned   boolean not null default false,
  created_at  timestamptz not null default now(),
  unique(user_id, job_id)
);

create index idx_saved_user_id on saved_analyses(user_id);
```

---

## Row Level Security (RLS) Policies

```sql
-- Enable RLS on all user-facing tables
alter table profiles enable row level security;
alter table jobs enable row level security;
alter table pipeline_steps enable row level security;
alter table raw_api_responses enable row level security;
alter table processed_results enable row level security;
alter table saved_analyses enable row level security;

-- profiles: users can only read/update their own profile
create policy "profiles_self_access" on profiles
  for all using (auth.uid() = id);

-- jobs: users see only their own jobs
create policy "jobs_owner_access" on jobs
  for all using (
    auth.uid() = user_id or
    guest_session_id is not null  -- guest jobs readable by session (handled in app layer)
  );

-- pipeline_steps: readable if user owns the parent job
create policy "steps_via_job" on pipeline_steps
  for select using (
    exists (
      select 1 from jobs
      where jobs.id = pipeline_steps.job_id
        and jobs.user_id = auth.uid()
    )
  );

-- processed_results: same pattern
create policy "results_via_job" on processed_results
  for select using (
    exists (
      select 1 from jobs
      where jobs.id = processed_results.job_id
        and jobs.user_id = auth.uid()
    )
  );

-- raw_api_responses: backend service role only (never exposed to frontend directly)
-- Frontend never calls raw_api_responses directly — always through processed_results

-- Cache tables: public read (no PII), backend write only
alter table sequence_cache enable row level security;
create policy "seq_cache_public_read" on sequence_cache for select using (true);

alter table blast_cache enable row level security;
create policy "blast_cache_public_read" on blast_cache for select using (true);

alter table structure_cache enable row level security;
create policy "structure_cache_public_read" on structure_cache for select using (true);
```

---

## Supabase Functions (Database Triggers)

```sql
-- Auto-create profile on user signup
create or replace function handle_new_user()
returns trigger language plpgsql security definer as $$
begin
  insert into profiles (id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data->>'full_name', 'Researcher'));
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure handle_new_user();

-- Auto-update updated_at on profiles
create or replace function update_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_updated_at
  before update on profiles
  for each row execute procedure update_updated_at();

-- Auto-expire guest sessions (called by a scheduled job)
create or replace function cleanup_expired_data()
returns void language plpgsql as $$
begin
  delete from guest_sessions where expires_at < now();
  delete from jobs where expires_at < now();
  delete from sequence_cache where expires_at < now();
  delete from blast_cache where expires_at < now();
  delete from structure_cache where expires_at < now();
end;
$$;
-- Schedule via Supabase pg_cron: SELECT cron.schedule('cleanup', '0 2 * * *', 'SELECT cleanup_expired_data()');
```

---

## Cloudflare R2 Key Convention

All objects stored in R2 follow this naming pattern:

```
raw/{step_id}/{service}.{ext}
  e.g. raw/abc123/ncbi_blast.xml
  e.g. raw/abc123/pdb_rest.json

results/{job_id}/{result_type}.{ext}
  e.g. results/xyz789/structure_coordinates.pdb
  e.g. results/xyz789/msa_result.fasta

cache/blast/{cache_key}.xml
cache/structure/{pdb_id}.pdb
```

---

## Input Params Schema (Per Workflow Type)

These are stored in `jobs.input_params` as JSONB:

```typescript
// blast
{
  sequence: string,           // raw sequence or null if accession provided
  accession: string | null,   // e.g. "NP_000509.1"
  db_source: string | null,   // where accession was fetched from
  blast_database: string,     // "nr" | "swissprot" | "pdbaa" | "refseq_protein"
  blast_program: string,      // "blastp" | "blastn" | "blastx" | "tblastn"
  evalue_threshold: number,   // default 0.001
  max_hits: number,           // default 100
  scoring_matrix: string      // "BLOSUM62" | "PAM30" etc.
}

// pairwise_alignment
{
  sequence_a: string,
  sequence_b: string,
  accession_a: string | null,
  accession_b: string | null,
  algorithm: "needleman_wunsch" | "smith_waterman",
  scoring_matrix: string,
  gap_open: number,
  gap_extend: number
}

// structure_retrieval
{
  pdb_id: string | null,
  protein_name: string | null,
  uniprot_accession: string | null,
  fetch_alphafold_if_missing: boolean
}
```

---

## Migration Notes

- Run migrations in order via Supabase SQL editor or `supabase db push`
- Never modify enum types after data exists — add new values only
- Cache tables do not need migrations for TTL changes — update application config
- R2 bucket name: `bioflow-raw-responses` (create in Cloudflare dashboard before deploying)

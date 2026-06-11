-- Bio Nexus Platform — Initial Schema
-- Run: supabase db push

-- Waitlist
create table if not exists waitlist (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  created_at timestamptz default now()
);

-- Users (extends Supabase auth.users)
create table if not exists profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  full_name text,
  institution text,
  role text default 'researcher',
  created_at timestamptz default now()
);

-- Jobs
create table if not exists jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id) on delete cascade,
  tool text not null,
  query_preview text,
  status text default 'queued' check (status in ('queued', 'running', 'complete', 'failed')),
  progress_pct int default 0,
  result jsonb,
  error text,
  created_at timestamptz default now(),
  completed_at timestamptz
);

-- Cached results (for BLAST/UniProt)
create table if not exists cached_queries (
  id uuid primary key default gen_random_uuid(),
  query_hash text unique not null,
  tool text not null,
  result jsonb not null,
  created_at timestamptz default now(),
  expires_at timestamptz default (now() + interval '24 hours')
);

-- AI interpretations
create table if not exists ai_interpretations (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references jobs(id) on delete cascade,
  tool text not null,
  prompt_version text,
  model text,
  response text,
  tokens_used int,
  created_at timestamptz default now()
);

-- Usage tracking
create table if not exists usage_log (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id),
  tool text not null,
  tokens int default 0,
  model text,
  cost_usd numeric(10,6) default 0,
  created_at timestamptz default now()
);

-- Indexes
create index if not exists idx_jobs_user on jobs(user_id);
create index if not exists idx_jobs_status on jobs(status);
create index if not exists idx_cached_hash on cached_queries(query_hash);
create index if not exists idx_usage_user on usage_log(user_id);

-- Row Level Security
alter table profiles enable row level security;
alter table jobs enable row level security;
alter table ai_interpretations enable row level security;
alter table usage_log enable row level security;

create policy "Users can view own profile" on profiles for select using (auth.uid() = id);
create policy "Users can update own profile" on profiles for update using (auth.uid() = id);
create policy "Users can view own jobs" on jobs for select using (auth.uid() = user_id);
create policy "Users can create own jobs" on jobs for insert with check (auth.uid() = user_id);
create policy "Users can delete own jobs" on jobs for delete using (auth.uid() = user_id);
create policy "Users can view own AI results" on ai_interpretations for select
  using (job_id in (select id from jobs where user_id = auth.uid()));
create policy "Users can view own usage" on usage_log for select using (auth.uid() = user_id);

-- Function to auto-create profile on signup
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
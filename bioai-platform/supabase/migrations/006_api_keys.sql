create table if not exists api_keys (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  name text not null,
  key_hash text not null,
  key_prefix text not null,
  created_at timestamptz default now(),
  last_used_at timestamptz
);

create index if not exists idx_api_keys_user on api_keys(user_id);
create index if not exists idx_api_keys_hash on api_keys(key_hash);

alter table api_keys enable row level security;

create policy "Users can manage own API keys" on api_keys for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

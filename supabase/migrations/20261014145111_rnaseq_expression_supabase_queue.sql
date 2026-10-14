-- Server-only queue. Public browser roles have no direct access, even to RPCs.
create table if not exists public.rnaseq_expression_queue (
  id uuid primary key,
  owner text not null check (owner ~ '^[0-9a-f]{64}$'),
  user_id text not null,
  state text not null check (state in ('QUEUED','RUNNING','QC_REVIEW','SUCCEEDED','FAILED','CANCELLED')),
  phase text not null check (phase in ('qc','infer','full')),
  payload jsonb not null,
  result jsonb,
  error text,
  attempts integer not null default 0 check (attempts between 0 and 3),
  lease uuid,
  claimed_by text,
  heartbeat double precision,
  progress jsonb not null default '[]'::jsonb,
  created double precision not null,
  updated double precision not null
);
create index if not exists rnaseq_expression_queue_pending_idx
  on public.rnaseq_expression_queue (created,id) where state='QUEUED';
create index if not exists rnaseq_expression_queue_owner_idx
  on public.rnaseq_expression_queue (owner,created desc);
create table if not exists public.rnaseq_expression_workers (
  id text primary key,
  heartbeat double precision not null
);
alter table public.rnaseq_expression_queue enable row level security;
alter table public.rnaseq_expression_workers enable row level security;
revoke all on public.rnaseq_expression_queue, public.rnaseq_expression_workers from public,anon,authenticated;
grant select,insert,update,delete on public.rnaseq_expression_queue,public.rnaseq_expression_workers to service_role;

create or replace function public.claim_rnaseq_expression_job(worker_id text)
returns setof public.rnaseq_expression_queue
language plpgsql security invoker set search_path = '' as $$
declare claimed uuid; now_seconds double precision := extract(epoch from clock_timestamp());
begin
  update public.rnaseq_expression_queue
    set state=case when attempts<3 then 'QUEUED' else 'FAILED' end,
        error='Worker lease expired', lease=null, updated=now_seconds
    where state='RUNNING' and (heartbeat is null or heartbeat<now_seconds-120);
  select id into claimed from public.rnaseq_expression_queue
    where state='QUEUED' and attempts<3 order by created,id
    for update skip locked limit 1;
  if claimed is null then return; end if;
  return query update public.rnaseq_expression_queue
    set state='RUNNING',lease=gen_random_uuid(),claimed_by=worker_id,
        heartbeat=now_seconds,attempts=attempts+1,error=null,updated=now_seconds,progress='[]'::jsonb
    where id=claimed returning *;
end;
$$;
revoke all on function public.claim_rnaseq_expression_job(text) from public,anon,authenticated;
grant execute on function public.claim_rnaseq_expression_job(text) to service_role;

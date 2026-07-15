# Durable Job Worker — Design Doc

**Scope:** replace `run_in_executor`-based docking (and sequencing/pipeline_v2) execution with a durable, restart-safe worker.
**Status:** proposal, not yet implemented.

---

## 1. Problem statement

Today, `create_docking_job` does:

```python
loop = asyncio.get_event_loop()
asyncio.ensure_future(loop.run_in_executor(None, _run_docking_sync, job_id, row))
```

This ties a 1–5 minute compute job to the lifetime of the web request's event loop / process. Consequences:

- **Any deploy, restart, or crash silently strands jobs** in `queued`/`running` forever — no process is left to finish or retry them.
- **Multiple web workers = unpredictable scheduling.** If you scale to 2+ Uvicorn workers (or HF/Render restarts mid-request), a job started on worker A is invisible to worker B; nothing coordinates who's doing what.
- **No retry, no backoff, no dead-letter handling.** A transient failure (e.g. CACTUS timeout) just fails the job permanently.
- **No concurrency control.** Nothing stops 50 simultaneous Vina jobs from OOMing the box (this already happened once for unrelated reasons — see the Render OOM incident).
- **No visibility** beyond polling the DB row's `status` column — no queue depth, no stuck-job detection, no metrics.

We need a model where **job submission and job execution are decoupled processes**, and execution survives the web process dying.

---

## 2. Options considered

### Option A — Supabase-polling worker (no new infra)

A separate long-running process (or the same container, second entrypoint) polls `docking_jobs` / `sequencing_jobs` / `jobs` tables for rows with `status = 'queued'`, claims one, runs it, updates status.

**How claiming works (avoid double-processing):**
```sql
UPDATE docking_jobs
SET status = 'running', claimed_at = now(), claimed_by = $worker_id
WHERE id = (
  SELECT id FROM docking_jobs
  WHERE status = 'queued'
  ORDER BY created_at ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED
)
RETURNING *;
```
`FOR UPDATE SKIP LOCKED` is the key primitive — Postgres lets concurrent workers each grab a different row without blocking each other or double-claiming. This works through PostgREST only if exposed via an RPC function (`supabase.rpc(...)`), since PostgREST doesn't expose raw `FOR UPDATE SKIP LOCKED` through its normal REST interface.

**Pros:**
- Zero new infrastructure — no Redis, no broker, nothing new to pay for or operate.
- Uses the database you already have and already trust.
- Easy to reason about: one table = one queue, visible with a normal `SELECT`.
- Natural fit for HF Spaces / Render, which don't easily support a second always-on process type (no separate "worker dyno" concept) — the worker can run as a background asyncio task *within* the same container using `asyncio.create_task` at startup instead of `run_in_executor` per-request, OR as a fully separate container/Space if you want isolation.

**Cons:**
- Polling has inherent latency (job sits `queued` until next poll tick — mitigate with a short interval, e.g. 2–3s, acceptable for 1–5 min jobs).
- You're hand-rolling retry/backoff/dead-letter logic that a real queue gives you for free.
- Postgres becomes your queue *and* your system of record — fine at this scale, but it doesn't scale to high job throughput (not a concern for your usage right now).
- Requires a Postgres function (`SECURITY DEFINER` RPC) to do the atomic claim safely — a bit of extra Supabase-side setup, not just application code.

### Option B — Redis + RQ (or Celery)

Add Redis as a message broker; jobs get pushed onto a Redis list/stream; RQ (simpler) or Celery (heavier, more features) workers consume from it.

**Pros:**
- Purpose-built for this — retries, backoff, dead-letter queues, concurrency limits, scheduling, and monitoring (RQ Dashboard / Flower for Celery) come out of the box.
- No polling latency — push-based.
- Scales cleanly if job volume grows a lot later.

**Cons:**
- **New infra dependency.** You already tried Redis for caching and noted "Redis unavailable — caching disabled" in your logs — meaning you don't currently have a reliable Redis instance running. This option requires actually standing one up (Upstash Redis, which you already have config fields for in `settings`, is the natural choice) and keeping it available, or job submission breaks.
- More moving parts to deploy/monitor/pay for, on top of an already multi-platform deployment (Vercel + HF/Render + Supabase).
- Given the recent debugging saga (Render OOM, HF migration, proxy misconfig), adding a 4th platform dependency raises operational risk right when things are stabilizing.

### Option C — External queue service (e.g. Supabase Edge Functions + pg_cron, or a managed queue like AWS SQS)

Considered and set aside: adds either vendor lock-in (SQS) or relies on Supabase-specific cron/edge tooling that's a bigger conceptual leap than A or B for the amount of job volume you actually have (single-digit concurrent jobs, not thousands/day).

---

## 3. Recommendation: **Option A — Supabase-polling worker**

Given:
- Current job volume is low (solo-developer / early-stage usage, not production traffic yet)
- You don't have a currently-working Redis instance (Upstash config exists but isn't active — "Redis unavailable" in every log)
- You're already juggling 3 deployment platforms (Vercel, HF Spaces, Supabase) and just spent a full day untangling a 4th (Render) — adding Redis as a 5th moving part right now works against stabilizing the stack
- `FOR UPDATE SKIP LOCKED` gives real correctness guarantees (no double-processing) without new infra

**Start with Option A.** If job volume grows enough that polling latency or Postgres-as-queue becomes a real bottleneck, migrating to Option B later is a contained, well-understood change (the job execution logic itself doesn't need to change — only how jobs get dispatched to the worker).

---

## 4. Proposed architecture (Option A)

### 4.1 Components

```
┌─────────────┐        ┌──────────────────┐        ┌────────────────┐
│  FastAPI     │ insert │  docking_jobs /   │ poll   │  Worker process │
│  web routes  │───────▶│  sequencing_jobs  │◀──────▶│  (same container│
│ (unchanged   │        │  tables           │ claim  │   or separate)  │
│  API surface)│        │  (Postgres queue) │        │                 │
└─────────────┘        └──────────────────┘        └────────────────┘
```

- **Web routes** (`create_docking_job`, etc.) only ever `INSERT ... status='queued'` and return immediately. They never call `_run_docking_sync` directly anymore.
- **Worker** runs independently: a loop that claims one job at a time (or up to `N` concurrent, bounded), executes it, writes results.
- **Job tables** are the single source of truth and the queue itself — no separate broker.

### 4.2 Where the worker runs

Two sub-options, both viable:

**4.2a — In-process background task (simplest to ship first)**
At FastAPI startup (`@app.on_event("startup")` or lifespan), launch `asyncio.create_task(worker_loop())`. The worker runs inside the same Uvicorn process as the API.

- Pro: zero deployment changes, ships today.
- Con: still coupled to the web process's lifetime — a redeploy still interrupts in-flight jobs. **This does not fully solve the durability problem**, only the "multiple workers double-claim" problem. Acceptable as a *first step* since `FOR UPDATE SKIP LOCKED` at least makes retries safe (an interrupted job can be picked back up by the next process on restart, see §4.5).

**4.2b — Separate worker process/container (real fix)**
A second entrypoint (`python -m app.worker`) deployed as its own HF Space / Render service / process, running only the poll loop, no HTTP server. The web API and the worker scale and restart independently.

- Pro: actually decouples job execution from web process restarts — a Vercel/HF web redeploy no longer touches in-flight jobs.
- Con: a second thing to deploy and monitor (but same platform, no new vendor — just "one more Space" or "one more Render service").

**Recommendation:** ship 4.2a first (fast, and net positive vs. today even without full durability), then move to 4.2b once the claim/retry logic is proven correct. The application code is identical between the two — only how the process is launched differs.

### 4.3 Required Supabase-side changes

1. Add columns to `docking_jobs` / `sequencing_jobs` / `jobs`:
   ```sql
   ALTER TABLE docking_jobs
     ADD COLUMN IF NOT EXISTS claimed_at timestamptz,
     ADD COLUMN IF NOT EXISTS claimed_by text,
     ADD COLUMN IF NOT EXISTS attempts integer NOT NULL DEFAULT 0,
     ADD COLUMN IF NOT EXISTS max_attempts integer NOT NULL DEFAULT 3;
   ```

2. Add a `SECURITY DEFINER` RPC function to do the atomic claim (PostgREST can't express `FOR UPDATE SKIP LOCKED` directly):
   ```sql
   CREATE OR REPLACE FUNCTION claim_next_docking_job(worker_id text)
   RETURNS docking_jobs
   LANGUAGE plpgsql
   SECURITY DEFINER
   AS $$
   DECLARE
     job docking_jobs;
   BEGIN
     SELECT * INTO job
     FROM docking_jobs
     WHERE status = 'queued'
       AND attempts < max_attempts
     ORDER BY created_at ASC
     LIMIT 1
     FOR UPDATE SKIP LOCKED;

     IF job.id IS NOT NULL THEN
       UPDATE docking_jobs
       SET status = 'running',
           claimed_at = now(),
           claimed_by = worker_id,
           attempts = attempts + 1,
           updated_at = now()
       WHERE id = job.id
       RETURNING * INTO job;
     END IF;

     RETURN job;
   END;
   $$;
   ```
   Called from Python via `supabase.rpc("claim_next_docking_job", {"worker_id": WORKER_ID}).execute()`.

3. **Stuck-job recovery**: a job claimed but never completed (worker crashed mid-run) needs to be reclaimable. Add a periodic sweep (in the worker loop itself, every N iterations):
   ```sql
   UPDATE docking_jobs
   SET status = 'queued', claimed_at = NULL, claimed_by = NULL
   WHERE status = 'running'
     AND claimed_at < now() - interval '10 minutes';
   ```
   (10 minutes should comfortably exceed the longest expected Vina run; tune as needed.)

### 4.4 Worker loop (pseudocode)

```python
WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"
POLL_INTERVAL_SECONDS = 3
MAX_CONCURRENT_JOBS = 2  # bound memory/CPU use — was a real problem before (OOM)

async def worker_loop():
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
    sweep_counter = 0

    while True:
        sweep_counter += 1
        if sweep_counter % 20 == 0:  # every ~60s at 3s interval
            await reclaim_stuck_jobs()

        if semaphore.locked():
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue

        job = await claim_next_job("docking_jobs")
        if job is None:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue

        asyncio.create_task(run_claimed_job(job, semaphore))


async def run_claimed_job(job, semaphore):
    async with semaphore:
        try:
            await asyncio.to_thread(_run_docking_sync, job["id"], job)
        except Exception:
            # _run_docking_sync already writes status='failed' internally;
            # this catch is a last-resort safety net only.
            logger.exception("Unhandled worker error for job %s", job["id"])
```

Note: `_run_docking_sync` stays synchronous internally (it shells out to Vina/Open Babel via `subprocess.run`, which is inherently blocking) — it's run via `asyncio.to_thread` from the worker loop rather than `loop.run_in_executor` from a request handler. Functionally similar today, but now driven by the worker's own loop instead of a web request's, and bounded by `MAX_CONCURRENT_JOBS`.

### 4.5 Retry semantics

- `attempts` increments on every claim (see RPC above).
- `_run_docking_sync`'s failure path checks `attempts >= max_attempts` before setting `status='failed'` permanently; otherwise sets back to `status='queued'` for another pickup.
- This requires a small change to the existing `except Exception as exc:` block in `_run_docking_sync` to branch on attempt count rather than unconditionally marking `failed`.

### 4.6 Traceback exposure (bundled fix, from the audit)

While touching this code path: stop writing `str(exc)` (which can include full tracebacks depending on exception type) into the `error` column that the frontend reads directly. Instead:
```python
except Exception as exc:
    logger.exception("Docking job %s failed", job_id)  # full traceback goes to server logs only
    user_facing_error = "Docking failed during execution. Reference ID: " + job_id[:8]
    ...
```

---

## 5. Migration plan

1. Add new columns + RPC function to Supabase (docking_jobs first, then mirror to sequencing_jobs/jobs).
2. Implement `worker.py` with the claim/run/sweep loop described above.
3. Change `create_docking_job` to stop calling `run_in_executor` — just insert and return.
4. Launch the worker as an in-process background task (4.2a) behind a feature flag / env var (`ENABLE_INPROCESS_WORKER=true`) so it can be toggled off instantly if something's wrong.
5. Bake in `MAX_CONCURRENT_JOBS` from day one — directly addresses the earlier OOM incident.
6. Verify: submit several jobs concurrently, kill the process mid-job, confirm the stuck-job sweep reclaims it after the timeout.
7. Once stable, evaluate moving to a separate worker process (4.2b) if redeploy-safety becomes important (e.g. once this is used by others, not just you).

---

## 6. Explicitly out of scope for this doc

- Auth/ownership enforcement on job endpoints (separate P0 item, tracked separately)
- SSRF protection on `pdb_url` (separate P0 item)
- Chemically-accurate interaction detection (separate scientific-quality item)
- MD simulation, ADMET, DeepFRI — new feature modules, would each get queued through this same worker once it exists, but are not part of building the worker itself

---

## 7. Open questions for you

1. Are you okay running the worker in-process first (4.2a), accepting it's not *fully* durable yet, in exchange for shipping faster? Or do you want to go straight to a separate worker container (4.2b)?
2. `MAX_CONCURRENT_JOBS` — what's a safe number given HF's free-tier RAM (16GB) and the fact that each Vina job is a `subprocess`, not just memory in Python? I'd default to 2 and let you tune based on observed memory per job.
3. Do you want `sequencing_jobs` and the general `jobs` table migrated to the same worker pattern at the same time, or docking first as a proof of concept?

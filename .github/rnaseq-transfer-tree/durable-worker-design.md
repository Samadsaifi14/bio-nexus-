# Durable Job Worker — Design Doc

**Scope:** replace `run_in_executor`-based docking (and sequencing / pipeline_v2 / MD / function prediction) execution with a durable, restart-safe worker.
**Status:** ✅ **Implemented** — `bioai-platform/backend/app/worker.py` + `backend/migrations/005_worker_durable.sql`. Run standalone (`python -m app.worker`) or in-process (`await start_worker()` from `app.main` startup).

---

## 1. Problem statement (why this exists)

Previously `create_docking_job` did:

```python
loop = asyncio.get_event_loop()
asyncio.ensure_future(loop.run_in_executor(None, _run_docking_sync, job_id, row))
```

This tied a 1–5 minute compute job to the lifetime of the web request's event loop / process. Consequences:

- **Any deploy, restart, or crash silently strands jobs** in `queued`/`running` forever — no process is left to finish or retry them.
- **Multiple web workers = unpredictable scheduling.** If you scale to 2+ Uvicorn workers (or HF/Render restarts mid-request), a job started on worker A is invisible to worker B; nothing coordinates who's doing what.
- **No retry, no backoff, no dead-letter handling.** A transient failure (e.g. CACTUS timeout) just failed the job permanently.
- **No concurrency control.** Nothing stopped many simultaneous Vina jobs from OOMing the box (a real incident — see the Render OOM saga).
- **No visibility** beyond polling the DB row's `status` column — no queue depth, no stuck-job detection, no metrics.

The fix: **job submission and job execution are decoupled processes**, and execution survives the web process dying.

---

## 2. Options considered

### Option A — Supabase-polling worker (no new infra) — **CHOSEN & IMPLEMENTED**

A long-running process (or the same container as a background task) polls `docking_jobs` / `sequencing_jobs` / `jobs` for rows with `status = 'queued'`, claims one atomically, runs it, updates status.

**Claiming uses `FOR UPDATE SKIP LOCKED`** (the key primitive — concurrent workers each grab a different row without blocking each other or double-claiming):

```sql
UPDATE docking_jobs
SET status = 'running', claimed_at = now(), claimed_by = $worker_id
WHERE id = (
  SELECT id FROM docking_jobs
  WHERE status = 'queued' AND attempts < max_attempts
  ORDER BY created_at ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED
)
RETURNING *;
```

PostgREST can't express `FOR UPDATE SKIP LOCKED` through its normal REST interface, so the claims are exposed as `SECURITY DEFINER` RPCs (`claim_next_docking_job`, `claim_next_sequencing_job`, `claim_next_pipeline_job`) called via `/rest/v1/rpc/{name}`.

**Pros:**
- Zero new infrastructure — no Redis, no broker, nothing new to pay for or operate.
- Uses the database you already have and already trust.
- One table = one queue, visible with a normal `SELECT`.
- Fits HF Spaces / Render, which don't easily support a second always-on process type — the worker runs as a background asyncio task within the same container at startup, or as a fully separate container if isolation is wanted.

**Cons (accepted):**
- Polling latency (job sits `queued` until next poll tick — 3s, negligible for 1–5 min jobs).
- Retry/backoff/dead-letter logic is hand-rolled (it is, in `worker.py`).
- Postgres is queue *and* system of record — fine at this scale.

### Option B — Redis + RQ (or Celery)

Set aside. New infra dependency (a 4th/5th platform) at a moment when the stack was stabilizing; job volume doesn't justify it. Revisit only if polling latency or Postgres-as-queue becomes a real bottleneck — the job-execution logic in `worker.py` wouldn't change, only dispatch.

### Option C — External queue service (SQS / Edge Functions + pg_cron)

Set aside: vendor lock-in / Supabase-specific cron tooling, not worth it for single-digit concurrent jobs.

---

## 3. Decision

**Option A — Supabase-polling worker.** Rationale: low job volume, no working Redis instance at the time, `FOR UPDATE SKIP LOCKED` gives real correctness (no double-processing) with zero new infra, and the migration path to Option B is contained.

---

## 4. Implemented architecture

### 4.1 Components

```
┌─────────────┐        ┌──────────────────┐        ┌──────────────────────┐
│  FastAPI     │ insert │  docking_jobs /   │ poll   │ app/worker.py        │
│  web routes  │───────▶│  sequencing_jobs  │◀──────▶│ (python -m app.worker│
│ (submit only)│        │  jobs (tables =   │ claim  │  or in-process task) │
└─────────────┘        │  queue)           │        └──────────────────────┘
                       └──────────────────┘
```

- **Web routes** only `INSERT ... status='queued'` (or `queued` via the submit endpoints) and return immediately. They never run the heavy work inline.
- **Worker** (`app/worker.py`) claims one job per table per tick, bounded by per-type semaphores, executes, writes results, requeues on transient failure, permanently fails after `max_attempts`.
- **Job tables** are the single source of truth and the queue itself — no separate broker.

### 4.2 Where the worker runs — both options live

Both launch paths are implemented; application code is identical:

- **4.2a — In-process background task:** `app/main.py` startup calls `await start_worker()` (an `asyncio.create_task` on `_loop()`). Zero extra deploy surface. Redeploy still interrupts in-flight jobs, but `FOR UPDATE SKIP LOCKED` + the stuck-job sweep makes them safely reclaimable on the next boot.
- **4.2b — Separate worker process:** `python -m app.worker` (module `__main__` calls `main()`), which installs `SIGTERM`/`SIGINT` handlers for graceful shutdown and runs the same `_loop()`. Decouples job execution from web redeploys entirely. Use this on a long-lived host for full durability.

### 4.3 Worker configuration (constants in `worker.py`)

```python
WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"
POLL_INTERVAL = 3                       # seconds between poll ticks
STUCK_JOB_TIMEOUT_MIN = 90              # reclaim running jobs older than this
SWEEP_EVERY = 20                        # sweep every 20 ticks (~60s)

MAX_CONCURRENT = {
    "docking": 2,          # Vina subprocesses (was the OOM culprit)
    "sequencing": 1,
    "pipeline": 1,
    "md": 1,               # OpenMM is CPU/memory heavy
    "function_predict": 1,
}
```

Per-type `asyncio.Semaphore`s bound concurrent execution. **The concurrency caps directly address the earlier OOM incident.**

### 4.4 Dispatch table

```python
_DISPATCH = {
    "docking_jobs":     ("claim_next_docking_job",     _run_docking,     "docking"),
    "sequencing_jobs":  ("claim_next_sequencing_job",  _run_sequencing,  "sequencing"),
    "jobs":             ("claim_next_pipeline_job",    _run_pipeline,    "pipeline"),
}
```

- **`docking_jobs`** also carries **MD** and **function prediction** jobs, distinguished by `payload.tool_type` (`"md"` / `"function_predict"` / else docking). `_run_docking` dispatches on that field.
- `_run_docking` → `app.routers.docking._run_docking_sync` (blocking Vina/Open Babel via subprocess, run with `asyncio.to_thread`).
- `_run_sequencing` → `app.routers.sequencing._worker` (async, run in a fresh event loop per job).
- `_run_pipeline` → `app.workers.pipeline_worker.process_job` (async, fresh event loop per job).
- Heavy runs (`_run_md`, `_run_function_predict`) write results to Supabase Storage via `services/artifact_storage.upload_json` and store only `storage_url` on the row (inline `result_sdf` is deprecated).

### 4.5 Failure & retry semantics

`_handle_failure(table, job, exc)`:
- `attempts >= max_attempts` → patch `status='failed'` (plus `done_at` for non-`jobs` tables) with a **user-facing, traceback-free** error: `"Job failed: {exc}. Reference ID: {job_id[:8]}"`. Full tracebacks go only to server logs via `logger.exception`.
- otherwise → patch `status='queued'`, clear `claimed_at/claimed_by` so the next poll picks it up again.

### 4.6 Stuck-job recovery

Every `SWEEP_EVERY` ticks, `_sweep_stuck(table)` finds rows with `status='running'` and `claimed_at < now() - 90 min` and resets them to `queued` (clearing the claim). A worker that dies mid-run therefore gets its in-flight jobs reclaimed within ~90 min.

### 4.7 Native-library ordering (MD safety)

`worker.py` imports `openmm.app` **before** any rdkit import. The OpenMM and RDKit wheels bundle conflicting copies of the MSVC runtime DLLs (`msvcp140`/`concrt140`); if rdkit loads first, OpenMM's Context creation crashes with a native access violation. ADMET/docking jobs import rdkit lazily, so preloading OpenMM guarantees safe ordering for MD jobs.

### 4.8 Supabase-side changes (already applied via `005_worker_durable.sql`)

1. Columns added to `docking_jobs`, `sequencing_jobs`, `jobs`:
   `claimed_at timestamptz`, `claimed_by text`, `attempts integer NOT NULL DEFAULT 0`, `max_attempts integer NOT NULL DEFAULT 3`.
2. `SECURITY DEFINER` RPCs: `claim_next_docking_job(worker_id text)`, `claim_next_sequencing_job(worker_id text)`, `claim_next_pipeline_job(worker_id text)` — each returns the oldest eligible `queued` row (attempts < max_attempts), marks it `running`, stamps the claim, increments `attempts`.
3. `docking_jobs.payload jsonb` added for the MD / function-prediction tool-type dispatch; `storage_url text` added (with `006_artifact_storage`) for artifact offload.

---

## 5. Migration status

| Step | Status |
|---|---|
| 1. Columns + RPC functions in Supabase (`005_worker_durable.sql`) | ✅ done |
| 2. `app/worker.py` claim/run/sweep loop | ✅ done |
| 3. Submit routes stop calling `run_in_executor`; just insert and return | ✅ done |
| 4. In-process launch at startup (`app/main.py`) + standalone entrypoint | ✅ both shipped — use standalone on a long-lived host for full durability |
| 5. `MAX_CONCURRENT` caps from day one | ✅ done — docking 2, everything else 1, tuned per observed memory/CPU |
| 6. Verify concurrent submit + kill-mid-job → sweep reclaims | ✅ tested |

---

## 6. Out of scope (for this doc)

- ~~Auth/ownership on job endpoints~~ — **done** (`services/auth.py`: `require_user_id`, `require_user_or_api_key`).
- ~~SSRF protection on URLs~~ — **done** (`services/ssrf.py`).
- Chemically-accurate interaction detection — separate scientific-quality item.
- New tool modules (MD, ADMET, function prediction, etc.) — built and queued **through this worker** (`tool_type` dispatch on `docking_jobs`), so no longer gated on worker existence.

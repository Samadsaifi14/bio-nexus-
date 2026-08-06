# Bio Nexus — Technical Specification

**Version:** 3.0
**Repos:** Monorepo at `bioai-platform/` — `frontend/` (Next.js 14 App Router, TypeScript) · `backend/` (FastAPI, async + thread workers)
**Last Updated:** August 2026
**Runtime status:** Phase 1–2 shipped, Phase 3 partial, Phase 4 partial, sequencing MVP, durable worker live, dark-only design system.

---

## Repository Structure

### `bioai-platform/frontend` (Current Structure)

```
bioai-platform/frontend/
├── src/
│   ├── app/
│   │   ├── (auth)/                       # auth, auth/callback
│   │   ├── (dashboard)/
│   │   │   ├── layout.tsx                # App shell: collapsible sidebar + header
│   │   │   ├── dashboard/page.tsx        # Stats, quick-tools grid, recent jobs
│   │   │   ├── analyze/page.tsx          # Operation hub (all tools listed)
│   │   │   ├── analyze/{tool}/page.tsx   # 17 tool pages:
│   │   │   │   │                         #   admet alignment blast compare docking
│   │   │   │   │                         #   domains function interactions md pairwise
│   │   │   │   │                         #   pathway phylo primers sequencing structure
│   │   │   │   │                         #   tools uniprot
│   │   │   ├── wizard/page.tsx           # 8-step guided pipeline wizard
│   │   │   ├── jobs/page.tsx             # Job list with filter tabs
│   │   │   ├── jobs/[jobId]/page.tsx     # Job detail + share
│   │   │   ├── results/[jobId]/page.tsx  # Unified results page
│   │   │   ├── report/[jobId]/page.tsx   # Print-to-PDF report
│   │   │   ├── history/page.tsx
│   │   │   ├── retrieve/page.tsx         # Fetch-by-accession
│   │   │   ├── settings/page.tsx         # API keys, profile, guest upgrade, tutorial replay
│   │   │   ├── learn/                    # Docs: page.tsx + [topic]/page.tsx
│   │   │   └── shared/[token]/page.tsx   # Public share link viewer
│   │   ├── layout.tsx                    # Root layout (Geist fonts, providers)
│   │   ├── providers.tsx                 # Auth + toast providers
│   │   └── globals.css                   # Tailwind + dark semantic tokens + HUD glass
│   ├── components/
│   │   ├── ui/                           # Design-system kit: GlassPanel, HudPanel, HudLegend,
│   │   │   │                             #   ClaySegmented, ClaySlider, ClayToggle, CriticalButton,
│   │   │   │                             #   FlatInput, DataCard, TiltCard, PageHeader, BackButton,
│   │   │   │                             #   ResultsReadyBanner, index.ts
│   │   ├── results/                      # PipelineResults, AIInterpretation, BlastPanel, ScoreBars,
│   │   │   │                             #   AlignmentView, PairwiseAlignView, UniprotPanel,
│   │   │   │                             #   PathwayDiagram, PathwayEnrichment
│   │   ├── structure/                    # RamachandranPlot, SecondaryStructure, StructureComparison
│   │   ├── phylo/PhyloTreeViewer.tsx
│   │   ├── alignment/                    # ConservationTrack, PairwiseResultDisplay
│   │   ├── domains/DomainArchitecture.tsx
│   │   ├── interactions/StringDBViewer.tsx
│   │   ├── primers/PrimerDesigner.tsx
│   │   ├── pipeline/                     # JobProgress, PipelineSelector, SequenceInput
│   │   ├── wizard/AnalysisWizard.tsx
│   │   ├── three/DNAHelix.tsx            # Landing hero background (three.js)
│   │   ├── AlphaFoldViewer.tsx · DockingViewer.tsx · StructureViewer.tsx
│   │   ├── learn/LearnPopover.tsx        # Inline help popover
│   │   ├── TutorialWalkthrough.tsx       # First-run onboarding modal
│   │   ├── SequenceTypewriter.tsx · SequenceRetrieval.tsx · AuditInsightPanel.tsx
│   │   ├── InteractionPanel.tsx · GuestBanner.tsx · ErrorBoundary.tsx
│   │   └── SmoothScrollProvider.tsx      # lenis smooth scroll
│   ├── contexts/auth.tsx                 # Supabase session context
│   ├── hooks/useAuditTrail.ts
│   ├── lib/
│   │   ├── api.ts                        # axios client (baseURL /api/backend, 30s/660s timeouts)
│   │   ├── supabase.ts                   # Supabase browser client (PKCE)
│   │   ├── confidence.ts                 # 4-band confidence token logic
│   │   ├── share.ts · errors.ts · export-utils.ts · status-colors.ts
│   │   └── animations.ts
│   ├── types/                            # pipeline.ts, results.ts, audit.ts
├── sentry.client.config.ts · sentry.server.config.ts
├── next.config.js                       # /api/backend rewrite → backend + Sentry wrapper
└── package.json                         # deps: @phosphor-icons/react, @sentry/nextjs,
                                          #   @supabase/ssr, @supabase/supabase-js, axios,
                                          #   framer-motion, geist, lenis, three, react-hot-toast
```

### `bioai-platform/backend` (Current Structure)

```
bioai-platform/backend/
├── app/
│   ├── main.py                    # FastAPI app, CORS, Sentry init, startup resume sweeps,
│   │                              #   MD probe, in-process durable worker launch
│   ├── config.py                  # Settings loaded from .env.deploy → .env → env vars
│   ├── deps.py                    # slowapi Limiter (per-user JWT sub, else IP)
│   ├── logging_config.py          # JSON logging + request_id var
│   ├── middleware.py              # RequestIDMiddleware (X-Request-Id)
│   ├── worker.py                  # Durable job worker: python -m app.worker
│   ├── routers/                   # 26 route modules (see API surface below)
│   ├── services/
│   │   ├── auth.py                # get_user_id / require_user_id (Supabase JWT),
│   │   │                          #   X-API-Key auth (SHA-256 hashed keys)
│   │   ├── supabase.py            # get_supabase() service-role client (+ get_client alias)
│   │   ├── cache.py               # Redis wrapper, @ttl_cache, cache stats (optional Redis)
│   │   ├── artifact_storage.py    # Large-result offload to Supabase Storage (public bucket)
│   │   ├── audit_engine.py        # Usage/audit event capture
│   │   ├── export.py              # PDF/JSON report generation (reportlab)
│   │   ├── ncbi_service.py        # NCBI Entrez fetch/search (@ttl_cache)
│   │   ├── pathway_enrichment.py  # Reactome enrichment (cached)
│   │   ├── ssrf.py                # SSRF validation for user-supplied URLs
│   │   ├── rate_limit.py · sequence_utils.py · validators.py · blast_config.py
│   ├── tools/                     # Tool classes (many @ttl_cache on run()):
│   │   ├── blast.py · uniprot.py · alphafold.py · sequence_fetch.py
│   │   ├── ebi_msa.py · pairwise_alignment.py · domain_analysis.py
│   │   ├── admet.py (RDKit) · docking.py (AutoDock Vina) · md_sim.py + md_config.py (OpenMM)
│   │   ├── function_predict.py · sequencing.py
│   │   ├── base.py · registration.py
│   ├── ai/
│   │   ├── interpreter.py · llm_client.py (Groq → Gemini fallback chain) · prompts.py
│   ├── pipeline/                  # assembler.py, registry.py, definitions/protein_analysis.py
│   ├── workers/pipeline_worker.py # process_job(): runs `jobs`-table pipelines (heartbeat, live status PATCH)
│   ├── integrations/ncbi/         # blast.py (submit/poll), parser.py
│   ├── data/demo_results.py
│   ├── models/responses.py
│   └── core/storage.py            # (kept; artifacts now go to Supabase Storage)
├── migrations/                    # 001_docking_jobs_columns, 004_auth_user_id,
│                                  #   005_worker_durable (claim RPCs), 006_artifact_storage
├── requirements.txt               # fastapi, uvicorn, slowapi, redis, httpx, biopython,
│                                  #   litellm, sentry-sdk, supabase, reportlab, rdkit,
│                                  #   openmm, pytest
├── Dockerfile · render.yaml
└── supabase/                      # canonical DB migrations (001–007)
```

---

## Authentication Architecture

Auth is Supabase-native (no NextAuth, no custom JWT signing).

```
[Browser]
  1. getSupabase() creates a Supabase client (anon key, PKCE flow).
  2. First visit: signInAnonymously() → guest session.
  3. "Sign in with Google" → supabase.auth.signInWithOAuth('google').

[Guest → Account upgrade]
  4. Guest upgrades via linkIdentity({ provider: 'google' }) — same user_id,
     zero data migration.

[Frontend → Backend API call]
  5. lib/api.ts axios interceptor attaches Authorization: Bearer {access_token}
     (from supabase.auth.getSession()) on every request.
  6. Backend deps (app/services/auth.py) decode the Supabase JWT payload
     (base64url, unverified signature — trusted because requests arrive over
     the private service-role backend and Supabase is the source of truth),
     and return claims['sub'] as user_id.
```

### Guest Flow

- Anonymous Supabase session from first visit.
- Guests can run jobs; the guest banner invites conversion.
- `get_user_id` returns `None` for anonymous requests → routes use `get_user_id` (optional auth) or `require_user_id` (401 if absent).
- **API keys** are an alternative auth path: `X-API-Key` header → SHA-256 hashed → `api_keys.key_hash` lookup → user_id (`get_user_id_from_api_key`, `require_user_or_api_key`).

### Environment Variables

**`bioai-platform/frontend/.env.local`**

```env
NEXT_PUBLIC_API_URL=http://localhost:8000   # backend origin; /api/backend rewrites to it
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_SENTRY_DSN=
```

**`bioai-platform/backend/.env.deploy`** (loaded first by `config.py`)

```env
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=        # backend uses service role (RLS bypass) — never exposed

GROQ_API_KEY=                     # primary AI provider (DEFAULT_MODEL)
GOOGLE_API_KEY=                   # fallback AI provider (gemini-2.0-flash, and pro model route)
SENTRY_DSN=

NCBI_EMAIL=                       # required by NCBI Entrez policy
NCBI_API_KEY=                     # optional, raises rate ceiling to 10 req/s
REDIS_URL=                        # optional — caching silently disabled if unreachable

CORS_ORIGIN=https://bioai-platform.vercel.app
ENVIRONMENT=development
DEFAULT_MODEL=groq/llama-3.3-70b-versatile
PRO_MODEL=claude-sonnet-4-20250514
DEMO_MODE=false
```

---

## API Surface

There is **no `/api/v1` prefix**. The frontend proxies every backend call through a Next.js rewrite:

```
Browser → /api/backend/{path}  →  {NEXT_PUBLIC_API_URL}/{path}
```

Routers are mounted in `app/main.py` (many declare their own `prefix`):

| Prefix | Module | Endpoints |
|---|---|---|
| `/api/pipelines` | pipelines | `POST /run`, `GET /definitions`, `GET /{pipeline_type}/definition` |
| `/api/pipeline/v2` | pipeline_v2 | `POST /run`, `GET /status/{job_id}` |
| `/api/ai` | ai | `POST /interpret`, `POST /interpret/stream` |
| `/api/jobs` | jobs | `GET /`, `GET /count`, `GET /{job_id}`, `DELETE /{job_id}` |
| `/api/share` | share | `POST /`, `GET /{token}` |
| `/api/profile` | profile | `GET/PUT /` |
| `/api/sequences` | sequences | `POST /fetch`, `POST /validate`, `POST /search` |
| `/api/uniprot` | uniprot | `POST /search`, `POST /detail`, `POST /cds` |
| `/api/alignment` | alignment | `POST /run` (MSA, 5 methods), `POST /pairwise` |
| `/api/structures` | structures | `POST /fetch`, `POST /search`, `POST /inventory` |
| `/api/pathways` | pathways | `POST /search`, `POST /detail`, `POST /kegg/search`, `POST /enrichment` |
| `/api/domains` | domains | `GET /{accession}` + `/features /sites /ptm /topology /motifs /variants /disulfide /composition /go /pathways /all`, `POST /scan` |
| `/api/interactions` | interactions | `GET /{gene_name}` |
| `/api/primers` | primers | `POST /design` |
| `/api/structure_analysis` | structure_analysis | `GET /ramachandran/{pdb_id}`, `GET /secondary_structure/{identifier}`, `GET /compare/{pdb_id}` |
| `/phylo` | phylo | `POST /run`, `GET /status/{job_id}`, `GET /models` |
| `/api/export` | export | `GET /job/{job_id}?format=pdf\|json` |
| `/api/keys` | api_keys | `GET /`, `POST /`, `DELETE /{key_id}` |
| `/api/admin` | cache_stats | `GET /cache-stats`, `POST /cache-stats/reset` |
| `/api/docking` | docking | `POST /run`, `GET /status/{job_id}`, `GET /result/{job_id}/pdb` |
| `/api/sequencing` | sequencing | `POST /run`, `GET /status/{job_id}`, `GET /references` |
| `/api/md` | md | `GET /forcefields`, `POST /run`, `GET /status/{job_id}` |
| `/api/function` | function_predict | `POST /predict`, `GET /status/{job_id}` |
| `/api/admet` | admet | `POST /descriptors` |
| `/api/audit` | audit | `POST /event`, `GET /insights` |
| `/health` | main | `GET /health` (cache stats, queue depth, OpenMM status) |

**Response envelope:** plain JSON bodies per endpoint (no generic `{data, error}` wrapper). Errors return `{"detail": ..., "request_id": ...}`; the frontend normalizes them in `lib/errors.ts`.

### Representative contracts

**`POST /api/pipeline/v2/run`**
```jsonc
// Request
{ "sequence": ">id\nMKTAY...", "steps": ["blast","uniprot","msa","phylo","domains","pathway","alphafold","ai"] }
// Response
{ "job_id": "uuid" }
```

**`GET /api/pipeline/v2/status/{job_id}`**
```jsonc
{ "job_id": "uuid", "status": "running", "current_step": "blast",
  "steps": { "blast": {"status":"complete","progress":100,"data":{...}} } }
```
Pipeline v2 jobs are **in-memory** (`_jobs` dict, daemon thread executor) with best-effort persistence into the `jobs` table so wizard runs appear in history and are shareable.

**`GET /api/jobs`**
```jsonc
{ "jobs": [ { "id": "...", "tool": "blast", "status": "complete", "result": {...} } ] }
```

**`GET /api/docking/status/{job_id}`** returns `{ job_id, status, result?: { poses, vina_log, vina_version, rmsd_*, interactions, from_cache }, error? }`.

**`GET /api/sequencing/status/{job_id}`** returns `{ job_id, status, result?: { qc, alignment, variants, consensus_sequence, report, steps_completed }, error? }`.

**`POST /api/md/run`** `{ pdb_id, mode, forcefield?, solvent?, run_length_ps? }` → `{ job_id }`; status returns the full OpenMM trajectory summary (energy, rmsd, rmsf, temperature, radius_of_gyration, sasa).

---

## Job Execution Architecture

Two execution paths coexist.

### 1. Durable worker (docking, sequencing, pipeline jobs) — `app/worker.py`

Runs as an **in-process background task launched in the FastAPI startup** (`await start_worker()`) and can also run standalone (`python -m app.worker`). See `durable-worker-design.md`.

- **Claim:** `claim_next_docking_job` / `claim_next_sequencing_job` / `claim_next_pipeline_job` RPCs use `FOR UPDATE SKIP LOCKED` against `status = 'queued' AND attempts < max_attempts`.
- **Tables:** `docking_jobs` (also carries `tool_type="md"` and `tool_type="function_predict"` jobs), `sequencing_jobs`, `jobs`.
- **Concurrency caps:** `docking: 2`, `sequencing: 1`, `pipeline: 1`, `md: 1`, `function_predict: 1`.
- **Retry:** `attempts` increments per claim; on failure, job is re-queued unless `attempts >= max_attempts` (→ `failed`).
- **Stuck-job sweep:** every 20 poll ticks (~60s), rows stuck in `running` with `claimed_at` older than 90 min are reset to `queued`.
- **Live progress:** `workers/pipeline_worker.process_job()` PATCHes job status to Supabase via a callback and heartbeats `claimed_at` so the sweep never reclaims a live job.

### 2. In-memory thread executor (pipeline v2 / interactive)

`pipeline_v2` runs each job in a daemon `threading.Thread` (`_run_pipeline`), storing progress in a process-local `_jobs` dict guarded by a lock. It persists a lightweight `jobs` row for history/share.

### Startup resilience (`app/main.py`)

- `_fail_stuck_jobs()` — non-terminal `jobs` left from a previous process are marked `failed` on boot.
- `_fail_stuck_dockseq_jobs()` — same for `docking_jobs` / `sequencing_jobs` older than a 30-min grace period.
- MD force-field/solvent matrix verified at startup (real alanine-dipeptide `createSystem` probe); OpenMM presence checked.

---

## External Service Wrappers

External calls live in `app/tools/*` and `app/services/*` as thin clients (httpx/async). Most `run()`/`fetch_*` methods are wrapped with `@ttl_cache` from `services/cache.py`.

| Service | Client | Notes |
|---|---|---|
| NCBI Entrez | `services/ncbi_service.py` | `tool` + `email` params, optional API key, cached |
| EMBL-EBI Tools | `tools/blast.py`, `tools/ebi_msa.py` | job-based submit/poll; BLAST honors program/db/max_hits, DNA queries, 65-min poll cap |
| UniProt REST | `tools/uniprot.py` | reviewed/organism filters, fast-path + debounce |
| AlphaFold DB | `tools/alphafold.py` | prediction retrieval via PDB/AlphaFold |
| RCSB PDB | `routers/structures.py`, `structure_analysis.py` | fetch, inventory, Ramachandran, DSSP, Foldseek compare |
| InterProScan / PROSITE | `tools/domain_analysis.py` | domains + raw-sequence scan |
| Reactome / KEGG | `services/pathway_enrichment.py`, `routers/pathways.py` | search, detail, enrichment (cached) |
| STRING | `routers/interactions.py` | interaction lookup |
| AutoDock Vina | `tools/docking.py` | local subprocess; parses 1.2.7 log (RMSD l.b./u.b., version, seed) |
| OpenMM | `tools/md_sim.py` | implicit-solvent MD; validated ff×solvent matrix |
| RDKit | `tools/admet.py` | in-process descriptor computation |
| LiteLLM | `ai/llm_client.py` | Groq (primary) → Gemini (fallback) → pro model; only configured providers are added |

### AI fallback chain (`ai/llm_client.py`)

```
provider list (in order):
  groq/{DEFAULT_MODEL}          if GROQ_API_KEY set
  gemini/gemini-2.0-flash       if GOOGLE_API_KEY set
  pro model (claude-sonnet-4)   via Google key, for pro prompts
```
On provider failure the client advances to the next configured model. If none succeed the endpoint returns an honest error the UI surfaces as a visible banner — never fabricated analysis.

---

## Frontend API Client (`lib/api.ts`)

- Two axios instances: `api` (30s timeout) and `longApi` (660s) — both `baseURL: '/api/backend'`.
- Request interceptor attaches `Authorization: Bearer` from `supabase.auth.getSession()`.
- Typed function exports per resource: `runPipelineV2`, `getPipelineStatusV2`, `runBlast`, `runAlignment`, `runPairwiseAlignment`, `fetchStructure`, `runDocking`, `runSequencing`, `computeADMET`, `runMD`, `predictFunction`, `searchUniprot`, `scanPrositeSequence`, `searchPathways`, `runEnrichment`, `getApiKeys`, `createShareLink`, `getExportUrl`, etc.
- Streaming AI text uses `fetch('/api/backend/api/ai/interpret/stream')` directly.

## Job Status Polling (Frontend)

Tool pages poll their job-status endpoint with `setInterval` while `status` is non-terminal (`queued`, `running`, and the intermediate states like `submitted_to_ncbi`, `polling_ncbi`, `parsing`, `interpreting`, `pathway_enrichment`, `fetching_alphafold`), and stop on `complete` / `failed`. Terminal statuses are `complete` + `failed`.

## TypeScript Types

Types live in `src/types/` (`pipeline.ts`, `results.ts`, `audit.ts`) — e.g. `JobStatus`, `BlastResult`, `DockingResult` (poses, vina log, interactions), `SequencingResult` (QC, variants, consensus), `ADMETResult` (Lipinski/Veber/Ghose/Egan/MDDR, PAINS/Brenk, absorption/distribution/metabolism/toxicity), `MDSimulationResult` (energy/RMSD/RMSF/Rg/SASA), `FunctionPredictionResult` (GO terms, EC numbers). No `any` in new code; unknown external JSON is narrowed explicitly.

## CORS Configuration

`app/main.py` allows `http://localhost:3000`, `http://localhost:3001`, `CORS_ORIGIN`, and `https://bioai-platform.vercel.app` with `allow_methods=["*"]`, `allow_headers=["*"]`, credentials enabled.

## Error Codes Reference

```
AUTH_REQUIRED        — missing/invalid Supabase JWT (401)
JOB_NOT_FOUND        — job_id does not exist or is not owned by the caller (404)
SEQUENCE_INVALID     — FASTA/sequence fails validation (400)
BLAST_TIMEOUT        — external BLAST job exceeded poll cap (65 min)
EXTERNAL_API_DOWN    — external service unavailable
RATE_LIMIT_EXCEEDED  — slowapi 429 (per-user by JWT sub, else IP)
WORKER_LOST_ON_RESTART — job stranded by a previous process (marked failed at boot)
```
Errors carry `request_id` (from `RequestIDMiddleware`) so support can correlate logs/Sentry.

## Deployment

### Frontend — Vercel
- Deployed from `bioai-platform/frontend/`; `NEXT_PUBLIC_API_URL` read at build time (rewrite forces clean rebuild).
- Sentry DSN as `NEXT_PUBLIC_SENTRY_DSN`.
- Production URL: https://bioai-platform.vercel.app

### Backend — Hugging Face Spaces
- Space: `Samad14/bio-nexus-api` (SDK docker, `app_port: 7860`); Dockerfile installs OpenMM, RDKit, and pre-compiled PhyML from bioconda.
- Env vars set as Space secrets.

### Data — Supabase
- Single project; RLS enabled; migrations in `bioai-platform/supabase/migrations/` (run via `supabase db push`).
- Large artifacts offloaded to a Supabase Storage bucket (`services/artifact_storage.py`) with `storage_url` recorded on `docking_jobs`, `sequencing_jobs`, `jobs`.
- Redis optional; if `REDIS_URL` is unreachable, `@ttl_cache` degrades to no-op and the app still works.

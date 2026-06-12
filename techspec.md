# BioFlow AI — Technical Specification

**Version:** 1.0  
**Repos:** `bioflow-frontend` (Next.js 14) · `bioflow-backend` (FastAPI)  
**Last Updated:** June 2026

---

## Repository Structure

### `bioflow-frontend`

```
bioflow-frontend/
├── app/
│   ├── (auth)/
│   │   ├── login/
│   │   │   └── page.tsx
│   │   └── signup/
│   │       └── page.tsx
│   ├── (app)/
│   │   ├── dashboard/
│   │   │   └── page.tsx          # Job history, saved analyses
│   │   ├── job/
│   │   │   └── [jobId]/
│   │   │       └── page.tsx      # Live job status + results
│   │   └── layout.tsx            # App shell with nav
│   ├── wizard/
│   │   ├── page.tsx              # Workflow selection entry
│   │   └── [workflowType]/
│   │       └── page.tsx          # Specific wizard flow
│   ├── api/
│   │   └── auth/
│   │       └── [...nextauth]/
│   │           └── route.ts      # NextAuth handlers
│   ├── layout.tsx                # Root layout
│   ├── page.tsx                  # Landing page
│   └── globals.css
├── components/
│   ├── ui/                       # Primitive components (button, input, card, etc.)
│   ├── visualizations/
│   │   ├── SequenceViewer.tsx    # Colored sequence display with annotations
│   │   ├── BlastResultsTable.tsx # Interactive BLAST hits table
│   │   ├── AlignmentViewer.tsx   # Color-coded pairwise alignment
│   │   ├── MSAViewer.tsx         # Multiple sequence alignment block view
│   │   ├── StructureViewer.tsx   # NGL.js / Mol* 3D structure wrapper
│   │   ├── PhyloTreeViewer.tsx   # phylotree.js tree renderer
│   │   ├── RamachandranPlot.tsx  # D3.js phi/psi scatter plot
│   │   ├── ConservationPlot.tsx  # Per-position conservation bar chart
│   │   └── PathwayViewer.tsx     # Reactome pathway embed
│   ├── wizard/
│   │   ├── WizardShell.tsx       # Step container, progress bar, navigation
│   │   ├── WizardStep.tsx        # Individual step wrapper
│   │   └── steps/
│   │       ├── SequenceInputStep.tsx
│   │       ├── DatabaseSelectStep.tsx
│   │       ├── AlgorithmSelectStep.tsx
│   │       └── ConfirmRunStep.tsx
│   ├── job/
│   │   ├── JobStatusCard.tsx     # Live step-by-step progress display
│   │   ├── StepTimeline.tsx      # Visual pipeline step timeline
│   │   └── ResultsPage.tsx       # Full results layout wrapper
│   └── layout/
│       ├── Navbar.tsx
│       ├── Sidebar.tsx
│       └── GuestBanner.tsx       # Shown to guest users prompting signup
├── lib/
│   ├── api.ts                    # Type-safe backend API client
│   ├── supabase.ts               # Supabase client (browser)
│   ├── supabase-server.ts        # Supabase client (server components)
│   ├── types.ts                  # All shared TypeScript types
│   └── constants.ts              # Workflow types, step labels, etc.
├── hooks/
│   ├── useJobPolling.ts          # React Query polling for job status
│   ├── useGuestSession.ts        # Guest session cookie management
│   └── useWorkflowWizard.ts      # Wizard state machine
└── public/
    └── fonts/                    # Self-hosted Space Grotesk + JetBrains Mono
```

### `bioflow-backend`

```
bioflow-backend/
├── app/
│   ├── main.py                   # FastAPI app, CORS, lifespan events
│   ├── api/
│   │   ├── deps.py               # Auth dependencies, DB session
│   │   └── routes/
│   │       ├── jobs.py           # POST /jobs, GET /jobs/{id}, GET /jobs/{id}/steps
│   │       ├── sequences.py      # POST /sequences/fetch, POST /sequences/validate
│   │       ├── blast.py          # POST /blast/submit, GET /blast/{job_id}/status
│   │       ├── alignment.py      # POST /align/pairwise, POST /align/msa
│   │       ├── structures.py     # POST /structures/fetch, POST /structures/predict
│   │       └── dashboard.py      # GET /dashboard/jobs (paginated job history)
│   ├── services/
│   │   ├── ncbi_service.py       # Entrez API wrapper (fetch, BLAST)
│   │   ├── embl_service.py       # EMBL-EBI tools (BLAST, ClustalOmega, MUSCLE)
│   │   ├── pdb_service.py        # RCSB PDB REST API
│   │   ├── uniprot_service.py    # UniProt REST API
│   │   ├── alphafold_service.py  # AlphaFold EBI API
│   │   ├── reactome_service.py   # Reactome REST + WikiPathways fallback
│   │   ├── groq_service.py       # Groq API for AI interpretation
│   │   ├── r2_service.py         # Cloudflare R2 upload/download
│   │   └── cache_service.py      # Cache read/write logic
│   ├── workers/
│   │   └── pipeline_worker.py    # Celery task: executes pipeline steps
│   ├── parsers/
│   │   ├── blast_parser.py       # NCBI BLAST XML → structured dict
│   │   ├── alignment_parser.py   # ClustalW/MSA output → structured dict
│   │   ├── pdb_parser.py         # PDB/mmCIF parsing via BioPython
│   │   └── newick_parser.py      # Newick tree validation/normalization
│   ├── models/
│   │   └── schemas.py            # Pydantic v2 request/response models
│   └── core/
│       ├── config.py             # Settings (env vars via pydantic-settings)
│       ├── database.py           # Supabase + async DB client
│       └── exceptions.py         # Custom exception classes
├── requirements.txt
├── .env.example
├── Dockerfile
└── celery_worker.py              # Celery worker entrypoint
```

---

## Authentication Architecture

### Flow

```
[Browser]
  1. User clicks "Continue with Google"
  2. NextAuth handles OAuth redirect → Google → callback
  3. NextAuth creates JWT (signed with NEXTAUTH_SECRET)
  4. JWT stored in httpOnly cookie

[Frontend → Backend API call]
  5. lib/api.ts reads session token from NextAuth
  6. Sends as Authorization: Bearer {token} header

[FastAPI Backend]
  7. deps.py validates JWT signature
  8. Extracts user_id (sub claim)
  9. Looks up profiles table in Supabase
  10. Injects user context into route handlers
```

### Guest Flow

```
[Browser - no account]
  1. useGuestSession hook checks cookie 'bioflow_guest_id'
  2. If not present: POST /api/guest/session → returns session_id
  3. Session_id stored in cookie (24h expiry, SameSite=Strict)
  4. All API calls include X-Guest-Session-Id header
  5. After 1 job: GuestBanner shows "Save your analysis — create account"
```

### Environment Variables

**`bioflow-frontend/.env.local`**

```env
# NextAuth
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=                      # openssl rand -base64 32

# Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# Supabase
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=            # server-side only, never exposed to browser

# Backend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**`bioflow-backend/.env`**

```env
# Supabase
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=            # backend uses service role for RLS bypass

# External APIs
NCBI_API_KEY=                         # register at ncbi.nlm.nih.gov/account
NCBI_EMAIL=                           # required by NCBI Entrez policy
GROQ_API_KEY=
ANTHROPIC_API_KEY=

# Cloudflare R2
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=bioflow-raw-responses
R2_PUBLIC_URL=                        # optional CDN URL for public assets

# Redis (Upstash)
REDIS_URL=                            # rediss://... from Upstash dashboard

# App
SECRET_KEY=                           # for JWT verification (same as NEXTAUTH_SECRET)
ENVIRONMENT=development               # development | production
CORS_ORIGINS=http://localhost:3000
```

---

## API Contracts

### Base URL: `{API_URL}/api/v1`

All responses follow:

```typescript
// Success
{ data: T, error: null }

// Error
{ data: null, error: { code: string, message: string, details?: any } }
```

---

### Jobs

**`POST /jobs`**  
Create a new job and enqueue it.

```typescript
// Request
{
  workflow_type: WorkflowType,
  input_params: Record<string, any>,   // workflow-specific (see schema.md)
  title?: string                        // auto-generated if omitted
}

// Response
{
  job_id: string,
  status: "queued",
  total_steps: number,
  estimated_duration_seconds: number   // rough estimate shown in UI
}
```

**`GET /jobs/{job_id}`**  
Poll job status. Called every 5–10 seconds by frontend.

```typescript
// Response
{
  id: string,
  status: JobStatus,
  workflow_type: WorkflowType,
  title: string,
  total_steps: number,
  completed_steps: number,
  current_step_label: string | null,
  steps: PipelineStep[],
  created_at: string,
  completed_at: string | null,
  error_message: string | null
}
```

**`GET /jobs/{job_id}/results`**  
Fetch all processed results once job is complete.

```typescript
// Response
{
  job_id: string,
  results: {
    step_id: string,
    result_type: ResultType,
    result_data: Record<string, any>,  // workflow-specific shape
    ai_interpretation: string | null,
    created_at: string
  }[]
}
```

**`GET /dashboard/jobs`**  
Paginated job history for authenticated user.

```typescript
// Query params: ?page=1&limit=20&status=completed
// Response
{
  jobs: JobSummary[],
  total: number,
  page: number,
  has_more: boolean
}
```

---

### Sequences

**`POST /sequences/fetch`**  
Fetch sequence by accession number. Cache-first.

```typescript
// Request
{
  accession: string,         // "NP_000509.1", "P12345", "1TIM"
  db_preference?: string     // "ncbi" | "uniprot" | "pdb" — auto-detected if omitted
}

// Response
{
  accession: string,
  db_source: string,
  sequence_type: "protein" | "dna" | "rna",
  sequence: string,
  length: number,
  organism: string,
  description: string,
  gene_name: string | null,
  go_terms: string[],
  from_cache: boolean
}
```

**`POST /sequences/validate`**  
Validate raw sequence string (format, type detection).

```typescript
// Request
{ sequence: string }

// Response
{
  valid: boolean,
  sequence_type: "protein" | "dna" | "rna" | "unknown",
  length: number,
  issues: string[]           // e.g. ["Contains non-standard residue 'X' at position 42"]
}
```

---

## Job Queue Architecture

### Stack
- **Broker:** Upstash Redis (serverless Redis, no infra to manage)
- **Worker:** Celery (Python) running on Railway alongside FastAPI
- **Task:** `pipeline_worker.execute_pipeline(job_id: str)`

### Worker Logic

```python
# Simplified pipeline_worker.py
@celery.task
def execute_pipeline(job_id: str):
    job = db.get_job(job_id)
    db.update_job_status(job_id, "running")

    for step in db.get_pending_steps(job_id):
        try:
            db.update_step_status(step.id, "running")
            
            # Execute the step
            result = execute_step(step)
            
            # Store raw response
            raw_key = store_raw_response(step.id, result.raw)
            
            # Parse and store structured result
            parsed = parse_result(step.step_type, result.raw)
            db.store_processed_result(step.id, job_id, parsed)
            
            # Generate AI interpretation (async, non-blocking)
            generate_interpretation.delay(step.id, parsed)
            
            db.update_step_status(step.id, "completed")
            db.increment_job_progress(job_id)

        except ExternalAPIError as e:
            if step.retry_count < step.max_retries:
                # Exponential backoff retry
                execute_pipeline.apply_async(
                    args=[job_id], 
                    countdown=2 ** step.retry_count * 30
                )
                return
            db.update_step_status(step.id, "failed", error=str(e))
            db.update_job_status(job_id, "partial")
            return

    db.update_job_status(job_id, "completed")
```

### Async External Job Polling

EMBL-EBI BLAST, ClustalOmega, etc. return a job ID and require polling.

```python
@celery.task
def poll_external_job(step_id: str, external_job_id: str, service: str):
    result = check_external_status(service, external_job_id)
    
    if result.status == "running":
        # Re-schedule poll in 15 seconds
        poll_external_job.apply_async(
            args=[step_id, external_job_id, service],
            countdown=15
        )
    elif result.status == "completed":
        handle_completed_external_job(step_id, result)
    elif result.status == "failed":
        handle_failed_external_job(step_id, result)
```

---

## External Service Wrappers

Every external service wrapper follows this contract:

```python
# Standard service result type
@dataclass
class ServiceResult:
    success: bool
    raw_response: str | bytes    # always stored as-is
    response_format: str         # 'json', 'xml', 'fasta', etc.
    parsed_data: dict | None     # None if parsing should happen in parser layer
    error: str | None
    http_status: int
    response_time_ms: int

# Standard wrapper pattern
class NCBIService:
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    
    async def fetch_sequence(self, accession: str) -> ServiceResult:
        start = time.time()
        try:
            response = await self.client.get(
                f"{self.BASE_URL}efetch.fcgi",
                params={"db": "protein", "id": accession, "rettype": "fasta"}
            )
            return ServiceResult(
                success=True,
                raw_response=response.text,
                response_format="fasta",
                parsed_data=None,
                error=None,
                http_status=response.status_code,
                response_time_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return ServiceResult(success=False, error=str(e), ...)
```

---

## Frontend API Client

```typescript
// lib/api.ts — centralized, type-safe API client

const API_BASE = process.env.NEXT_PUBLIC_API_URL + '/api/v1'

async function apiCall<T>(
  endpoint: string,
  options?: RequestInit
): Promise<{ data: T | null; error: ApiError | null }> {
  const session = await getSession()
  
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(session?.accessToken 
        ? { Authorization: `Bearer ${session.accessToken}` }
        : {}),
      ...options?.headers
    }
  })

  const json = await res.json()
  return json
}

// Typed exports
export const api = {
  jobs: {
    create: (payload: CreateJobRequest) =>
      apiCall<CreateJobResponse>('/jobs', { method: 'POST', body: JSON.stringify(payload) }),
    
    getStatus: (jobId: string) =>
      apiCall<JobStatusResponse>(`/jobs/${jobId}`),
    
    getResults: (jobId: string) =>
      apiCall<JobResultsResponse>(`/jobs/${jobId}/results`),
    
    list: (params?: { page?: number; status?: JobStatus }) =>
      apiCall<JobListResponse>(`/dashboard/jobs?${new URLSearchParams(params as any)}`),
  },
  
  sequences: {
    fetch: (accession: string) =>
      apiCall<SequenceResponse>('/sequences/fetch', {
        method: 'POST',
        body: JSON.stringify({ accession })
      }),
    
    validate: (sequence: string) =>
      apiCall<ValidationResponse>('/sequences/validate', {
        method: 'POST',
        body: JSON.stringify({ sequence })
      })
  }
}
```

---

## Job Status Polling (Frontend)

```typescript
// hooks/useJobPolling.ts
export function useJobPolling(jobId: string | null) {
  return useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api.jobs.getStatus(jobId!),
    enabled: !!jobId,
    refetchInterval: (data) => {
      const status = data?.state?.data?.status
      if (!status) return 5000
      if (['completed', 'failed', 'cancelled'].includes(status)) return false
      return status === 'running' ? 5000 : 10000
    },
    staleTime: 0
  })
}
```

---

## TypeScript Types

```typescript
// lib/types.ts

export type WorkflowType =
  | 'blast' | 'pairwise_alignment' | 'msa'
  | 'phylogenetics' | 'msa_phylogenetics'
  | 'structure_retrieval' | 'structure_prediction'
  | 'structural_comparison' | 'structural_analysis'
  | 'homology_modeling' | 'pathway_analysis'
  | 'compound_search' | 'admet_screening' | 'docking'

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'partial' | 'cancelled'

export type StepStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | 'retrying'

export interface Job {
  id: string
  workflowType: WorkflowType
  status: JobStatus
  title: string
  totalSteps: number
  completedSteps: number
  currentStepLabel: string | null
  steps: PipelineStep[]
  createdAt: string
  completedAt: string | null
  errorMessage: string | null
}

export interface PipelineStep {
  id: string
  stepNumber: number
  stepType: string
  stepLabel: string
  status: StepStatus
  startedAt: string | null
  completedAt: string | null
  durationMs: number | null
  errorMessage: string | null
}

export interface ProcessedResult {
  stepId: string
  resultType: string
  resultData: Record<string, unknown>
  aiInterpretation: string | null
}

// BLAST-specific result shape
export interface BlastResult {
  hits: BlastHit[]
  queryLength: number
  database: string
  program: string
  totalHits: number
}

export interface BlastHit {
  accession: string
  description: string
  organism: string
  length: number
  score: number
  bitScore: number
  evalue: number
  identity: number          // percentage
  similarity: number        // percentage
  gaps: number              // percentage
  alignmentLength: number
  queryStart: number
  queryEnd: number
  hitStart: number
  hitEnd: number
  queryAlignment: string
  hitAlignment: string
  midline: string
}
```

---

## CORS Configuration

```python
# app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),  # ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Guest-Session-Id"],
)
```

---

## Error Codes Reference

```
SEQUENCE_NOT_FOUND       — accession number not found in database
SEQUENCE_INVALID         — sequence contains invalid characters
BLAST_TIMEOUT            — external BLAST job exceeded 20-minute limit
BLAST_QUEUE_FULL         — NCBI/EMBL-EBI queue at capacity, retry later
EXTERNAL_API_DOWN        — external service unavailable
PARSE_ERROR              — failed to parse tool output (report to dev)
JOB_NOT_FOUND            — job_id does not exist
UNAUTHORIZED             — missing or invalid token
GUEST_LIMIT_REACHED      — guest user has used their 1 free job
RATE_LIMIT_EXCEEDED      — user has exceeded daily job quota
```

---

## Deployment

### Frontend — Vercel
- Repo: `bioflow-frontend`
- Framework preset: Next.js
- Environment variables: set in Vercel dashboard
- Domain: bioflow.ai (or subdomain for staging: staging.bioflow.ai)

### Backend — Railway
- Repo: `bioflow-backend`
- Service 1: FastAPI web (`uvicorn app.main:app --host 0.0.0.0 --port $PORT`)
- Service 2: Celery worker (`celery -A celery_worker worker --loglevel=info`)
- Both services share same repo, different start commands
- Redis: Upstash (external, connects via REDIS_URL)

### Staging vs Production
- Two Vercel deployments: `main` → production, `dev` → staging
- Two Railway environments: production and staging
- Two Supabase projects: `bioflow-prod` and `bioflow-dev`

# BioFlow AI — Rules

**Version:** 2.0  
**Scope:** Both repos — `bioflow-frontend` and `bioflow-backend` (monorepo at `bio-nexus/bioai-platform/`)  
**Last Updated:** June 2026

---

## 0 — The Prime Rule

**The prototype shipped June 30 — Phase 2 is complete.**  
Hardening (docs, Sentry, cache checks) is done. Phase 3+ items should be planned before building.

---

## 1 — Git Rules

### Branching

```
main          → production (protected, no direct push)
dev           → staging (all PRs merge here first)
feature/*     → new features (branch from dev)
fix/*         → bug fixes (branch from dev)
hotfix/*      → production hotfixes only (branch from main)
```

During the prototype sprint (until June 30): work directly on `dev`.  
Only push to `main` when something is demo-ready.

### Commit Messages

```
Format: <type>(<scope>): <short description>

Types:
  feat      — new feature
  fix       — bug fix
  chore     — setup, config, deps
  refactor  — code restructuring, no behavior change
  style     — CSS/design only
  docs      — documentation only

Scope examples:
  blast, msa, structure, auth, wizard, results, db, cache, worker, ci

Examples:
  feat(blast): add EMBL-EBI BLAST submission and polling
  fix(cache): prevent duplicate sequence_cache entries on concurrent requests
  feat(wizard): add sequence type auto-detection in step 1
  chore(deps): add biopython and httpx to requirements
```

No commit messages like "fix stuff", "wip", "updates". Every commit must be understandable in 6 months.

### Tags

```
v0.1.0-prototype    → demo day commit (June 30)
v0.2.0              → Phase 1 complete (pairwise alignment)
v0.3.0              → Phase 2 complete (MSA + phylogenetics)
```

---

## 2 — Frontend Rules (`bioflow-frontend`)

### File Naming

```
Components:     PascalCase.tsx         BlastResultsTable.tsx
Pages:          page.tsx               (Next.js App Router convention)
Hooks:          camelCase, use prefix  useJobPolling.ts
Lib utilities:  camelCase.ts           api.ts, types.ts
Constants:      SCREAMING_SNAKE.ts     WORKFLOW_TYPES.ts
```

### Component Rules

Every component file must:
1. Export a named function (not default export, except page.tsx files)
2. Have typed props with an interface at the top of the file
3. Use destructured props, never `props.x`

```typescript
// ✓ Correct
interface BlastResultsTableProps {
  hits: BlastHit[]
  isLoading: boolean
  onHitSelect: (hit: BlastHit) => void
}

export function BlastResultsTable({ hits, isLoading, onHitSelect }: BlastResultsTableProps) {
  ...
}

// ✗ Wrong
export default function({ hits, isLoading, onHitSelect }) {
  ...
}
```

### Styling Rules

All styles use Tailwind utility classes. No inline `style={}` objects except:
- Dynamic values that can't be expressed as Tailwind classes (e.g. animated percentages)
- NGL.js / D3.js canvas dimensions

No CSS Modules. No styled-components. No emotion.

```typescript
// ✓ Correct
<div className="bg-bg-surface border border-bg-border rounded-lg p-6">

// ✗ Wrong
<div style={{ backgroundColor: '#0D1117', borderRadius: '12px' }}>
```

Color classes must use the custom tokens defined in tailwind.config.ts. Never hardcode hex values in JSX.

### State Management Rules

- UI state (open/closed, hover, active): `useState` in the component
- Server state (jobs, results): React Query (`useQuery`, `useMutation`)
- Cross-component state: React Context (only for auth session and theme)
- No Redux, no Zustand — they're not needed at this scale

### API Call Rules

All backend calls go through `lib/api.ts`. No direct `fetch()` calls in components.

```typescript
// ✓ Correct
const { data, error } = await api.jobs.create(payload)

// ✗ Wrong
const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/jobs`, { ... })
```

### Type Rules

All types live in `lib/types.ts`. No inline type definitions in component files except simple local types.

No `any`. If the type is genuinely unknown (e.g. raw JSON from external API), use `unknown` and narrow explicitly.

```typescript
// ✓
function parseBlastResult(raw: unknown): BlastResult {
  if (!raw || typeof raw !== 'object') throw new Error('Invalid BLAST result')
  ...
}

// ✗
function parseBlastResult(raw: any): BlastResult {
```

### Sequence Display Rule

All sequence data (DNA, protein, accession numbers) is rendered in the `font-mono` family (JetBrains Mono). No exceptions. Sequence data rendered in sans-serif is a bug.

```typescript
// ✓
<span className="font-mono text-sm text-accent">{accession}</span>
<pre className="font-mono text-seq-md leading-relaxed">{sequenceString}</pre>
```

### Error Display Rule

Every async operation must show one of three states: loading, error, or data. No operation silently fails.

```typescript
// Every results component follows this pattern
if (isLoading) return <ResultsSkeleton />
if (error) return <ErrorState message={error.message} onRetry={refetch} />
return <ResultsDisplay data={data} />
```

---

## 3 — Backend Rules (`bioflow-backend`)

### File Naming

```
Services:    snake_case_service.py    ncbi_service.py
Parsers:     snake_case_parser.py     blast_parser.py
Routes:      snake_case.py            jobs.py, sequences.py
Models:      schemas.py               (all Pydantic models in one file per domain)
Workers:     snake_case_worker.py     pipeline_worker.py
```

### Service Layer Rules

Every external API call is wrapped in its own service class. Route handlers never call `httpx` or `requests` directly.

```python
# ✓ Correct
@router.post("/sequences/fetch")
async def fetch_sequence(body: FetchSequenceRequest, db = Depends(get_db)):
    result = await ncbi_service.fetch_sequence(body.accession)
    ...

# ✗ Wrong
@router.post("/sequences/fetch")
async def fetch_sequence(body: FetchSequenceRequest):
    response = await httpx.get(f"https://eutils.ncbi.nlm.nih.gov/...")
    ...
```

### Service Result Rule

Every service method returns a `ServiceResult` dataclass (defined in `app/core/types.py`). Services never raise exceptions for external API failures — they return `ServiceResult(success=False, error=...)`. Only programming errors (bugs) raise exceptions.

```python
# ✓ Correct
async def fetch_sequence(self, accession: str) -> ServiceResult:
    try:
        response = await self.client.get(...)
        if response.status_code != 200:
            return ServiceResult(success=False, error=f"HTTP {response.status_code}")
        return ServiceResult(success=True, raw_response=response.text, ...)
    except httpx.TimeoutException:
        return ServiceResult(success=False, error="Request timed out", error_code="timeout")

# ✗ Wrong
async def fetch_sequence(self, accession: str) -> str:
    response = await self.client.get(...)
    response.raise_for_status()
    return response.text
```

### Route Handler Rules

Route handlers are thin. Their job: validate input, call service, handle result, return response. No business logic in route handlers.

Maximum 20 lines per route handler. If longer, extract to a service or helper.

```python
# ✓ Correct (14 lines)
@router.post("/sequences/fetch", response_model=SequenceResponse)
async def fetch_sequence(
    body: FetchSequenceRequest,
    db=Depends(get_db),
    user=Depends(get_optional_user)
):
    cached = await cache_service.get_sequence(body.accession)
    if cached:
        return SequenceResponse(**cached, from_cache=True)
    
    result = await ncbi_service.fetch_sequence(body.accession)
    if not result.success:
        raise HTTPException(status_code=502, detail=result.error)
    
    parsed = sequence_parser.parse_fasta(result.raw_response)
    await cache_service.set_sequence(body.accession, parsed)
    return SequenceResponse(**parsed, from_cache=False)
```

### Celery Worker Rules

Workers are the most critical code in the backend. Rules:

1. Every step update is immediately persisted to the database. No batching.
2. Every raw API response is stored before parsing begins. If parsing fails, the raw response is still there for debugging.
3. Workers catch all exceptions and update job/step status accordingly. A worker crash must never leave a job stuck in "running" forever.
4. Workers never make direct HTTP calls to external APIs. They call service methods.

```python
# ✓ Correct pattern
try:
    db.update_step_status(step.id, "running")
    result = await service.call_external_api(...)
    
    # Store raw FIRST
    raw_key = await r2_service.store_raw_response(step.id, result.raw_response)
    db.store_raw_api_response(step.id, raw_key=raw_key)
    
    # Then parse
    parsed = parser.parse(result.raw_response)
    db.store_processed_result(step.id, job.id, parsed)
    db.update_step_status(step.id, "completed")

except Exception as e:
    db.update_step_status(step.id, "failed", error_message=str(e))
    raise  # re-raise so Celery marks task as failed
```

### Pydantic Schema Rules

All request bodies and response models are Pydantic v2 models. No raw dicts as API contracts.

Model naming:
- Request body: `{Action}Request` (e.g. `FetchSequenceRequest`)
- Response body: `{Thing}Response` (e.g. `SequenceResponse`, `JobStatusResponse`)
- DB model: `{Thing}` (e.g. `Job`, `PipelineStep`)

```python
# ✓ Correct
class FetchSequenceRequest(BaseModel):
    accession: str
    db_preference: Literal["ncbi", "uniprot", "pdb"] | None = None
    
    @field_validator("accession")
    @classmethod
    def validate_accession(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Accession cannot be empty")
        return v.strip().upper()
```

### Environment Variable Rules

All config comes from `app/core/config.py` via pydantic-settings. Never read `os.environ` directly in service or route files.

```python
# ✓ Correct
from app.core.config import settings
api_key = settings.NCBI_API_KEY

# ✗ Wrong
import os
api_key = os.environ.get("NCBI_API_KEY")
```

---

## 4 — External API Rules

### Rate Limit Compliance

| Service | Limit | Our handling |
|---|---|---|
| NCBI Entrez (no key) | 3 req/s | Register API key immediately. With key: 10 req/s |
| NCBI Entrez (with key) | 10 req/s | Celery task queue naturally spaces requests |
| EMBL-EBI Tools | Job-based (no strict limit) | Single job per step, poll at 15s intervals |
| UniProt REST | 200 req/s | Cache aggressively (24h TTL) |
| RCSB PDB | No stated limit | Cache (7-day TTL) |
| AlphaFold EBI | Job-based | Cache predictions (30-day TTL) |
| Reactome | No stated limit | Cache (12h TTL) |
| Groq API | Depends on plan | Cache AI interpretations per result hash |

Never hit any external API without checking cache first.

### NCBI Policy Compliance

NCBI Entrez requires:
- An email address in all requests (`tool` and `email` params)
- An API key for >3 requests/second
- No automated querying of the main web interface (only use Entrez API)

Always set in NCBIService:
```python
params = {
    "tool": "bioflow-ai",
    "email": settings.NCBI_EMAIL,
    "api_key": settings.NCBI_API_KEY,
    ...
}
```

### Fallback Chains

When an external service fails, follow these fallback chains:

```
BLAST:       EMBL-EBI BLAST → NCBI BLAST → error (log both failures)
Sequence:    sequence_cache → NCBI Entrez → UniProt REST → error
Pathways:    Reactome → WikiPathways → error (never fall back to KEGG if monetized)
Structure:   structure_cache → RCSB PDB → error
```

Fallback must be transparent to the user: "We're using a backup service — results may take slightly longer."

---

## 5 — Database Rules

### Query Rules

All DB operations go through the Supabase Python client. No raw SQL in route handlers or service files. SQL belongs only in:
- `schema.md` (the schema itself)
- `app/core/database.py` (connection setup)
- Supabase SQL editor (migrations)

### Job Status Rule

Job status and step status must always be consistent. When a step transitions:
- `step → running`: Update step, update `jobs.current_step_label`
- `step → completed`: Update step, increment `jobs.completed_steps`
- `step → failed`: Update step, set `jobs.status = 'failed'` (or `'partial'` if some steps completed)
- All steps completed: Set `jobs.status = 'completed'`, set `jobs.completed_at`

Never update only one without updating the other.

### Cache-First Rule

Before any external API call, check the corresponding cache table. After any successful external API call, write to the cache. This is mandatory, not optional.

```python
# ✓ Always cache-first
async def fetch_sequence(accession: str) -> SequenceData:
    cached = await db.get_cached_sequence(accession)
    if cached:
        await db.increment_cache_hit(cached.id)
        return cached.sequence_data
    
    result = await ncbi_service.fetch_sequence(accession)
    await db.cache_sequence(accession, result)
    return result

# ✗ Never skip cache
async def fetch_sequence(accession: str) -> SequenceData:
    return await ncbi_service.fetch_sequence(accession)  # always hits NCBI
```

### RLS Rule

The frontend Supabase client uses the `anon` key. It must never access `raw_api_responses` directly — this table is backend/service-role only. The frontend reads only `processed_results`, `jobs`, `pipeline_steps`, and `profiles`.

---

## 6 — AI Interpretation Rules

These are non-negotiable and exist to prevent scientific misinformation.

1. **AI interpretations are always labeled** as "AI-generated explanation" in the UI. Never presented as ground truth.

2. **AI prompts are factual, not speculative.** Prompts include the actual numerical output. The model explains the numbers; it does not invent numbers.

3. **Uncertainty language is mandatory.** Prompts instruct the model to use phrases like "suggests", "indicates", "may be", "consistent with". The model must not say "this protein IS a hemoglobin" — it says "this protein is likely a hemoglobin based on X% identity with known hemoglobin sequences."

4. **No hallucination of citations.** Prompts explicitly state: "Do not cite any papers, databases, or sources. Only describe what the numerical results show."

5. **Prompt templates are versioned.** When a prompt is changed, add a comment with the date and reason.

```python
# Prompt template — v1 (June 2026)
# Changed: removed "significant" as too vague; added specific threshold language
BLAST_INTERPRETATION_PROMPT = """
You are explaining bioinformatics results to a biology student.
Based only on the data provided below, write 2-3 sentences explaining what these 
BLAST results suggest about the query sequence. Use clear, educational language.
Do not cite papers or invent information not present in the data.
Use hedged language: 'suggests', 'indicates', 'consistent with', 'likely'.

Data:
- Query: {query_description} ({query_length} residues)
- Database: {database}
- Top hit: {top_hit_organism} | {top_hit_description}
- Identity: {identity}% over {alignment_length} residues
- E-value: {evalue}
- Total significant hits (E < 0.001): {significant_hit_count}
"""
```

6. **Groq for speed, Claude for depth.** Groq (llama-3.1-8b-instant) generates the inline paragraph interpretation (shown immediately on results page). Claude API generates the full PDF report interpretation (triggered only when user requests PDF). Never reverse these.

---

## 7 — Security Rules

1. **NCBI API key, Groq API key, Anthropic API key** — never logged, never returned in API responses, never committed to git.

2. **Guest session IDs** — treated as sensitive. Not logged in plaintext. The ID is a secret that controls access to a job.

3. **Sequence data** — user sequences are private. Never returned in error messages. Never logged in application logs at INFO level (DEBUG only, and debug logging disabled in production).

4. **No sequence data in URLs.** Sequences are never passed as query parameters. Always in request body (POST).

5. **R2 objects** — never publicly readable. Always accessed via signed URLs with 1-hour expiry. The R2 bucket is private.

6. **CORS** — `CORS_ORIGINS` is explicitly set. Never use `allow_origins=["*"]` in production.

---

## 8 — Monitoring & Observability Rules (Sentry)

1. **Errors must be captured.** Every unhandled exception in production should reach Sentry. Frontend: `@sentry/nextjs` with `beforeSend` filtering. Backend: `sentry_sdk.init()` in startup.

2. **No secrets in Sentry.** Ensure `beforeSend` strips auth tokens, API keys, and sequence data from Sentry events.

3. **Traces** at `tracesSampleRate: 0.1` (10%) — enough for debugging, cheap enough for free tier.

4. **Environment tagging.** All Sentry events must be tagged with `environment: development | production`.

---

## 9 — Caching Rules

1. **Cache-first architecture.** Every external API call must check the corresponding cache before executing. Use `@ttl_cache` decorator from `services/cache.py`.

2. **Cache key format.** `{prefix}:{sha256_first_16_chars_of_json_input}` — consistent, deterministic.

3. **TTL guidelines:**
   - BLAST results: 24h
   - UniProt records: 24h
   - AlphaFold predictions: 30 days
   - Pathway enrichment: 12h
   - NCBI sequence/search: 24h

4. **Cache misses are tracked.** `get_cache_stats()` exposes hit/miss counts. Monitor via `/api/admin/cache-stats`.

5. **`from_cache` flag.** All cached results include `from_cache: true/false` in the response dict for observability.

6. **Graceful fallback.** If Redis is unavailable (`_redis = None`), caching is silently disabled — the app still works.

---

## 10 — Documentation & Learning Rules

1. **`/learn` is the canonical docs source.** All inline "Learn more →" links must point to a valid `/learn/{topic}` route.

2. **LearnPopover consistency.** Every scientific term shown to users (E-value, bit score, pLDDT, bootstrap, etc.) must have a LearnPopover component available.

3. **First-run tutorial.** New users see the TutorialWalkthrough once. It must be re-accessible from the Settings page.

4. **Plain language.** All docs and help text must be understandable by a first-year M.Sc. student. No jargon without explanation.

---

## 11 — What NOT To Build (Current)

This list keeps scope in check for Phase 3+.

❌ **Phase 2 items** — already built (MSA, Phylo, Domains, Pathways, Primers, API keys, Share, Export, Guest upgrade, Docs, Sentry, Cache checks)  
❌ **Molecular docking / DiffDock** — requires revenue for paid Replicate API  
❌ **RNA-seq pipeline** — Phase 3, requires file storage infrastructure  
❌ **FASTQ / variant calling** — Phase 3, requires compute  
❌ **Lab workspaces** — Phase 4, requires institution licensing  
❌ **Custom pipeline builder** — Phase 4  
❌ **Mobile app** — not planned  
❌ **Email notifications** — not planned until Phase 4  
❌ **Admin panel** — not needed until 100+ users

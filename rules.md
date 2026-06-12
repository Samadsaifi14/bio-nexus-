# rules.md — BioFlow AI House Rules

## 1. Repo Structure

**bioflow-frontend**
/app

/(marketing)/page.tsx       landing

/(app)/analyze/...           wizard

/(app)/jobs/[id]/page.tsx    processing + results

/(app)/dashboard/page.tsx

/auth/...

/components

/ui          shared primitives (button, badge, etc.)

/sequence    sequence display, alignment view

/results     hits table, score bars, AI summary

/lib

/api         backend client

/supabase

/utils

/hooks

/prompts       (none here — prompts live in backend)

/styles        design tokens

**bioflow-backend**
/app

main.py

/api/v1/jobs

/api/v1/sequences

/core          config, db.py, storage.py

/integrations

/ncbi        blast.py, efetch.py

/uniprot     (Phase 1)

/pdb         (Phase 1)

/ebi         (Phase 1 — Clustal Omega)

/reactome    (Phase 1)

/services      job orchestration, interpreter.py

/models        Pydantic schemas

/prompts         *.md — AI prompt templates

## 2. Naming Conventions
- **Files/components:** PascalCase for React components (`HitsTable.tsx`), kebab-case for routes/folders.
- **API routes:** `/api/v1/{resource}`, plural nouns (`/jobs`, `/sequences`).
- **Database:** snake_case (per schema.md).
- **Branches:** `feat/`, `fix/`, `chore/`, `docs/`.
- **Commits:** Conventional Commits — `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`.

## 3. Adding a New Bioinformatics API Integration
Every integration in `/integrations/{source}/` follows the same shape:

1. A thin client function per operation (e.g., `submit_blast`, `check_status`, `fetch_results`) — no business logic, just the HTTP call.
2. **Rate limits are checked and documented in a comment at the top of the file** before any code is written — this was the lesson from NCBI's 1-req/10s limit.
3. Raw response → uploaded to R2 first, unconditionally. Parsing happens from the stored copy, never inline with the request — this is what makes results reprocessable without re-calling the API (your schema.md decision).
4. Parsed output → written to `job_steps.result_json` via the shared service layer, never directly from the integration module.
5. Errors map to `{error: {code, message, retryable}}` (see §5) — integration modules raise typed exceptions; the service layer translates them.

## 4. AI Prompts
- Location: `/prompts/*.md` in the backend repo.
- Every prompt's system instruction includes the standing framing: results are a **faithful execution of the underlying tool**, not a guarantee of biological truth — confidence language (E-value, etc.) is explained, never smoothed over.
- Versioned by suffix when iterating (`blast_interpretation_v2.md`) rather than overwritten, so you can roll back a prompt that produces worse explanations.

## 5. Error Handling Contract
- Backend: every error response is `{error: {code, message, retryable}}`.
- Frontend: a single `<ErrorState>` component consumes this shape — one place to control all error copy and retry behavior.
- `retryable: true` → show a "Try again" button; `false` → show guidance text instead (e.g., "this sequence format isn't supported").

## 6. Environment Variables
- `.env.example` committed in both repos, kept in sync manually — no secrets ever committed.
- Naming: `{SERVICE}_{PURPOSE}`, e.g., `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `R2_BUCKET`, `GEMINI_API_KEY`.

## 7. No Automated Tests — What Replaces Them
- `tsconfig.json`: `strict: true` — non-negotiable, this is your real safety net on the frontend.
- Every FastAPI endpoint has a Pydantic request/response model — invalid shapes fail loudly at the boundary instead of silently downstream.
- Before any deploy: run the full wizard → job → results flow manually, once, with a real sequence. This single manual check catches the vast majority of regressions in a project this size.

## 8. Working With AI Coding Assistants
You're not using Claude Code, but whichever tool you use (Claude.ai, Cursor, etc.): start new feature chats by pasting schema.md + techspec.md + this file as context. It's the fastest way to keep any assistant — including a fresh chat with me — aligned with decisions already made, without re-explaining the architecture each time.

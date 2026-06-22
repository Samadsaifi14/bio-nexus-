# implementationplan.md — BioFlow AI Implementation Plan

## Track A — Prototype Sprint (18 Days)

One golden path only: **Sequence In → BLAST → AI-interpreted report.** Everything else is Track B.

### Day 0 — Pre-flight (~2 hrs, today)
- [ ] Create `bioflow-frontend` and `bioflow-backend` repos
- [ ] Create Supabase project, run schema.md migrations
- [ ] Create Cloudflare R2 bucket
- [ ] Get API keys: Gemini (Resend optional for prototype)
- [ ] Confirm NCBI BLAST URL API access — **no key required, but max 1 request every 10s**; build this constraint in from day one, not as a fix later

### Days 1–2 — Foundations
**Backend**
- FastAPI scaffold + `/health`
- Supabase client wrapper (`core/db.py`), R2 wrapper (`core/storage.py`)
- Pydantic models for `jobs` / `job_steps`
- `POST /jobs` (create, status=`queued`), `GET /jobs/{id}`

**Frontend**
- Next.js + TS + Tailwind scaffold, design tokens from design.md → `tailwind.config.ts` / `globals.css`
- Supabase client (anon key) + anonymous session on first visit
- Layout shell, static landing page

> Job CRUD is the spine everything attaches to — get it working with dummy data before touching NCBI.

### Days 3–4 — NCBI BLAST Integration (core engine)
- `integrations/ncbi/blast.py`: `submit_blast()`, `check_status()`, `fetch_results()` against the QBLAST URL API
- Background task (start with `asyncio.create_task` — sufficient for a single-instance prototype): on job create, submit → poll every 15s → on `READY`, fetch XML, push to R2, update `job_steps`
- XML parser → hit list (accession, description, % identity, E-value, bit score, alignment)

**Risk flag:** NCBI `nr` searches can take 1–5 min and occasionally queue longer. Build a **demo-mode fallback** now — pick 1–2 well-characterized sequences (e.g., human insulin), pre-run them, cache the result. This is your insurance for Day 18.

### Day 5 — Sequence Input + Validation
- `integrations/ncbi/efetch.py` — fetch sequence by accession
- Sequence-type detection (nucleotide vs. protein, composition-based)
- `POST /sequences/validate`
- Frontend: wizard shell, step indicator, Step 1 (operation grid), Step 2 (paste/accession tabs + validation feedback)

### Days 6–7 — Wizard → Job Creation → Processing Screen
- Step 3 (confirm/run) → `POST /jobs` → `/jobs/[id]`
- Processing screen: `useJobStatus` polling hook, animated status indicator, friendly per-state copy
- Backend: wire job creation to the Day 3–4 background task, update `job_steps` at each stage

**Checkpoint:** by end of Day 7 you can paste a sequence, hit run, and watch real NCBI status updates. First "it's alive" moment.

### Days 8–9 — Results Rendering (raw, no AI yet)
- Frontend: hits table, score-bar visualization (confidence bands), alignment view for top hit
- Backend: `GET /jobs/{id}/results` — parsed hits + top-hit alignment from stored XML

### Days 10–11 — AI Interpretation Layer
- `services/interpreter.py` — Gemini call
- Prompt template at `/prompts/blast_interpretation.md`: takes parsed hits, returns a 2–3 sentence summary + per-term explanations (E-value, bit score, % identity) *in context of this specific result*. System instruction bakes in the "faithful execution, not 100% accuracy" framing from the PRD.
- New step `interpreting` → result stored in `job_steps.result_json`
- Frontend: AI Summary component, "What does this mean?" expandables wired to the AI response

### Day 12 — Guest → Account Flow
- Banner component (appflow §3.5/3.6)
- Sign-up modal → Supabase `linkIdentity` upgrade
- Post-conversion redirect handling

### Day 13 — Dashboard
- `GET /jobs?user_id=`
- Dashboard page — job cards, empty state, click-through

### Day 14 — Landing Page Polish
- Full design system applied
- Sequence typewriter hero animation
- CTA wiring

### Day 15 — Error States & Edge Cases
- Invalid sequence input messaging
- NCBI timeout/failure → `failed` status + retry
- Zero significant hits → its own AI framing ("no strong matches — here's what that can mean")
- Rate-limit queueing if multiple jobs fire close together

### Day 16 — Deploy
- Frontend → Vercel, Backend → Railway or Render
- Env vars wired per techspec.md
- Full flow test on deployed URLs

### Day 17 — Demo Prep + Buffer
- Finalize 2–3 demo sequences with rich, interesting hits; pre-run and cache them
- Fix whatever broke on Day 16

### Day 18 — Demo Day
- Final run-through with cached demo-mode results as backup
- Buffer only — no new features

---

## Track B — Phase 1 Full Build (post-prototype, ~10–12 weeks)

### Sprint 1–2: Pairwise Alignment + Pipeline Chaining Foundation
- Add Clustal Omega pairwise alignment as the second live operation
- Implement `parent_job_id` chaining (schema already supports this)
- Operation grid: two live cards

### Sprint 3–4: UniProt + PDB
- UniProt annotation lookup
- PDB structure fetch + Mol* 3D viewer
- Chain: "from this BLAST hit → fetch structure"

### Sprint 5–6: MSA + Phylogenetic Tree
- Clustal Omega multi-sequence alignment
- Basic tree construction + visualization
- Completes the BLAST → shortlist → MSA → tree workflow from your syllabus mapping

### Sprint 7: Pathway Integration
- Gene/protein → pathway lookup via Reactome/WikiPathways
- Pathway diagram viewer

### Sprint 8: Onboarding + `/learn`
- First-run tutorial
- Documentation pages generated from existing "what does this mean" content — write once, reuse

### Sprint 9–10: Hardening
- PDF report export
- Cache-hit check before re-calling external APIs (raw responses already stored from Day 1)
- Error monitoring (Sentry free tier)

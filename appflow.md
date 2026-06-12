# appflow.md — BioFlow AI Application Flow

## 1. Two Tracks
- **Prototype Track (Days 1–18):** one golden path — Sequence In → BLAST → AI-interpreted report.
- **Full Build Track:** additional operations, pipeline chaining, learning section, projects.

## 2. Sitemap (Prototype)
/                    Landing

/analyze             Wizard — Step 1: Choose Operation

/analyze/blast       Wizard — Step 2 & 3: Input + Confirm

/jobs/[id]           Processing → Results (shareable, persistent)

/dashboard           Job history (guest + authed)

/auth/*              Sign-up / sign-in (triggered from guest banner)

## 3. Screen-by-Screen

### 3.1 Landing (`/`)
- Hero with a live "typewriter" sequence animation (see design.md §6).
- Single CTA: **Analyze a Sequence** → `/analyze`. No login wall.

### 3.2 Wizard Step 1 — Choose Operation (`/analyze`)
- Grid of operation cards. For the prototype, **BLAST Search** is the only active card.
- All others (UniProt lookup, MSA, Structure lookup, Pathway lookup) render with a "Coming in Phase 1" badge — this doubles as your operation catalog and a roadmap teaser for the demo.
- State: `selectedOperation: 'blast' | null`

### 3.3 Wizard Step 2 — Provide Input (`/analyze/blast`)
- Two tabs:
  - **Paste Sequence** — textarea, client-side FASTA validation, auto-detects nucleotide vs. protein (composition heuristic).
  - **Fetch by Accession** — text input → backend calls NCBI `efetch` → returns sequence + metadata for the user to confirm before proceeding.
- Database/program auto-suggested from detected type (`blastp`/`nr` for protein, `blastn`/`nt` for nucleotide), with an **Advanced** disclosure for manual override.
- State: `inputMode`, `rawInput`, `detectedType`, `advancedParams`

### 3.4 Wizard Step 3 — Confirm & Run
- Plain-English summary card: *"We'll run a blastp search of your 142-aa protein against the nr database."*
- **Run Analysis** → `POST /jobs` (status: `queued`) → redirect to `/jobs/[id]`.

### 3.5 Job Page — Processing State (`/jobs/[id]`)
- Polls `GET /jobs/{id}` every 3s.
- Step states: `queued` → `submitted_to_ncbi` → `polling_ncbi` → `parsing` → `interpreting` → `complete` | `failed`.
- Each state has friendly copy + expectation-setting: *"Usually 30s–3min depending on NCBI load."*
- **This page is the persistence guarantee**: closing the tab and returning to the same URL later shows the saved result — no "session expired" dead end.
- Guest banner: *"This result is saved for 24 hours. Create a free account to keep it forever."*

### 3.6 Job Page — Results State
1. **AI Summary** (always visible, top) — 2–3 sentence plain-English overview.
2. **Top Hits Table** — accession, description, % identity, E-value, bit score; rows expandable.
3. **Visual Score Bar** — top 10 hits, color-coded by confidence band (design.md §2.4).
4. **Alignment View** — monospace, matched regions highlighted, for the top hit.
5. **"What does this mean?" expandables** next to E-value / bit score / % identity — contextual instruction, not a separate manual.
6. **Export** — "Copy as report" now; PDF export in Phase 1.

### 3.7 Guest → Account Conversion
- Triggered from the banner (3.5/3.6) or "Save to Dashboard."
- Implementation: Supabase anonymous auth (already active from first visit) → upgrade via `linkIdentity` when the user adds email/password. Same `user_id`, zero data migration.
- Post-conversion: redirect back to the same `/jobs/[id]`, banner disappears permanently.

### 3.8 Dashboard (`/dashboard`)
- Job cards: operation type, input snippet, status, date → click through to `/jobs/[id]`.
- Empty state: *"Run your first analysis"* → `/analyze`.

## 4. Job Lifecycle (drives 3.5 + 3.8)

| Step status         | User-facing label                          | Typical duration |
|----------------------|---------------------------------------------|-------------------|
| `queued`             | "Queued"                                     | < 1s |
| `submitted_to_ncbi`  | "Submitted to NCBI BLAST"                    | instant |
| `polling_ncbi`       | "NCBI is searching — this can take a minute" | 30s–5min |
| `parsing`            | "Reading results"                            | < 5s |
| `interpreting`       | "Writing your explanation"                   | 5–15s |
| `complete`           | results render                               | — |
| `failed`             | error state + retry button                   | — |

## 5. Full Build Additions (not in prototype)
- Operation catalog expands: UniProt annotation, PDB structure + Mol* 3D viewer, pairwise alignment, Clustal Omega MSA, Reactome/WikiPathways lookup.
- **Pipeline chaining**: Wizard Step 1 gains "I want to do multiple things" → builds a step sequence (BLAST → top hit → MSA → tree), each step a `job_steps` row linked via `parent_job_id`.
- `/learn` documentation section (generated from the same explanation content used in §3.6.5 — write once, reuse).
- Onboarding tutorial (first-run modal series).
- "Projects" — group related jobs.
- `/settings`.

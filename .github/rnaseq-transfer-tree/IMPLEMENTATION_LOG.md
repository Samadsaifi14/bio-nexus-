# Bio Nexus — Implementation Log

> Sprint-by-sprint build history. This file answers "what shipped and when."
> For *why* Bio Nexus exists and how it's architected, see `MASTER_PLAN.md`.
> For coding conventions, see `RULES.md`. For the job worker, see `durable-worker-design.md`. For the DB, see `schema.md`.

**Last Updated:** August 2026

---

## Track A — Prototype Sprint (18 days) ✅

Goal: one golden path — sequence in → BLAST → AI-interpreted report. Everything else deferred to Track B.

- Day 0: repo/infra pre-flight (Supabase project, storage bucket, API keys, NCBI access confirmed)
- Days 1–2: job CRUD spine (FastAPI + Next.js scaffolds, dummy data)
- Days 3–4: NCBI BLAST integration, demo-mode fallback for slow/queued searches
- Day 5: sequence input + validation, wizard shell
- Days 6–7: wizard → job creation → live processing screen (first end-to-end run)
- Days 8–9: raw results rendering (hits table, alignment view, no AI yet)
- Days 10–11: AI interpretation layer (Gemini), hedged-language prompt template
- Day 12: guest → account upgrade flow
- Day 13: dashboard (job list)
- Day 14: landing page polish
- Day 15: error states (invalid input, NCBI timeout, zero hits, rate-limit queueing)
- Day 16: deploy (Vercel + Railway/Render)
- Day 17: demo prep, cached demo sequences as backup
- Day 18: demo day

## Track B — Full Build (post-prototype)

| Sprint | Scope | Status |
|---|---|---|
| 1–2 | Pairwise alignment, `parent_job_id` pipeline chaining | ✅ |
| 3–4 | UniProt annotation, PDB structure fetch + 3Dmol.js viewer | ✅ |
| 5–6 | Multi-method MSA (ClustalOmega/MUSCLE/Kalign/MAFFT/T-Coffee), phylogenetic tree (NJ/UPGMA/ML) | ✅ |
| 7 | Pathway lookup (Reactome/WikiPathways) + diagram viewer | ✅ |
| 8 | Onboarding tutorial + `/learn` docs (10+ pages, glossary, inline help) | ✅ |
| 9–10 | PDF/JSON export, cache-hit tracking, Sentry monitoring | ✅ |
| 11 | Pipeline v2 engine (8-step BLAST→UniProt→MSA→Phylo→Domains→Pathway→AlphaFold→AI), pairwise/domain/structure depth | ✅ |
| 12 | Drug discovery compute: AutoDock Vina docking, MD simulation, ADMET, function prediction, protein interactions | ✅ |
| 13 | Sequencing MVP: FASTQ QC → trimming → assembly/consensus → variant calling → annotation (SARS-CoV-2 reference) | ✅ |
| 14 | Reliability: AI fallback chain (Groq→Gemini→Ollama), share links for all job types, wizard job persistence | ✅ |
| 15 | Design system v4.0: dark-only OLED theme, semantic tokens, Geist/Phosphor, landing rebuild | ✅ |

## Platform Hardening (ongoing, not tied to a single sprint)

- API key system (`sk_bio_` prefix, SHA-256 hashed)
- Share links (token-based, all job types)
- Guest → account upgrade via `linkIdentity`
- Enhanced dashboard/jobs/settings UI
- Durable job worker (see `durable-worker-design.md`) — replaced in-request job execution for docking/MD/function-predict/sequencing/pipeline

## Tool Verification Audit (Aug 2026)

Live audit of the four 🔴 tools from `FEATURE_VERIFICATION_CHECKLIST.md`; every fix is a `fix(...)` commit.

- `fix(pathways)` `bde6aea` — Pathway enrichment no longer depends on the Reactome `/token/{token}/pathways` endpoint (which 404s on the URL-encoded token). Reads the `pathways` array directly from the projection response, parses species, and surfaces `geneRatio` + per-pathway p-value to the UI and TSV export. Live-verified: 20 pathways for the TP53 gene set.
- `fix(interactions)` `d2ea003` — STRING-DB viewer upgraded: evidence-type filter (experimental / database / co-expression / text-mining, threshold 0.3), JSON export alongside PNG/TSV, and LearnPopover tooltips on the combined + evidence score headers linking to `learn/interactions`. Backend endpoint live-verified (TP53 → 5 partners).

## Structure Prep Hardening (Aug 2026) — pre-work for techspec.md §1–§3

All seven audit findings from `techspec.md` fixed; manifest rows added to `FEATURE_VERIFICATION_CHECKLIST.md` (Structure Prep / De Novo / Export / Page Capture sections).

- **A1** `fix(structure-prep)` — PyMOL cleanup now uses the importable open-source wheel (`pymol-open-source-whl`, provides the `pymol2` module — no binary, no X server) with a loudly-logged Biopython fallback. fpocket built from source (`Discngine/fpocket` v4.0.0, needs `libnetcdf-dev`) in both API Dockerfiles — it is *not* packaged in Debian repos (pool dir 404s). Note: spec's "pymol2 on PyPI" assumption corrected during implementation.
- **A2+A6** — new `backend/migrations/008_structure_prep_jobs.sql`: durable job table with `user_id` ownership + RLS (pattern-matched to ngs_jobs). Router persists state per step and scopes status reads to the owning user (`require_user_id`, matching every other job router).
- **A3** — broken chains that can't be repaired (no accession or no >80% template) proceed but are tagged `chain_integrity="broken_unrepaired"`; repaired runs get `"repaired"`; clean runs `"intact"`. ESMFold window-splicing deferred with reason in manifest.
- **A4** — PDB ID / UniProt accession (reuses `UNIPROT_RE` from identifier_resolution) / SMR template IDs validated by regex before any network call; sequence alphabet + 10–768 length checked at request time.
- **A5** — `swissmodel.expasy.org`, `cfold.bme.uic.edu`, `api-inference.huggingface.co` added to SSRF allowlist; every outbound call in `structure_prep.py` now routes through `validate_url()`.
- **A7** — CASTp polling timeout now sets explicit `castp_status: "timed_out"` (plus `skipped`/`running`/`complete`/`error`); fpocket gets a symmetric `fpocket_status` incl. `unavailable`.
- Tests: `test_structure_prep_validation.py` (25 cases) + existing identifier-resolution suite pass.

## De Novo Pipeline Branch — tier 6 (Aug 2026) — techspec.md §1

Unknown sequences that fail tiers 1–5 (no BLAST hit / resolution exhausted) now complete the pipeline as a first-class "de novo" run instead of erroring. Confidence tiers threaded through the whole context: `identified` (direct/xref/name) → `homolog` (sequence/idmapping similarity) → `de_novo`.

- **Backend** `feat(pipeline)` — `identifier_resolution.resolve_to_uniprot` returns an enriched result (`status`/`confidence`) and never `None`; `pipeline_v2._execute` branches at the BLAST step: zero-hit proteins set `denovo_mode`, mark blast complete with an explanatory note, and run `_run_denovo_steps()` instead of failing. Resolution-exhausted runs (hits exist, no accession) fall through to homolog-confidence gating: `_run_domains_or_denovo()` swaps InterProScan5 sequence-search for accession lookup; `_run_alphafold_or_esmfold()` swaps ESMFold HF API for the AlphaFold repository.
- **New service** `app/services/de_novo.py` — `interpro_sequence_search()` (EBI iprscan5 submit/poll/JSON → normalized domain shape), `esmfold_structure()` (predict + mean pLDDT from CA B-factors, alphafold-shaped card with inline `pdb_text`), `composition_stats()` + `function_hints()` (honest heuristic labeling). MSA/phylo/pathway steps are marked failed with "Unavailable for de novo sequences — no identified homolog" rather than silently empty.
- **Frontend** — new `ConfidenceBadge` (three states: cyan identified / amber homolog / dashed-purple de_novo), new `DeNovoPanel` (dashed-border composition + function-hints card replacing UniProt panel when the bundle carries `_de_novo`); job page renders de novo results where it previously showed a dead-end "No significant similarity found" card; `AlphaFoldViewer` gains a `pdbData` prop so inline ESMFold models render without a fetch (title: "Predicted structure (ESMFold)"); pathway card shows an explicit unavailable notice in de novo runs; docking button hidden when no receptor PDB URL exists.
- Tests: `test_de_novo_branch.py` (8 cases incl. pipeline-level zero-hit acceptance test with mocked EBI/ESMFold) — 63 backend tests green across the three touched suites; frontend `tsc --noEmit` + `next lint` clean.
- Pending live verification: real ESMFold/InterProScan E2E run; migration `008` application (pre-work §A2).

## Structure Export — techspec.md §2 (Aug 2026)

- **New router** `app/routers/structure_export.py` (`/api/structure-export`) — authenticated downloads keyed by UniProt accession (AlphaFold DB file pattern) or 4-char PDB ID (RCSB). Formats: `.pdb`, `.cif`, and a genuine PyMOL session `.pse` built server-side with the pymol-open-source wheel (cartoon + `spectrum b` pLDDT rainbow + transparent background pre-applied — no manual coloring, acceptance §2.5). Missing upstream models map to clean 404s; pymol2-less deployments get an explicit 503 instead of a broken file.
- **Honest-scoping rule honored (§2.3b)** — ChimeraX/VMD ship as the preferred coordinate format plus a client-generated command script (`.cxc` / `.tcl`), never fake session files. `.cxs`/VMD state exports remain documented exclusions.
- **Docking exports** — worker now persists `result_sdf` (docked poses) and `receptor_pdb`; new endpoints `GET /api/docking/result/{id}/complex.pdb` (receptor + docked ligand merged) and `/ligand.sdf`. Legacy rows pre-dating persistence return an actionable "re-run" message rather than junk.
- **Frontend** — new `StructureExportMenu.tsx` dropdown: PDB/mmCIF/PyMOL-session items on `AlphaFoldViewer`'s toolbar (hidden without an accession — de novo models export via the existing PDB button); Complex-PDB/Ligand-SDF items on the docking results page. Downloads go through the authed axios instance as blobs.
- Tests: `test_structure_export.py` (12 cases — routing, URL patterns, format gate, 404 mapping, empty-pymol-output guard).

## Page Capture + Final Synthesis — techspec.md §3 (Aug 2026)

- **New table** `migrations/009_page_captures.sql` — one row per external source queried during a run, keyed `(job_id, source)` with RLS; stores the human-facing page URL, title, extracted text sections, figure image URLs, and an honest `fetch_status` (`captured`/`failed`/`skipped`). Must be applied in Supabase SQL Editor.
- **New service** `app/services/page_capture.py` — stdlib-only HTML extraction (no new deps), per-host rate limiter (1.5 s minimum interval), every fetch through `ssrf.validate_url()` (§3.2: no new SSRF surface). Captures are strictly best-effort fire-and-forget; failures still record a row with `fetch_status="failed"` so coverage is auditable.
- **Wiring** — `pipeline_v2._finalize_context()` queues captures for NCBI top hit, UniProt entry, RCSB structure, InterPro entry, AlphaFold DB page, and Reactome pathway browser — derived from actual run results; de novo runs correctly record no annotation-source pages.
- **New service** `app/services/final_synthesis.py` — deterministic findings assembly from real step results, each tagged with the run's confidence tier (identified/homolog/de_novo) and source-tool page link, plus tier-appropriate caveats. An optional LLM pass polishes wording only (`_mode: llm_polished|deterministic`); it can never invent findings or block the pipeline.
- **Frontend** — new `FinalReport.tsx` panel rendered above the AI interpretation card on the job page: headline, summary, per-finding rows with confidence badges and source-page links, caveats footer.
- Tests: `test_page_capture_synthesis.py` (9 cases — extraction, failure-honesty, rate limiting, tier threading, de novo caveats, deterministic fallback). Suite total: 84 tests green across the five touched files.

## Open / Next

- Phase 3 depth: RNA-seq differential expression, larger file storage and compute
- Phase 4 (not started): lab workspaces, custom pipeline builder, institution licensing, public API access

---

*When a sprint or phase ships, add one row here — do not restate the shipped-feature list in `MASTER_PLAN.md`.*

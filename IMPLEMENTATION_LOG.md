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

## Open / Next

- Phase 3 depth: RNA-seq differential expression, larger file storage and compute
- Phase 4 (not started): lab workspaces, custom pipeline builder, institution licensing, public API access

---

*When a sprint or phase ships, add one row here — do not restate the shipped-feature list in `MASTER_PLAN.md`.*

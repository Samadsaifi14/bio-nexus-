# BioNexus User Guide

BioNexus runs interdisciplinary bioscience analysis: protein/sequence
annotation, phylogeny, structure (AlphaFold-style + experimental PDB), docking,
molecular dynamics, and NGS pipelines — each step recorded for provenance and
published into a reproducible artifact.

## Quick start

1. **Run an experiment** — POST a sequence to `/api/pipeline/v2/run` (or use the
   classic `/api/pipelines/{pipeline_id}/run` on a template). The pipeline
   persists a job with a full result context.
2. **Inspect the AI's work** — GET `/api/experiments/{job_id}/evidence`
   (evidence graph), `/api/experiments/{job_id}/ledger` (+ `/validate`) for the
   reproducibility ledger, and `/api/experiments/{job_id}/paper` for a
   journal-formatted manuscript.
3. **Recorded benchmarks** — `/api/benchmarks` lists the curated catalog;
   POST `/api/benchmarks/{benchmark_id}/runs/{job_id}` compares a stored result
   against ground truth (metrics + tolerance).
4. **Figures & export** — GET `/api/figures/{job_id}` (publication SVG),
   `/api/figure/formats` for the format matrix. Engines export JSON/CSV via
   `/api/engines/{name}/result`.
5. **Scientific dashboard** — `/api/dashboard/summary`, `/api/dashboard/engines`,
   `/api/dashboard/datasets` (catalog + your uploads), `/api/dashboard/runs`.
   Upload your own dataset via `/api/dashboard/upload_data`, then snapshot it
   into an engine workspace with `/api/datasets/{name}/snapshot`.

## Engines

Twelve registered engines (`GET /api/engines`): blast, uniprot, msa, phylo,
domains, alphafold, pathway, interpret, evidence, ngs, docking, md. Each
implements `parse → validate → export → figure` and a competing-quality claim.

## Reproducibility ledger

Every recorded operation is a carbon: input digest → process → output digest,
chained by sha256. `ledger/validate` never passes an empty chain, a broken hash
link, or a step that dropped its input or output.

## Deployment notes

- Data is truer when seeds are migrated to latest. Apply `supabase/migrations/`
  in order (009, 010) to the live Supabase project; benchmark seeding degrades
  gracefully (`omit_depth`) until 010 is applied.
- The API deploys to a Hugging Face Space; figures are dependency-free SVG.
- Run `python scripts/ci_validate.py` and `python -m pytest` before pushing.
# BioNexus codebase map

This map was checked against the GitHub main branch on 2026-10-10. It describes the source paths to inspect first; it does not certify that every listed capability is production-validated. Use the validation registry, feature checklist, tests, and live outputs for that.

## Product areas and entry points

| Product area | Frontend surface | Backend path |
| --- | --- | --- |
| Sequence retrieval, BLAST, alignment, MSA, phylogeny, primers, sequence utilities | bioai-platform/frontend/src/app/(dashboard)/analyze/{blast,alignment,pairwise,phylo,primers,sequences}/page.tsx and related results components | bioai-platform/backend/app/routers/, app/engines/{blast,msa,phylo}_engine.py, app/integrations/ncbi/, app/tools/ |
| Protein annotation, domains, UniProt, pathways, interactions | analyze/{domains,uniprot,pathway,interactions,function}/page.tsx and components/results/ | app/routers/{domains,uniprot,pathways,interactions,function_predict}.py, app/engines/{domains,pathway,uniprot}_engine.py, app/services/pathway_enrichment.py |
| Structures, structure preparation, docking, MD, ADMET | analyze/{structure,structure-prep,predict-structure,docking,md,md-v2,admet}/page.tsx and structure/docking result components | app/routers/{structures,structure_prep,structure_predict,docking,md,md_v2,admet}.py, app/engines/docking_engine.py, app/md/, app/tools/ |
| Sequencing and NGS | analyze/{sequencing,ngs,ngs-v2}/page.tsx and components/ngs/ | app/routers/{sequencing,ngs,ngs_v2}.py, app/ngs/, app/engines/ngs_engine.py |
| GEO counts and RNA-seq differential expression | the GEO search/results surfaces, components/results/RnaSeqExpressionWorkspace.tsx, and lib/rnaseqExpressionApi.ts | app/routers/{geo_search,rnaseq_expression,rnaseq_recovery,rnaseq_production}.py, app/rnaseq/, app/data/rnaseq/ |
| Pipelines, durable jobs, history, sharing, export, AI interpretation | analyze, wizard, jobs, history, results, report pages; components/pipeline/ and components/results/ | app/pipeline/, app/workers/, app/worker.py, app/services/{job_state,job_access,provenance,reproducibility,export}.py, app/ai/ |
| Scientific contracts, evidence, validation, benchmarks | results and benchmark surfaces; components/results/ScientificDataSurface.tsx and ProvenancePanel.tsx | app/science/, app/scientific/, app/services/evidence_policy.py, app/benchmarking/, app/routers/{scientific_validation,benchmarks,reproducibility}.py |

## Cross-cutting implementation layers

- Frontend pages live under bioai-platform/frontend/src/app/. Shared presentation and API clients are under src/components/, src/lib/, and src/types/.
- Backend HTTP entry points are registered in bioai-platform/backend/app/main.py; endpoint behavior is implemented in app/routers/.
- Scientific methods belong in app/engines/, app/tools/, app/ngs/, app/rnaseq/, app/md/, or app/engines/stats_engine.py according to the existing feature boundary. Avoid putting scientific calculations in routers or React components.
- Long-running work uses the job/pipeline/worker and storage layers. Inspect app/workers/, app/worker.py, app/services/job_state.py, app/services/artifact_storage.py, and the feature's router before adding a new execution path.
- ScientificResult and evidence semantics are defined in app/science/result.py, app/science/validation_registry.py, app/scientific/contract.py, and app/services/evidence_policy.py.
- Existing system-level checks include .github/workflows/backend-ci.yml, frontend-ci.yml, security.yml, scientific-integrity.yml, rnaseq-expression-ci.yml, rnaseq-real-data-benchmark.yml, bbs2-scientific-foundation.yml, and full-feature-audit.yml.

## Start a change

1. Find the corresponding page, API client, router, engine/service, and tests using this map.
2. Read RULES.md and the feature's checklist entry before changing behavior.
3. Trace the input and output through the API, worker, artifact storage, provenance, and frontend renderer.
4. Add or update focused tests that cover a real failure mode and the scientifically important boundaries.
5. Update documentation when a route, source of truth, or execution boundary moves.

Use Graft for local symbol and call-path lookup after its dry-run-reviewed setup. Keep this file concise and correct as architecture changes.

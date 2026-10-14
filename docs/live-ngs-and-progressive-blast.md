# Live NGS example and early BLAST results

## Delivered behavior

- RNA-seq opens with GSE336901 preloaded. Run live example selects the published `GSE336901_Fig3_FFPE_raw_counts_matrix_GEO.csv.gz` supplement, checks current GEO metadata and input hashes, then requests a fresh durable full-analysis job.
- The live example requires dedicated expression-worker readiness. It fails explicitly when the worker is unavailable; ordinary GEO submissions retain the existing hosted-R fallback.
- R emits stage-start and stage-completion events. The owner-scoped job endpoint returns complete validated events from the current attempt only. The page refreshes actual progress every two seconds without simulated percentages.
- Completed RNA-seq results expose a continuation into existing enrichment recovery, retaining the differential-expression results and tested-gene background. GO, preranked GSEA and supplied pathway GMT collections remain subject to organism, identifier and annotation checks.
- Comprehensive protein BLAST jobs publish the completed search context before downstream annotation, MSA, domains, pathways and structure analysis. The active job page renders the real hit table while downstream work continues. Final artifact hydration replaces the preview, so final evidence is not hidden by an older search snapshot.
- Fixed the legacy results redirect to await Next.js route parameters.

## Verification

54 targeted Python tests passed, covering automatic GEO preparation/submission, queue recovery/ownership, expression contracts, BLAST semantics and new progress/preview regressions. TypeScript and the production webpack build passed with telemetry disabled.

Executed the modified R engine on the bundled 221-gene SALS regression fixture, retaining all 18 samples. It tested 198 genes and emitted starts for all ten stages, completions for stages 1–9, and an unavailable event for enrichment because the extracted local runtime lacks GO annotations. This verifies real engine events and computed artifacts, not a fresh full GSE336901 deployment run.

## Deployment requirements and limits

The API and expression worker need the same persistent `BIONEXUS_EXPRESSION_ROOT`, compatible R/DESeq2 versions, private artifact storage credentials, annotation packages and an active worker heartbeat. The existing `Dockerfile.rnaseq` defines the dedicated worker. A frontend deployment alone does not provision it.

Provider queue time remains external to BioNexus. Early BLAST display removes waiting for downstream analyses; it cannot promise instantaneous NCBI/EBI search completion. No database narrowing, fabricated hits, cached demo results or simulated progress were introduced.

Live authenticated end-to-end execution and deployment of this commit must be checked separately. The GitHub main push triggers the existing deployment workflow; a triggered workflow is not proof of successful rollout.

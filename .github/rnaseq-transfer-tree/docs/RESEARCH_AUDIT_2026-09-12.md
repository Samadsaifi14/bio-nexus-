# BioNexus publication-focused technical and scientific audit

**Audit date:** 2026-09-12  
**Audited branch baseline:** `main` at `112bf4cfb8535823c5eee5b7a973f27aca377563`  
**Hardening branch:** `audit/research-hardening-2026-09-12`  
**Production UI:** `https://bio-nexus-ebon.vercel.app/`

## Scope and evidence boundary

This audit reviewed the executable BioNexus frontend/backend structure, NGS production and exploratory code paths, workflow/provenance tests, deployment metadata, benchmark assets, security-sensitive request handling, and the scientific claim boundary needed for a publishable software paper. It also incorporated recent public user/maintainer feedback from Galaxy about large-data transfer, queue-state ambiguity, and late workflow validation.

This is a **software and scientific-method audit**, not independent wet-lab validation. A passing unit test, schema check, synthetic fixture, successful deployment, or AI grounding check does **not** prove biological accuracy. The paper must distinguish:

1. deterministic computation;
2. reference retrieval;
3. evidence-backed inference;
4. heuristic/surrogate evidence;
5. AI-generated interpretation;
6. experimental observation;
7. benchmark result; and
8. unsupported/insufficient evidence.

## Executive assessment

BioNexus already contains a stronger scientific spine than its older product copy suggests: experiment/provenance services, evidence classification, benchmark protocols, deterministic tool adapters, result-integrity checks, and durable NGS execution adapters exist in the repository. The largest publication risk was **inconsistency between implementation, UI language and provenance**, especially in NGS. The hardening branch therefore prioritizes claim correctness before cosmetic expansion.

The current project is appropriate for a **bioinformatics software/platform paper** if the manuscript states exactly what is implemented and reports measured benchmark results only where a completed benchmark artifact exists. It is **not yet defensible** to claim equivalence or superiority to Galaxy, nf-core/Sarek, nf-core/rnaseq, GIAB, or clinical-grade pipelines as a whole.

## Critical findings and actions

| Area | Finding | Risk to users / paper | Hardening action |
|---|---|---|---|
| Rate limiting | Request identity was derived by base64-decoding an unverified JWT payload. | Forged `sub` values could evade per-user quotas; unsafe to describe as authenticated rate limiting. | Replaced with network-source limiting until a verified-principal middleware is used. |
| NGS local input | Exploratory endpoint accepted arbitrary server-local file paths. | Authenticated or anonymous callers could probe readable filesystem paths; parse errors could reveal paths. | Local FASTQ use now requires authentication and resolution beneath `NGS_INPUT_ROOT`; remote URL ingestion is rejected rather than implied. |
| NGS assay routing | Unknown assays defaulted to WGS; Amplicon was offered in UI although its production-quality path was not implemented. | Silent scientific misrouting. | Unknown/unsupported assays now fail closed; Amplicon removed from the active preview selector until a real contract exists. |
| NGS production UI | UI described WGS/WES as “PLAN ONLY” although durable local/SLURM/AWS Batch execution code exists. | Paper/UI contradicted backend capability. | Rebuilt NGS entry page around three explicit lanes: production WGS/WES, production RNA-seq, exploratory preview. |
| RNA-seq provenance | Shared executor persisted RNA-seq submissions as `nf-core/sarek 3.10.0`. | Incorrect workflow identity in reproducibility records. | `submit_run()` now requires/stores explicit workflow and revision. |
| RNA-seq artifacts | Shared artifact importer expected small-variant/identity evidence for RNA-seq. | Successful transcriptomics runs could be classified as incomplete for irrelevant files. | Artifact contracts are now workflow-specific: execution/FastQC/MultiQC/alignment/quantification/expression-QC/provenance for RNA-seq. |
| Public diagnostics | `/health` returned cache, queue and runtime/platform detail. | Unnecessary infrastructure reconnaissance surface. | Public health response reduced to liveness/version only. |
| Autonomous paper generation | Continuous paper daemon was enabled by default. | Surprising background compute and mutation of scientific artifacts. | Changed to explicit opt-in. |
| CORS | Trusted origins were duplicated/hard-coded and did not consistently reflect the deployed domain. | Configuration drift. | Added exact comma-separated `CORS_ORIGINS`; canonical production domain included. |
| CI | Existing backend CI did not gate NGS execution/provenance security tests; no dedicated frontend build workflow existed. | Regressions could merge without scientific or type/build validation. | Added NGS production/security suites to backend CI and created frontend lint/build CI. |

## NGS redesign

### 1. Production WGS/WES lane

The production genomics lane validates and, when compute is configured, submits a **real pinned `nf-core/sarek 3.10.0`** workflow through a non-shell argv contract. Supported execution adapters are:

- local durable worker;
- SLURM; and
- AWS Batch.

The UI now reports executor capability dynamically. It never substitutes the exploratory Python preview when production compute is unavailable. A submitted run preserves workflow, revision, executor, executor job ID, output location, timestamps and a SHA-256 hash of the launch argv.

The software clinical gate remains deliberately fail-closed. Passing the gate means only that the recorded evidence package satisfies BioNexus software policy; it does not establish laboratory validation, accreditation or clinical authorization.

### 2. Production RNA-seq lane

BioNexus now exposes the existing pinned **`nf-core/rnaseq 3.26.0`** planner/executor in the NGS user interface rather than leaving it as backend-only capability. The lane exposes:

- reference selection;
- strandedness;
- alignment/quantification strategy;
- trimming policy;
- local/SLURM/AWS Batch execution profile;
- exact launch command;
- observed output-group inventory; and
- a clear separation between base RNA-seq processing and downstream differential-expression inference.

The UI states that raw integer counts are the inferential input for DESeq2/edgeR-style testing, while TPM-like abundance measures are descriptive. PCA/sample-distance QC, recorded experimental design, contrasts and multiple-testing correction must precede DEG claims.

### 3. Exploratory evidence preview

The preview remains useful for teaching, interface testing and deterministic functional controls, but it is now framed as a different evidence class:

- synthetic demonstrations are explicitly labelled;
- server-local FASTQ input is sandboxed and authenticated;
- a per-file 2,000-record cap is disclosed;
- truncated input is labelled `SAMPLED_PREVIEW`;
- unsupported/unknown assays fail closed;
- missing evidence remains missing/unevaluated rather than being converted to zero; and
- no preview result is promoted to a production claim.

The compact synthetic control currently demonstrates **narrow workflow-output portability**, not biological validation. Its one known heterozygous SNP produced the same normalized output in the recorded BioNexus direct and Nextflow runs; the Galaxy wrapper command produced the same table without a completed Galaxy server run. This result must not be generalized to Sarek/Galaxy pipeline parity.

## RNA-seq design requirements incorporated from supplied teaching material

The supplied RNA-seq lectures/practical material reinforces the following product rules, all of which should be represented in either the execution contract or the downstream result workspace:

- biological replication and experimental design are first-class metadata;
- confounding/batch variables must be recorded before model fitting;
- read-level QC and post-trimming QC are distinct evidence stages;
- strandedness must be explicit or inferred and then verified;
- alignment/quantification and gene-level counts must preserve software/reference versions;
- count normalization is for making samples comparable, not for creating biological replication;
- differential expression should report effect size and adjusted significance, not p-values alone;
- PCA/sample-distance views are required for sample-level QC;
- volcano and heatmap views are secondary visualizations of a defined statistical contrast, not substitutes for a statistical model;
- multiple-testing correction/FDR is mandatory for DEG reporting; and
- compute placement matters: large genomics should run where the data resides, with durable HPC/cloud execution rather than browser-request lifetimes.

## User-feedback-driven architecture decisions

Recent Galaxy community reports provide concrete evidence for several design choices:

1. **Large FASTQ transfer is a product problem, not only a bandwidth problem.** Public users reported 38 GB and 180 GB upload difficulty. BioNexus production contracts therefore reference staged data and durable storage rather than pretending multi-hundred-GB browser upload is the optimal path.
2. **Queue state needs semantic clarity.** Users commonly interpret “queued/scheduled/running” incorrectly. BioNexus uses explicit `SUBMITTED`, `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, and `UNKNOWN` states and keeps executor identifiers visible.
3. **Validate before expensive execution.** Galaxy maintainers have explicitly identified schema-aware workflow validation as necessary to catch invalid workflow state before consuming resources. BioNexus production planners therefore return blockers/warnings and an exact launch contract before submission.
4. **Do not overload one giant workflow screen.** Large workflow run pages can become slow and cognitively dense. BioNexus now starts with a scientific question/execution lane and uses progressive disclosure for exact command/provenance detail.

These are design inputs, not claims that BioNexus is “better than Galaxy.” Any comparative paper result must use matched workloads and measured outcomes.

## Cross-feature publication-readiness matrix

| Feature family | Current implementation evidence | Publication-safe claim | Main remaining validation |
|---|---|---|---|
| BLAST | EBI/NCBI provider adapters, normalization, resilience tests, benchmark fixtures | BioNexus orchestrates similarity-search providers and normalizes evidence for one result workspace. | Re-run matched live queries and retain raw provider responses/checksums. |
| UniProt | REST retrieval/search adapters and tests | Reference retrieval with structured provenance. | Live E2E regression set across reviewed/unreviewed entries. |
| MSA | EBI methods plus explicit in-process fallback | Alignment orchestration with source/method disclosure. | Quantify fallback equivalence limits; never label different algorithms as identical. |
| Phylogeny | Tree generation/visualization plus tests | Reproducible tree construction for supported methods/inputs. | Method-specific truth/fixture comparisons and bootstrap validation. |
| Domains/motifs | InterPro/PROSITE-related adapters/tests | Structured domain/motif evidence retrieval/scanning. | Live E2E status still needs a retained benchmark artifact. |
| Primer design | Primer3 integration plus primer QC | Primer candidates with explicit thermodynamic/QC summaries. | Compare against a frozen Primer3 reference fixture and retain parameter snapshots. |
| Structure retrieval | RCSB PDB / AlphaFold DB-oriented retrieval | Retrieval and visualization of recorded structural models. | Keep “retrieved model” separate from de-novo prediction claims. |
| Docking | AutoDock Vina 1.2.7 path, run logs, docking analytics | Reproducible docking execution when the backend returns measured poses. | BBS-1 redocking fixture still has a ligand-SDF sanitization failure before RMSD; do not claim validated redocking accuracy yet. |
| MD | OpenMM-backed hosted path; explicit current implicit-solvent scope | Short hosted OpenMM simulation workflow for exploratory structural dynamics. | Benchmark energy/trajectory invariants and keep fallback paths from being presented as equivalent production MD. |
| ADMET | RDKit descriptor computation | Deterministic physicochemical/descriptive property calculation. | Do not call descriptors pharmacokinetic/clinical ADMET prediction without validated models. |
| NGS WGS/WES | Pinned Sarek planner + durable executors + provenance/artifact import | Production workflow orchestration when executor is configured; exploratory preview separately labelled. | Full matched HG002/other GIAB benchmark still required. |
| RNA-seq | Pinned nf-core/rnaseq planner + executors + workflow-specific artifacts | Production RNA-seq orchestration; downstream DEG remains a separate statistical analysis. | Add retained multi-sample benchmark with known design, DESeq2 output and QC figures. |
| AI interpretation | Grounding/claim-validation infrastructure | AI explanation is an interpretation layer over deterministic/reference evidence. | Report false-claim rejection performance on a fixed adversarial test set. |
| Provenance/evidence | experiment/evidence/benchmark services, checksums, CI | BioNexus records machine-readable provenance and classifies evidence. | Export/round-trip validation and DOI/archive workflow should be tested before claiming archival reproducibility. |

## Required benchmark program before strong manuscript claims

### Genomics

Use GIAB HG002 (and preferably additional GIAB genomes) with a fixed reference and confident-region BED. Run the same input/reference/regions through:

- BioNexus production Sarek execution;
- an independently invoked `nf-core/sarek 3.10.0` reference run; and
- a defined Galaxy workflow using equivalent tools/parameters where practical.

Evaluate each callset independently using a GA4GH-compatible benchmarking method. Report SNVs and indels separately, including TP/FP/FN, precision, recall, F1, genotype concordance/no-calls and stratified difficult-region results. Record input/reference/truth checksums, container digests, commands, hardware, runtime and software versions.

### RNA-seq

Use a public, well-annotated multi-replicate dataset with a declared experimental design. Retain raw reads or accession IDs, reference FASTA/GTF release, sample sheet, strandedness, workflow revision, counts and MultiQC output. Compare base-processing outputs at matched stages, then run a documented downstream differential-expression model. Report sample PCA/distances, library sizes, dispersion/MA diagnostics, adjusted p-values, effect sizes and the exact contrast.

### Other scientific engines

Promote each engine through the repository's maturity ladder only after a reproducible fixture is executable in CI or a retained live benchmark artifact is generated. External-provider tests should save source identifiers, query parameters, response hashes and timestamps so later database drift can be distinguished from code regressions.

## Remaining red flags before journal submission

1. **Full NGS biological benchmarking remains incomplete.** The compact synthetic control is not enough for an accuracy claim.
2. **Several external-provider tests are mocked/offline.** Mocked unit tests establish adapter behavior, not current provider correctness.
3. **README/product copy is older than the implementation.** It still describes a SARS-CoV-2 sequencing MVP and other historical states; it should be rewritten before publication.
4. **Deployment configuration must be checked against the new NGS executor flags and migration.** Code capability does not mean the current hosted backend has Nextflow/SLURM/AWS Batch infrastructure enabled.
5. **The `ngs_production_runs` migration must be applied with the new `command_sha256` column.** Local JSON fallback is useful for self-hosting but is not an acceptable sole durable record for a hosted paper benchmark.
6. **Clinical language must remain restricted.** “Software gate passed” is not “clinically validated.”
7. **Docking validation is incomplete.** The recorded BBS-1 1IEP redocking path currently fails before RMSD because ligand SDF sanitization fails.
8. **MD scope must remain explicit.** Current hosted workflow is implicit-solvent OpenMM; no explicit-solvent equivalence claim should appear.
9. **AI grounding is not independent scientific validation.** Deterministic/reference results remain authoritative.
10. **Comparative language must be metric-specific.** “Better,” “more accurate,” and “same or better” are prohibited unless a matched benchmark directly supports the named metric and stratum.

## Publication claim boundary

A defensible central claim for the current manuscript is:

> BioNexus is an evidence-aware bioinformatics orchestration and interpretation workspace that integrates heterogeneous sequence, structure, molecular-modelling and NGS workflows while making execution state, provenance, evidence class and unsupported claims explicit.

A claim that BioNexus is globally more accurate than Galaxy, Nextflow/nf-core, NCBI BLAST, or established specialist tools is **not supported** by the current evidence and should not appear in the manuscript.

## External design/validation sources used in this audit

- nf-core/sarek 3.10.0 documentation: https://nf-co.re/sarek/3.10.0/
- nf-core/rnaseq 3.26.0 documentation: https://nf-co.re/rnaseq/3.26.0
- Galaxy 2024 platform paper: https://doi.org/10.1093/nar/gkae410
- Nextflow paper: https://doi.org/10.1038/nbt.3820
- DESeq2: https://doi.org/10.1186/s13059-014-0550-8
- MultiQC: https://doi.org/10.1093/bioinformatics/btw354
- GA4GH/GIAB benchmarking best practices: https://doi.org/10.1038/s41587-019-0054-x
- NIST Genome in a Bottle: https://www.nist.gov/programs-projects/genome-bottle
- Galaxy large-file user report: https://help.galaxyproject.org/t/uploading-fastq-gz-is-very-slow/18315
- Galaxy queue-state user report: https://help.galaxyproject.org/t/jobs-queues-usegalaxy-eu-august-2026/18289
- Galaxy schema-aware workflow validation issue: https://github.com/galaxyproject/galaxy/issues/21971

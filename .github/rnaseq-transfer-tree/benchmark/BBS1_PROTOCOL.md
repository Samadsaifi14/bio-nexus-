# BioNexus Benchmark Suite 1 (BBS-1) — Protocol

Status: pre-results protocol
Branch: `research/bbs1-hardening`

## Purpose

BBS-1 is the pre-specified validation protocol for the BioNexus research release. It exists to prevent retrospective metric selection and unsupported performance claims. No manuscript result is considered reportable unless it is reproducible from an artifact under `benchmark/` and linked to the exact software commit and reference-tool version used to generate it.

## Scientific claim boundary

BBS-1 evaluates BioNexus as an integration and execution platform. It does **not** treat BioNexus as the inventor of BLAST, Primer3, InterPro, AutoDock Vina, RDKit, OpenMM, or other integrated methods. Module-level validation asks whether BioNexus preserves the relevant scientific inputs, parameters, outputs, provenance, and failure states of the reference implementation.

Words such as `validated`, `accurate`, `reproducible`, `production-ready`, `clinical`, or `equivalent` must not be used for a module unless the corresponding BBS-1 criterion has been met. Clinical claims are out of scope for BBS-1.

## Evidence classes

Every manuscript claim must be traceable to one of:

- `CODE`: directly established by inspected implementation.
- `BENCHMARK`: recomputable from BBS-1 raw/derived artifacts.
- `SOURCE`: supported by a cited external publication/database specification.
- `INFERENCE`: interpretation explicitly derived from CODE/BENCHMARK/SOURCE evidence.
- `LIMITATION`: an unvalidated, unavailable, restricted, or known-incomplete capability.

## Reproducibility requirements

Each benchmark run must record:

1. BioNexus git commit SHA.
2. Date/time in UTC.
3. Operating system/container image.
4. CPU, memory and GPU where relevant.
5. Reference-tool and database versions.
6. Complete non-secret run parameters.
7. Input identifiers plus checksums for local files.
8. Raw BioNexus output.
9. Raw reference output.
10. Comparison output and metric definitions.
11. Explicit pass/warn/fail decision.

External databases are versioned or timestamped where immutable releases are unavailable. Network/service failures are recorded as failures or unavailable observations; they are never converted into empty biological results.

## Benchmark strata

### A. Sequence and annotation

- Pairwise alignment: exact score/alignment consistency against the same Needleman-Wunsch/Smith-Waterman implementation and parameters.
- BLAST: top-hit/accession overlap and numerical-field preservation against the configured EMBL-EBI/NCBI endpoint using identical program/database settings where possible.
- MSA: method execution, sequence preservation, deterministic/repeatability checks, and alignment-column comparison where the same reference implementation is used.
- Primer design: primer sequence, product size, Tm and GC-content concordance against Primer3 using identical settings.
- UniProt/domain annotation: accession, term and coordinate agreement against timestamped UniProt/InterPro responses.
- Function inference: GO-term precision/recall against a frozen set of reviewed proteins, stratified by evidence source. Uncalibrated heuristic scores are not treated as probabilities.

### B. Evolution and pathways

- Phylogenetics: topology comparison using Robinson-Foulds distance when the same input alignment/model is comparable; export validity for Newick/SVG/PNG.
- Pathway enrichment: term-ID overlap, adjusted-significance values, input coverage and source provenance against direct Reactome/g:Profiler calls using the same identifiers. Different multiple-testing procedures are reported separately rather than numerically equated.

### C. Structure and drug discovery

- Structure retrieval/preparation: identifier integrity, chain-health reporting, repair state, provenance and export parseability.
- Docking: AutoDock Vina parameter preservation, deterministic repeat runs with fixed seed, score/log preservation, and redocking pose RMSD for curated co-crystal complexes.
- ADMET/descriptors: numerical equality/tolerance against the same RDKit version and documented descriptor definitions. BioNexus descriptor rules are not presented as experimentally validated pharmacokinetic predictions.
- MD: configuration validation, deterministic setup checks and physical-output sanity checks. Current implicit-solvent workflows are benchmarked only within their stated scope and are not compared as substitutes for production explicit-solvent protocols.

### D. Sequencing

Sequencing is evaluated per declared assay/reference profile. Truth-set benchmarking uses precision, recall and F1 for variant calls where a suitable truth set exists, plus QC/mapping/coverage concordance and stage completeness. Unsupported assay classes remain limitations rather than being generalized from a single profile.

Variant annotation is benchmarked separately against curated transcript examples and an external annotator on variants for which transcript/reference definitions can be matched exactly.

### E. AI interpretation

AI text is evaluated separately from deterministic analysis. Required metrics include:

- numeric claim fidelity;
- unsupported factual claim rate;
- identifier/provenance fidelity;
- omission rate for predefined critical findings;
- correct communication of WARN/FAIL/NOT_APPLICABLE states.

A generated explanation cannot alter deterministic results, thresholds or scientific status.

### F. Platform integration

For scripted end-to-end tasks record:

- task completion rate;
- wall-clock runtime;
- number of external services actually contacted;
- number of explicit user-level transitions required by BioNexus versus a predeclared manual reference workflow;
- number of intermediate file-format handoffs;
- completeness of provenance and export artifacts;
- repeatability across repeated runs where upstream services are unchanged.

Without a human-participant study, these are workflow metrics only; they do not justify claims that users find BioNexus easier, faster to learn, or more usable.

## Maturity gates

A module is `research-ready` only when all applicable gates pass:

1. Scientific method/source is named accurately.
2. Inputs and parameters are preserved and inspectable.
3. Output schema distinguishes measured/computed values from heuristic/inferred values.
4. Failure, timeout, fallback and NOT_APPLICABLE states are explicit.
5. Provenance and reference/database source are exposed.
6. Export preserves the values needed to reproduce the conclusion.
7. Unit/integration tests cover critical transformations and edge cases.
8. A reference benchmark exists and its metric is pre-specified.
9. Known limitations are documented.
10. UI wording does not imply stronger validation than the evidence supports.

## Initial hardening priorities

Based on the repository verification checklist, the first research-hardening tranche is:

1. Function prediction — remove probability-like uncalibrated confidence claims; expose evidence provenance; define GO benchmark; document EC-number scope until a defensible method is implemented.
2. Pathway enrichment — correct significance terminology, expose source/fallback status, and benchmark Reactome/g:Profiler outputs without conflating their correction procedures.
3. Sequencing annotation — fix strand/indel consequence edge cases, expose annotation source/transcript provenance, and build transcript-grounded unit/reference cases.
4. Docking/MD/ADMET — verify scientific outputs and exports against their underlying reference implementations and add benchmark fixtures where absent.
5. Structure preparation — complete live/container verification before claiming research readiness.

## Result embargo rule

The manuscript Results section remains empty until benchmark artifacts are generated from the frozen research release. Failed benchmarks are retained and reported; they are not deleted merely because a module is subsequently fixed. Pre-fix and post-fix results should be distinguishable by commit SHA.

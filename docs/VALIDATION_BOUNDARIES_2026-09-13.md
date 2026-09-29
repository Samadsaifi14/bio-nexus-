# BioNexus scientific validation boundaries and remediation status

Last reviewed: 2026-09-19

This document is a machine-implementation companion to the manuscript limitations. It distinguishes issues that can be fixed in software from scientific claims that require new external evidence. BioNexus must not turn an unavailable validation result into a positive claim by changing UI wording.

## 1. BBS-1 breadth

**Remediation:** a machine-readable validation-claims registry now states that BBS-1 evidence is module-specific and does not cover the complete supported input space. Platform-wide accuracy claims remain blocked until representative input strata, retained execution artifacts, reference outputs, failure states and regression evidence exist.

**Result:** benchmark coverage can expand without conflating `defined`, `executed`, `passed`, and `validated`.

## 2. Germline WGS/WES accuracy

The compact synthetic WGS control remains a functional/portability fixture only. It cannot establish production accuracy.

**Remediation:** `POST /api/benchmarks/germline/giab/plan` creates a formal non-synthetic truth-set evaluation plan. The planner requires:

- a query VCF and accepted non-synthetic truth VCF;
- a confident-region BED;
- an explicit reference FASTA;
- exact agreement between query and truth reference-build identifiers;
- hap.py as the haplotype-aware evaluator;
- optional GIAB stratification TSV input;
- retained SNP/INDEL TP, FP, FN, precision, recall and F1;
- genotype concordance, no-call counts and region denominators;
- checksums, evaluator/container provenance and retained logs/artifacts.

The planner emits a non-shell argument array and returns `PLANNED_NOT_EXECUTED`. `accuracy_claim_allowed` remains `false` until a completed report is retained. Synthetic truth-set identifiers and reference-build mismatches are rejected.

## 3. SALS RNA-seq full-study boundary

The bundled every-100th-gene matrix remains a 221-gene CI regression fixture. It is always labeled `CI_REGRESSION_ONLY` and can never support ALS biological claims.

A separate retained real-data benchmark now uses the official public GSE67196 processed count source for 8 healthy/control and 10 sporadic ALS cerebellum samples. Source preparation preserves 23,344 unique deposited GeneIDs before the declared DESeq2 prefilter. The retained condition-only `~condition` execution kept 16,995 genes and reported 6 genes meeting the predeclared adjusted-P and absolute-log2-fold-change thresholds. Source files, source mappings, design audit, normalized counts, complete and significant result tables, plot-source tables, figures, software versions and SHA-256 values are retained in the benchmark artifact and compact committed manifest.

The design matrix is full rank for the declared model, but the retained metadata records the experimental unit as `NOT_DECLARED`. Consequently this benchmark verifies reproducible execution and evidence correspondence for the declared statistical workflow; it does not establish an ALS biomarker, causal mechanism, clinical validity, or independence of biological replicates. Biological interpretation still requires study-design/covariate review and independent domain review.

## 4. Docking redocking validation

The recorded 1IEP ligand-SDF path is no longer the canonical BBS-1 redocking fixture because it failed during ligand sanitization before RMSD could be computed.

**Remediation:** the canonical fixture is now `BBS1-DOCK-1STP-BTN` (streptavidin-biotin, PDB 1STP). It extracts the crystallographic ligand directly from the PDB entry, converts the ligand through the same Open Babel/PDBQT preparation path used by the benchmark runner, runs AutoDock Vina with a fixed seed, and evaluates pose recovery against the crystallographic coordinates. The acceptance threshold is a predeclared heavy-atom RMSD of 2.0 Å.

The predeclared fixture was executed in GitHub Actions run `35389973834`. The retained best pose produced a symmetry-aware heavy-atom RMSD of **0.7252 Å**, below the predeclared **2.0 Å** threshold, using AutoDock Vina 1.2.7, seed 42, exhaustiveness 32 and 20 emitted poses. The retained workflow artifact has SHA-256 `7844d5f217a2c7105ca4c022a2b18667e2fc085dd10df2ee8fcb1db26fbacba2`.

This passes the canonical 1STP-biotin pose-recovery fixture only. It does not validate Vina affinity estimates, other receptor-ligand systems, clinical use, or general docking superiority. The threshold was not changed after observing the result.

## 5. Molecular dynamics scope

The hosted MD path remains implicit-solvent OpenMM. The API now exposes this as a machine-readable scientific scope and reports:

- `solvent_model=implicit`;
- explicit solvent unsupported by the hosted workflow;
- `equivalent_to_validated_explicit_solvent_production=false`.

The word `production` in an MD run mode refers to the production phase of this hosted implicit-solvent trajectory, not equivalence to a validated explicit-water production protocol.

## 6. AI grounding

BBS-2 numeric, citation and unsupported-claim checks remain useful evidence-fidelity controls.

**Remediation:** the public evaluation response now distinguishes `grounding_passed` from scientific validation and always reports `scientifically_validated=false` and `biological_truth_established=false`. Grounding establishes correspondence to supplied recorded evidence only.

## 7. Deployment availability

BioNexus exposes the web control plane, production compute worker and scientific artifact store as operationally distinct components through `GET /api/engines/deployment/components`.

The endpoint does not infer worker or artifact-store liveness from the web request. It reports configuration separately and leaves `end_to_end_available=null` until component-specific runtime probes exist. Therefore a live website can no longer be interpreted as evidence that every scientific production workflow is continuously executable.

## Claim policy after remediation

The codebase may accurately say that the validation **paths and claim controls are implemented**, that the declared GSE67196 statistical workflow has retained real-data execution evidence, and that the single predeclared 1STP-biotin redocking fixture passed its pose-RMSD acceptance criterion. It must not say that full GIAB germline accuracy, general docking accuracy or affinity prediction, explicit-solvent MD equivalence, ALS biological truth, or clinical validity have been demonstrated without the corresponding retained external evidence.

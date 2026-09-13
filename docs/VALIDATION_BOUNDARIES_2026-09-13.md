# BioNexus scientific validation boundaries and remediation status

Last reviewed: 2026-09-13

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

The authenticated DESeq2 upload path can process the complete matrix. When the emitted result contains the expected 22,085 genes, all 18 samples, healthy as reference and SALS as test level, the API classifies it as `FULL_SALS_STATISTICAL_EXECUTION`. Derived results, figures, checksums and provenance are retained in private per-user artifact storage.

Even a matching full-study execution returns `manuscript_claim_ready=false`. The remaining requirements are study-design/covariate review, QC review and independently reviewable biological interpretation. This prevents the software from converting statistical significance directly into biological truth.

## 4. Docking redocking validation

The recorded 1IEP ligand-SDF path is no longer the canonical BBS-1 redocking fixture because it failed during ligand sanitization before RMSD could be computed.

**Remediation:** the canonical fixture is now `BBS1-DOCK-1STP-BTN` (streptavidin-biotin, PDB 1STP). It extracts the crystallographic ligand directly from the PDB entry, converts the ligand through the same Open Babel/PDBQT preparation path used by the benchmark runner, runs AutoDock Vina with a fixed seed, and evaluates pose recovery against the crystallographic coordinates. The acceptance threshold is a predeclared heavy-atom RMSD of 2.0 Å.

The fixture state is `FIXTURE_READY_EXECUTION_EVIDENCE_REQUIRED`; it is not reported as passed until a retained execution artifact records the predicted pose and RMSD.

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

The codebase may accurately say that the validation **paths and claim controls are implemented**. It must not yet say that full GIAB germline accuracy, canonical docking pose recovery, explicit-solvent MD equivalence, or independent biological truth have been demonstrated unless the corresponding retained external evidence is produced.

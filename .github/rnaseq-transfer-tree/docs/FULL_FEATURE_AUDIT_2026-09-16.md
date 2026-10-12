# BioNexus full feature scientific audit — 2026-09-16

Status: **IN PROGRESS — audit branch only. Do not merge to `main` yet.**

Audit branch: `audit/full-feature-validation-2026-09-16`

Baseline `main` at audit start: `8111fb54c67833644e53ebb0036fe3bdce239968`

## Acceptance rule

A feature is marked PASS only when its implemented result is checked with deterministic known-answer fixtures and/or independently reproducible calculations, seeded randomized inputs exercise invariants and boundary conditions, malformed inputs fail without fabricated output, repeat runs are reproducible within a scientifically justified tolerance, and displayed/exported claims do not exceed the evidence produced by the implementation. Synthetic fixtures validate implementation only; they are not biological or clinical validation.

`NOT_EVALUATED` is retained where the required real-data or external-compute evidence has not actually been produced.

## Current ledger

| Feature / layer | Evidence exercised | Findings | Current status |
|---|---|---|---|
| Frontend lint + production build | GitHub Actions on isolated audit branch | Lint and production build completed successfully on multiple audit heads | PASS for build integrity; feature result rendering still audited per module |
| Retained benchmark JSON / claim-boundary static checks | Non-finite JSON scan; NGS/BBS boundary-marker checks | No NaN/Inf found in retained benchmark JSON examined by audit workflow; required synthetic/GIAB/integration boundary markers present | PASS for current static checks |
| Sequence utilities | Known-answer tests; 100 seeded random DNA + 100 seeded random RNA cases against Biopython; IUPAC and malformed alphabet cases | Found incorrect RNA U->T handling, incorrect multi-base nucleotide molecular-weight formula, incomplete IUPAC reverse complements, mixed T/U misclassification, and silent invalid-letter deletion. Fixes are on audit branch. | FIXED; final suite confirmation pending |
| Pairwise alignment | Existing known-answer tests; 75 seeded identical proteins in global/local modes; 40 randomized internal local matches; 75 random global invariant cases; invalid residues/gap rewards | Found local-alignment coordinates were relative to cropped alignment rather than original sequence. Added matrix-alphabet and gap-penalty validation. Fixes are on audit branch. | FIXED; final suite confirmation pending |
| ADMET / molecular descriptors | PubChem aspirin known-answer fixture; seeded valid/invalid SMILES; explicit RDKit descriptor conventions; claim-boundary checks | Found unsupported numerical LipE derived from QED and an unsupported ad-hoc LD50 formula. Both numerical claims are now withheld. HBA/rotatable-bond method conventions are made explicit; local PAINS/Brenk implementation is labelled as an incomplete screening subset rather than full validated prediction. | FIXED for identified claim defects; complete ADMET suite confirmation pending |
| BLAST | Existing comprehensive/program-matrix/resilience fixtures identified | Full random/known-answer audit not yet completed in this pass | IN PROGRESS |
| MSA / phylogeny | Existing endpoint and engine tests identified | Independent randomized taxon/alignment/tree audit not yet completed | NOT YET EVALUATED |
| UniProt / domains / interactions / protein properties | Existing tests identified | Live-reference versus deterministic-contract separation still required | NOT YET EVALUATED |
| Primer / CRISPR / Sanger | Existing tests identified | Known-answer and seeded boundary audit still required | NOT YET EVALUATED |
| Protein structure / structure prep / export | Existing structure tests identified | Chain/residue/geometry/output parity audit still required | NOT YET EVALUATED |
| Docking | Existing redocking workflow and pose analytics identified | Publication acceptance remains canonical redocking evidence; threshold will not be relaxed to force PASS | NOT_EVALUATED until retained benchmark passes |
| MD | Existing MD v2 / advanced-analysis / runtime tests identified | Current hosted workflow remains implicit-solvent OpenMM; plot/source parity and numerical audit still required | NOT YET EVALUATED |
| NGS exploratory / production planner | Synthetic truth fixture and production-boundary tests identified | Synthetic truth remains implementation evidence only | IN PROGRESS |
| GIAB HG002 truth evaluation | Real HG002 chr20 independent public query versus GIAB truth using hap.py harness | Evaluates real-callset truth harness only; query calls were not produced by BioNexus/Sarek | PASS for evaluator harness only; BioNexus production accuracy remains NOT_EVALUATED |
| RNA-seq expression | Full GSE67196 real-data benchmark plus existing contract tests | Real condition-only DESeq2 run retained separately; biological interpretation remains limited by available covariates/model | PASS for retained run execution; randomized/output-parity audit still in progress |
| Pathway enrichment / function prediction | Existing research-grade tests identified | Live-database drift and reference-version provenance still need explicit audit | NOT YET EVALUATED |
| AI grounding / evidence engine | Existing evidence/grounding tests identified | Grounding may establish correspondence to recorded evidence, not biological truth | NOT YET EVALUATED in this pass |
| Exports / reproducibility / provenance | Existing reproducibility and experiment-provenance tests identified | End-to-end source=table=plot=download parity audit still required | NOT YET EVALUATED |
| Security / malformed-input boundaries | Existing security-regression and fuzz tests identified | Existing fuzz suite currently permits HTTP 500 in several cases, so it is not sufficient as a crash-safety acceptance test and will be tightened | IN PROGRESS |

## Scientific claim boundaries retained during audit

- Deterministic/reference results remain authoritative over AI prose.
- Synthetic/randomized fixtures test implementation behavior only.
- Missing evidence is not converted into a negative biological finding.
- The HG002 chr20 independent-query fixture validates the truth-evaluation harness, not BioNexus/Sarek whole-genome accuracy.
- Production WGS/WES accuracy remains `NOT_EVALUATED` until an end-to-end production callset is actually generated and compared against an accepted GIAB truth set.
- Hosted MD is currently implicit-solvent OpenMM and is not represented as a validated explicit-solvent production protocol.
- Docking acceptance thresholds will not be weakened to make a failed redocking benchmark pass.
- Rule-based ADMET screening flags are not presented as validated QSAR predictions or experimental toxicity/pharmacokinetic measurements.

This document is updated as each module moves through the audit. A final PASS state requires all publication-scope modules either to pass their stated acceptance criteria or to remain explicitly outside the claim boundary as `NOT_EVALUATED`.

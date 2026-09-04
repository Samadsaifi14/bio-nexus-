# BioNexus publication-readiness plan

This document turns the manuscript audit into executable engineering requirements. It does **not** claim that BioNexus is accepted by, endorsed by, or ready for a Nature journal. Publication readiness is an evidence state, not a branding label.

## Claim boundary

BioNexus is an integration and scientific-result normalisation platform. Validation of one wrapped tool does not validate another tool, and exact integration parity is not equivalent to biological or clinical accuracy.

The words **accurate**, **validated**, **reproducible**, **production-ready**, **clinically valid**, **equivalent**, or **superior** must be tied to a named experiment, dataset, comparator and pre-specified criterion.

## Evidence upgrades implemented in this branch

1. **Expanded external concordance**
   - 20 chemically heterogeneous RDKit descriptor cases.
   - 10 reviewed UniProt accessions.
   - 5 RCSB PDB structures.
   - 3 known-sequence BLAST recovery cases.
   - 10 deterministic Primer3 templates.
   - independent Clustal Omega parity retained as an algorithm-level alignment check.
   - Runner: `run_reference_concordance_expanded.py`.

2. **Redocking chemistry repair**
   - 1IEP/STI coordinates remain those deposited in the co-crystal.
   - Ligand bond order is assigned from the RCSB Chemical Component Dictionary STI template before PDBQT preparation.
   - Pose RMSD remains the pre-specified endpoint; affinity remains separate.
   - Runner: `run_redocking.py`.

3. **NGS truth-set harness**
   - Can ingest GA4GH `hap.py` summary output for publication-grade germline benchmarking.
   - Provides SNP/INDEL precision, recall and F1 preservation from the external evaluator.
   - Includes a conservative exact-normalised-allele fallback only for software smoke tests.
   - The fallback is explicitly marked non-publication-grade.
   - Runner: `run_ngs_truthset.py`.

4. **AI factual-grounding metrics**
   - Numeric Claim Fidelity.
   - Structured Identifier Claim Fidelity.
   - Unsupported Structured Claim Rate.
   - UI blocks explanations that introduce unsupported numeric values or common structured biological identifiers.
   - Backend scorer: `app/benchmarking/ai_factuality.py`.
   - Corpus runner: `run_ai_factuality.py`.

5. **Objective workflow-fragmentation comparison**
   - Manifest-based action counting for the same pre-specified task across BioNexus and a comparator such as Galaxy.
   - Counts service switches, manual transfers, format conversions, parameter-entry steps, executions, exports and verification steps.
   - Every counted action requires evidence.
   - The runner refuses to call these measurements usability, cognitive load, productivity or preference.
   - Runner: `run_workflow_burden.py`.

6. **Continuous validation**
   - PR builds test the AI factuality scorer, syntax-check the publication benchmark runners and build the frontend.
   - Expanded network reference benchmarks and repaired redocking are available as manual evidence-generating CI jobs so transient external-service availability is not confused with deterministic software correctness.

## Evidence still required before a strong Nature-family submission

### A. Execute and freeze the expanded suite

A successful run must retain:
- exact commit SHA;
- UTC timestamp;
- dependency versions;
- raw reference outputs where licences permit;
- BioNexus outputs;
- machine-readable comparisons;
- failures and unavailable services;
- checksums for frozen inputs and outputs.

Do not replace failed cases post hoc. A repeat is a new run.

### B. Redocking series, not one complex

The repaired 1IEP experiment must first be executed. If it reaches RMSD calculation, expand to a pre-registered multi-complex redocking panel with:
- experimentally observed co-crystal pose;
- receptor and ligand identity;
- explicit protonation/preparation protocol;
- fixed Vina version, seed, exhaustiveness and search box;
- symmetry-aware heavy-atom RMSD;
- a pre-specified success threshold;
- affinity reported separately from pose recovery.

No docking accuracy claim is permitted until the multi-complex benchmark exists.

### C. Public NGS truth set

For germline WGS/WES claims use a supported, reference-matched GIAB/GA4GH case and evaluate within the corresponding high-confidence regions using `hap.py` or `vcfeval`. Report at minimum:
- SNP precision, recall, F1;
- INDEL precision, recall, F1;
- callable/evaluated region;
- reference build;
- pipeline/tool versions and commands;
- stratification by difficult regions when available.

If the current BioNexus sequencing implementation cannot process the selected truth-set workflow end-to-end, the manuscript must retain the current scope limitation instead of borrowing accuracy values from a different pipeline.

### D. AI factuality corpus

Freeze deterministic outputs first, then generate explanations. The corpus should cover multiple modules and include both ordinary and adversarial cases. Report the aggregate metrics from `run_ai_factuality.py` and retain every unsupported numeric or identifier claim.

Mechanistic/causal biological claims are not fully validated by the deterministic scorer and require source- or expert-based review.

### E. BioNexus vs comparator workflow burden

Use exactly the same task and start/end state for BioNexus and Galaxy (or another named comparator). Record each action with evidence. The manifest comparison may support claims about observable fragmentation or manual transfer counts only.

Claims that BioNexus is easier, faster to learn or preferred require a prospective human-participant usability study and appropriate ethics review where applicable.

### F. Release and archival requirements

Before submission:
- tag a release corresponding to the manuscript;
- archive the release and benchmark artifacts in a DOI-backed repository such as Zenodo;
- publish the benchmark manifests and machine-readable results;
- add a data/code availability statement that resolves to the frozen release;
- retain licence information for all redistributed fixtures;
- verify every manuscript number against its frozen artifact.

## Manuscript decision rule

A result may move from **LIMITATION** to **RESULT** only when a frozen artifact exists and its pre-specified criterion has been evaluated. A module may move from **integration tested** to **scientifically benchmarked** only when its external or truth-set comparison is complete.

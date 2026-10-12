# BioNexus Benchmark Suite 2 (BBS-2)

BBS-2 is the scientific validation contract for BioNexus. A benchmark is counted as **covered** only when it has a versioned input fixture, pinned reference or ground truth, an executable comparator, declared acceptance criteria, and a persisted run result. Merely defining an endpoint or demonstrating that a tool runs does not count as scientific validation.

## Status semantics

- `defined`: benchmark specification exists.
- `fixture-ready`: versioned input and expected output are committed with checksums.
- `executable`: BioNexus can run the benchmark end to end.
- `validated`: a recorded run satisfies the predeclared acceptance rule.
- `regression`: the benchmark is mandatory in CI and blocks release on failure.

No UI, manuscript, or README may translate `defined` or `executable` into `validated`.

## Domains

Sequence: pairwise alignment, BLAST, HMMER, PSI-BLAST, MSA, motif detection. Annotation: UniProt, InterPro, GO, Reactome, KEGG, Pfam. Structure: PDB retrieval, AlphaFold, DSSP, pocket detection, surface calculations. Docking: redocking, cross-docking, pose RMSD, pose clustering, binding affinity. Molecular dynamics: RMSD, RMSF, SASA, radius of gyration, PCA, DCCM, free-energy landscape. NGS: FASTQ QC, alignment, variant calling, annotation, RNA-seq, CNV, structural variants. AI: hallucination/unsupported-claim rate, numeric fidelity, citation fidelity, and biological correctness.

## Reproducibility requirements

Every benchmark run must record the BBS-2 benchmark ID and registry version, fixture checksum, expected-output checksum, BioNexus experiment ID, Git commit, software/container/database versions, random seed when applicable, wall time, hardware metadata, measured metrics, pass/fail decision, and exact acceptance rule. Where a comparator can vary by platform or floating-point backend, tolerance must be declared before execution.

## Ground truth policy

Ground truth must be externally defensible. Accepted sources include version-pinned curated databases, published challenge datasets, truth sets such as GIAB for germline variants, crystallographic ligand poses for docking redocking, experimental affinity data for ranking benchmarks, and expert-reviewed biological answer keys for AI correctness. Synthetic fixtures are allowed for deterministic regression tests but must be labelled synthetic and must not be presented as evidence of biological accuracy.

## AI benchmark policy

The audited AI mode has a hard failure condition for unsupported factual or numeric claims. Numeric fidelity is conservative: a generated number must appear in supplied deterministic evidence or in an explicitly recorded derived-computation node. Citation fidelity requires every generated identifier to resolve to a source supplied to the model. Biological correctness requires a separate curated answer key or expert review and cannot be inferred from citation presence alone.

## Release gate

A high-impact scientific release should publish the registry snapshot, fixture manifests, raw run outputs, aggregate metrics with sample sizes and confidence intervals where appropriate, and failed cases. Failed or unsupported benchmarks remain visible. This suite is intended to measure BioNexus, not advertise it.

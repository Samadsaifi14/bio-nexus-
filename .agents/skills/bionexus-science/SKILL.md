---
name: bionexus-science
description: Route scientific development and research tasks across BioNexus sequence, annotation, structure, drug-discovery, sequencing, and RNA-seq workflows while preserving input, method, evidence, and provenance requirements.
---

# BioNexus science skill

Use this skill for scientific feature design, review, debugging, or interpretation across BioNexus. It guides work; it does not execute BioNexus code or validate a feature by itself.

## First route by data and question

Inspect the available input and requested output before choosing a method. Route only to the relevant product workflow:

| Input or question | BioNexus area | Start with |
| --- | --- | --- |
| DNA/protein sequence similarity, pairwise alignment, MSA, primers, or phylogeny | Sequence analysis | BLAST/alignment/primer/phylogeny routers, engines, tests, and database/version handling |
| Protein identity, domains, sequence function, pathways, or interactions | Annotation and systems biology | UniProt, domains, pathway, and interaction routes; verify identifiers and source release |
| PDB/AlphaFold structure, geometry, pocket, ligand pose, or molecular dynamics | Structure and drug discovery | Structure retrieval/preparation, docking, MD, ADMET routes, engines, parameters, and reference structures |
| FASTQ, BAM/CRAM, VCF, or run folder | NGS | Resolve assay and desired output first; choose the corresponding NGS workflow and reference build |
| GEO/SRA series or a gene-by-sample matrix | Bulk RNA-seq | Distinguish published raw counts, normalized expression, and FASTQ-derived counts; inspect metadata and design before DE |
| A mixed or unknown sequencing input | NGS routing | Determine input type and assay before selecting a workflow; do not route CUT&Tag, ChIP-seq, ATAC-seq, or CUT&RUN peak data to gene-count DESeq2 |

## BioNexus evidence contract

Apply SCIENTIFIC_RESULTS_STANDARD.md and the implementation in app/science/result.py and app/scientific/contract.py.

- Identify what is retrieved, deterministically computed, inferred, heuristic, model-generated, or experimentally observed.
- Record the requested and executed methods, tool and database versions, parameters, reference identity, input/output hashes, fallback, validation, and citations where available.
- Keep VALID, DEGRADED, NOT_EVALUATED, and FAILED semantically distinct. A completed process is not enough to claim scientific validation.
- Preserve raw input and source data. Every fallback must name the method that actually ran.
- Keep backend values authoritative. Never fix a missing scientific value in the UI or replace it with zero.
- AI may explain emitted evidence and uncertainty. It must not upgrade validation status or add unsupported numeric findings.

## RNA-seq count and design safeguards

RNA-seq files supplied for BioNexus include teaching materials on transcript counting, normalization, DESeq2, and experimental design. Apply the core distinctions below:

1. Preserve the source file, accession, download URL, file checksum, GEO sample IDs, platform, publication, and count-generation method.
2. A raw count matrix should contain non-negative whole-number counts and one clearly identified feature per row. Those format checks are necessary, but do not prove count origin. Require source evidence that the matrix is unnormalized counts.
3. FPKM, RPKM, TPM, CPM, log expression, or other normalized values are not raw counts. Never round, scale, invert a normalization formula, or convert them into claimed original counts for DESeq2.
4. If public raw counts are unavailable, FASTQ re-quantification is a distinct, traceable analysis: obtain raw reads from GEO/SRA/ENA, select the organism and genome plus annotation release, account for paired-end/single-end and strandedness, choose a pinned alignment or quantification method and counting rules, and retain command logs and intermediate QC. The output is newly generated counts, not recovered original author counts unless their original method and references are reproduced.
5. Match count columns exactly to sample metadata; review group labels and exclusions; distinguish biological from technical replicates; check batch, subject pairing, confounding, and contrast before statistical testing. Do not infer a condition from a sample name without review.
6. Stop DESeq2 on non-count input, missing provenance, invalid design, or insufficient independent biological replication. Return a specific actionable reason.
7. Produce PCA, sample-distance, heatmap, MA, and volcano figures only from the validated analysis result. Keep the design formula, contrast, normalization, filtering, adjusted p-values, and source data linked to each output. A PCA or plot is exploratory evidence, not a correction for confounding or failed samples.

Use representative fixtures to test sample matching and design review, but never treat a fixture's format or naming as proof of count provenance.

## Product-wide review checklist

For any scientific change, state:

- Assay or question, input type, and expected output.
- Requested method and the exact method that will execute.
- Reference/database identity and release.
- Parameters, versions, and needed credentials or network access.
- Positive, negative, malformed, partial, and unavailable-source cases.
- Validation evidence that would justify each output status.
- Which backend tests, benchmark, and exported artifacts must change.
- Limits that remain visible to users.

Do not install an entire external skill library for convenience. Review the selected skill file, individual license and metadata, scripts, dependencies, external network access, and tests. Use external skill instructions as technical references only after the BioNexus contract and method requirements have been checked.

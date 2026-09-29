# GSE67196 real-data RNA-seq benchmark

This is the first **real experimental-data** publication benchmark for the BioNexus downstream RNA-seq statistical path. It is separate from the small deterministic CI regression fixture and is intended to generate retained, reviewable evidence.

## Source and cohort

- NCBI GEO: **GSE67196**
- BioProject: **PRJNA279249**
- SRA study: **SRP056477**
- Study: *Distinct brain transcriptome profiles in c9orf72-associated and sporadic ALS*
- PMID: **26192745**
- Organism: *Homo sapiens*
- Tissue: cerebellum
- Comparison: **10 sporadic ALS (sALS) versus 8 healthy/control samples**
- Official processed source: `GSE67196_Petrucelli2015_ALS_genes.rawcount.txt.gz`
- GEO records the original processing as hg19 alignment followed by gene-level counting with `htseq-count`.

The workflow downloads the official GEO count matrix and GEO family SOFT metadata during the run. It does not use simulated expression values and it does not substitute the 221-gene CI fixture.

## Reproducible preparation

`prepare_gse67196_sals.py` selects samples from GEO metadata by tissue and genotype and requires exactly 8 controls and 10 sALS cerebellum samples. It retains the original GSM accession, GEO title, deposited count-column name, genotype and tissue in `source_sample_mapping.tsv`.

The current official processed table contains **23,398 deposited source rows** and **23,344 unique deposited `GeneID` values**. Rows sharing the same deposited `GeneID` are summed sample-wise, with every contributing source row recorded in `source_gene_id_mapping.tsv`. In the selected 18-sample cohort, **2,294 unique genes have total count zero**. These rows are *not* silently removed in source preparation; all 23,344 unique GeneIDs are passed into the same declared DESeq2 prefilter used by the BioNexus application. This avoids forcing the official source into the 22,085-row teaching/CI matrix and keeps the public-source transformation explicit.

No normalization, imputation, fold-change selection, P-value selection or other outcome-dependent filtering is performed before the declared statistical workflow.

The workflow locks the current official GEO source files by SHA-256 so source drift becomes visible rather than silently changing the benchmark.

## Statistical contract

The benchmark calls the same BioNexus `deseq2_analysis.R` implementation used by the application:

- reference: `healthy`
- test: `SALS`
- prefilter: count >= 10 in at least 8 samples
- normalization: DESeq2 median-of-ratios
- sample QC: blind VST, PCA and sample-distance matrix
- inference: DESeq2 negative-binomial model
- reportable threshold: adjusted P < 0.05 and |log2 fold change| > 1
- expression heatmap: significant genes if >=2 exist; otherwise explicitly a top-variable-gene QC heatmap

Thresholds are declared before inspecting the result and are not changed merely to obtain a non-empty significant set.

## Retained evidence

`.github/workflows/rnaseq-real-data-benchmark.yml` retains:

- source-file SHA-256 values;
- exact sample and GeneID source mappings;
- R session information and execution-environment metadata;
- normalized counts and size factors;
- PCA coordinates and sample-distance matrix;
- complete and significant DESeq2 result tables;
- plot-source matrices/tables and analysis summary;
- PCA, distance, MA, volcano and expression-heatmap figures as SVG, PDF and 300-DPI PNG; and
- a final SHA-256 manifest over the retained evidence bundle.

## Latest retained execution

A successful full-study run was retained from GitHub Actions run
`35328958705` at commit
`eae16513b56044f11c39a60227cfe26ddbc13b64`. The workflow artifact is
`rnaseq-gse67196-sals-full-study` (artifact ID `10539549875`; ZIP SHA-256
`ce0fa52c75e0b5c40d7e5cc8c7d222fc03416d57f0a1ecf1db4405d9575a9cf0`).

The compact, reviewable record is committed as
`retained_run_manifest.json`. It locks source hashes, the statistical
contract, key output hashes and the design-audit state. The retained design is
full rank for the declared `~condition` model, but the experimental unit is
recorded as `NOT_DECLARED`; that limitation must remain visible in biological
interpretation.

GitHub workflow artifacts are retention-limited rather than persistent
archives. The manifest therefore records
`WORKFLOW_ARTIFACT_NOT_PERSISTENT_ARCHIVE`; a DOI-bearing archival deposit is
still required before final publication packaging.

## Claim boundary

This benchmark can support claims about reproducible processing of this declared public dataset and the behaviour of the BioNexus DESeq2 path. Biological interpretation still requires study-design review and independent domain interpretation. This benchmark does not by itself establish an ALS biomarker, causal biology, clinical validity, or platform-wide superiority.

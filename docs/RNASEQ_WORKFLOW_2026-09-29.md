# BioNexus RNA-seq counts workflow

The primary NGS page follows one runnable route: GEO Series search → source-linked supplementary matrix selection → validation of raw integer gene counts → explicit sample mapping and group review → R/DESeq2 → figures and exportable source tables.

The page does not present the unavailable nf-core worker as part of this route. FASTQ alignment/quantification is a different upstream analysis and must not be reported as executed by importing a published count matrix.

## GEO handoff

GEO SOFT Series and Sample records provide the supplementary file URLs, GSM identifiers, titles and recorded characteristics. BioNexus accepts bounded CSV/TSV files (optionally gzip compressed) hosted under NCBI's GEO Series path. It does not fetch an arbitrary caller-supplied URL. The parser retains the first gene identifier column, excludes named annotation fields such as `gene_symbol`, and rejects non-integer, missing, negative, duplicate or malformed counts. It rejects ambiguous sample matches and requires an explicit one-to-one mapping to GEO samples and a reviewed two-group contrast before fitting.

Preview includes the original source SHA-256. Analysis refetches the file and fails if that checksum changed, then writes a temporary gene-by-GSM TSV and metadata TSV for the existing R execution engine. The derived run provenance includes source URL, source SHA-256, original count columns and reviewed group assignments. Raw source and temporary converted files are not stored in the result bucket.

The GSE336901 FFPE raw-count supplement is a concrete supported example: the CSV has `gene_id`, `gene_symbol`, then ten integer count columns. The parser recognizes `gene_symbol` as annotation and maps the count columns to ten GSM records using their laboratory sample IDs. This example is independent of the bundled SALS practical.

The uploaded SALS teaching matrix contains 22,085 genes and 18 samples (8 healthy, 10 SALS); 20,169 genes meet the practical filter of at least ten counts in at least eight samples. Users can upload that full file with matching metadata through the secondary manual upload control. The bundled 221-gene demo is a regression fixture, not a full biological analysis.

## Execution boundary

The statistical backend requires Rscript, DESeq2, ComplexHeatmap, ggplot2, jsonlite and circlize plus private artifact storage. The Dockerfile installs the R packages, while the local development environment may not. A GEO Series without a suitable raw integer count matrix remains browseable but cannot enter this DESeq2 route. Input validation and statistical execution do not independently validate the study design or biological interpretation.

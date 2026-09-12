# BioNexus RNA-seq statistical execution

This path begins from a **raw integer gene-count matrix** plus explicit sample metadata. It is separate from the upstream FASTQ production workflow (`nf-core/rnaseq`), which remains responsible for read QC, trimming, alignment/quantification and count generation.

## Statistical contract

1. Validate raw non-negative integer counts and unique gene/sample identifiers.
2. Require metadata sample identifiers to match the count columns exactly; reorder only after set equality is established.
3. Build the model as `~ covariate_1 + ... + condition`, keeping the biological condition last. Do not claim adjustment for a variable that was not supplied in the metadata.
4. Pre-filter by a declared minimum count/minimum sample rule.
5. Estimate DESeq2 size factors and export normalized counts and size factors.
6. Use a blind DESeq2 variance-stabilizing transform for sample-level QC; export PCA coordinates and the sample-distance matrix.
7. Fit the DESeq2 negative-binomial model and test the explicit contrast (`test` versus `reference`).
8. Export all-gene statistics and the significant-gene subset using the predeclared adjusted-p-value and absolute log2-fold-change thresholds.
9. Generate PCA, sample-distance heatmap, MA and volcano figures in R. Generate the expression heatmap only when at least two significant genes exist.
10. Export every plotted matrix/table alongside SVG, PDF and 300-dpi PNG figures.

## Evidence and privacy boundary

Uploaded count matrices and metadata are processed in a temporary server directory and are not persisted by the expression route. BioNexus records SHA-256 digests and parameters, then stores only derived artifacts in a private per-user Supabase Storage namespace. Download links are expiring signed URLs.

Deterministic DESeq2 output is authoritative for the computation performed. A statistically significant result is not, by itself, independent biological or clinical validation.

## Bundled SALS validation subset

The repository includes a deterministic **every-100th-gene subset** of the course-supplied cerebellum sporadic-ALS count matrix. It preserves the original 18 sample columns (8 healthy and 10 SALS) and the original integer counts for those selected rows. It exists to regression-test the R execution and figure/export contracts. It is **not** a replacement for the full 22,085-gene analysis.

To reproduce the full practical, upload the complete supplied matrix with matching metadata, use `healthy` as the reference and `SALS` as the test level, and set the practical pre-filter to at least 10 counts in at least 8 samples.

# GEO normalized-expression recovery

The GEO count importer inspects Series and GSM supplements. It preserves sample supplement links with GSM-qualified file names so files with the same basename cannot be confused. A deposited multi-sample raw matrix may enter the existing preview validation. One-sample count files are not merged automatically. Filename eligibility identifies candidates, not proof of raw counts.

When normalized supplements or no raw candidates are found, the frontend shows recovery options and offers a source-linked ZIP from `/api/ngs/v2/geo/series/{accession}/recovery`.

The ZIP includes the source-record snapshot/checksum, SHA-256 checksums of package contents, blank group/biological-unit metadata, an unsent author-request draft, and:

- featureCounts counting with explicit strandedness/layout and an exact BAM-to-sample converter. Paired libraries use fragment counting. Native annotation columns are excluded. Fractional assignments are rejected.
- Salmon/tximport/DESeq2 code requiring actual quant.sf files and their annotation-matched transcript-to-gene mapping. Estimated counts and length corrections remain in the DESeq2 RDS. A normalized expression matrix is not a substitute for those quantifier outputs.
- A separately labelled exploratory limma-trend script on unlogged FPKM/TPM, with an explicit log2(x+1) transform, outcome-independent expression filter, reviewed two-group design, optional additive covariates, BH-adjusted results and SVG/PDF/PNG volcano exports. Effects are differences on the transformed scale. This option does not repair missing library/composition information or guarantee valid differential inference on arbitrary normalized data.

The R scripts require exactly matched sample names, independent biological units, at least two samples per group, recorded varying technical variables in the model, full design rank and residual degrees of freedom. They record package versions, method, transformation and input MD5 checksums. The package itself retains SHA-256 checksums.

These scripts execute in the user's R/compute environment. Downloading them does not execute a hosted alignment, quantification or alternate statistical analysis. The existing raw-count endpoint remains DESeq2 only. Source email drafts are never sent automatically.

FPKM/TPM rounding or pseudo-count reconstruction is not offered as a way to bypass count validation. voom requires counts. The separate limma-trend fallback requires analyst review of source normalization, mean-variance assumptions and pseudocount/filter sensitivity. Raw counts or re-quantification are preferred.

For GSE336902, the inspected public record currently lists `GSE336902_Fig6_cell_line_FPKM_matrix_GEO.csv.gz`; no supported raw candidate was discovered. This is a source-availability limitation, not an integer-parser fault.

Validation: Python source discovery, ZIP integrity, endpoint and featureCounts conversion tests; frontend type/lint checks; shell syntax; R known-answer tests compare limma effects/BH p-values with direct limma, and tximport/DESeq2 counts, normalization factors, fold changes and adjusted p-values with direct package execution. Tests use synthetic controls, not biological validation of GSE336902.

References:
- https://bioconductor.org/packages/release/bioc/vignettes/tximport/inst/doc/tximport.html
- https://bioconductor.org/packages/release/bioc/vignettes/DESeq2/inst/doc/DESeq2.html
- https://bioconductor.org/packages/release/bioc/vignettes/limma/inst/doc/usersguide.pdf

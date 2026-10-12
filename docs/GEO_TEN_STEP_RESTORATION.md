# GEO accession-to-figures restoration

The primary RNA-seq page now takes a GEO accession and runs the complete analysis. It retrieves and validates the deposited count matrix, matches unique GEO sample identifiers, derives documented groups, normalizes counts in R, and displays the existing PCA, sample-distance, MA, dispersion, volcano and heatmap figures with downloadable tables. The ten practical steps remain visible during execution. Step ten reports the actual functional-enrichment outcome, including annotation availability, rather than claiming every step succeeded.

Manual column assignments, count-method fields, annotation fields, and the second mandatory QC approval are removed from this simple path. Existing advanced recovery and reviewed QC/inference routes remain accessible inside closed Advanced sections. The user asks for the complete analysis by pressing Run analysis. R still validates replication, experimental units, requested model rank, confounding, integer counts and artifact completeness.

Automatic preparation requires a source statement supporting count provenance: GEO processing methods describing raw counts/counting or an explicitly raw-count-labelled deposited supplement. Integer formatting alone is insufficient. Source methods, sample identities, unit inference basis, matrix checksum and GEO record checksum are retained. Missing annotation details remain undeclared source information; they are not fabricated. Ambiguous matrices or biological comparisons get a short choice. Unresolved identities and unsupported designs stop with a specific explanation rather than merging unrelated columns.

Recorded varying batches are included as categorical model terms. Identified paired subjects are modelled as categorical units. Missing batch values and repeated within-condition measurements require advanced review. Multiple or redundant covariates can produce an unidentifiable model; R rejects that model.

The original deployed readiness endpoint reported installed R but unavailable durable storage and a blank missing-package entry. Empty R preflight lines are now ignored, and callers receive a copy of the cached package list so durable-readiness checks cannot contaminate it. Configured workers receive full-stage retained jobs. Otherwise the hosted R service executes the complete request directly, retaining final artifacts in the existing private Supabase store. Direct runs require the browser request to remain open and do not promise durable input/checkpoint recovery. Advanced recovery still requires configured persistent worker storage.

## Verification

- 87 backend contracts passed, covering the automatic route, legacy GEO import, overlapping identifiers, reordered metadata, count provenance, and durable recovery.
- The actual downloaded GSE336901 record and supplement prepared without manual assignments: 42,000 genes, ten samples, five resistant and five sensitive samples. Full R analysis retained 14,343 genes after filtering and validated 37 artifacts. Local functional enrichment reported UNAVAILABLE because the extracted verification runtime lacks GO annotation packages; this limitation is explicit.
- The complete supplied SALS matrix (22,085 genes, 18 samples) passed the pinned independent-reference numerical regression again. It compares DESeq2 results, normalized counts, size factors, PCA, distances and plotting data.
- Frontend TypeScript and scoped ESLint passed; existing native-image optimization warnings remain.

The concise verification record is retained at `benchmark/results/rnaseq/geo-restoration/verification.json`. Statistical equivalence checks and artifact validation do not establish independent raw-count provenance or biological validity.

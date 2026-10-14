# RNA-seq enrichment recovery

The results workspace provides **Recovery and alternative analyses**. Its authenticated
`POST /api/ngs/v2/rnaseq/expression/runs/{run_id}/enrichment` endpoint reuses the
owner's saved, checksum-verified DESeq2 result table. It creates a new run ID and
preserves links to the original DESeq2 artifacts. The parent run is unchanged.

## Identifier recovery

Human/mouse local GO supports per-row Ensembl gene/transcript IDs, Entrez gene IDs
and exact gene symbols. Ensembl version suffixes are removed. Official symbols
are tried before optional aliases; only unique mappings are accepted. Mixed human
and mouse Ensembl identifiers block local analysis. Case conversion and ortholog
projection are not performed. Species-specific Ensembl IDs can inform auto-detection;
otherwise select the organism from the study metadata. Sample identities and
condition labels must still be reviewed in the GEO/count-matrix workflow.

Mapping TSVs record original IDs, lookup IDs, mapping routes, ambiguity and inclusion
in the background. Coverage below 50% produces a visible warning; that threshold is
an operational review prompt, not a validated quality cutoff.

## Databases

Choose all GO or BP/MF/CC. For another organism or a different database, upload a
species-matched GMT (including Reactome exports or a curated laboratory set) with
its source/release label and identifier namespace. This is an uploaded annotation
route, not a live Reactome API integration. BioNexus records those user declarations,
retains the original GMT and optional mapping TSV, and records their SHA-256 values.
No gene lists are sent to external annotation services.

GMT rows are tab-separated: `term_id`, `description`, then gene IDs. Up to 10 MB
and 10,000 unique terms are accepted. Custom IDs match exactly and case-sensitively.
An optional TSV with `source_id` and `target_id` maps the result IDs to GMT IDs.
One-to-many mappings are excluded. Many input rows mapping to one target are counted
once in ORA; targets with conflicting up/down calls leave both query sets while remaining in the background. Ranked testing uses the median Wald statistic for that target.

## Methods

- **ORA**: one-sided hypergeometric tests on existing up/down DEG calls. Background:
  uniquely mapped, annotated genes with non-missing DESeq2 adjusted p-values.
- **Ranked Wilcoxon**: exploratory competitive rank-sum testing of signed DESeq2
  Wald statistics inside each set versus remaining annotated genes. It uses finite
  statistics with non-missing unadjusted p-values, without a DEG cutoff. The normal
  approximation includes ties and continuity correction. It is not GSEA and does
  not model inter-gene correlation or permute sample labels.

Both methods use 10–500 genes per set after background intersection and a single BH
family across term-direction tests for the selected annotation collection. Separate
reruns are not jointly corrected; retain and report all sensitivity analyses.
The enrichment alpha is inherited from the DESeq2 run. Methods/databases never
switch automatically because a run produces no significant terms.

## Verification

`tests/test_go_enrichment.R` covers known hypergeometric probabilities, BH, mixed IDs,
alias recovery, species conflicts, custom GMT parsing, ambiguous mappings, rank-sum
parity against R's `wilcox.test` (including ties), constant scores, and actual saved-
result execution with SVG/PDF/PNG output. `tests/test_enrichment_retry.py` covers
owner-scoped downloads, source checksums, invalid paths, original-run preservation,
and removal of stale enrichment figures. These are software/regression checks;
biological conclusions require study-specific QC and interpretation.

References: [R Wilcoxon documentation](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/wilcox.test.html),
[Bioconductor annotation resources](https://bioconductor.org/help/course-materials/2022/CSAMA/lecture/3-wednesday/lecture-12-annotation-resources/annotation.html).

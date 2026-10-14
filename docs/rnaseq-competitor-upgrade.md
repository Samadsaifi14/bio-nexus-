# RNA-seq: first delivery of the feature-by-feature roadmap

## User-visible changes

The existing GEO accession → raw counts → ten-step R workflow now has an interactive PCA and volcano viewer. Search for a sample or gene, select it to see the emitted values, toggle groups, and zoom around the selected point. PCA can be coloured by model metadata, including batch variables when they were supplied. Every finite point is rendered; the viewer does not downsample. The accessible table displays six significant digits, with full precision in point selection and the original TSV. Missing coordinates are excluded explicitly rather than converted to zero.

The original R SVG/PDF/PNG exports remain available. Interactive data is fetched from the owner-scoped artifact URL and must match the manifest byte count and SHA-256 before rendering.

Step 10's alternative analyses now include preranked GSEA through fgsea. Choose a documented organism and local GO database, or a species-matched GMT with its source/release and identifier namespace. The result remains linked to the immutable DESeq2 parent run; statistical fitting is not repeated.

GSEA uses signed Wald statistics without a DEG cutoff, median aggregation for duplicate mapped targets, deterministic ordering of tied statistics, seed 1729, one worker, standard two-sided enrichment, weighted exponent 1, minimum set size 10, maximum 500, sampleSize 101, nPermSimple 1000 and an estimation floor of 1e-10. The package version, NES, ES, leading-edge genes, uncertainty estimate, mapped background and execution warnings are retained. All uniquely mapped eligible genes remain in the ranked universe, including genes outside the selected gene sets. BH correction covers the tested sets. Missing estimates remain unresolved; an entirely unresolved result is not reported as no enrichment.

Batch adjustment remains part of the declared DESeq2 design. Viewing PCA by batch does not remove batch effects from the plot or alter the counts. Confounded designs remain blocked by the existing full-rank check. Normalized FPKM/TPM data cannot be reconstructed into original raw counts; the existing source retrieval and quantification-import boundaries remain in force.

## Execution and exports

The VST shortcut now checks the number of genes with mean normalized count above 5, rather than the total retained gene count. Valid large, low-abundance matrices use the exact DESeq2 transformation when shortcut prerequisites are absent. QC summaries record the actual transform and effective pre-filter sample count. Library tables also retain detected-gene counts; PCA tables retain sample metadata for inspection.

New expression runs emit a methods paragraph and a ZIP with original count/metadata bytes, R scripts, numerical outputs, figures, provenance and a checksum index. Salmon ZIPs additionally include the quant.sf files, transcript-to-gene mapping and a portable quantification manifest. Enrichment reruns produce their own methods and enrichment ZIP; they do not inherit an obsolete expression bundle or methods paragraph as if it described the new analysis.

Both backend images install fgsea and execute the GSEA regression during image builds. Backend CI runs the numerical GSEA and exploration controls. Frontend CI runs the plot evidence contract and uses the existing BIONEXUS_LOCAL_VERIFY mode for builds without outbound Sentry build reporting.

## Executed verification, 2026-10-14

- 119 backend tests passed across GEO import/sample matching/recovery, source provenance, queue isolation/recovery, experimental designs, DESeq2/tximport parity, expression contracts, export bundles and enrichment reruns.
- The new low-abundance numerical control passed with over 1,000 retained genes and exported batch metadata.
- The complete supplied matrix (SHA-256 `b7a9736672a6cebfdeea78dd151f5c764b058537cac09aeb0256cbfb7123dc08`) retained 22,085 input genes and all 18 samples. After the practical pre-filter, 20,169 genes remained. Independent R parity passed for results, normalization, PCA, distances, volcano and heatmap matrices. The retained report is `benchmark/results/rnaseq/complete-matrix/latest.json`; the fixture and independent reference are versioned. Full generated execution artifacts were kept locally during this check; CI uploads them as run artifacts rather than duplicating 80 MB in this commit.
- GSEA matched a direct fgsea call with the recorded parameters, including NES, p-values and BH values; positive/negative direction, reproducibility and retention of genes outside sets passed. Tested runtime: R 4.3.3, DESeq2 1.42.0, ggplot2 3.4.4 and fgsea 1.28.0. Deployment images resolve the Bioconductor release compatible with their R version and retain the installed version in results.
- TypeScript, changed-component lint, plot evidence tests and the production build passed. Existing image-element lint warnings remain in the original R figure cards.
- Browser checks against a temporary local review page passed for 18 PCA samples and 20,169 volcano points: sample/gene search, selection, zoom, group toggling, accessible tables, desktop rendering and a 390-pixel mobile viewport without page overflow. Direct Playwright was used after the CLI's Unix socket was unavailable. The temporary page and fixture copies are excluded from production.

These are computational regression checks, not independent biological validation or a comparison against Partek/CLC. Existing STAR/HISAT2/Salmon production execution is outside this increment; it has not been newly benchmarked here. The other 24 feature areas remain separate roadmap deliveries.

## Repeating the checks

From `bioai-platform/frontend`, run `npm ci`, `npm run typecheck`, and `npm run test:rnaseq-plots`. Build locally with `BIONEXUS_LOCAL_VERIFY=1 NEXT_TELEMETRY_DISABLED=1 npm run build`.

From `bioai-platform/backend`, with the documented R runtime installed, run `Rscript tests/test_preranked_gsea.R` and `python -m pytest tests/test_rnaseq_exploration.py tests/test_enrichment_retry.py -q`. Use a test temporary directory outside `/tmp` for queue checks, because the durable runtime rejects `/tmp` as a production storage root. The complete-matrix harness is `python benchmark/fixtures/rnaseq/full_matrix/run_regression.py` from the repository root and enforces its numerical runtime lock.

Primary method documentation: [DESeq2](https://bioconductor.org/packages/release/bioc/vignettes/DESeq2/inst/doc/DESeq2.html), [fgsea](https://bioconductor.org/packages/release/bioc/vignettes/fgsea/inst/doc/fgsea-tutorial.html). The installed fgsea 1.28.0 package declares MIT with its LICENCE file; retain the applicable package notices when distributing software.

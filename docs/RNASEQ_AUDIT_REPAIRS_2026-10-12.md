# RNA-seq provenance, design and execution audit repairs

## Outcome

| Finding | Implemented behavior | Measured boundary |
| --- | --- | --- |
| 2. Integer format is not provenance | Explicit `deposited_raw_counts`, `verified_count_estimates`, `normalized_expression` and `unknown_origin` classes. Source URI/document identifier, methods, annotation and review are required before analysis. Estimates additionally require evidence linking original quantifier files to their annotation. | Source classification remains analyst-attested, with `independently_verified: false`. Integer-format previews remain unknown-origin until review. Normalized/unknown input cannot enter DESeq2. |
| 3. Format versus design | GEO matrix inspection accepts one or more samples and one or more genes. All-zero libraries can be inspected with a warning. Replication/group requirements remain at configured analysis and R model boundaries. | Small/one-sample matrices do not become eligible for differential testing merely because import succeeded. |
| 4. Count-file compatibility | Per-file sample mapping, reference build, annotation, counting method, strandedness and feature definition are required before assembly. All selected records must agree and receive explicit review. | Mismatches fail before combination. Gene-set equality is still required; missing observations are rejected. Compatibility is reviewed evidence, not an independent reconstruction of counts. |
| 5. Realistic designs | Recorded nesting generates warnings; rank checks apply to the requested model. Included perfectly confounded terms fail. Numeric experimental-unit IDs are categorical blocks. Independent units are checked, and within-condition repeats require aggregation or a suitable correlation model. | Seven executed R controls passed: crossed batches, partial confounding, recorded/unmodelled nesting, paired subjects, requested perfect confounding, ignored repeated units and within-condition repeated observations. |
| 6. Numerical reproducibility | Complete supplied 22,085-gene/18-sample input runs QC → checkpoint → inference and is compared with an independent package-level reference calculation. Core R/DESeq2/ggplot2 versions are pinned. | Complete-matrix parity PASSED. All seven compared table families had zero observed difference at exported numeric precision, within declared tolerance 1e-7. 20,169 genes were retained by the declared filter. |
| 7. Upstream execution | Plans explicitly identify themselves as plans. Local workers retain argv, command hash, state history, exit state and log hash. A retained-bundle verifier checks run identity, reference/input/output checksums, required artifacts, process states and immutable container digests. | Worker/integrity process controls passed. Actual Sarek execution is NOT_EXECUTED here: local, SLURM and AWS Batch executors are all disabled/unavailable, and no actual run bundle was supplied. No completed upstream sequencing claim follows. |

## Exact code paths

- `app/rnaseq/input_contract.py`: reviewed provenance classification and evidence gate.
- `app/rnaseq/geo_counts.py`: matrix-only format validation and unknown-origin preview.
- `app/routers/geo_search.py`: preview warnings and reviewed design handoff.
- `app/rnaseq/count_recovery.py`: per-file compatibility review and strict assembly.
- `app/routers/rnaseq_recovery.py`: preserve original source/mapping records through archive and GEO recovery.
- `app/rnaseq/deseq2_analysis.R`: design identifiability, experimental units and recorded runtime versions.
- `app/rnaseq/expression.py`: required runtime/normalization artifacts, retained R logs and script/runtime provenance.
- `app/ngs/production.py`, `nextflow_worker.py`, `execution_evidence.py`: plan, process and execution-evidence boundaries.

Paths above are relative to `bioai-platform/backend`. The GEO/recovery frontend
forms expose the new classification, source documentation and compatibility
review; changing relevant fields invalidates the associated review.

## Retained numerical evidence

Complete-matrix run: `20261012T085955700359Z`.

- R 4.3.3; DESeq2 1.42.0; ggplot2 3.4.4.
- 22,085 input genes; 18 samples; 20,169 genes after filtering.
- Compared all standard DESeq2 columns and significance calls, size factors,
  normalized counts, PC1/PC2, sample distances, volcano data and heatmap z-scores.
- Independent reference does not source the application script, use its
  checkpoint or read its fitted objects. QC is checked to stop before inference.
- `benchmark/results/rnaseq/complete-matrix/latest.json` identifies the dated
  retained run and 68 artifact hashes. All 68 hashes were rechecked after completion.
- `benchmark/results/rnaseq/design-controls/manifest.json` retains 124 synthetic
  R control tables, audits and logs from nine passed R tests (seven designs and
  two direct DESeq2/tximport numerical controls).
- `benchmark/results/rnaseq/runtime-package-checksums.json` records the 84
  official package checksums from Ubuntu's 20260828 snapshot. The runtime was
  extracted into a local prefix; only launcher/configuration paths were adjusted.

This verifies computational parity for the stated input and software. It does
not independently verify the supplied matrix's raw-count origin, experimental
independence, disease associations or biological generalizability. Its metadata
does not declare experimental units or technical covariates; none were invented.

## Verification and reproduction

All **97 Python contract/parity-checker tests and 9 executed R tests passed** (106 tests total). The Python controls have retained JUnit reports
at `benchmark/results/rnaseq/contracts.xml` and `parity-gate.xml`. Frontend
TypeScript checking passed; scoped ESLint reported no errors (one existing image
optimization warning). R tests ran using the pinned isolated local runtime.

```bash
PYTHONPATH=bioai-platform/backend OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python benchmark/fixtures/rnaseq/full_matrix/run_regression.py

PYTHONPATH=bioai-platform/backend python benchmark/fixtures/ngs/verify_sarek_execution.py \
  --run-record owned_run_record.json --bundle retained_run_directory
```

See the corresponding fixture READMEs for runtime and bundle requirements.
`Complete RNA-seq numerical regression` installs the pinned numerical core,
runs the design controls and complete-matrix parity test, and retains evidence
in GitHub Actions. That new workflow has not been executed on GitHub here.
Executor capability details are retained at `benchmark/results/ngs/sarek-execution/executor-readiness.json`. Local downstream statistical execution is measured separately from hosted API
deployment/private-storage integration and from upstream Sarek execution.

## Scientific method references

- [DESeq2 vignette: count/estimated-count inputs, designs and model-matrix rank](https://bioconductor.org/packages/release/bioc/vignettes/DESeq2/inst/doc/DESeq2.html)
- [tximport vignette: original quantifications and gene-level length offsets](https://bioconductor.org/packages/release/bioc/vignettes/tximport/inst/doc/tximport.html)
- [Ubuntu's pinned DESeq2 1.42.0 package](https://packages.ubuntu.com/en/noble/amd64/r-bioc-deseq2)

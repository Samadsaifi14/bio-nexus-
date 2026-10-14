# Complete-matrix numerical control

`counts.tsv` is the complete user-supplied `Cer_SALS_file_for_Dseq_input.txt`,
preserved byte-for-byte: 22,085 genes and 18 sample columns. SHA-256:
`b7a9736672a6cebfdeea78dd151f5c764b058537cac09aeb0256cbfb7123dc08`.
The accompanying repository metadata has eight healthy and ten SALS rows and
matches every column. Experimental units and technical covariates are not
declared here; do not invent them or claim biological validation from this test.
Integer formatting does not independently verify this supplied matrix's origin.

The runner tests QC → retained checkpoint → inference against an independently
executed package-level calculation. The reference script neither sources the
application script nor reads its checkpoint/fitted R objects. Numerical parity
is assessed at relative and absolute tolerance 1e-7 for full DESeq2 statistics,
size factors, normalized counts, both PCA coordinates, sample distances,
volcano plotting values, significance calls and heatmap plotting matrices.
Gene/sample identities and missing-value patterns must also match. This is
computational regression evidence, not independent biological truth.

R 4.3.3, DESeq2 1.42.0 and ggplot2 3.4.4 are pinned in `runtime-lock.json`.
All loaded dependencies and platform details are retained in sessionInfo.txt.
Use one BLAS/OMP thread for the reference control. A mismatched runtime blocks
the benchmark; a missing R runtime writes NOT_EXECUTED, never PASS.

```bash
PYTHONPATH=bioai-platform/backend OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python benchmark/fixtures/rnaseq/full_matrix/run_regression.py
```

The dated directory retains both inputs, independent output tables, application
QC/inference artifacts, logs, checkpoints and SHA-256 manifests. The manual/main
`Complete RNA-seq numerical regression` workflow retains the evidence as an
artifact. A workflow definition alone is not an executed passing run.

# GEO recovery and durable RNA-seq execution

This implementation requires deployment of the API and worker together. It reuses pinned
nf-core/rnaseq 3.26.0 and the existing local, Slurm and AWS Batch adapters.
The statistical handoff now supports raw gene counts and genuine Salmon
quantifications. It does not reconstruct original counts from FPKM/TPM.

## User guide

1. Search a GEO Series in **RNA-seq analysis**. Inspect the source and choose a
   raw-count candidate. Preview validates formatting, not raw-count provenance.
2. Map columns to GEO samples, declare actual biological-unit IDs and review
   groups, source methods, counting method and annotation release. A GSM ID is
   not evidence of biological independence.
3. Select **Generate PCA and QC for review**. Save the returned job ID.
4. At **QC_REVIEW**, inspect PCA, sample distances, library sizes and the design
   audit. Approve only after checking the recorded design. Approval is bound to
   the checkpoint SHA-256. Inference then emits DESeq2 tables, MA, volcano and
   heatmap figures with their exact plotted source data.
5. If a ready cohort matrix is unavailable, open **Retrieve raw counts from GEO
   supplements or archives**. Select source files and inspect them. Choose one
   cohort matrix, or explicitly map individual sample files to reviewed metadata.
   Per-sample files must contain a header and exactly `gene` and `count` columns.
   All selected files must have the same gene set, counting basis and annotation.
   Missing genes are rejected rather than filled with zero. ZIP/TAR links,
   traversal paths, duplicate members and oversized archives are rejected.
6. Alternatively upload the same reviewed archive/matrix. Metadata is TSV with
   `sample`, `condition`, and `experimental_unit`, plus any declared covariates.
   The UI provides a four-sample template. For repeated units, a scientifically
   appropriate block must be modelled; confounded or saturated designs fail.
7. If counts are unavailable but FASTQ exists, use **Regenerate counts from FASTQ
   with durable compute**. Stage reads and a sample sheet on the configured
   executor. The required columns are `sample,fastq_1,fastq_2,strandedness`.
   Use the same sample ID for lanes of one sample. Review the plan before
   submitting; this can incur compute and storage charges.
8. Monitor the saved production run ID. Review FastQC, MultiQC, alignment,
   strandedness and quantification evidence. Execution success is not a QC pass.
9. Choose **Salmon quant.sf + matching transcript annotation**. Upload a ZIP of
   genuine quant.sf files or import them from your completed production run.
   Select relative paths, map them to metadata sample IDs, and provide the exact
   annotation-matched two-column transcript-to-gene TSV. The full count and length
   model is imported via tximport/DESeqDataSetFromTximport; TPM is not rounded.
10. Review the resulting expression QC checkpoint, approve inference, and export
    results and provenance. Keep the job ID to resume after closing the browser.

Mixed/non-RNA-seq Series remain blocked by the automatic gene-expression
importer. CUT&Tag/ChIP-seq needs a reviewed peak/region counting workflow; signal
tracks are not gene counts. This change does not claim to execute that assay.
The recovery route supports exact gene-set assembly, not arbitrary author formats
or inferred sample identities. GEO/SRA discovery does not automatically download
and stage FASTQ; the executor's reviewed sample sheet supplies those inputs.

## Deployment prerequisites

The API and dedicated statistical worker must share the same persistent,
private, **local** volume. SQLite WAL is intended for a single-host deployment
with one or more worker processes; do not put this database on NFS or mount it
independently on multiple hosts. Cross-host statistical queues require a separate
database adapter. Nextflow computation may run on AWS Batch or Slurm while the
statistical worker remains on this persistent host.

Set on both the API and worker:

```dotenv
BIONEXUS_EXPRESSION_ROOT=/var/lib/bionexus-expression
SUPABASE_URL=<existing project URL>
SUPABASE_SERVICE_ROLE_KEY=<existing private service key>
BIONEXUS_RSCRIPT=Rscript
```

The root must be an absolute persistent path outside `/tmp` and `/var/tmp`.
Configuration alone cannot prove a volume survives host replacement; provision
and back up the volume before enabling submissions. Directory permissions must
allow the API and worker service account to read the same retained inputs.

Build and run the dedicated statistical worker from the backend directory:

```bash
docker build -f Dockerfile.rnaseq -t bionexus-rnaseq-worker .
docker volume create bionexus-expression
docker run -d --name bionexus-rnaseq-worker --restart unless-stopped \
  --env-file /secure/path/rnaseq.env \
  -v bionexus-expression:/var/lib/bionexus-expression \
  bionexus-rnaseq-worker
```

Mount `bionexus-expression` at the same path in the API container. The API's
existing image includes R/DESeq2; this change adds tximport there too. The general
`app.worker` does not replace the dedicated `python -m app.rnaseq.durable` worker.
No background process is silently launched by an HTTP request.

The dedicated image includes human GO annotations. Mouse GO annotations must be
installed separately if required; absent enrichment annotation is reported as a
separate status rather than fabricated gene-set evidence. Full production image
build and cloud execution must be tested in the target deployment.

The capabilities endpoint reports R executable/package readiness, artifact
storage configuration and a recent dedicated-worker heartbeat. Actual private
bucket access is checked before R execution. Missing infrastructure rejects
submission; there is no fallback to exploratory read processing.

For FASTQ production, configure the existing settings:

```dotenv
NGS_RUN_ROOT=/var/lib/bionexus-nextflow
NGS_INPUT_ROOT=/data/rnaseq
NGS_AWS_BATCH_EXECUTION_ENABLED=true
NGS_AWS_REGION=<region>
NGS_AWS_BATCH_JOB_QUEUE=<reviewed queue>
NGS_AWS_BATCH_JOB_DEFINITION=<Nextflow driver job definition>
BIONEXUS_RNASEQ_CONFIG_ROOT=/data/reviewed-nextflow-configs
BIONEXUS_RNASEQ_S3_INPUT_ROOT=s3://<private bucket>/rnaseq-inputs
BIONEXUS_RNASEQ_S3_OUTPUT_ROOT=s3://<private bucket>/rnaseq-results
```

Use the executor appropriate to your host. Local execution requires Nextflow,
Java and the selected container engine. Slurm requires shared persistent input,
work and output storage plus sbatch/sacct. AWS Batch requires a Nextflow driver
image, IAM role, S3 access, queue, job definition and a reviewed Nextflow config.
These resources are not created by this code change.

Input and output namespaces use the first 32 hexadecimal characters of
SHA-256(user ID). Stage a user's sample sheet and reads below their configured
input namespace. Select a distinct run folder below their output namespace.
Custom configs must live below the administrator-reviewed config root; users
must not have write permission to that config root. Preserve reference/index
checksums and nf-core execution manifests in the production output.

For a production import, only the authenticated owner's completed nf-core/rnaseq
run is accepted. Selected quant.sf paths must remain within that run's authorized
output directory/prefix; local symlink escapes are rejected. S3 imports are
bounded streams, not downloads of the entire output bucket.

## Durability, retention and provenance

The queue retains reviewed counts/quantifications, metadata, mapping and private
owner identity on the worker volume. This is an intentional change from the
older ephemeral upload route. Budget and manage retention for sensitive data.
Do not remove active jobs or checkpoints. After archival, operators may remove
the corresponding completed job directory under their retention policy; derived
private artifacts remain separately stored in Supabase.

Claims are atomic SQLite transactions. A worker heartbeats every ten seconds;
leases expire after 120 seconds. Stale work is retried at most three times.
Invalid scientific input is terminal. Lease-specific QC files prevent an older
worker from overwriting a replacement worker's checkpoint. The R implementation,
inputs and approved checkpoint are checksummed. A changed script or DESeq2
version requires a new reviewed run. Status reads refresh private artifact URLs.

Count provenance is explicitly `ANALYST_ATTESTED`, not independently verified.
FPKM/TPM normalization cannot be undone reliably from the published matrix.
Re-quantification produces new counts under recorded references and parameters;
it does not guarantee reproduction of the author's original counts.

## Validation and acceptance

Run the focused Python suites, numerical R comparisons and frontend checks:

```bash
cd bioai-platform/backend
PYTHONPATH=. python -m pytest --basetemp="$PWD/pytest-work" \
  tests/test_rnaseq_durable_recovery.py tests/test_geo_counts_import.py \
  tests/test_geo_recovery.py tests/test_rnaseq_expression_contract.py \
  tests/test_rnaseq_expression_source_boundary.py tests/test_rnaseq_production.py \
  tests/test_ngs_production_execution.py tests/test_rnaseq_recovery_r.py -q
cd ../frontend
npm run typecheck
npm run build
```

The numerical tests compare raw-count fold changes/FDR with direct DESeq2 and
Salmon normalization factors/statistics with direct tximport/DESeq2. They use
synthetic controls and do not establish biological or clinical accuracy.
Deployment acceptance additionally requires a real reviewed FASTQ job, retained
read QC/provenance, an API/worker restart test and private artifact retrieval.

References:
- https://nf-co.re/rnaseq/3.26.0/docs/usage
- https://bioconductor.org/packages/release/bioc/vignettes/DESeq2/inst/doc/DESeq2.html
- https://bioconductor.org/packages/release/bioc/vignettes/tximport/inst/doc/tximport.html

## Repair brief: evidence and bounded changes

| Finding | Exact code path | Repair |
| --- | --- | --- |
| FPKM/normalized data can resemble counts after formatting or rounding; integer checks cannot establish scientific provenance | `backend/app/rnaseq/geo_counts.py` → `backend/app/routers/geo_search.py`; manual `backend/app/routers/rnaseq_expression.py` | Require reviewed `CountOrigin` evidence in `backend/app/rnaseq/input_contract.py`, reject declared normalization, and retain the attestation. This remains analyst-attested, not independently verified. |
| Historical `(intermediate value).join is not a function` | `backend/app/rnaseq/deseq2_analysis.R` jsonlite `auto_unbox` → summary vectors → frontend `src/components/ngs/RnaSeqWorkflow.tsx` rendering | Existing `as.list`/`stringList` fixes already addressed singleton serialization; `frontend/src/lib/rnaseqExpressionApi.ts` now validates the runtime contract and normalizes legacy scalar strings. |
| GEO supplementary counts lacked an explicit reviewed assembly route | `backend/app/routers/rnaseq_recovery.py` → `backend/app/rnaseq/count_recovery.py` | Bounded archive inspection, source checksum review, explicit sample mapping, identical gene sets, and recorded counting/annotation evidence. |
| Synchronous analysis did not retain a resumable statistical job or enforce a QC decision | `backend/app/rnaseq/expression.py` → `backend/app/rnaseq/durable.py` → `backend/app/rnaseq/deseq2_analysis.R` | Persistent local queue, leases, retries, immutable input checksums, retained R checkpoint, and approval bound to its checksum before inference. |
| FASTQ execution did not provide the full reviewed quantifier-to-expression handoff | `backend/app/routers/rnaseq_production.py` and existing `backend/app/ngs/execution.py` → recovery production import | Owner-scoped persistent inputs/outputs, existing pinned nf-core executor, selected completed-run Salmon artifacts, matched tx2gene, genuine tximport length offsets. Staging reads remains explicit. |
| Result success could omit required figures or lose plotted evidence | `backend/app/rnaseq/expression.py` and `backend/app/rnaseq/deseq2_analysis.R` → `frontend/src/components/results/RnaSeqExpressionWorkspace.tsx` | Required artifact checks; exact volcano data; zero-variance heatmap exclusion audit; source matrices and fitted R objects. |

Paths beginning `backend/` and `frontend/` are relative to `bioai-platform/`.
The R PCA, MA, volcano and heatmap implementations already existed; the repairs
complete their input, durable execution, QC approval and artifact contracts.
Raw-count retrieval downloads submitted count files. FASTQ re-quantification runs
reads against a declared reference and annotation to create new quantifications.
They are separate operations; FPKM/TPM cannot be converted back to original counts
by rounding or multiplication.

## Local validation status

- 50 focused backend tests passed, including archives, provenance, source changes,
  ownership, leases, retry bounds, checkpoint approval and production namespaces.
- Two synthetic R tests passed: raw counts compared with direct DESeq2, and Salmon
  quantifications compared with direct tximport/DESeq2, including length offsets.
- Frontend TypeScript passed; scoped lint had zero errors and three native-image
  warnings. Browser testing could not run because the browser download failed.
- Production build was blocked by automatic approval review because the
  Sentry-enabled build could export source maps or build metadata. It was not retried.
- Validation did not provision cloud resources or run a live FASTQ workload.
  Real executor/storage credentials and an approved production acceptance run
  are still required. These local tests do not establish performance, cost or
  scientific correctness for an arbitrary GEO study.

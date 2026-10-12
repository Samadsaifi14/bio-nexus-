# BioNexus production NGS execution

BioNexus submits the pinned `nf-core/sarek` 3.10.0 command produced by the production validator. Production execution never falls back to the exploratory Python pipeline.

## Shared requirements

- Apply `migrations/011_ngs_production_runs.sql` to Supabase.
- Configure authentication and the existing Supabase service credentials.
- Stage the Sarek samplesheet, reference resources, optional WES BED, work directory and result directory where the selected executor can read them.
- Provide a reviewed Nextflow configuration for SLURM and AWS Batch.
- Keep the executor disabled until its preflight requirements are satisfied.

## Local Docker, Apptainer or Singularity

Run the API on the workstation that owns the staged paths. Install Java, Nextflow, and the selected container runtime, then set:

```env
NGS_LOCAL_EXECUTION_ENABLED=true
NGS_RUN_ROOT=/durable/bionexus-ngs-runs
```

The detached worker writes its real Nextflow log and status under `NGS_RUN_ROOT/<run-id>/`. The output artifacts remain in the requested Sarek `--outdir`.

## SLURM

Run the API or a private execution service on a SLURM login/head node with `nextflow`, `java`, `sbatch`, and `sacct` on `PATH`. Samples, references, work and results must use shared cluster paths.

```env
NGS_SLURM_EXECUTION_ENABLED=true
NGS_RUN_ROOT=/shared/bionexus/ngs-runs
```

Select the SLURM profile and provide the reviewed site-specific Nextflow configuration. BioNexus submits with `sbatch` and reads scheduler state with `sacct`.

## AWS Batch

Create an AWS Batch queue and a driver job definition whose image includes Java, Nextflow and the AWS permissions required to submit Sarek process jobs. Grant the BioNexus API role `batch:SubmitJob`, `batch:DescribeJobs`, S3 access to the staged inputs/results, and the appropriate job-role permissions.

```env
NGS_AWS_BATCH_EXECUTION_ENABLED=true
NGS_AWS_REGION=ap-south-1
NGS_AWS_BATCH_JOB_QUEUE=<queue-name-or-arn>
NGS_AWS_BATCH_JOB_DEFINITION=<driver-job-definition-name-or-arn>
```

Use S3 input/result locations or mounts explicitly configured in the job definition. The artifact importer inventories the real S3 output prefix after the Batch job succeeds.

## Scientific boundary

Successful workflow execution is not clinical validation. BioNexus imports observed execution, MultiQC, alignment, variant, coverage, identity/contamination and provenance artifacts. Missing groups remain missing and keep the clinical gate closed.

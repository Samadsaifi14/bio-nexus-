# NGS benchmark status

Last reviewed: 2026-09-01

## Current conclusion

Bio-Nexus NGS v2 has **not** been shown to match or outperform nf-core/sarek. No same-input
Nextflow comparison or GIAB truth-set evaluation has completed. The current endpoint is an
exploratory, sampled, surrogate implementation and must not be used for whole-run, research,
diagnostic, or clinical conclusions.

## Compact portability benchmark

A separate synthetic positive control now runs without large downloads. It contains 20 mapped
reads across a 200 bp reference and one known heterozygous SNP (`chrTiny:50 C>G`, `GT=0/1`,
`DP=20`, `AD=10,10`). Bio-Nexus direct execution and Nextflow 26.04.6 produced byte-identical
normalized call tables using samtools/bcftools 1.24. The Galaxy wrapper command produced the same
table; wrapper lint passed, while a Galaxy 25.1 server bootstrap was interrupted by proxy failures.

All three normalized tables have SHA-256
`cefef322e336202da82549c1d5c09cf546a70b4aacfe9d1cc7e090a8aa23bbb1` and score TP=1, FP=0,
FN=0, precision=1.0, recall=1.0 and F1=1.0 against the synthetic truth. This proves only narrow
workflow-output portability. It does not change the full-pipeline conclusion above.

## Defect found during validation review

The FASTQ reader processes at most 2,000 records per input file. Earlier results did not expose
that cap and could display an analysis-readiness label. The API and UI now disclose the cap,
list truncated files, label the analysis `EXPLORATORY_PREVIEW`, and set `research_ready=false`.

## Full HG002 comparison requested

The intended independent validation uses the same:

- GIAB HG002 paired-end whole-genome reads;
- GRCh38 reference sequence and contig naming;
- GIAB HG002 benchmark VCF and benchmark BED;
- sample metadata, intervals, and filtering policy;
- variant classes and benchmark regions.

The reference comparator is nf-core/sarek 3.10.0 under Nextflow, with exact pipeline revision,
profile, containers, commands, checksums and resource versions retained. The Bio-Nexus callset
and the selected Sarek callset must each be evaluated independently with GA4GH hap.py or vcfeval.

Required reported metrics:

1. SNP and INDEL true positives, false positives and false negatives.
2. Precision, recall and F1 for SNPs and INDELs separately.
3. Genotype concordance and no-call counts.
4. Stratified performance in difficult-to-map, low-complexity, MHC and medically relevant regions.
5. Callable-region and benchmark-region denominators.
6. Coverage, duplication, insert size, mapping, contamination, sex and identity QC.
7. Runtime, peak memory, storage, tool/container versions and complete provenance.

“Same or better” is allowed only for a named metric and matched stratum when the measured value
supports it. It must never be generalized from one caller, region, sample, or variant class to the
whole pipeline.

## Current execution blockers

Preflight on 2026-09-01 found:

- 29 GB free storage, 15 GiB RAM, 9 CPUs and no swap;
- no Nextflow, Docker, Singularity or Apptainer;
- no samtools, bcftools, BWA-MEM2, GATK or DeepVariant;
- no HG002 WGS FASTQs or matching GIAB truth VCF/BED;
- no configured GRCh38 FASTA, indexes, dictionary, annotation, known-sites or blacklist bundle;
- repository inputs consist only of two tiny single-end cleaned FASTQs with no truth data.

This workspace therefore cannot execute the selected full-genome comparison. A storage-backed
HPC or cloud runner with a container runtime is required. Until a completed signed benchmark
report is ingested, all comparison entries remain `NOT_EVALUATED` and all accuracy claims remain
`NO_ACCURACY_CLAIM`.

## Acceptance gate

A benchmark may change to `EVALUATED` only when its report includes input and resource checksums,
the query VCF checksum, truth VCF/BED versions, benchmark command, evaluator version, stratified
metrics, logs, and an artifact location. Missing evidence keeps the status `NOT_EVALUATED`.

## Production WGS/WES support

Bio-Nexus now exposes a production launch planner at `POST /api/ngs/v2/production/plan` for
human WGS and WES from FASTQ, BAM or CRAM inputs. It supports singleton, cohort, duo, trio and
family models across Docker, Singularity, Apptainer, SLURM and AWS Batch execution profiles.
Plans pin `nf-core/sarek` 3.10.0, return a non-shell argument array, declare required artifacts
and provenance, and block incomplete WES or cluster/cloud plans before launch.

The planner is not the compute worker. The deployment must stage private inputs and references
on an authorized durable worker, execute the returned argument array without shell interpolation,
then import the actual run trace, reports, checksums, QC, alignment and variant artifacts. Until
that import is implemented and completes, the plan remains `PLANNED` and never `EXECUTED`.

## Clinical-intent software gate

`POST /api/ngs/v2/clinical/evaluate` evaluates a signed evidence package. The gate requires:

- a server-verified signature over the full evidence payload;
- an assay-validation record and completed pinned workflow;
- reference, sample-sheet, input and container provenance;
- required artifacts plus run, identity, contamination and sex/ploidy QC;
- a non-synthetic truth set, confident-region checksum, matched sample/reference/regions,
  class-specific SNP/INDEL metrics and a passed approved benchmark protocol;
- authorized human review, release signature and no unresolved deviations.

If `NGS_CLINICAL_EVIDENCE_HMAC_KEY` is not configured, or any required evidence is missing, the
gate returns `NOT_CLINICALLY_RELEASABLE`. A complete signed package can return
`SOFTWARE_GATE_PASSED`, but `clinically_validated` remains `false`: the software does not replace
laboratory validation, accreditation, jurisdictional compliance or report authorization.

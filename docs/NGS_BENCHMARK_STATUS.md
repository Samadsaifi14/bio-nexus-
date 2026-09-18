# NGS benchmark status

Last reviewed: 2026-09-19

## Current conclusion

BioNexus has **not** been shown to match or outperform nf-core/sarek for production germline
accuracy. The product now has two deliberately separate execution classes: (1) an exploratory,
sampled Python preview for bounded teaching/UI evidence and (2) configured durable production
execution that submits pinned nf-core workflows through local, SLURM or AWS Batch adapters.
Neither the existence nor successful execution of a production adapter establishes variant-calling
accuracy. BioNexus-produced germline accuracy remains `NOT_EVALUATED` until a matched GIAB
benchmark is completed and retained.

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

## Current production-benchmark requirement

The repository now contains durable production executor adapters, but the selected full HG002
experiment still requires a storage-backed execution environment with staged HG002 reads, the
matching GRCh38 reference/resource bundle, the accepted GIAB truth VCF and confident-region BED,
Nextflow and an appropriate container runtime. Local, SLURM and AWS Batch adapters fail closed
when their preflight requirements are not configured.

The retained real HG002 chr20 benchmark currently exercises the hap.py truth-evaluation harness
against an independent public query callset. It verifies the evaluator path only; those calls were
not produced by BioNexus/Sarek. Until a BioNexus production Sarek callset is generated and a
complete matched benchmark report is retained, production accuracy remains `NOT_EVALUATED` and
the claim state remains `NO_ACCURACY_CLAIM`.

## Acceptance gate

A benchmark may change to `EVALUATED` only when its report includes input and resource checksums,
the query VCF checksum, truth VCF/BED versions, benchmark command, evaluator version, stratified
metrics, logs, and an artifact location. Missing evidence keeps the status `NOT_EVALUATED`.

## Production WGS/WES support

BioNexus exposes a production plan/submit/status/artifact path for human WGS/WES. Plans pin
`nf-core/sarek` 3.10.0, return a non-shell argument array, declare required artifacts and
provenance, and block incomplete WES or executor configurations before launch.

When explicitly enabled and preflight-ready, the production executor can submit the validated
command to a durable local worker, SLURM or AWS Batch. The run record preserves workflow/revision,
executor identity and the launch contract; artifact import inventories the observed output groups.
Production execution never falls back to the exploratory Python preview. An unavailable executor
therefore blocks submission rather than producing a surrogate result.

A `SUBMITTED` or `SUCCEEDED` workflow state means that the configured execution adapter handled
the pinned workflow. It does **not** mean that the caller is scientifically validated against GIAB,
nor does it establish clinical validity.

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

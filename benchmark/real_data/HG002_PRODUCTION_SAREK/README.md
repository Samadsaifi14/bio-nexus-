# HG002 production germline benchmark — external execution contract

This package defines the **next publication-grade, end-to-end germline experiment** for BioNexus. It is intentionally separate from the smaller retained chromosome-20 real-callset evaluation fixture.

The experiment is not marked executed in this repository. It requires a durable HPC/cloud worker with enough storage and compute for ~35x paired-end whole-genome FASTQ input, nf-core/sarek, reference resources and retained outputs. The BioNexus production planner is an orchestration/evidence contract; it is not itself the compute worker.

## Biological sample and reads

Sample: **GIAB HG002 / NA24385**.

Use the publicly released PrecisionFDA Truth Challenge V2 Illumina PCR-free 35x data from the NIST data repository (DOI `10.18434/mds2-2336`):

- `HG002.novaseq.pcr-free.35x.R1.fastq.gz` (~29.9 GB)
- `HG002.novaseq.pcr-free.35x.R2.fastq.gz` (~31.0 GB)

NIST public download base:

`https://opendata.nist.gov/pdrsrv/mds2-2336/input_fastqs/`

Before analysis, retain source URLs, byte sizes and locally computed SHA-256 hashes. Do not copy a checksum from an unrelated mirror.

## Truth set

For a new 2026 production benchmark, use the then-current accepted **NIST GIAB HG002 v5.0q** benchmark and the matching GRCh38 benchmark regions/resources. NIST states that HG002 v5.0q supersedes v4.2.1 for HG002; v4.2.1 remains useful only for explicitly historical/stable fixtures such as the retained chr20 benchmark elsewhere in this repository.

Authoritative release root:

`https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/AshkenazimTrio/HG002_NA24385_son/v5.0q/`

Read the release README before execution and retain it in the evidence bundle. The exact VCF/BED/reference files selected must be mutually compatible and their SHA-256 values must be recorded before hap.py evaluation.

## Pinned production workflow

- workflow: `nf-core/sarek`
- release: **3.10.0**
- execution engine: Nextflow
- profile: deployment-specific Docker, Singularity/Apptainer, SLURM or AWS Batch
- germline caller for the primary declared comparison: **DeepVariant**
- mapping: a Sarek-supported aligner declared before execution (recommended `bwa-mem2` for the linear GRCh38 run)
- benchmark evaluator: **hap.py**, with GIAB benchmark regions and the matched reference

The exact Sarek release, Nextflow version, container digests, command argv, executor configuration and all reference-resource hashes must be retained.

## Samplesheet

A template is supplied as `samplesheet.csv`. Replace `/data/...` with durable worker-local or mounted paths after downloading and verifying the two NIST FASTQs.

## Execution outline

```bash
nextflow run nf-core/sarek \
  -r 3.10.0 \
  -profile <docker|singularity|apptainer|institutional-profile> \
  --input benchmark/real_data/HG002_PRODUCTION_SAREK/samplesheet.csv \
  --outdir /results/hg002_sarek_3.10.0 \
  --genome GATK.GRCh38 \
  --aligner bwa-mem2 \
  --tools deepvariant \
  -with-report /results/hg002_sarek_3.10.0/nextflow_report.html \
  -with-trace /results/hg002_sarek_3.10.0/nextflow_trace.tsv \
  -with-timeline /results/hg002_sarek_3.10.0/nextflow_timeline.html \
  -with-dag /results/hg002_sarek_3.10.0/nextflow_dag.html
```

The production operator must confirm that the reference used for calling is compatible with the selected GIAB v5.0q GRCh38 truth resources. If the release README requires a specific GIAB/GRC reference variant, use that exact reference instead of relying on an alias such as `GATK.GRCh38`.

The primary query VCF is the Sarek DeepVariant small-variant VCF for HG002. Evaluate it with hap.py against the selected v5.0q truth VCF and benchmark BED, not against a synthetic fixture.

## Required retained outputs

At minimum retain:

1. read URLs, byte sizes and SHA-256 values;
2. samplesheet checksum;
3. exact reference FASTA/build identity and checksum plus indexes/dictionary hashes;
4. GIAB v5.0q README, truth VCF and benchmark BED identifiers/checksums;
5. Sarek 3.10.0 revision, Nextflow version, profile and container digests;
6. complete Nextflow command, config, trace, report, timeline and DAG;
7. MultiQC and mapping/coverage/duplication/insert-size QC;
8. identity, contamination and sex/ploidy QC where available;
9. DeepVariant VCF/gVCF plus indexes and checksums;
10. hap.py summary and extended outputs;
11. SNP and INDEL TP, FP, FN, precision, recall and F1 separately;
12. genotype concordance/no-call information and benchmark-region denominators;
13. GA4GH/GIAB difficult-region stratification metrics when configured;
14. runtime, peak memory/storage and executor provenance;
15. a final SHA-256 manifest of the retained evidence bundle.

## Claim gate

Until this exact or an explicitly amended, preregistered production experiment completes with retained evidence, BioNexus must continue to report production germline accuracy as **NOT_EVALUATED**.

A completed run may support only the metrics that were actually measured for the named caller, sample, truth release, reference, confident regions and stratifications. It must not be generalized into a claim that BioNexus is universally more accurate than nf-core, Galaxy, NCBI or another platform.

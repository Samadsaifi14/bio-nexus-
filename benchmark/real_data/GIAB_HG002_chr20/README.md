# HG002 real-callset truth benchmark (GRCh38 chromosome 20)

This benchmark is a **real-data, region-limited validation of the BioNexus germline truth-evaluation path**. It is deliberately smaller than a production whole-genome Sarek benchmark so that the evidence harness can be executed and retained in ordinary CI infrastructure.

It does **not** claim that BioNexus production WGS/WES has been biologically validated end-to-end. The query VCF is an independently generated public DeepVariant callset for GIAB HG002; the truth is the NIST GIAB HG002 benchmark. The purpose is to verify the formal truth-set evaluation contract, metric extraction, provenance, checksums and claim boundaries on real human data before the larger production Sarek benchmark is run on HPC/cloud infrastructure.

The executable contract lives in `.github/workflows/giab-hg002-real-callset-benchmark.yml`; successful runs retain the complete evaluation bundle as a GitHub Actions artifact rather than treating CI status alone as scientific evidence.

## Declared source data

- Sample: **GIAB HG002 / NA24385**
- Reference coordinate system: **GRCh38 / hg38 chromosome 20**
- Truth: NIST GIAB HG002 v4.2.1 small-variant benchmark VCF and confident-region BED
- Query: public 40x PCR-free HiSeq X **DeepVariant v1.0** HG002 GRCh38 callset used in published GIAB stratification work
- Evaluator: **hap.py 0.3.15**
- Region: **chr20 only**

NIST now lists HG002 v5.0q as the newer HG002 benchmark and describes v4.2.1 as deprecated for HG002. This fixture retains v4.2.1 because the public DeepVariant callset and extensive published benchmarking examples are directly aligned to this GRCh38 truth resource. It must therefore be described as a stable, published **region-limited validation fixture**, not as the current final HG002 benchmark for a production pipeline. The publication-grade end-to-end Sarek benchmark should use the then-current accepted GIAB release with matched reference/resources.

## Why chromosome 20

The full HG002 WGS benchmark requires large read datasets, a full reference bundle and durable compute. Restricting an already-called real HG002 VCF and the accepted truth set to chr20 keeps the validation computationally practical while still exercising real variant representation, genotypes, false positives and false negatives. Every result is labelled region-limited.

## Acceptance contract

The workflow must retain:

- original URL/source identifiers;
- SHA-256 values for downloaded source files;
- exact chr20 truth/query VCFs and confident-region BED checksums;
- reference FASTA checksum;
- evaluator image/version information;
- complete hap.py summary and extended tables;
- SNP and INDEL precision, recall and F1 from the `ALL` rows;
- the exact Git commit and execution environment;
- a final artifact checksum manifest.

A successful run allows only a statement such as:

> Under the declared HG002/GRCh38 chromosome-20 fixture, the retained public DeepVariant query callset achieved the reported SNP/INDEL metrics against the GIAB v4.2.1 truth set when evaluated through the BioNexus benchmark harness.

It does **not** support a claim that BioNexus itself produced those variant calls, that BioNexus is more accurate than another platform, or that whole-genome performance is represented.

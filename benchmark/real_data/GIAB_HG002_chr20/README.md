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

## Retained execution

A retained run completed successfully in GitHub Actions on 2026-09-15 (run `34953070610`, source commit `0741ed4b228ce244fad4961cee575fc14edb2d6e`). The evidence artifact was `giab-hg002-grch38-chr20-real-callset` (artifact ID `10390485858`), and the uploaded ZIP SHA-256 reported by GitHub Actions was:

`ee8507a34fd13dc4800034f3dd4268d3342466ef81c76f7372d894ddbd5e0178`

The retained hap.py `ALL` rows were:

| Variant class | Truth total | Truth TP | Truth FN | Query total | Query FP | Query UNK | Recall | Precision | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SNP | 71,333 | 70,948 | 385 | 87,245 | 46 | 16,197 | 0.994603 | 0.999353 | 0.996972 |
| INDEL | 11,256 | 11,188 | 68 | 21,195 | 28 | 9,552 | 0.993959 | 0.997595 | 0.995774 |

`QUERY.UNK` is retained explicitly and must not be silently treated as false positive or true negative. These metrics describe the declared public DeepVariant callset against GIAB v4.2.1 within the declared chr20 confident regions; they do not measure a BioNexus-produced callset.

Source file SHA-256 values retained by the workflow include:

- GIAB truth VCF: `adb4d4a50048aa13353a06b84fcfcbca09a5d17525efaa4cea44f8822e81175c`
- GIAB confident-region BED: `fba9a57c36ec88e5d14ea3e259c8866c7935f4998d3ec0fa2d6c3962da5b5575`
- public DeepVariant query VCF: `467015b70e187b7093e2044c50d7f5b7f15d422f52984f4747fb717b4bc788e4`
- UCSC chr20 FASTA gzip: `271ca0ee4247c2fa30c8491764ad8acd4bdde8eb3cf314f0720235010ae85c9f`
- hap.py container digest: `sha256:492574403bf5cc648cf9c297957cc2eac60cbbc7da1a968984bafad060536bdc`

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

A successful run allows only the following class of statement:

> Under the declared HG002/GRCh38 chromosome-20 fixture, the retained public DeepVariant query callset achieved SNP precision 0.999353, recall 0.994603 and F1 0.996972, and INDEL precision 0.997595, recall 0.993959 and F1 0.995774, against the GIAB v4.2.1 truth set within the declared confident regions when evaluated through the BioNexus benchmark harness.

It does **not** support a claim that BioNexus itself produced those variant calls, that BioNexus is more accurate than another platform, or that whole-genome performance is represented.

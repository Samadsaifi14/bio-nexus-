# Portable NGS positive-control benchmark

This benchmark proves a narrow statement: with identical samtools/bcftools versions, inputs,
parameters and filters, Bio-Nexus direct execution and Nextflow orchestration emit the same
normalized SNP result. A Galaxy wrapper invokes the same contract.

It does **not** prove accuracy on real samples or parity with nf-core/sarek or Galaxy as whole
platforms. The fixture contains one synthetic heterozygous SNP in an easy 200 bp target.

## Verified result

| Field | Value |
|---|---|
| Variant | `chrTiny:50 C>G` |
| Genotype | `0/1` |
| Depth | `20` |
| Allelic depth | `10,10` |
| TP / FP / FN | `1 / 0 / 0` |
| Precision / recall / F1 | `1.0 / 1.0 / 1.0` |
| Normalized result SHA-256 | `cefef322e336202da82549c1d5c09cf546a70b4aacfe9d1cc7e090a8aa23bbb1` |

Direct and Nextflow executions completed. The Galaxy wrapper passed Planemo lint and its exact
command completed with the same checksum. A local Galaxy 25.1 server test did not complete because
the environment proxy interrupted Galaxy's pinned dependency bootstrap; it remains separately
labelled and is not claimed as a Galaxy-server execution.

## Reproduce

Generate the fixture:

```bash
python generate_fixture.py --outdir fixtures
```

Direct execution:

```bash
SAMTOOLS_BIN=samtools BCFTOOLS_BIN=bcftools bash run_calling.sh \
  fixtures/reference.fa fixtures/reads.sam \
  results/direct/calls.vcf results/direct/calls.tsv results/direct/metrics.json
```

Nextflow execution:

```bash
SAMTOOLS_BIN=samtools BCFTOOLS_BIN=bcftools nextflow run main.nf \
  --reference fixtures/reference.fa --sam fixtures/reads.sam \
  --outdir results/nextflow
```

The Galaxy wrapper is `galaxy/bionexus_tiny_variant.xml` and declares samtools 1.24 and bcftools
1.24. Run `planemo lint galaxy/bionexus_tiny_variant.xml` before publishing it.

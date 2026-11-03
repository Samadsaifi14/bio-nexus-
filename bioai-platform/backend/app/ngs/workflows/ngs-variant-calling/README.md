# BioNexus Nextflow NGS workflow

This directory contains the real Nextflow DSL2 workflow used by the in-app NGS
runner (`/analyze/ngs`). It is shipped inside the backend so the executed
definition is always inspectable.

## Processes

| Process | Tool | Purpose |
|---|---|---|
| `INDEX_REFERENCE` | `samtools faidx` | Build the FASTA index required by mpileup. |
| `SORT_BAM` | `samtools view` + `samtools sort` | Convert the SAM input to a coordinate-sorted BAM. |
| `INDEX_BAM` | `samtools index` | Build the BAM index. |
| `CALL_VARIANTS` | `bcftools mpileup` + `bcftools call -mv` | Pile up reads and call small variants. |
| `FILTER_VARIANTS` | `bcftools filter` + `bcftools query` | Apply `QUAL`/`FORMAT/DP` filters and emit a TSV call table. |
| `VARIANT_METRICS` | Python helper | Record observed call counts, mapped reads, depth and tool versions. |
| `EVALUATE_TRUTH` | Python helper | Score exact CHROM/POS/REF/ALT concordance against the declared truth set. |

The DAG is linear except for `VARIANT_METRICS`, which consumes the filtered VCF,
the call table, the BAM/index and the reference/index, and `EVALUATE_TRUTH`,
which consumes the truth set and the call table.

## Run it locally

Build the tool image once (Nextflow, samtools, bcftools and Python in one image):

```bash
docker build -t bionexus/ngs-tools:1.0 .
```

Run directly:

```bash
docker run --rm \
  -v "$PWD:/opt/workflow:ro" \
  -v "$PWD/run:/work" \
  -w /work \
  bionexus/ngs-tools:1.0 \
  nextflow run /opt/workflow/main.nf \
    -c /opt/workflow/nextflow.config \
    --reference /work/fixtures/reference.fa \
    --sam /work/fixtures/reads.sam \
    --truth /work/fixtures/truth.tsv \
    --outdir /work/results \
    -ansi-log false
```

The backend does the same through `app.ngs.nextflow_runner`, with inputs copied
into a durable run directory and status recorded by `nextflow_worker.py`.

With a host Nextflow installation and Docker, each process can instead run in the
same image:

```bash
nextflow run main.nf -profile docker \
  --reference fixtures/reference.fa --sam fixtures/reads.sam \
  --truth fixtures/truth.tsv --outdir results
```

## Artifacts

Every successful run publishes:

- `results/pipeline_info/trace.txt` — per-process task trace
- `results/pipeline_info/report.html` — Nextflow execution report
- `results/pipeline_info/dag.html` — workflow DAG
- `results/pipeline_info/timeline.html` — task timeline
- `results/variants/calls.vcf` — filtered calls
- `results/variants/calls.tsv` — call table
- `results/metrics/metrics.json` — observed run metrics and tool versions
- `results/benchmark/benchmark.json` — truth concordance

The committed run in `app/ngs/nextflow_evidence/` was produced by this workflow
on a Docker-capable workstation. Its manifest records the Nextflow version, tool
versions, container digest, command hash, process trace and SHA-256 for every
artifact. The hosted backend cannot run Docker, so it reports the runner as
unavailable and serves this evidence read-only rather than pretending to execute
a workflow.

## Scope and limitations

The fixture is a deterministic synthetic positive control: 20 reads of 100 bp
over a 200 bp reference with one heterozygous SNP (`chrTiny:50 C>G`, `0/1`,
depth 20). It validates deterministic execution and exact truth concordance. It
does **not** establish real-sample accuracy, performance on difficult regions,
indel/structural-variant/CNV calling, clinical validity, or parity with
nf-core/sarek as a whole.

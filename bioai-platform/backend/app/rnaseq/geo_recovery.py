"""Downloadable, source-linked recovery instructions; no hidden method substitution."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

from app.rnaseq.geo_counts import GEO_URL, GeoCountsError

TEMPLATES = Path(__file__).with_name("recovery_templates")


def recovery_bundle(series: dict) -> bytes:
    if series.get("workflow_issue"):
        raise GeoCountsError(series["workflow_issue"])
    accession = series["accession"]
    metadata = io.StringIO()
    writer = csv.writer(metadata, delimiter="\t", lineterminator="\n")
    writer.writerow(["sample", "condition", "experimental_unit"])
    for sample in series["samples"]:
        writer.writerow([sample["accession"], "", ""])
    author_request = (
        f"To: {series.get('contact_email') or '[Find the corresponding author in the GEO source record]'}\n"
        f"Subject: Request for unnormalized gene counts and sample metadata for {accession}\n\n"
        f"Dear corresponding author,\n\nI am analysing your publicly deposited study {accession}. "
        "The available expression supplements include normalized values. Could you please share the "
        "unnormalized gene-level read/fragment count matrix, sample-to-column mapping, biological replicate "
        "and batch metadata, and reference genome/annotation versions? If counts are unavailable, could "
        "you confirm the raw-read accessions and quantification method?\n\nThank you.\n[Your name and affiliation]\n"
    )
    contents = {
        "source_record.json": json.dumps(series, indent=2),
        "metadata_to_review.tsv": metadata.getvalue(),
        "author_request_draft.txt": author_request,
        "bam_samples.tsv": "bam\tsample\n",
        "bam_paths.txt": "",
        "quantfiles.tsv": "sample\tquant_file\n",
        "tx2gene.tsv": "transcript\tgene\n",
        "README.md": f"""# Expression-data recovery for {accession}

Source: {GEO_URL}?acc={accession}
This package contains instructions/templates, not regenerated counts or a completed analysis.
GEO Series and GSM supplements were inspected. Candidate raw matrices: {', '.join(series.get('raw_candidates', [])) or 'none currently listed'}.
Candidates still need content and source validation. A one-sample file is not a cohort matrix.
Check source_record.json for sample characteristics and supplement links. Select one coherent
experiment/cohort; do not mix figure panels, library assays, or technical replicates.

## 1. Obtain deposited counts
Use an eligible supplement in BioNexus, or extract an archive and upload a verified raw-count matrix
with reviewed metadata. If authors did not deposit counts, use author_request_draft.txt as an email
draft. Nothing has been sent. Keep the authors' sample mapping and reference/method details.

## 2. Regenerate from reads (preferred when counts are unavailable)
Inspect the linked SRA/ENA records for the study's actual read accessions. Obtain all selected reads
and checksums through the repository's supported downloader. Review species, reference FASTA/GTF,
library layout, strandedness, biological units, batches and read QC before quantification.

### STAR/HISAT2 alignment plus featureCounts
Generate sorted/indexed BAMs with a reviewed splice-aware alignment workflow. Populate bam_paths.txt
and bam_samples.tsv with the exact BAM column names and sample IDs. Confirm featureCounts version
supports --countReadPairs for paired libraries. Count fragments with the correct strand code.

    bash featurecounts.sh annotation.gtf bam_paths.txt output 0 paired
    python featurecounts_to_matrix.py --input output/featurecounts_native.tsv --bam-samples bam_samples.tsv --output output/raw_counts.tsv

Review native assignment summaries, then upload output/raw_counts.tsv and completed metadata to
BioNexus. Gene length and location columns are removed, not interpreted as sample counts. Do not
silently merge transcript isoforms, fractional assignments or incompatible annotations.

### Salmon plus tximport
Quantify selected FASTQs with a versioned, matching Salmon transcriptome index. Put one real quant.sf
path per sample in quantfiles.tsv. Fill tx2gene.tsv from that same transcript annotation/index.
Complete metadata_to_review.tsv, rename it metadata.tsv and retain only the selected sample cohort.
Install tximport and DESeq2 with BiocManager in R. Run:

    Rscript tximport_deseq2.R quantfiles.tsv tx2gene.tsv metadata.tsv reference_group test_group tximport_results

An optional final comma-separated covariate argument, such as batch, adds recorded covariates.
The script keeps tximport counts and length corrections in dds_with_length_offsets.rds and generates
results and an MA plot. This path runs in your R environment; BioNexus's raw-matrix endpoint does not
currently import a tximport object. A TPM/FPKM matrix alone is not a Salmon quantification object.

## 3. Only normalized expression is available
Use the separate exploratory limma-trend script only after reviewing how values were normalized.
Prepare an unlogged gene-by-sample TSV containing unique feature IDs and numeric sample columns only.
Remove annotation columns and map columns explicitly to metadata sample IDs. Install limma in R.

    Rscript limma_trend.R expression.tsv metadata.tsv reference_group test_group FPKM limma_results

Use TPM instead of FPKM only if those are the actual source units. Optional final covariates work as
above. The script records log2(expression + 1), an expression >= 1 filter in at least the smaller-group
sample count, eBayes(trend=TRUE), BH adjustment, design and package versions. It exports results and
SVG/PDF/PNG volcano plots. This is an exploratory continuous-expression analysis, not DESeq2 or voom.
Inspect the mean-variance assumptions, original between-sample normalization and pseudocount/filter
sensitivity. TPM composition can distort comparisons; no universal normalized-data fallback is guaranteed.

## No FPKM back-calculation as a DESeq2 workaround
Do not round FPKM/TPM or reconstruct pseudo-counts to pass BioNexus's raw-count validation. Rounded
values lose information about counts, effective lengths, library denominators and quantification
uncertainty. They do not restore the count model. tximport is different: it uses actual quantifier
outputs and their corresponding length corrections. voom also needs counts, not FPKM/TPM.

The templates leave groups and biological units blank deliberately. They must be reviewed. No files
are fetched from arbitrary URLs and no alignment, author email or statistical analysis occurs merely
by downloading this package. Repeated-measure/factorial models require a separately reviewed design.

References:
- https://bioconductor.org/packages/release/bioc/vignettes/DESeq2/inst/doc/DESeq2.html
- https://bioconductor.org/packages/release/bioc/vignettes/tximport/inst/doc/tximport.html
- https://bioconductor.org/packages/release/bioc/vignettes/limma/inst/doc/usersguide.pdf
""",
    }
    for path in sorted(TEMPLATES.iterdir()):
        if path.is_file() and path.suffix in {".R", ".py", ".sh"}:
            contents[path.name] = path.read_text()
    contents["checksums.sha256"] = "".join(f"{hashlib.sha256(body.encode()).hexdigest()}  {name}\n" for name, body in contents.items())
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
        for name, body in contents.items():
            handle.writestr(name, body)
    return archive.getvalue()

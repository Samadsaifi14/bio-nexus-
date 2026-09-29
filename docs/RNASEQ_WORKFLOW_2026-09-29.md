# RNA-seq workflow in the NGS workspace

The NGS screen follows the supplied ten-stage RNA-seq sequence: question/design; GEO/SRA selection; FASTQ acquisition; raw QC; contextual identity/homology check; matching FASTA/GTF reference; alignment/quantification; raw counts; sample/design QC; differential expression.

## What is executable

- **GEO discovery** searches NCBI's GDS E-utilities for public Series and opens the source record. Inspect its sample metadata, supplementary files and SRA links. Search results alone do not supply an analysis-ready matrix.
- **FASTQ production** uses the existing pinned nf-core/rnaseq 3.26.0 runner when a staged sample sheet, reference, worker and storage are configured. The screen reports capability status and never calls a plan an executed analysis.
- **Count-matrix statistics** accept a raw integer gene-by-sample TSV and a separate sample metadata TSV. The existing R/DESeq2 engine audits design, filters, normalizes, computes VST sample QC, tests the declared contrast and emits downloadable tables and figures.
- **SALS practical**: the uploaded teaching matrix has 22,085 genes, 18 samples (8 healthy, 10 SALS), no malformed rows, and 20,169 genes meeting at least 10 counts in at least 8 samples. Upload the complete matrix and a matching metadata file to run the full practical. The bundled demo remains a 221-gene regression subset.

GEO studies do not have one universal processed-data format. A GEO result must be inspected to establish whether the supplementary file is raw integer counts, normalized expression, or another assay. The current GEO search does not automatically convert arbitrary Series to DESeq2 input. SRA acquisition and homology checks remain separate operations; the ten-stage list is a guide to the scientific sequence, not a claim that every stage was run by a search result.

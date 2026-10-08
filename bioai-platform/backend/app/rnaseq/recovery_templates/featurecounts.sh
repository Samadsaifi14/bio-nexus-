#!/usr/bin/env bash
set -euo pipefail
# Run after reviewed STAR/HISAT2 alignment, sorting and indexing.
# Usage: bash featurecounts.sh annotation.gtf bam_paths.txt output_directory 0|1|2 single|paired
# bam_paths.txt: one BAM path per line, in the order used in sample metadata.
[[ $# == 5 ]] || { echo 'Expected GTF, BAM-list, output directory, strand code and single|paired' >&2; exit 1; }
[[ "$4" =~ ^[012]$ ]] || { echo 'Strand code must be 0, 1 or 2, based on the library protocol' >&2; exit 1; }
[[ "$5" == single || "$5" == paired ]] || { echo 'Layout must be single or paired' >&2; exit 1; }
[[ -f "$1" && -f "$2" ]] || exit 1
command -v featureCounts >/dev/null
mapfile -t bam_paths < "$2"
[[ ${#bam_paths[@]} -ge 4 ]] || { echo 'At least four BAM files are required for the replicated comparison' >&2; exit 1; }
for bam in "${bam_paths[@]}"; do [[ -f "$bam" ]] || { echo 'A listed BAM file is missing' >&2; exit 1; }; done
mkdir -p "$3"
layout=()
[[ "$5" != paired ]] || layout=(-p --countReadPairs)
# Integer assignment only: no fractional counting, no automatic multi-mapping assignment.
featureCounts -T 4 -t exon -g gene_id -s "$4" "${layout[@]}" -a "$1" -o "$3/featurecounts_native.tsv" "${bam_paths[@]}"
featureCounts -v > "$3/featurecounts_version.txt" 2>&1
sha256sum -- "$1" "$2" "${bam_paths[@]}" > "$3/input_checksums.sha256"
# The native output includes annotation columns. Use the supplied converter and reviewed
# bam_samples.tsv to make the gene-by-sample matrix; inspect assignment summaries first.

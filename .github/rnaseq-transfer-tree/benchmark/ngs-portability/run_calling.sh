#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 5 ]; then
  echo "usage: run_calling.sh REFERENCE_FASTA INPUT_SAM OUTPUT_VCF OUTPUT_TSV OUTPUT_METRICS" >&2
  exit 2
fi

reference_fasta="$1"
input_sam="$2"
output_vcf="$3"
output_tsv="$4"
output_metrics="$5"

: "${SAMTOOLS_BIN:=samtools}"
: "${BCFTOOLS_BIN:=bcftools}"

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

"$SAMTOOLS_BIN" faidx "$reference_fasta"
"$SAMTOOLS_BIN" view -bS "$input_sam" | "$SAMTOOLS_BIN" sort -o "$work_dir/reads.bam"
"$SAMTOOLS_BIN" index "$work_dir/reads.bam"
"$BCFTOOLS_BIN" mpileup -Ou -f "$reference_fasta" -a FORMAT/DP,FORMAT/AD "$work_dir/reads.bam" \
  | "$BCFTOOLS_BIN" call -mv -Ov -o "$work_dir/raw.vcf"
"$BCFTOOLS_BIN" filter -i 'QUAL>=20 && FORMAT/DP>=10' "$work_dir/raw.vcf" -Ov -o "$output_vcf"

{
  printf 'CHROM\tPOS\tREF\tALT\tGT\tDP\tAD\n'
  "$BCFTOOLS_BIN" query -f '%CHROM\t%POS\t%REF\t%ALT[\t%GT\t%DP\t%AD]\n' "$output_vcf"
} > "$output_tsv"

called_variants="$(grep -vc '^#' "$output_vcf" || true)"
mapped_reads="$("$SAMTOOLS_BIN" view -c -F 4 "$work_dir/reads.bam")"
depth_at_truth="$("$SAMTOOLS_BIN" depth -r chrTiny:50-50 "$work_dir/reads.bam" | awk '{print $3}')"
printf '{"called_variants":%s,"mapped_reads":%s,"depth_at_truth":%s,"filter":"QUAL>=20 && FORMAT/DP>=10"}\n' \
  "$called_variants" "$mapped_reads" "${depth_at_truth:-0}" > "$output_metrics"

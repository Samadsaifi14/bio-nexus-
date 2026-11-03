#!/usr/bin/env nextflow
// BioNexus NGS small-variant-calling workflow.
//
// This is a real Nextflow DSL2 workflow. It performs reference indexing, SAM->BAM
// conversion/sorting, BAM indexing, bcftools mpileup/call, quality filtering,
// call-table generation, run metrics and (optionally) truth concordance scoring.
// Every process emits a published artifact so a completed run is auditable.

nextflow.enable.dsl = 2

params.reference = null
params.sam       = null
params.truth     = null
params.outdir    = 'results'
params.min_qual  = 20
params.min_dp    = 10
params.threads   = 1

log.info """\
BioNexus NGS variant-calling workflow
  reference : ${params.reference}
  sam       : ${params.sam}
  truth     : ${params.truth ?: 'not supplied'}
  filter    : QUAL>=${params.min_qual} && FORMAT/DP>=${params.min_dp}
  outdir    : ${params.outdir}
"""

process INDEX_REFERENCE {
    tag "${reference.name}"
    publishDir "${params.outdir}/reference", mode: 'copy'

    input:
    path reference

    output:
    path "${reference.name}.fai", emit: fai
    path reference, emit: fasta

    script:
    """
    samtools faidx ${reference}
    """
}

process SORT_BAM {
    tag "${sam.name}"
    publishDir "${params.outdir}/alignment", mode: 'copy'

    input:
    path sam

    output:
    path 'reads.bam', emit: bam

    script:
    """
    samtools view -@ ${params.threads} -bS ${sam} | samtools sort -@ ${params.threads} -o reads.bam -
    """
}

process INDEX_BAM {
    publishDir "${params.outdir}/alignment", mode: 'copy'

    input:
    path bam

    output:
    path 'reads.bam.bai', emit: bai
    path bam, emit: bam_out

    script:
    """
    samtools index ${bam}
    """
}

process CALL_VARIANTS {
    publishDir "${params.outdir}/variants", mode: 'copy'

    input:
    path reference
    path reference_index
    path bam
    path bam_index

    output:
    path 'raw.vcf', emit: raw

    script:
    """
    bcftools mpileup -Ou -f ${reference} -a FORMAT/DP,FORMAT/AD ${bam} \\
      | bcftools call -mv -Ov -o raw.vcf
    """
}

process FILTER_VARIANTS {
    publishDir "${params.outdir}/variants", mode: 'copy'

    input:
    path raw_vcf

    output:
    path 'calls.vcf', emit: vcf
    path 'calls.tsv', emit: tsv

    script:
    """
    bcftools filter -i 'QUAL>=${params.min_qual} && FORMAT/DP>=${params.min_dp}' ${raw_vcf} -Ov -o calls.vcf
    {
      printf 'CHROM\\tPOS\\tREF\\tALT\\tGT\\tDP\\tAD\\n'
      bcftools query -f '%CHROM\\t%POS\\t%REF\\t%ALT[\\t%GT\\t%DP\\t%AD]\\n' calls.vcf
    } > calls.tsv
    """
}

process VARIANT_METRICS {
    publishDir "${params.outdir}/metrics", mode: 'copy'

    input:
    path vcf
    path tsv
    path bam
    path bam_index
    path reference
    path reference_index

    output:
    path 'metrics.json', emit: metrics

    script:
    """
    python3 ${baseDir}/bin/compute_metrics.py \\
      --vcf ${vcf} --tsv ${tsv} --bam ${bam} --fai ${reference_index} \\
      --min-qual ${params.min_qual} --min-dp ${params.min_dp} \\
      --output metrics.json
    """
}

process EVALUATE_TRUTH {
    publishDir "${params.outdir}/benchmark", mode: 'copy'

    input:
    path truth
    path calls

    output:
    path 'benchmark.json', emit: benchmark

    script:
    """
    python3 ${baseDir}/bin/evaluate_truth.py \\
      --truth ${truth} --calls ${calls} --output benchmark.json
    """
}

workflow {
    if (!params.reference) {
        error 'Both --reference and --sam are required'
    }
    if (!params.sam) {
        error 'Both --reference and --sam are required'
    }

    reference_ch = file(params.reference)
    sam_ch       = file(params.sam)

    INDEX_REFERENCE(reference_ch)
    SORT_BAM(sam_ch)
    INDEX_BAM(SORT_BAM.out.bam)

    CALL_VARIANTS(
        INDEX_REFERENCE.out.fasta,
        INDEX_REFERENCE.out.fai,
        SORT_BAM.out.bam,
        INDEX_BAM.out.bai
    )

    FILTER_VARIANTS(CALL_VARIANTS.out.raw)

    VARIANT_METRICS(
        FILTER_VARIANTS.out.vcf,
        FILTER_VARIANTS.out.tsv,
        SORT_BAM.out.bam,
        INDEX_BAM.out.bai,
        INDEX_REFERENCE.out.fasta,
        INDEX_REFERENCE.out.fai
    )

    if (params.truth) {
        EVALUATE_TRUTH(file(params.truth), FILTER_VARIANTS.out.tsv)
    }
}

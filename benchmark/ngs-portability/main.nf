nextflow.enable.dsl=2

params.reference = null
params.sam = null
params.outdir = 'results/nextflow'
params.runner = "${projectDir}/run_calling.sh"

process CALL_VARIANTS {
    publishDir params.outdir, mode: 'copy', overwrite: true

    input:
    path reference
    path sam

    output:
    path 'calls.vcf'
    path 'calls.tsv'
    path 'metrics.json'

    script:
    """
    bash ${params.runner} ${reference} ${sam} calls.vcf calls.tsv metrics.json
    """
}

workflow {
    if (!params.reference || !params.sam) {
        error 'Both --reference and --sam are required'
    }
    CALL_VARIANTS(file(params.reference), file(params.sam))
}

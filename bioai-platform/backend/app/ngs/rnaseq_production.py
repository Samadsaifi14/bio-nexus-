"""Production RNA-seq launch contract using nf-core/rnaseq.

This module plans durable execution; it does not relabel the in-process preview
as a production run. The pinned release and CLI options are explicit so the
experiment fingerprint can record the exact workflow contract.
"""
from __future__ import annotations

import shlex
from typing import Any

from app.models.responses import NgsRnaSeqProductionPlanRequest

RNASEQ_RELEASE = "3.26.0"
SCHEMA_VERSION = "1.0"


def _artifact(artifact_id: str, description: str, patterns: list[str]) -> dict[str, Any]:
    return {"id": artifact_id, "required": True, "description": description, "patterns": patterns}


REQUIRED_ARTIFACTS = [
    _artifact("execution", "Nextflow trace, report and timeline from the executed workflow", ["pipeline_info/execution_trace*.txt", "pipeline_info/execution_report*.html", "pipeline_info/execution_timeline*.html"]),
    _artifact("fastqc", "Raw/processed read QC", ["fastqc/", "fastqc/**/*fastqc*", "trimgalore/fastqc/"]),
    _artifact("multiqc", "Aggregated RNA-seq QC", ["multiqc/multiqc_report.html", "multiqc/multiqc_data/"]),
    _artifact("alignment", "Splice-aware alignment plus index where alignment is enabled", ["star_salmon/**/*.bam|star_rsem/**/*.bam|hisat2/**/*.bam|bowtie2_salmon/**/*.bam", "**/*.bai|**/*.csi"]),
    _artifact("quantification", "Gene/transcript abundance outputs", ["star_salmon/", "star_rsem/", "salmon/", "rsem/", "results/quantification/"]),
    _artifact("counts", "Cross-sample gene/transcript matrices when generated", ["**/*gene_counts*.tsv|**/*transcript_counts*.tsv|**/*gene_tpm*.tsv|**/*transcript_tpm*.tsv"]),
    _artifact("qc_expression", "Expression-level PCA/heatmap and assignment QC when emitted", ["deseq2/", "rseqc/", "qualimap/", "featurecounts/"]),
    _artifact("provenance", "Checksums and immutable workflow/reference identifiers", ["run_manifest.json", "checksums.sha256"]),
]

PROVENANCE_REQUIREMENTS = [
    "nf-core/rnaseq revision and Nextflow version",
    "container image digest for every executed process",
    "sample-sheet SHA-256 and FASTQ checksums",
    "reference FASTA/GTF and generated/prebuilt index checksums",
    "complete command argument array, profile and custom configuration checksum",
    "execution trace with process exit status and retry history",
]


def build_rnaseq_production_plan(request: NgsRnaSeqProductionPlanRequest) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []

    if not request.samplesheet_path.lower().endswith(".csv"):
        blockers.append("nf-core/rnaseq requires a CSV sample sheet for --input.")
    if request.execution_profile in {"slurm", "awsbatch"} and not (request.custom_config or "").strip():
        blockers.append(f"{request.execution_profile} requires a reviewed Nextflow custom configuration.")
    if not request.genome and not (request.fasta and request.gtf):
        blockers.append("Declare either a genome catalogue key or both custom FASTA and GTF resources.")
    if bool(request.fasta) != bool(request.gtf):
        blockers.append("Custom reference mode requires FASTA and GTF together so alignment and quantification use the same annotation basis.")
    if request.aligner == "hisat2" and request.pseudo_aligner is None:
        warnings.append("HISAT2 alone provides genomic alignment but nf-core/rnaseq does not use that route for expression quantification; add Salmon pseudo-alignment or choose STAR-Salmon/RSEM when abundance estimates are required.")
    if request.differential_expression_requested:
        warnings.append("The base nf-core/rnaseq execution provides counts/QC but is not being claimed here as a differential-expression study. A design-aware statistical stage with contrasts and multiple-testing correction must be recorded separately.")
    if request.fusion_detection_requested:
        warnings.append("Fusion detection is not inferred from the base rnaseq workflow. Run a dedicated validated fusion workflow and import its artifacts/provenance separately.")
    if request.strandedness != "auto":
        warnings.append("Library strandedness is a sample-level property and must agree with the nf-core sample-sheet metadata; this planner records the requested expectation but does not override inconsistent sample metadata.")

    argv = [
        "nextflow", "run", "nf-core/rnaseq", "-r", RNASEQ_RELEASE,
        "-profile", request.execution_profile,
        "--input", request.samplesheet_path,
        "--outdir", request.outdir,
        "--aligner", request.aligner,
    ]
    if request.genome:
        argv.extend(["--genome", request.genome])
    if request.fasta and request.gtf:
        argv.extend(["--fasta", request.fasta, "--gtf", request.gtf])
    if request.pseudo_aligner:
        argv.extend(["--pseudo_aligner", request.pseudo_aligner])
    if request.skip_trimming:
        argv.append("--skip_trimming")
    if request.save_trimmed:
        argv.append("--save_trimmed")
    if request.trim_nextseq is not None:
        argv.extend(["--trim_nextseq", str(request.trim_nextseq)])
    if request.custom_config:
        argv.extend(["-c", request.custom_config])

    ready = not blockers
    quantification_expected = request.aligner in {"star_salmon", "star_rsem", "bowtie2_salmon"} or request.pseudo_aligner == "salmon"
    return {
        "schema_version": SCHEMA_VERSION,
        "workflow": {
            "name": "nf-core/rnaseq",
            "revision": RNASEQ_RELEASE,
            "execution_engine": "Nextflow",
            "assay": "RNA-seq",
            "aligner": request.aligner,
            "quantification_expected": str(quantification_expected).lower(),
        },
        "state": "PLANNED" if ready else "BLOCKED",
        "ready_to_launch": ready,
        "blockers": blockers,
        "warnings": warnings,
        "command_argv": argv,
        "command_display": shlex.join(argv),
        "required_artifacts": REQUIRED_ARTIFACTS,
        "provenance_requirements": PROVENANCE_REQUIREMENTS,
        "clinical_boundary": {
            "clinical_intent": False,
            "current_status": "RESEARCH_WORKFLOW_ONLY",
            "reason": "RNA-seq execution and QC do not constitute clinical assay validation, differential-expression inference, or fusion validation without their respective evidence protocols.",
        },
        "analysis_contract": {
            "fastq_qc": "FastQC + MultiQC artifacts required",
            "alignment": request.aligner,
            "quantification_expected": quantification_expected,
            "differential_expression": "SEPARATE_EVIDENCE_REQUIRED" if request.differential_expression_requested else "NOT_REQUESTED",
            "fusion_detection": "SEPARATE_EVIDENCE_REQUIRED" if request.fusion_detection_requested else "NOT_REQUESTED",
            "strandedness_expectation": request.strandedness,
        },
    }

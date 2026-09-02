"""Production Sarek planning and fail-closed clinical software gates.

This module does not execute Nextflow inside the request process. It emits an auditable,
pinned launch contract for a durable compute worker and evaluates imported run evidence.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import shlex
from typing import Any

from app.models.responses import NgsClinicalEvidenceRequest, NgsProductionPlanRequest
from app.config import settings

SAREK_RELEASE = "3.10.0"
SCHEMA_VERSION = "1.0"
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _artifact(artifact_id: str, description: str, patterns: list[str]) -> dict[str, Any]:
    return {"id": artifact_id, "required": True, "description": description, "patterns": patterns}


REQUIRED_ARTIFACTS = [
    _artifact("execution", "Nextflow execution reports from the actual run", ["pipeline_info/execution_trace*.txt", "pipeline_info/execution_report*.html", "pipeline_info/execution_timeline*.html"]),
    _artifact("multiqc", "Aggregated Sarek QC report and parsed data", ["multiqc/multiqc_report.html", "multiqc/multiqc_data/"]),
    _artifact("alignment", "Coordinate-sorted alignment and index", ["**/*.bam|**/*.cram", "**/*.bai|**/*.crai"]),
    _artifact("small_variants", "Caller VCF/gVCF and tabix index", ["**/*.vcf.gz", "**/*.vcf.gz.tbi"]),
    _artifact("coverage", "Assay-appropriate coverage metrics", ["reports/**/mosdepth*", "reports/**/coverage*"]),
    _artifact("identity_qc", "Sample identity, contamination and sex/ploidy evidence", ["reports/**/*contamination*", "reports/**/*fingerprint*", "reports/**/*sex*"]),
    _artifact("provenance", "Checksums and immutable workflow/resource identifiers", ["run_manifest.json", "checksums.sha256"]),
]

PROVENANCE_REQUIREMENTS = [
    "nf-core/sarek revision and Nextflow version",
    "container image digest for every executed process",
    "input sample-sheet SHA-256 and input file checksums",
    "reference FASTA, indexes, known-sites, target BED and annotation-cache checksums",
    "complete command argument array, profile and custom configuration checksum",
    "execution trace with process exit status and retry history",
]


def build_production_plan(request: NgsProductionPlanRequest) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if request.assay == "WES" and not (request.target_bed or "").strip():
        blockers.append("WES requires a reference-matched target BED.")
    if request.execution_profile in {"slurm", "awsbatch"} and not (request.custom_config or "").strip():
        blockers.append(f"{request.execution_profile} requires a reviewed Nextflow custom configuration.")
    if request.input_type == "FASTQ" and request.start_step != "mapping":
        blockers.append("FASTQ input must start at Sarek's mapping step.")
    if request.input_type == "CRAM" and request.start_step == "mapping":
        blockers.append("CRAM input must start at markduplicates or variant_calling and include its CRAI in the sample sheet.")
    if request.input_type == "BAM" and request.start_step == "mapping":
        warnings.append("BAM at the mapping step must be an unmapped BAM; prepared alignments should start at markduplicates or variant_calling with an index.")
    if request.genome == "GRCh37":
        warnings.append("GRCh37 resources must all use the same contig naming and bundle; hg19 resources are not interchangeable by label alone.")
    if request.clinical_intent:
        warnings.append("Clinical intent activates a fail-closed evidence gate; this launch plan alone cannot validate or authorize an assay.")
    if request.sample_model != "singleton" and request.caller != "haplotypecaller":
        warnings.append("The selected caller produces per-sample results here; joint germline calling is enabled only for HaplotypeCaller.")

    profile = request.execution_profile
    sarek_genome = {"GRCh38": "GATK.GRCh38", "GRCh37": "GATK.GRCh37"}[request.genome]
    argv = [
        "nextflow", "run", "nf-core/sarek", "-r", SAREK_RELEASE,
        "-profile", profile,
        "--input", request.samplesheet_path,
        "--outdir", request.outdir,
        "--genome", sarek_genome,
        "--tools", f"{request.caller}{',vep' if request.annotate_with_vep else ''}",
        "--step", request.start_step,
    ]
    if request.assay == "WES":
        argv.extend(["--wes", "--intervals", request.target_bed or ""])
    if request.custom_config:
        argv.extend(["-c", request.custom_config])
    if request.sample_model != "singleton" and request.caller == "haplotypecaller":
        argv.append("--joint_germline")

    ready = not blockers
    return {
        "schema_version": SCHEMA_VERSION,
        "workflow": {
            "name": "nf-core/sarek",
            "revision": SAREK_RELEASE,
            "execution_engine": "Nextflow",
            "assay": request.assay,
            "sample_model": request.sample_model,
            "input_type": request.input_type,
            "start_step": request.start_step,
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
            "clinical_intent": request.clinical_intent,
            "current_status": "NOT_CLINICALLY_RELEASABLE",
            "reason": "No executed run evidence, assay-validation record, benchmark evidence or authorized review has been imported.",
        },
    }


def _present(value: str | None) -> bool:
    return bool(value and value.strip())


def _sha256(value: str | None) -> bool:
    return bool(value and SHA256_RE.fullmatch(value))


def clinical_signature_payload(evidence: NgsClinicalEvidenceRequest) -> bytes:
    """Canonical bytes signed by the trusted evidence-import service."""
    if hasattr(evidence, "model_dump"):
        payload = evidence.model_dump(mode="json", exclude={"evidence_signature"})
    else:  # Pydantic v1 compatibility for older self-hosted deployments.
        payload = evidence.dict(exclude={"evidence_signature"})
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _signature_verified(evidence: NgsClinicalEvidenceRequest) -> bool:
    key = settings.NGS_CLINICAL_EVIDENCE_HMAC_KEY
    if not key or not evidence.evidence_signature or not _sha256(evidence.evidence_bundle_sha256):
        return False
    expected = hmac.new(key.encode("utf-8"), clinical_signature_payload(evidence), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, evidence.evidence_signature)


def evaluate_clinical_evidence(evidence: NgsClinicalEvidenceRequest) -> dict[str, Any]:
    metrics_present = all(value is not None for value in (
        evidence.snv_precision, evidence.snv_recall,
        evidence.indel_precision, evidence.indel_recall,
    ))
    truth_is_external = _present(evidence.truthset_name) and "synthetic" not in evidence.truthset_name.lower()
    review_complete = evidence.human_reviewed and _present(evidence.reviewer_id) and _present(evidence.release_signature_id)
    signature_verified = _signature_verified(evidence)

    checks: list[tuple[str, str, bool, str]] = [
        ("evidence_signature", "Trusted evidence bundle signature verified", signature_verified, evidence.evidence_bundle_sha256 or "missing or unverified"),
        ("assay_validation", "Validated assay record", _present(evidence.assay_validation_id), evidence.assay_validation_id or "missing"),
        ("execution", "Pinned workflow completed", evidence.workflow_status == "COMPLETED" and _present(evidence.sarek_revision), f"{evidence.workflow_status}; revision={evidence.sarek_revision or 'missing'}"),
        ("reference", "Reference and sample-sheet checksums", evidence.reference_build is not None and _sha256(evidence.reference_manifest_sha256) and _sha256(evidence.samplesheet_sha256), evidence.reference_build or "missing"),
        ("containers", "Container digests captured", evidence.container_digests_complete, str(evidence.container_digests_complete)),
        ("complete_input", "All input records processed", evidence.complete_input_processed, str(evidence.complete_input_processed)),
        ("artifacts", "Required artifacts imported", evidence.required_artifacts_present, str(evidence.required_artifacts_present)),
        ("qc", "Run QC passed", evidence.qc_pass, str(evidence.qc_pass)),
        ("identity", "Sample identity passed", evidence.sample_identity_pass, str(evidence.sample_identity_pass)),
        ("contamination", "Contamination gate passed", evidence.contamination_pass, str(evidence.contamination_pass)),
        ("sex_ploidy", "Sex/ploidy reviewed", evidence.sex_ploidy_reviewed, str(evidence.sex_ploidy_reviewed)),
        ("truth_benchmark", "External truth benchmark passed its approved protocol", bool(truth_is_external and _present(evidence.benchmark_protocol_id) and evidence.benchmark_acceptance_pass and _sha256(evidence.confident_regions_sha256) and evidence.same_sample_reference_regions and metrics_present), evidence.truthset_name or "missing"),
        ("human_release", "Authorized human review and release signature", review_complete, evidence.reviewer_id or "missing"),
        ("deviations", "No unresolved deviations", not evidence.unresolved_deviations, ", ".join(evidence.unresolved_deviations) or "none"),
    ]
    gates = [
        {"id": gate_id, "label": label, "status": "PASS" if passed else "FAIL", "evidence": detail}
        for gate_id, label, passed, detail in checks
    ]
    missing = [label for _gate_id, label, passed, _detail in checks if not passed]
    passed = not missing
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SOFTWARE_GATE_PASSED" if passed else "NOT_CLINICALLY_RELEASABLE",
        "clinically_validated": False,
        "gates": gates,
        "missing_or_failed": missing,
        "benchmark_summary": {
            "truthset": evidence.truthset_name,
            "protocol_id": evidence.benchmark_protocol_id,
            "same_sample_reference_regions": evidence.same_sample_reference_regions,
            "acceptance_pass": evidence.benchmark_acceptance_pass,
            "metrics": {
                "snv_precision": evidence.snv_precision,
                "snv_recall": evidence.snv_recall,
                "indel_precision": evidence.indel_precision,
                "indel_recall": evidence.indel_recall,
            },
        },
        "disclaimer": "This is a software evidence gate, not clinical validation, accreditation, diagnosis or report authorization. Laboratory validation and jurisdiction-specific governance remain required.",
    }

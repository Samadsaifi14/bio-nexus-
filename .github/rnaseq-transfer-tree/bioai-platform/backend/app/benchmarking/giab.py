"""Formal germline truth-set benchmark planning for GIAB/GA4GH-style evaluation.

The planner never converts a synthetic fixture into an accuracy claim. It emits a
non-shell argv and an evidence contract for an external authorized execution worker.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Any


class GermlineBenchmarkPlanError(ValueError):
    pass


@dataclass(frozen=True)
class GermlineBenchmarkRequest:
    query_vcf: str
    truth_vcf: str
    confident_regions_bed: str
    reference_fasta: str
    query_reference_build: str
    truth_reference_build: str
    truth_set_id: str
    output_prefix: str
    stratification_tsv: str | None = None
    evaluator: str = "hap.py"


_REQUIRED_METRICS = [
    "SNP TP/FP/FN, precision, recall and F1",
    "INDEL TP/FP/FN, precision, recall and F1",
    "genotype concordance",
    "no-call counts",
    "benchmark/confident-region denominators",
    "stratified difficult-region metrics",
]


def _required_text(name: str, value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise GermlineBenchmarkPlanError(f"{name} is required")
    if "\x00" in cleaned:
        raise GermlineBenchmarkPlanError(f"{name} contains a null byte")
    return cleaned


def _artifact_path(name: str, value: str) -> str:
    cleaned = _required_text(name, value)
    if cleaned.startswith(("http://", "https://")):
        raise GermlineBenchmarkPlanError(
            f"{name} must be a staged worker-local or mounted path; remote URLs are not executed by the planner"
        )
    return cleaned


def build_germline_truth_benchmark_plan(request: GermlineBenchmarkRequest) -> dict[str, Any]:
    """Build a strict hap.py execution plan for a non-synthetic truth benchmark."""
    if request.evaluator != "hap.py":
        raise GermlineBenchmarkPlanError("Only hap.py is currently accepted by this planner")

    query_build = _required_text("query_reference_build", request.query_reference_build)
    truth_build = _required_text("truth_reference_build", request.truth_reference_build)
    if query_build.casefold() != truth_build.casefold():
        raise GermlineBenchmarkPlanError(
            f"Reference-build mismatch: query={query_build!r}, truth={truth_build!r}"
        )

    truth_set_id = _required_text("truth_set_id", request.truth_set_id)
    if "synthetic" in truth_set_id.casefold():
        raise GermlineBenchmarkPlanError(
            "Formal production-accuracy benchmarking requires a non-synthetic accepted truth set"
        )

    truth_vcf = _artifact_path("truth_vcf", request.truth_vcf)
    query_vcf = _artifact_path("query_vcf", request.query_vcf)
    confident_bed = _artifact_path("confident_regions_bed", request.confident_regions_bed)
    reference = _artifact_path("reference_fasta", request.reference_fasta)
    output_prefix = _artifact_path("output_prefix", request.output_prefix)

    argv = [
        "hap.py",
        truth_vcf,
        query_vcf,
        "-f",
        confident_bed,
        "-r",
        reference,
        "-o",
        output_prefix,
    ]
    if request.stratification_tsv:
        argv.extend(["--stratification", _artifact_path("stratification_tsv", request.stratification_tsv)])

    return {
        "benchmark_type": "germline_small_variant_truth_set",
        "execution_status": "PLANNED_NOT_EXECUTED",
        "accuracy_claim_allowed": False,
        "evaluator": "hap.py",
        "truth_set_id": truth_set_id,
        "reference_build": query_build,
        "command_argv": argv,
        "shell_interpolation_allowed": False,
        "confident_regions_required": True,
        "required_metrics": list(_REQUIRED_METRICS),
        "required_provenance": [
            "query VCF SHA-256",
            "truth VCF SHA-256",
            "confident-region BED SHA-256",
            "reference FASTA/build identity and SHA-256",
            "evaluator version/container digest",
            "stratification definitions and checksums when used",
            "complete stdout/stderr and result artifacts",
        ],
        "acceptance_gate": (
            "Accuracy remains NOT_EVALUATED until the external worker returns a retained report "
            "containing all required metrics and provenance for the matched truth/reference/confident regions."
        ),
        "request": asdict(request),
        "output_basename": PurePosixPath(output_prefix).name,
    }

"""
Analysis orchestrator (blueprint point 2 / 26).

A pipeline is not a linear list of tool calls with no feedback. This orchestrator runs the
stages of a chosen assay as a workflow graph, where every stage is a QC contract:

    A
    |-- output
    |-- QC
    |     PASS -> continue
    |     WARN -> continue + warning
    |     FAIL -> stop (for blocking stages)
    `-- provenance

It threads a shared `state` dict between stages so later stages consume earlier outputs, and it
honours the STOP decision for fail-blocking stages (e.g. contamination FAIL blocks
interpretation). The result is a machine-auditable list of StageResult records plus provenance.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Callable, Optional

from app.ngs.contracts import (
    Decision,
    QcResult,
    QcStatus,
    StageContract,
    StageResult,
    run_contract,
)

logger = logging.getLogger(__name__)

BENCHMARK_REGISTRY = [
    {
        "id": "giab-hg002-v4.2.1",
        "source": "NIST Genome in a Bottle",
        "scope": "HG002 germline small variants within benchmark regions",
        "comparison_method": "GA4GH hap.py or vcfeval, stratified by variant type and genome context",
        "url": "https://www.nist.gov/programs-projects/genome-bottle",
        "status": "NOT_EVALUATED",
        "metrics": None,
        "reason": "This run did not supply HG002 reads, the matching truth VCF and benchmark BED, or a GA4GH comparison report.",
    },
    {
        "id": "precisionfda-truth-v2",
        "source": "FDA precisionFDA Truth Challenge V2",
        "scope": "HG002/HG003/HG004 variants, including difficult-to-map regions",
        "comparison_method": "Challenge-compatible precision, recall and F1 by region and variant class",
        "url": "https://precision.fda.gov/challenges/10/results",
        "status": "NOT_EVALUATED",
        "metrics": None,
        "reason": "No challenge-compatible callset and stratified evaluation output were produced by this run.",
    },
    {
        "id": "seqc-gse47774",
        "source": "NCBI GEO / SEQC consortium",
        "scope": "RNA-seq accuracy and reproducibility reference dataset GSE47774",
        "comparison_method": "Expression accuracy, replicate correlation and differential-expression reproducibility",
        "url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE47774",
        "status": "NOT_APPLICABLE",
        "metrics": None,
        "reason": "This WGS/WES workflow does not produce RNA-seq expression estimates.",
    },
]

PRODUCTION_REQUIREMENTS = [
    {"id": "complete_input", "label": "Complete FASTQ ingestion", "required": True,
     "detail": "All records processed; no preview cap or silent subsampling."},
    {"id": "production_alignment", "label": "Production read alignment", "required": True,
     "detail": "Executed BWA-MEM2/DRAGMAP or another validated aligner with command and version."},
    {"id": "bam_artifacts", "label": "Indexed alignment artifacts", "required": True,
     "detail": "Coordinate-sorted BAM/CRAM, index, flagstat, idxstats and alignment metrics."},
    {"id": "recalibration", "label": "Reference-matched recalibration", "required": True,
     "detail": "BQSR or a documented no-BQSR workflow using build-matched known sites."},
    {"id": "production_calls", "label": "Production germline callset", "required": True,
     "detail": "Caller-generated VCF/gVCF with genotype, DP, GQ, AD, filters and index."},
    {"id": "sample_qc", "label": "Sample QC and identity", "required": True,
     "detail": "Coverage, duplication, insert size, contamination, sex and concordance when applicable."},
    {"id": "truth_benchmark", "label": "GIAB/GA4GH truth comparison", "required": True,
     "detail": "hap.py/vcfeval precision, recall and F1 inside the matching benchmark BED, stratified by SNP/INDEL."},
    {"id": "reproducibility", "label": "Reproducible execution record", "required": True,
     "detail": "Reference/resource checksums, exact commands, pipeline revision and container digests."},
]


class Pipeline:
    """Runs an ordered list of StageContracts over a shared sample/state context."""

    def __init__(self, name: str, version: str = "0.1.0"):
        self.name = name
        self.version = version
        self.stages: list[StageContract] = []
        self.results: list[StageResult] = []
        self.state: dict = {}
        self.stopped_at: Optional[str] = None
        self.warnings: list[str] = []
        self.provenance: dict = {}

    def add(self, contract: StageContract) -> "Pipeline":
        self.stages.append(contract)
        return self

    def add_many(self, contracts: list[StageContract]) -> "Pipeline":
        self.stages.extend(contracts)
        return self

    def run(self, sample: dict) -> dict:
        """Execute stages in order; stop on a blocking FAIL. Returns full result dict."""
        for contract in self.stages:
            # Expose the stages completed so far so trailing meta-gates (e.g. final_gate) can
            # read the accumulated PASS/WARN/FAIL + decisions of every earlier stage.
            self.state["pipeline_report"] = {
                "stages": [r.to_dict() for r in self.results],
            }
            stage_result = run_contract(contract, sample, self.state)
            self.results.append(stage_result)

            if stage_result.qc:
                unevaluated = stage_result.data.get("unevaluated")
                if unevaluated:
                    self.warnings.append(
                        f"[{contract.step}] Not evaluated: {unevaluated}."
                    )
                elif contract.step != "final_gate":
                    for metric in stage_result.qc.metrics:
                        if metric.status != QcStatus.WARN or metric.value is None:
                            continue
                        expected = f"; expected {metric.expected}" if metric.expected else ""
                        detail = f" — {metric.detail}" if metric.detail else ""
                        self.warnings.append(
                            f"[{contract.step}] {metric.name}: {metric.value}{expected}{detail}"
                        )

            if stage_result.decision == Decision.STOP:
                self.stopped_at = contract.step
                logger.warning("Pipeline '%s' stopped at %s (blocking QC FAIL)",
                               self.name, contract.step)
                break

        self.provenance = self._build_provenance(sample)

        # Merge any structured payload from the last successful stage into state for consumers.
        return self.report()

    def _build_provenance(self, sample: dict) -> dict:
        """Build a compact, deterministic audit record from facts observed by this run."""
        metadata = sample.get("metadata") or {}
        input_stage = next((r for r in self.results if r.step == "input_validation"), None)
        checksums = input_stage.data.get("checksums", {}) if input_stage else {}
        files = []
        for path in sample.get("files") or []:
            item = {"name": os.path.basename(path)}
            checksum = checksums.get(path) or checksums.get(os.path.basename(path))
            if checksum:
                item["checksum"] = {"algorithm": "md5", "value": checksum}
            files.append(item)

        reference = self.state.get("reference", {}).get("declared") or {
            "id": sample.get("reference")
        }
        return {
            "schema_version": "1.0",
            "pipeline": {"name": self.name, "version": self.version},
            "analysis": {
                "assay": sample.get("assay"),
                "sample_type": sample.get("sample_type"),
                "platform": metadata.get("platform"),
                "demonstration_data": bool(
                    sample.get("demonstration_data") or metadata.get("demonstration_data")
                ),
                "synthetic_reference": bool(sample.get("synthetic_reference")),
            },
            "inputs": files,
            "reference": reference,
            "tools": [
                {"stage": r.step, "implementation": r.tool, "version": r.version,
                 "evidence_level": r.evidence_level}
                for r in self.results
            ],
        }

    def report(self) -> dict:
        surrogate_stages = [r.step for r in self.results if r.evidence_level == "SURROGATE"]
        requirements = [{**item, "status": "MISSING", "evidence": None}
                        for item in PRODUCTION_REQUIREMENTS]
        return {
            "pipeline": self.name,
            "pipeline_version": self.version,
            "pipeline_status": self._overall_status().value,
            "pipeline_decision": self._overall_decision().value,
            "stopped_at": self.stopped_at,
            "warnings": self.warnings,
            "stages": [r.to_dict() for r in self.results],
            "provenance": self.provenance,
            "validation": {
                "claim": "NO_ACCURACY_CLAIM",
                "analysis_grade": "EXPLORATORY_PREVIEW",
                "research_ready": False,
                "summary": "This internal sampled/surrogate workflow has not been validated against a public truth set.",
                "same_or_better_supported": False,
                "surrogate_stages": surrogate_stages,
                "production_requirements": requirements,
                "comparisons": BENCHMARK_REGISTRY,
            },
        }

    def _overall_status(self) -> QcStatus:
        if self.stopped_at is not None:
            return QcStatus.FAIL
        if any(r.qc and r.qc.status == QcStatus.WARN for r in self.results):
            return QcStatus.WARN
        return QcStatus.PASS

    def _overall_decision(self) -> Decision:
        if self.stopped_at is not None:
            return Decision.STOP
        if self._overall_status() == QcStatus.WARN:
            return Decision.CONTINUE_WITH_WARNING
        return Decision.CONTINUE


# ---------------------------------------------------------------------------
# Stage list builders per assay (blueprint point 1 + master architecture)
# ---------------------------------------------------------------------------


def wgs_wes_germline_stages(include: Optional[list[str]] = None) -> list[StageContract]:
    """Stages for human WGS/WES germline (the first serious pipeline, per blueprint).

    ``include`` filters by stage id so the caller can build lighter DAGs during development.
    """
    from app.ngs.stages.stage0_input import stage0_contract
    from app.ngs.stages.stage1_raw_qc import raw_qc_contract
    from app.ngs.stages.stage2_multiqc import stage2_contract
    from app.ngs.stages.stage3_preproc import stage3_contract
    from app.ngs.stages.stage4_reference import stage4_contract
    from app.ngs.stages.stage5_alignment import stage5_contract
    from app.ngs.stages.stage6_bam import stage6_contract
    from app.ngs.stages.stage7_alignment_qc import stage7_contract
    from app.ngs.stages.stage8_coverage import stage8_contract
    from app.ngs.stages.stage9_contamination import stage9_contract
    from app.ngs.stages.stage10_identity import stage10_contract
    from app.ngs.stages.stage11_variant_calling import stage11_contract
    from app.ngs.stages.stage12_normalize import stage12_contract
    from app.ngs.stages.stage13_variant_qc import stage13_contract
    from app.ngs.stages.stage14_filter import stage14_contract
    from app.ngs.stages.stage15_sv import stage15_contract
    from app.ngs.stages.stage16_cnv import stage16_contract
    from app.ngs.stages.stage17_annotation import stage17_contract
    from app.ngs.stages.stage18_knowledge import stage18_contract
    from app.ngs.stages.stage19_prioritize import stage19_contract
    from app.ngs.stages.stage21_final_gate import stage21_contract

    all_stages = {
        "input_validation": stage0_contract(),
        "raw_read_qc": raw_qc_contract(),
        "multiqc": stage2_contract(),
        "preprocessing": stage3_contract(),
        "reference_validation": stage4_contract(),
        "alignment": stage5_contract(),
        "bam_processing": stage6_contract(),
        "alignment_qc": stage7_contract(),
        "coverage": stage8_contract(),
        "contamination": stage9_contract(),
        "identity": stage10_contract(),
        "variant_calling": stage11_contract(),
        "variant_normalization": stage12_contract(),
        "variant_qc": stage13_contract(),
        "variant_filter": stage14_contract(),
        "structural_variant": stage15_contract(),
        "copy_number": stage16_contract(),
        "annotation": stage17_contract(),
        "knowledge": stage18_contract(),
        "prioritization": stage19_contract(),
        "final_gate": stage21_contract(),
    }
    if include:
        return [all_stages[s] for s in include if s in all_stages]
    return list(all_stages.values())


def build_dag(assay: str) -> Pipeline:
    """Build the appropriate Pipeline for a detected assay."""
    assay_l = assay.lower()
    if assay_l in ("wgs", "wes"):
        pipe = Pipeline(name=f"{assay}-germline", version="0.1.0")
        pipe.add_many(wgs_wes_germline_stages())
        return pipe
    if assay_l in ("rna-seq", "rnaseq"):
        return Pipeline(name="rna-seq", version="0.1.0")
    if assay_l in ("amplicon", "panel", "targeted"):
        return Pipeline(name="amplicon-variants", version="0.1.0")
    # Unknown / generic -> minimal generic stages.
    pipe = Pipeline(name="generic", version="0.1.0")
    pipe.add_many(wgs_wes_germline_stages())
    return pipe

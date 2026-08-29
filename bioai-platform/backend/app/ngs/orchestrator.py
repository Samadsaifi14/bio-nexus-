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
from datetime import datetime, timezone
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
            stage_result = run_contract(contract, sample, self.state)
            self.results.append(stage_result)

            if stage_result.qc:
                for m in stage_result.qc.metrics:
                    if m.status == QcStatus.WARN:
                        self.warnings.append(
                            f"[{contract.step}] {m.name}: {m.value} ({m.expected})"
                        )

            if stage_result.decision == Decision.STOP:
                self.stopped_at = contract.step
                logger.warning("Pipeline '%s' stopped at %s (blocking QC FAIL)",
                               self.name, contract.step)
                break

        # Merge any structured payload from the last successful stage into state for consumers.
        return self.report()

    def report(self) -> dict:
        return {
            "pipeline": self.name,
            "pipeline_version": self.version,
            "pipeline_status": self._overall_status().value,
            "pipeline_decision": self._overall_decision().value,
            "stopped_at": self.stopped_at,
            "warnings": self.warnings,
            "stages": [r.to_dict() for r in self.results],
            "provenance": self.provenance,
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
        # annotation, prioritization, final_gate
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

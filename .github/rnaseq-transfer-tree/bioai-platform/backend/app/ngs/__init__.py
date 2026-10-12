"""NGS platform — multi-assay pipeline router, QC contract engine, and stages.

Architecture (per the blueprint's six layers):

    INPUT
      |
      v
  Assay identifier ............ detects / chooses the assay (WGS / WES / RNA-seq / Amplicon)
      |
      v
  Analysis orchestrator ....... runs stages as a workflow graph, each stage = a QC contract
      |
      v
  QC contract engine .......... every stage declares INPUT / OUTPUT / QC / DECISION contracts
      |
      v
  Reference / database layer .. versioned reference registry (GRCh38 vs GRCh37, etc.)
      |
      v
  Storage + provenance ........ audit trail of tool/version/params/reference for every result

A "QC contract" makes the pipeline machine-auditable: each stage emits typed metrics with a
PASS / WARN / FAIL status and a downstream decision (CONTINUE / CONTINUE_WITH_WARNING / STOP),
so a contamination FAIL can block interpretation while a minor duplication WARN does not.
"""

from app.ngs.contracts import (
    QcStatus,
    Decision,
    Metric,
    QcResult,
    StageResult,
    evaluate_metric,
    evaluate_contract,
    run_contract,
)
from app.ngs.assays import (
    AssayType,
    AssayDetection,
    AssayRouter,
    detect_assay,
    classify_inputs,
)

__all__ = [
    "QcStatus",
    "Decision",
    "Metric",
    "QcResult",
    "StageResult",
    "evaluate_metric",
    "evaluate_contract",
    "run_contract",
    "AssayType",
    "AssayDetection",
    "AssayRouter",
    "detect_assay",
    "classify_inputs",
]

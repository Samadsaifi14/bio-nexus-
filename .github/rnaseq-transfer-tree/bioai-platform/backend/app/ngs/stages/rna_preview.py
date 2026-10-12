"""RNA-seq interactive preview stages.

The browser/API preview can inspect supplied FASTQ quality, but it must not
pretend to have run STAR/HISAT2/Salmon/RSEM when those durable production
processes were not executed. The final boundary stage therefore records that
quantification is unavailable in preview mode and directs production work to
the pinned nf-core/rnaseq contract.
"""
from __future__ import annotations

from app.ngs.contracts import QcStatus, StageContract, ThresholdRule


def _read_summary(sample: dict, state: dict) -> tuple[dict, dict]:
    reads = sample.get("reads") or []
    lengths = [len(seq) for _name, seq, _qual in reads if seq]
    q30_bases = 0
    total_bases = 0
    for _name, seq, qual in reads:
        n = min(len(seq), len(qual))
        total_bases += n
        q30_bases += sum(1 for ch in qual[:n] if (ord(ch) - 33) >= 30)
    q30 = (100.0 * q30_bases / total_bases) if total_bases else 0.0
    mean_len = (sum(lengths) / len(lengths)) if lengths else 0.0
    data = {
        "reads_observed": len(reads),
        "bases_observed": total_bases,
        "mean_read_length": round(mean_len, 3),
        "q30_pct": round(q30, 3),
        "scope": "FASTQ preview quality only; no splice-aware alignment or expression quantification was executed.",
    }
    state.setdefault("rna_seq", {})["read_summary"] = data
    return data, {"reads_present": len(reads), "q30_pct": q30}


def _positive(v):
    try:
        return QcStatus.PASS if float(v) > 0 else QcStatus.FAIL
    except (TypeError, ValueError):
        return QcStatus.FAIL


def _q30(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return QcStatus.FAIL
    if x >= 80.0:
        return QcStatus.PASS
    if x >= 60.0:
        return QcStatus.WARN
    return QcStatus.FAIL


def rna_read_summary_contract() -> StageContract:
    return StageContract(
        step="rna_read_summary",
        tool="BioNexus FASTQ preview",
        version="1.0.0",
        inputs=["FASTQ records"],
        outputs=["read-level quality summary"],
        rules=[
            ThresholdRule("reads_present", "reads_present", _positive, expectation="> 0 reads"),
            ThresholdRule("q30_pct", "q30_pct", _q30, expectation=">= 80% Q30 for preview PASS"),
        ],
        fail_blocks=True,
        run=_read_summary,
        evidence_level="INTERNAL_COMPUTATION",
    )


def _execution_boundary(sample: dict, state: dict) -> tuple[dict, dict]:
    data = {
        "status": "NOT_EXECUTED_IN_PREVIEW",
        "required_workflow": "nf-core/rnaseq",
        "required_revision": "3.26.0",
        "production_plan_endpoint": "/api/ngs/v2/rnaseq/production/plan",
        "missing_outputs": [
            "splice-aware BAM/index",
            "gene/transcript abundance tables",
            "cross-sample count matrix",
            "production MultiQC/provenance artifacts",
        ],
        "claim_boundary": "No gene-expression, differential-expression, or fusion conclusion is emitted by the FASTQ preview.",
    }
    state.setdefault("rna_seq", {})["production_boundary"] = data
    return data, {"production_quantification_executed": False}


def _not_executed(_value):
    return QcStatus.WARN


def rna_production_boundary_contract() -> StageContract:
    return StageContract(
        step="rna_production_boundary",
        tool="BioNexus evidence gate",
        version="1.0.0",
        inputs=["FASTQ preview summary"],
        outputs=["production execution requirement"],
        rules=[
            ThresholdRule(
                "production_quantification_executed",
                "production_quantification_executed",
                _not_executed,
                expectation="production nf-core/rnaseq artifacts required",
            )
        ],
        fail_blocks=False,
        run=_execution_boundary,
        evidence_level="UNSUPPORTED/INSUFFICIENT_EVIDENCE",
    )

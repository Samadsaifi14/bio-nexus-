"""Paired/multi-file raw-read QC contract for the exploratory NGS preview.

The legacy metric primitive computes one FASTQ at a time. This adapter executes it for
every supplied mate/file, preserves per-file evidence, and reports weighted aggregate
metrics. It remains an exploratory in-process QC implementation, not FastQC.
"""
from __future__ import annotations

from app.ngs.contracts import QcResult, StageContract, apply_rules
from app.ngs.stages.stage1_raw_qc import _qc_thresholds, compute_raw_qc


def _weighted(per_file: dict[str, dict], key: str, weight_key: str) -> float:
    numerator = 0.0
    denominator = 0.0
    for qc in per_file.values():
        try:
            weight = float(qc.get(weight_key) or 0)
            value = float(qc.get(key) or 0)
        except (TypeError, ValueError):
            continue
        numerator += value * weight
        denominator += weight
    return round(numerator / denominator, 4) if denominator else 0.0


def aggregate_raw_qc(per_file: dict[str, dict]) -> dict:
    total_reads = sum(int(qc.get("total_reads") or 0) for qc in per_file.values())
    total_bases = sum(int(qc.get("total_bases") or 0) for qc in per_file.values())
    sampled = any(bool(qc.get("sampling_limited")) for qc in per_file.values())
    return {
        "tool": "platform-raw-qc",
        "scope": "all_supplied_fastq_files",
        "file_count": len(per_file),
        "total_reads": total_reads,
        "total_bases": total_bases,
        "avg_read_length": _weighted(per_file, "avg_read_length", "total_reads"),
        "gc_percent": _weighted(per_file, "gc_percent", "total_bases"),
        "n_percent": _weighted(per_file, "n_percent", "total_bases"),
        "mean_quality": _weighted(per_file, "mean_quality", "total_bases"),
        "q20_percent": _weighted(per_file, "q20_percent", "total_bases"),
        "q30_percent": _weighted(per_file, "q30_percent", "total_bases"),
        "adapter_percent": _weighted(per_file, "adapter_percent", "total_reads"),
        "duplication_percent": _weighted(per_file, "duplication_percent", "total_reads"),
        "per_file": per_file,
        "sampling_limited": sampled,
        "interpretation": (
            "Metrics are weighted across every supplied FASTQ file. The in-process preview may sample large files; "
            "production conclusions require workflow-emitted QC artifacts."
        ),
    }


def _stage_run(sample: dict, state: dict) -> tuple[dict, dict]:
    assay = sample.get("assay") or "WGS"
    metadata = sample.get("metadata") or {}
    files = list(sample.get("files") or [])
    if not files:
        return {"error": "no files"}, {}

    per_file: dict[str, dict] = {}
    for path in files:
        qc = compute_raw_qc(path, assay, metadata)
        if "error" in qc:
            return {"error": "raw QC could not evaluate every supplied FASTQ"}, {}
        # The primitive reads at most 200k reads. Expose that boundary explicitly.
        qc["sampling_cap_reads"] = 200_000
        qc["sampling_limited"] = int(qc.get("total_reads") or 0) >= 200_000
        per_file[path] = qc
        state.setdefault("raw_qc", {})[path] = qc

    aggregate = aggregate_raw_qc(per_file)
    metrics = {
        "q20": aggregate["q20_percent"],
        "q30": aggregate["q30_percent"],
        "gc_content": aggregate["gc_percent"],
        "adapter_content": aggregate["adapter_percent"],
        "duplication": aggregate["duplication_percent"],
        "n_content": aggregate["n_percent"],
    }
    state["raw_qc_aggregate"] = aggregate
    return aggregate, metrics


def raw_qc_pair_contract() -> StageContract:
    return StageContract(
        step="raw_read_qc",
        tool="platform-raw-qc",
        version="0.2.0",
        inputs=["raw_fastq (all supplied files)"],
        outputs=["per_file_raw_qc", "aggregate_raw_qc"],
        rules=lambda sample: list(_qc_thresholds(
            sample.get("assay") or "WGS", sample.get("metadata") or {}
        ).values()),
        fail_blocks=True,
        evidence_level="SURROGATE",
        run=_stage_run,
    )


def run_raw_qc_pair(sample: dict) -> dict:
    contract = raw_qc_pair_contract()
    data, metric_values = _stage_run(sample, {})
    if "error" in data:
        return {"result": None, "summary": {"status": "FAIL", "decision": "STOP", "error": data["error"]}}
    metrics = apply_rules(contract.resolve_rules(sample), metric_values)
    result = QcResult.from_metrics(metrics, fail_blocks=True)
    return {
        "result": {"step": "raw_read_qc", "qc": result.to_dict(), "decision": result.decision.value, "data": data},
        "summary": {"status": result.status.value, "decision": result.decision.value, "qc": data},
    }

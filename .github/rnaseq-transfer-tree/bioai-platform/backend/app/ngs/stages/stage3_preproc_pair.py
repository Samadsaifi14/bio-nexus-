"""Paired/multi-file preprocessing adapter for the exploratory NGS preview.

Each FASTQ receives its own deterministic preprocessing plan and output. The adapter
then aggregates measured post-trim evidence across all mates. Production trimming is
still delegated to the pinned nf-core workflow and its emitted artifacts.
"""
from __future__ import annotations

import gzip
import os
from pathlib import Path

from app.ngs.contracts import QcResult, StageContract, ThresholdRule, apply_rules
from app.ngs.stages.stage3_preproc import (
    _quality_rule,
    _retention_rule,
    plan_preprocessing,
    preprocess_fastq,
)


def _post_trim_summary(path: str) -> dict:
    """Measure the actual written FASTQ rather than infer length from pre-trim reads."""
    total_reads = 0
    total_bases = 0
    quality_sum = 0
    q20 = 0
    q30 = 0
    quality_bases = 0
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="ascii", errors="replace") as handle:
        while True:
            header = handle.readline()
            if not header:
                break
            seq = handle.readline().strip()
            plus = handle.readline()
            qual = handle.readline().strip()
            if not plus or len(seq) != len(qual):
                continue
            total_reads += 1
            total_bases += len(seq)
            for char in qual:
                score = ord(char) - 33
                quality_sum += score
                quality_bases += 1
                if score >= 20:
                    q20 += 1
                if score >= 30:
                    q30 += 1
    return {
        "retained_reads_measured": total_reads,
        "retained_bases": total_bases,
        "avg_read_length_after": round(total_bases / total_reads, 2) if total_reads else 0.0,
        "mean_quality_after": round(quality_sum / quality_bases, 2) if quality_bases else 0.0,
        "q20_after": round(q20 / quality_bases * 100, 2) if quality_bases else 0.0,
        "q30_after": round(q30 / quality_bases * 100, 2) if quality_bases else 0.0,
    }


def _read_preview(path: str, max_reads: int = 3) -> list[dict]:
    """Return a tiny, authentic sequence preview for the interactive trimming map."""
    rows: list[dict] = []
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="ascii", errors="replace") as handle:
        while len(rows) < max_reads:
            header = handle.readline()
            if not header:
                break
            seq = handle.readline().strip()
            plus = handle.readline()
            qual = handle.readline().strip()
            if not header.startswith("@") or not plus.startswith("+"):
                continue
            rows.append({
                "name": header[1:].strip().split()[0],
                "sequence": seq,
                "length": len(seq),
                "mean_quality": round(sum(ord(ch) - 33 for ch in qual) / len(qual), 2) if qual else 0.0,
            })
    return rows


def _trim_examples(raw_path: str, clean_path: str) -> list[dict]:
    before = _read_preview(raw_path)
    after = _read_preview(clean_path)
    rows: list[dict] = []
    for index, raw in enumerate(before):
        clean = after[index] if index < len(after) else None
        clean_sequence = str(clean.get("sequence") or "") if clean else ""
        raw_sequence = str(raw.get("sequence") or "")
        rows.append({
            "name": raw.get("name"),
            "before": raw_sequence,
            "after": clean_sequence,
            "before_length": len(raw_sequence),
            "after_length": len(clean_sequence),
            "removed_bases": max(0, len(raw_sequence) - len(clean_sequence)),
            "mean_quality_before": raw.get("mean_quality"),
            "mean_quality_after": clean.get("mean_quality") if clean else None,
        })
    return rows


def aggregate_preprocessing(per_file: dict[str, dict]) -> dict:
    raw_reads = sum(int(item.get("raw_reads") or 0) for item in per_file.values())
    retained_reads = sum(int(item.get("retained_reads_measured") or 0) for item in per_file.values())
    discarded_reads = max(0, raw_reads - retained_reads)
    retained_bases = sum(int(item.get("retained_bases") or 0) for item in per_file.values())
    quality_weight = retained_bases

    def weighted(key: str) -> float:
        if not quality_weight:
            return 0.0
        numerator = sum(float(item.get(key) or 0) * int(item.get("retained_bases") or 0) for item in per_file.values())
        return round(numerator / quality_weight, 2)

    return {
        "tool": "platform-preprocess",
        "scope": "all_supplied_fastq_files",
        "file_count": len(per_file),
        "raw_reads": raw_reads,
        "retained_reads": retained_reads,
        "discarded_reads": discarded_reads,
        "read_loss_percent": round(discarded_reads / raw_reads * 100, 2) if raw_reads else 0.0,
        "adapter_removed_reads": sum(int(item.get("adapter_removed_reads") or 0) for item in per_file.values()),
        "retained_bases": retained_bases,
        "avg_read_length_after": round(retained_bases / retained_reads, 2) if retained_reads else 0.0,
        "mean_quality_after": weighted("mean_quality_after"),
        "q20_after": weighted("q20_after"),
        "q30_after": weighted("q30_after"),
        "per_file": per_file,
        "interpretation": (
            "Every supplied FASTQ mate/file was processed independently and aggregated. "
            "This preview implementation is not a substitute for production workflow trimming artifacts."
        ),
    }


def _stage_run(sample: dict, state: dict) -> tuple[dict, dict]:
    metadata = sample.get("metadata") or {}
    files = list(sample.get("files") or [])
    if not files:
        return {"error": "no files"}, {}

    workdir = sample.get("workdir") or metadata.get("out_dir") or "/tmp/bionexus-ngs-preview"
    out_dir = os.path.join(str(workdir), "clean")
    os.makedirs(out_dir, exist_ok=True)

    per_file: dict[str, dict] = {}
    for path in files:
        raw_qc = (state.get("raw_qc") or {}).get(path) or {}
        plan = plan_preprocessing(metadata, raw_qc)
        stats = preprocess_fastq(path, out_dir, plan, sample_name="")
        if "error" in stats:
            return {"error": "preprocessing could not evaluate every supplied FASTQ"}, {}
        measured = _post_trim_summary(stats["out_path"])
        entry = {
            **stats,
            **measured,
            "plan": plan,
            "trim_examples": _trim_examples(path, stats["out_path"]),
        }
        per_file[path] = entry
        state.setdefault("clean_fastq", {})[path] = stats["out_path"]

    aggregate = aggregate_preprocessing(per_file)
    state["preprocessing_aggregate"] = aggregate
    return aggregate, {
        "read_retention": 100.0 - aggregate["read_loss_percent"],
        "quality_after": aggregate["mean_quality_after"],
    }


def stage3_pair_contract() -> StageContract:
    return StageContract(
        step="preprocessing",
        tool="platform-preprocess",
        version="0.3.0",
        inputs=["raw_fastq (all supplied files)", "per_file_raw_qc"],
        outputs=["clean_fastq_per_file", "aggregate_preprocess_stats", "trim_examples"],
        rules=[
            ThresholdRule(name="read_retention", metric="read_retention", evaluate=_retention_rule),
            ThresholdRule(name="quality_after", metric="quality_after", evaluate=_quality_rule),
        ],
        fail_blocks=True,
        evidence_level="SURROGATE",
        run=_stage_run,
    )


def run_preprocessing_pair(sample: dict) -> dict:
    contract = stage3_pair_contract()
    data, values = _stage_run(sample, {})
    if "error" in data:
        return {"summary": {"status": "FAIL", "decision": "STOP", "error": data["error"]}}
    metrics = apply_rules(contract.resolve_rules(sample), values)
    result = QcResult.from_metrics(metrics, fail_blocks=True)
    return {
        "result": {"step": "preprocessing", "qc": result.to_dict(), "decision": result.decision.value, "data": data},
        "summary": {"status": result.status.value, "decision": result.decision.value, "stats": data},
    }

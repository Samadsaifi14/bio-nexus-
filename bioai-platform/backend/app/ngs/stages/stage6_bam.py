"""
Stage 6 — BAM processing (blueprint Stage 6).

RAW alignments (SAM records) -> sort by coordinate -> mark duplicates -> indexed BAM-equivalent.

The exact preprocessing (BQSR, base quality recalibration) depends on the selected validated
pipeline; this stage implements the core sort + MarkDuplicates surrogate and reports a
duplication QC metric. In production this maps onto samtools sort/idx + Picard MarkDuplicates;
the contract makes swapping the executor in a like-for-like change.

See also the pure-Python alignment surrogate in app.ngs.sam for the demo/fallback path.
"""

from __future__ import annotations

import os
from typing import Optional

from app.ngs.contracts import QcStatus, StageContract, ThresholdRule
from app.ngs.sam import read_sam, parse_sam

_DUP_TRYHARD = False  # simplified dedup key: (rname,pos,strand,qname-tag)


def _dedup_key(rec: dict) -> tuple:
    if rec.get("is_unmapped"):
        return None
    # Reads sharing a 5' mapping position + orientation are candidate duplicates (the
    # standard MarkDuplicates 5' coordinate strategy, simplified for a small-data surrogate).
    return (rec["rname"], rec["pos"], bool(rec["flag"] & 0x10))


def process_bam(
    sam_path: Optional[str] = None,
    records: Optional[list[dict]] = None,
    *,
    workdir: str = "",
) -> tuple[list[dict], dict]:
    """Sort records by coordinate and mark duplicates.

    Returns (processed_records, stats). stats includes duplicate_rate and counts.
    """
    recs = records if records is not None else (read_sam(sam_path) if sam_path else [])
    # Sort: unmapped (pos 0) at the end, then by (rname, pos).
    def _sort_key(r):
        if r.get("is_unmapped"):
            return (2, "", 0)
        return (0, r.get("rname", ""), r.get("pos", 0))

    mapped = [r for r in recs if not r.get("is_unmapped")]
    unmapped = [r for r in recs if r.get("is_unmapped")]
    mapped.sort(key=_sort_key)

    # Mark duplicates: group by dedup key, keep the highest-MAPQ first.
    dedup: dict = {}
    for r in mapped:
        key = _dedup_key(r)
        if key is None:
            continue
        if key not in dedup or r["mapq"] > dedup[key]["mapq"]:
            if key in dedup:
                dedup[key]["is_duplicate"] = True
            r["is_duplicate"] = False
            dedup[key] = r
        else:
            r["is_duplicate"] = True

    total = len(recs)
    dup = sum(1 for r in recs if r.get("is_duplicate"))
    stats = {
        "total_records": total,
        "mapped_records": len(mapped),
        "unmapped_records": len(unmapped),
        "duplicate_records": dup,
        "duplicate_rate": round(dup / total * 100.0, 2) if total else 0.0,
    }
    return mapped + unmapped, stats


def _stage6_run(sample: dict, state: dict) -> tuple[dict, dict]:
    sam_path = sample.get("bam") or sample.get("sam") or state.get("sam_path")
    records = state.get("aligned_records")
    _, stats = process_bam(sam_path, records)
    state.setdefault("bam_processed", {})["stats"] = stats
    return stats, {
        "duplicate_qc": 100.0 - stats["duplicate_rate"],
        "mapping_presence": (stats["mapped_records"] / stats["total_records"] * 100.0)
        if stats["total_records"] else 0.0,
    }


def stage6_contract() -> StageContract:
    return StageContract(
        step="bam_processing",
        tool="platform-sam-without-samtools (sort + MarkDuplicates surrogate)",
        version="0.1.0",
        inputs=["aligned_reads"],
        outputs=["sorted_bam", "duplicate_rate"],
        rules=[
            ThresholdRule(name="duplicate_qc", metric="duplicate_qc",
                          evaluate=lambda v: _dup_rule(v)),
            ThresholdRule(name="mapping_presence", metric="mapping_presence",
                          evaluate=lambda v: QcStatus.PASS if v > 0 else QcStatus.FAIL),
        ],
        fail_blocks=False,   # high duplication is a WARN, not a stop (it can be filtered)
        run=_stage6_run,
    )


def _dup_rule(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return QcStatus.FAIL
    # 100 - duplicate_rate: >= 80 -> PASS, >= 45 -> WARN, else FAIL
    if v >= 80.0:
        return QcStatus.PASS
    if v >= 45.0:
        return QcStatus.WARN
    return QcStatus.FAIL


def run_bam_processing(records: Optional[list[dict]] = None, sam_path: Optional[str] = None) -> dict:
    from app.ngs.contracts import apply_rules, QcResult
    contract = stage6_contract()
    state: dict = {}
    data, metrics = {}, {}
    if records is not None:
        _, stats = process_bam(records=records)
        state = {"aligned_records": records}
        data, metrics = _stage6_run({"records": records}, state)
        data["stats"] = stats
    else:
        data, metrics = _stage6_run({"bam": sam_path}, state)
    result = QcResult.from_metrics(apply_rules(contract.resolve_rules({}), metrics),
                                   fail_blocks=False)
    return {
        "result": {"step": "bam_processing", "qc": result.to_dict(),
                   "decision": result.decision.value, "data": data},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "stats": data},
    }

"""
Stage 7 — Alignment QC engine (blueprint Stage 7).

Collect the metrics a professional expects from aligned data and turn them into a
machine-auditable alignment-QC triage:

                 ALIGNMENT QC
       Mapping / Duplication / Insert size / Coverage / MAPQ / Pairing

Metrics computed (real, from SAM records):
    mapping_rate, proper_pair_rate, secondary_alignments, supplementary_alignments,
    MAPQ (median/mean + fraction high), insert_size (median + outlier %), duplicate_rate,
    unmapped_reads, per-contig coverage summary
"""

from __future__ import annotations

import statistics
from typing import Optional

from app.ngs.contracts import QcStatus, StageContract, ThresholdRule
from app.ngs.sam import read_sam, map_reads, align_read_exact, cigar_length
from app.ngs.stages.stage6_bam import process_bam


def alignment_qc(records: list[dict]) -> dict:
    """Compute alignment QC metrics from a list of SAM records (post MarkDuplicates)."""
    total = len(records)
    mapped = [r for r in records if not r.get("is_unmapped")]
    unmapped = [r for r in records if r.get("is_unmapped")]
    secondary = [r for r in records if r.get("is_secondary")]
    supplementary = [r for r in records if r.get("is_supplementary")]
    proper = [r for r in mapped if r.get("is_proper_pair")]
    duplicates = [r for r in records if r.get("is_duplicate")]

    mapqs = [r["mapq"] for r in mapped if r.get("mapq")]
    insert_sizes = [abs(r.get("tlen", 0)) for r in mapped
                    if r.get("tlen") and r.get("tlen") != 0 and abs(r.get("tlen")) < 2000]

    # per-contig coverage (consume reference bases per record)
    contig_bases: dict[str, int] = {}
    for r in mapped:
        if r.get("is_duplicate"):
            continue
        length = cigar_length(r.get("cigar", ""))
        contig_bases[r.get("rname", "?")] = contig_bases.get(r.get("rname", "?"), 0) + length

    med_mapq = statistics.median(mapqs) if mapqs else 0
    high_mapq = sum(1 for m in mapqs if m >= 30) / len(mapqs) * 100 if mapqs else 0.0
    med_insert = statistics.median(insert_sizes) if insert_sizes else 0
    insert_outliers = sum(1 for x in insert_sizes if x > 1000) / len(insert_sizes) * 100 if insert_sizes else 0.0

    return {
        "total_alignments": total,
        "mapped_alignments": len(mapped),
        "unmapped_reads": len(unmapped),
        "secondary_alignments": len(secondary),
        "supplementary_alignments": len(supplementary),
        "mapping_rate": round(len(mapped) / total * 100.0, 2) if total else 0.0,
        "proper_pair_rate": round(len(proper) / len(mapped) * 100.0, 2) if mapped else 0.0,
        "duplicate_rate": round(len(duplicates) / total * 100.0, 2) if total else 0.0,
        "median_mapq": med_mapq,
        "high_mapq_percent": round(high_mapq, 2),
        "median_insert_size": med_insert,
        "insert_size_outlier_percent": round(insert_outliers, 2),
        "coverage_by_contig": contig_bases,
    }


def _stage7_run(sample: dict, state: dict) -> tuple[dict, dict]:
    records = state.get("aligned_records")
    if records is None:
        sam_path = state.get("sam_path") or sample.get("bam") or sample.get("sam")
        if sam_path:
            records = read_sam(sam_path)
        else:
            return {"error": "no aligned data"}, {"mapping_ok": 0.0}
    qc = alignment_qc(records)
    state.setdefault("alignment_qc", {})["metrics"] = qc
    return qc, {
        "mapping_ok": qc["mapping_rate"],
        "proper_pair_ok": qc["proper_pair_rate"],
        "high_mapq": qc["high_mapq_percent"],
        "insert_ok": (100.0 - qc["insert_size_outlier_percent"]),
    }


def stage7_contract() -> StageContract:
    return StageContract(
        step="alignment_qc",
        tool="platform-alignment-qc",
        version="0.1.0",
        inputs=["processed_bam"],
        outputs=["alignment_qc_report"],
        rules=[
            ThresholdRule(name="mapping_ok", metric="mapping_ok",
                          evaluate=lambda v: _pct_rule(v, 95, 90)),
            ThresholdRule(name="proper_pair_ok", metric="proper_pair_ok",
                          evaluate=lambda v: _pct_rule(v, 90, 80)),
            ThresholdRule(name="high_mapq", metric="high_mapq",
                          evaluate=lambda v: _pct_rule(v, 90, 70)),
            ThresholdRule(name="insert_ok", metric="insert_ok",
                          evaluate=lambda v: _pct_rule(v, 90, 80)),
        ],
        fail_blocks=False,   # alignment QC flags problems; later stages can still run
        run=_stage7_run,
    )


def _pct_rule(v, ok, warn):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return QcStatus.FAIL
    if v >= ok:
        return QcStatus.PASS
    if v >= warn:
        return QcStatus.WARN
    return QcStatus.FAIL


def run_alignment_qc(records: Optional[list[dict]] = None, sam_path: Optional[str] = None) -> dict:
    from app.ngs.contracts import apply_rules, QcResult
    contract = stage7_contract()
    state = {"aligned_records": records} if records is not None else {
        "sam_path": sam_path}
    data, metrics = _stage7_run({"records": records} if records is not None else {"sam": sam_path}, state)
    result = QcResult.from_metrics(apply_rules(contract.resolve_rules({}), metrics),
                                   fail_blocks=False)
    return {
        "result": {"step": "alignment_qc", "qc": result.to_dict(),
                   "decision": result.decision.value, "data": data},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "metrics": data},
    }

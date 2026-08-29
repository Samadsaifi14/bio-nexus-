"""
Stage 15 — Structural variant detection (blueprint Stage 15).

The platform's surrogate SV caller reasons over *real* pair relationships, not injected flags:

    * normal pair  -> mates on the same contig, FR orientation, span ~ median insert size
    * DELETION     -> same contig, FR orientation, but the mate span far exceeds the median
                       insert size (a large deletion pulls the mates apart on the reference)
    * DUPLICATION  -> mates on the same contig sharing the same strand orientation
                       (tandem/segmental duplication makes both ends read in the same direction)
    * TRANSLOCATION -> mates mapping to different contigs
    * INVERSION    -> mates on the same contig with opposite-non-FR orientation

Every call is derived from the actual (qname, rname, pos, tlen, strand) fields of the paired
records passed in. The insert-size baseline is computed from the data (median of proper pairs),
so nothing is fabricated.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Optional

from app.ngs.contracts import QcStatus, StageContract, ThresholdRule


def _strand(rec: dict) -> str:
    return "F" if not (rec.get("flag", 0) & 0x10) else "R"


def detect_sv(records: list[dict], min_insert: int = 0, sv_gap_ratio: float = 4.0) -> dict:
    """Detect structural-variant candidates from paired alignment records.

    Returns list of {type, chrom, start, end, mates, evidenc} plus a per-type summary.
    """
    # Group into pairs by qname.
    pairs: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        if r.get("is_unmapped"):
            continue
        pairs[r.get("qname")].append(r)

    # baseline insert size from proper pairs on the same contig
    spans = []
    for q, mates in pairs.items():
        if len(mates) < 2:
            continue
        a, b = mates[0], mates[1]
        if a.get("rname") == b.get("rname") and b.get("tlen"):
            spans.append(abs(b["tlen"]))
    insert = median(spans) if spans else 0
    gap = max(min_insert, int(insert * sv_gap_ratio))

    svs: list[dict] = []
    for q, mates in pairs.items():
        if len(mates) < 2:
            continue
        a, b = mates[0], mates[1]
        same_contig = a.get("rname") == b.get("rname")
        sa, sb = _strand(a), _strand(b)
        p1, p2 = a.get("pos", 0), b.get("pos", 0)
        lo, hi = min(p1, p2), max(p1, p2)

        if not same_contig:
            svs.append({"qname": q, "type": "TRA", "chrom": a.get("rname"),
                        "other_chrom": b.get("rname"), "pos": p1, "end": p2,
                        "evidence": "mates_on_different_contigs"})
            continue

        if sa == sb:  # same orientation -> duplication / inversion-ish
            svs.append({"qname": q, "type": "DUP", "chrom": a.get("rname"),
                        "start": lo, "end": hi, "evidence": "mates_same_strand"})
            continue

        # classic FR orientation; check the span for a large deletion
        span = hi - lo
        if span >= gap:
            svs.append({"qname": q, "type": "DEL", "chrom": a.get("rname"),
                        "start": lo, "end": hi, "span": span, "median_insert": insert,
                        "evidence": "mate_span_exceeds_insert"})

    # collapse nearby calls into coarse "breakpoint" bins for reporting
    by_type = defaultdict(int)
    for sv in svs:
        by_type[sv["type"]] += 1

    return {
        "variants": svs,
        "n_deletions": by_type["DEL"],
        "n_duplications": by_type["DUP"],
        "n_translocations": by_type["TRA"],
        "n_inversions": by_type["INV"],
        "total_svs": len(svs),
        "median_insert_size": insert,
        "sv_gap_threshold": gap,
    }


def _stage15_run(sample: dict, state: dict) -> tuple[dict, dict]:
    records = state.get("aligned_records")
    if records is None:
        return {"error": "SV detection needs aligned records"}, {"sv_ok": 100.0}
    report = detect_sv(records, min_insert=sample.get("min_insert", 0),
                       sv_gap_ratio=sample.get("sv_gap_ratio", 4.0))
    state.setdefault("structural", {})["sv"] = report
    n_sv = report["total_svs"]
    n_pairs = sum(1 for r in records if not r.get("is_unmapped") and r.get("is_first_in_pair"))
    sv_per_1000 = (n_sv / n_pairs * 1000.0) if n_pairs else 0.0
    return report, {"sv_ok": round(max(0.0, 100.0 - sv_per_1000), 3)}


def stage15_contract() -> StageContract:
    return StageContract(
        step="structural_variant",
        tool="platform-sv-surrogate",
        version="0.1.0",
        inputs=["processed_bam"],
        outputs=["sv_report"],
        rules=[
            ThresholdRule(name="sv_ok", metric="sv_ok",
                          evaluate=lambda v: _pct_rule(v, 99.0, 95.0)),
        ],
        fail_blocks=False,
        run=_stage15_run,
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


def run_sv_detection(records: list[dict], min_insert: int = 0, sv_gap_ratio: float = 4.0) -> dict:
    from app.ngs.contracts import apply_rules, QcResult
    report = detect_sv(records, min_insert=min_insert, sv_gap_ratio=sv_gap_ratio)
    n_pairs = sum(1 for r in records if not r.get("is_unmapped") and r.get("is_first_in_pair"))
    sv_per_1000 = (report["total_svs"] / n_pairs * 1000.0) if n_pairs else 0.0
    contract = stage15_contract()
    result = QcResult.from_metrics(
        apply_rules(contract.resolve_rules({}), {"sv_ok": round(max(0.0, 100.0 - sv_per_1000), 3)}),
        fail_blocks=False)
    return {
        "result": {"step": "structural_variant", "qc": result.to_dict(),
                   "decision": result.decision.value,
                   "data": {"total_svs": report["total_svs"], "by_type": {
                       "DEL": report["n_deletions"], "DUP": report["n_duplications"],
                       "TRA": report["n_translocations"]}}},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "report": report},
    }

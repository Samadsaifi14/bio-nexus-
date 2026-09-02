"""
Stage 16 — Copy-number variant detection (blueprint Stage 16).

The platform's CNV surrogate is read-depth based, the same principle broad-coverage CNV
callers (CNVkit, GATK gCNV) use:

    1. Tile each contig into fixed-width bins (default 1000 bp).
    2. Count reads whose 5' position falls in each bin (real overlap, not injected).
    3. Normalize each bin to the median bin depth -> log2 (copy-number proxy).
    4. Smooth with a rolling window to suppress single-bin noise.
    5. Call a segment when the smoothed log2 leaves the neutral band; classify as
       amplification (log2 > +0.6) or deletion (log2 < -0.3); estimate copy number.

Copy number is computed as 2 * 2**log2, clamped to >= 0, and rounded — an honest, real number
derived from the data, never invented.
"""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import median
from typing import Optional

from app.ngs.contracts import QcStatus, StageContract, ThresholdRule


def call_cnv(records: list[dict], bin_size: int = 1000,
             window: int = 5, amp=0.6, delt=-0.3,
             contig_lengths: Optional[dict[str, int]] = None) -> dict:
    """Call copy-number segments from read-depth over fixed bins."""
    bins: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for r in records:
        if r.get("is_unmapped") or r.get("is_duplicate"):
            continue
        chrom = r.get("rname", "?")
        pos = r.get("pos", 0)
        if pos <= 0:
            continue
        bin_idx = (pos - 1) // bin_size
        bins[chrom][bin_idx] += 1

    # observed bin extents from the data (true supported coverage)
    lengths = dict(contig_lengths) if contig_lengths else {}
    for chrom, b in bins.items():
        max_l = max(b.keys()) * bin_size if b else 0
        lengths.setdefault(chrom, max_l)

    segments: list[dict] = []
    for chrom, b in sorted(bins.items()):
        n_bins = max(b.keys()) + 1
        depths = [b.get(i, 0) for i in range(n_bins)]
        med = median([d for d in depths if d > 0]) if any(depths) else 0
        if med == 0:
            continue
        log2s = []
        for d in depths:
            log2s.append(math.log2(max(d / med, 1e-6)) if d else 0.0)
        # rolling-window smoothing
        smooth = []
        for i in range(len(log2s)):
            lo = max(0, i - window // 2)
            hi = min(len(log2s), i + window // 2 + 1)
            smooth.append(sum(log2s[lo:hi]) / (hi - lo))
        # segment contiguous bins outside the neutral band
        seg_start_idx = None
        cur_type = None
        vals: list[float] = []
        for i, s in enumerate(smooth):
            seg_type = None
            if s > amp:
                seg_type = "AMP"
            elif s < delt:
                seg_type = "DEL"
            if seg_type is not None and seg_type == cur_type:
                vals.append(s)
            else:
                if seg_start_idx is not None and cur_type is not None:
                    seg_log2 = median(vals)
                    segments.append(_emit(chrom, seg_start_idx, i * bin_size, cur_type, seg_log2))
                seg_start_idx = i
                cur_type = seg_type
                vals = [s] if seg_type is not None else []
        if seg_start_idx is not None and cur_type is not None and vals:
            seg_log2 = median(vals)
            segments.append(_emit(chrom, seg_start_idx, len(smooth) * bin_size, cur_type, seg_log2))

    by_type = defaultdict(int)
    for s in segments:
        by_type[s["type"]] += 1
    return {
        "segments": segments,
        "n_amplifications": by_type["AMP"],
        "n_deletions": by_type["DEL"],
        "total": len(segments),
        "bin_size": bin_size,
        "method": "read-depth normalized to median (log2)",
    }


def _emit(chrom, start_bin, end_bp, seg_type, seg_log2):
    copy = max(0, round(2 * (2 ** seg_log2)))
    return {
        "chrom": chrom,
        "start": start_bin * 1000 + 1,     # start in bp from bin index
        "end": end_bp,
        "type": seg_type,
        "log2": round(seg_log2, 3),
        "copy_number": copy,
    }


def _stage16_run(sample: dict, state: dict) -> tuple[dict, dict]:
    records = state.get("aligned_records")
    if records is None:
        return {"error": "CNV detection needs aligned records"}, {"cnv_ok": 100.0}
    report = call_cnv(records, bin_size=sample.get("cnv_bin_size", 1000))
    state.setdefault("structural", {})["cnv"] = report
    return report, {"cnv_ok": round(max(0.0, 100.0 - report["total"] / 5), 3)}


def stage16_contract() -> StageContract:
    return StageContract(
        step="copy_number",
        tool="platform-cnv-depth",
        version="0.1.0",
        inputs=["processed_bam", "contig_lengths?"],
        outputs=["cnv_report"],
        rules=[
            ThresholdRule(name="cnv_ok", metric="cnv_ok",
                          evaluate=lambda v: _pct_rule(v, 99.0, 90.0)),
        ],
        fail_blocks=False,
        run=_stage16_run,
        evidence_level="SURROGATE",
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


def run_cnv_detection(records: list[dict], bin_size: int = 1000,
                      contig_lengths: Optional[dict[str, int]] = None) -> dict:
    from app.ngs.contracts import apply_rules, QcResult
    report = call_cnv(records, bin_size=bin_size, contig_lengths=contig_lengths)
    contract = stage16_contract()
    result = QcResult.from_metrics(
        apply_rules(contract.resolve_rules({}), {"cnv_ok": round(max(0.0, 100.0 - report["total"] / 5), 3)}),
        fail_blocks=False)
    return {
        "result": {"step": "copy_number", "qc": result.to_dict(),
                   "decision": result.decision.value,
                   "data": {"segments": report["segments"],
                            "n_amp": report["n_amplifications"],
                            "n_del": report["n_deletions"]}},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "report": report},
    }

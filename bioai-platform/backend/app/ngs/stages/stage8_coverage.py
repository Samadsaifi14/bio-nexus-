"""
Stage 8 — Coverage engine (blueprint Stage 8). FIRST-CLASS module, not "another tool output".

This module computes real per-base coverage from aligned reads and turns it into the
professional view a scientist needs:

    GENOME  ████████████████████ 97.4% >=20x
    TARGET  ███████████████████░ 94.8% >=20x
    POOR REGIONS  BRCA1 exon 11, TP53 exon 4, ...

Metrics (genome and target-region aware):
    mean_depths, median_depths, min_depths, max_depths,
    coverage_1x / 10x / 20x / 30x / 50x  (fraction of the locus at >= X fold)
    target_mean, target_10x/20x/30x/50x/100x
    uniformity (fraction of bases within [0.2x, 5x] of the mean), zero-coverage regions,
    poorly covered genes/exons
"""

from __future__ import annotations

import statistics
from typing import Optional

from app.ngs.contracts import QcStatus, StageContract, ThresholdRule
from app.ngs.sam import cigar_length


def build_depth(records: list[dict], ref_lengths: dict[str, int]) -> dict[str, list[int]]:
    """Per-base depth arrays per contig from mapped, non-duplicate alignments."""
    depth: dict[str, list[int]] = {}
    for r in records:
        if r.get("is_unmapped") or r.get("is_duplicate"):
            continue
        name = r.get("rname", "?")
        length = cigar_length(r.get("cigar", ""))
        start = r.get("pos", 0)
        end = start + length
        if name not in depth:
            depth[name] = [0] * ref_lengths.get(name, 0)
        arr = depth[name]
        # extend if needed when ref length unknown
        if len(arr) < end:
            arr.extend([0] * (end - len(arr)))
        for i in range(start - 1, min(end - 1, len(arr))):
            arr[i] += 1
    return depth


def _compute_locus(positions: Optional[list[int]]) -> dict:
    if not positions:
        return {
            "mean_depth": 0, "median_depth": 0, "min_depth": 0, "max_depth": 0,
            "coverage_1x": 0.0, "coverage_10x": 0.0, "coverage_20x": 0.0,
            "coverage_30x": 0.0, "coverage_50x": 0.0,
            "uniformity": 0.0, "zero_regions": [],
        }
    n = len(positions)
    mean = sum(positions) / n
    median = statistics.median(positions)
    maxd = max(positions)
    mind = min(positions)
    cov = {
        "mean_depth": round(mean, 2),
        "median_depth": median,
        "min_depth": mind,
        "max_depth": maxd,
    }
    for x in (1, 10, 20, 30, 50):
        cov[f"coverage_{x}x"] = round(sum(1 for p in positions if p >= x) / n * 100.0, 2)
    # uniformity: fraction of bases within [0.2x, 5x] of the mean depth
    lo, hi = 0.2 * mean, 5.0 * mean
    in_range = sum(1 for p in positions if lo <= p <= hi) / n * 100.0
    cov["uniformity"] = round(in_range, 2)
    # zero-coverage runs
    runs: list[dict] = []
    start = None
    prev = -2
    for i, p in enumerate(positions):
        if p == 0:
            if start is None:
                start = i
            prev = i
        else:
            if start is not None:
                runs.append({"start": start + 1, "end": prev + 1, "length": prev - start + 1})
                start = None
    if start is not None:
        runs.append({"start": start + 1, "end": prev + 1, "length": prev - start + 1})
    cov["zero_regions"] = runs[:50]
    return cov


def coverage_engine(
    records: list[dict],
    ref_lengths: dict[str, int],
    targets: Optional[list[dict]] = None,
) -> dict:
    """Compute genome + target coverage from aligned records.

    targets: list of {"name": str, "start": int(1-based), "end": int(inclusive)}.
    """
    depth = build_depth(records, ref_lengths)
    # concatenate all genomic positions for a whole-genome summary
    genome_positions: list[int] = []
    for name in sorted(depth):
        genome_positions.extend(depth[name])
    genome = _compute_locus(genome_positions)

    target_report = None
    if targets:
        target_positions: list[int] = []
        for t in targets:
            arr = depth.get(t.get("contig") or t.get("chrom") or "chr1", [])
            start = t.get("start", 1) - 1
            end = min(t.get("end", start + 1), len(arr))
            if end > start:
                target_positions.extend(arr[start:end])
        target_report = _compute_locus(target_positions)
        target_report["regions"] = [dict(t) for t in targets]

    # poorly covered genes/exons: for targets, flag those with < some threshold depth.
    poor = []
    if targets and target_report:
        for t in targets:
            arr = depth.get(t.get("contig") or "chr1", [])
            start = t.get("start", 1) - 1
            end = min(t.get("end", start + 1), len(arr))
            if end <= start:
                continue
            region_depth = arr[start:end]
            mean_r = sum(region_depth) / len(region_depth) if region_depth else 0
            cov20 = sum(1 for p in region_depth if p >= 20) / len(region_depth) * 100 if region_depth else 0
            if cov20 < 80.0:
                poor.append({"name": t.get("name"), "mean_depth": round(mean_r, 1),
                             "coverage_20x": round(cov20, 1)})

    return {
        "genome": genome,
        "target": target_report,
        "poorly_covered_regions": poor,
        "n_targets": len(targets or []),
    }


def _stage8_run(sample: dict, state: dict) -> tuple[dict, dict]:
    records = state.get("aligned_records")
    if records is None:
        sam_path = state.get("sam_path") or sample.get("bam") or sample.get("sam")
        if sam_path:
            from app.ngs.sam import read_sam
            records = read_sam(sam_path)
        else:
            return {"error": "no aligned data"}, {"coverage_ok": 0.0}
    ref_lengths = state.get("ref_lengths") or sample.get("ref_lengths") or {}
    targets = sample.get("targets") or sample.get("regions")
    eng = coverage_engine(records, ref_lengths, targets)
    state.setdefault("coverage", {})["engine"] = eng
    g = eng["genome"]
    return eng, {
        "coverage_ok": g["coverage_30x"],
        "uniformity_ok": g["uniformity"],
    }


def stage8_contract() -> StageContract:
    return StageContract(
        step="coverage",
        tool="platform-coverage-engine",
        version="0.1.0",
        inputs=["processed_bam", "reference_lengths", "target_regions?"],
        outputs=["coverage_report"],
        rules=[
            ThresholdRule(name="coverage_ok", metric="coverage_ok",
                          evaluate=lambda v: _pct_rule(v, 85, 60)),
            ThresholdRule(name="uniformity_ok", metric="uniformity_ok",
                          evaluate=lambda v: _pct_rule(v, 80, 60)),
        ],
        fail_blocks=False,
        run=_stage8_run,
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


def run_coverage(
    records: Optional[list[dict]] = None,
    ref_lengths: Optional[dict[str, int]] = None,
    targets: Optional[list[dict]] = None,
    sam_path: Optional[str] = None,
) -> dict:
    from app.ngs.contracts import apply_rules, QcResult
    contract = stage8_contract()
    state = {}
    if records is not None:
        state = {"aligned_records": records}
        data, metrics = {}, {}
        engines = coverage_engine(records, ref_lengths or {}, targets)
        state["coverage"] = {"engine": engines}
        g = engines["genome"]
        data = engines
        metrics = {"coverage_ok": g["coverage_30x"], "uniformity_ok": g["uniformity"]}
    else:
        data, metrics = _stage8_run({"sam": sam_path, "ref_lengths": ref_lengths, "targets": targets}, state)
    result = QcResult.from_metrics(apply_rules(contract.resolve_rules({}), metrics),
                                   fail_blocks=False)
    return {
        "result": {"step": "coverage", "qc": result.to_dict(),
                   "decision": result.decision.value, "data": data},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "genome": data.get("genome"), "target": data.get("target"),
                    "poorly_covered": data.get("poorly_covered_regions", [])},
    }

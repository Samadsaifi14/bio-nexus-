"""Advanced primer screening: SNP overlap and multiplex compatibility."""
from __future__ import annotations

from itertools import combinations
from typing import Any

from app.tools.oligo_qc import clean, dimer_analysis, salt_adjusted_tm


def snp_overlap(
    left_seq: str,
    right_seq: str,
    left_pos: int,
    right_pos: int,
    variants: list[dict[str, Any]],
) -> dict:
    """Map 0-based template variants onto Primer3 primer binding intervals.

    Primer3 LEFT position is the leftmost base. RIGHT position is the 3' base
    coordinate on the forward strand; therefore its covered interval extends
    leftward by primer length - 1.
    """
    left = clean(left_seq)
    right = clean(right_seq)
    left_start, left_end = int(left_pos), int(left_pos) + len(left) - 1
    right_start, right_end = int(right_pos) - len(right) + 1, int(right_pos)
    hits = []
    for variant in variants:
        try:
            pos = int(variant.get("position"))
        except (TypeError, ValueError):
            hits.append({**variant, "status": "invalid_position"})
            continue
        primer = None
        distance_from_3prime = None
        if left_start <= pos <= left_end:
            primer = "left"
            distance_from_3prime = left_end - pos
        elif right_start <= pos <= right_end:
            primer = "right"
            # Right primer's 3' end is Primer3's right_pos on the forward-strand coordinate convention.
            distance_from_3prime = right_end - pos
        if primer:
            hits.append({
                **variant,
                "status": "overlap",
                "primer": primer,
                "distance_from_3prime_bases": distance_from_3prime,
                "three_prime_critical": distance_from_3prime <= 4,
            })
    return {
        "coordinate_system": "0-based template coordinates (Primer3 convention)",
        "left_interval": [left_start, left_end],
        "right_interval": [right_start, right_end],
        "variant_count": len(variants),
        "overlap_count": sum(1 for h in hits if h.get("status") == "overlap"),
        "critical_3prime_overlap_count": sum(1 for h in hits if h.get("three_prime_critical")),
        "overlaps": hits,
    }


def multiplex_compatibility(pairs: list[dict[str, Any]], max_tm_spread: float = 3.0) -> dict:
    """Screen primer pairs for multiplex use using Tm spread and cross-dimers.

    This is a deterministic screening heuristic. It does not model full PCR
    kinetics, reagent competition, target abundance or empirical efficiency.
    """
    normalized = []
    all_primers: list[tuple[str, str]] = []
    for idx, pair in enumerate(pairs):
        left = clean(str(pair.get("left_seq") or ""))
        right = clean(str(pair.get("right_seq") or ""))
        if not left or not right:
            raise ValueError(f"pair {idx} requires left_seq and right_seq")
        pid = str(pair.get("id") or f"pair-{idx+1}")
        left_tm = float(pair.get("left_tm") or salt_adjusted_tm(left))
        right_tm = float(pair.get("right_tm") or salt_adjusted_tm(right))
        normalized.append({"id": pid, "left_seq": left, "right_seq": right, "left_tm": left_tm, "right_tm": right_tm})
        all_primers.extend([(f"{pid}:left", left), (f"{pid}:right", right)])

    tms = [p["left_tm"] for p in normalized] + [p["right_tm"] for p in normalized]
    tm_spread = max(tms) - min(tms) if tms else 0.0
    cross_dimers = []
    high_risk = 0
    for (name_a, seq_a), (name_b, seq_b) in combinations(all_primers, 2):
        if name_a.split(":")[0] == name_b.split(":")[0]:
            continue
        dimer = dimer_analysis(seq_a, seq_b)
        risk = dimer.get("risk", "none")
        if risk in {"high", "medium"}:
            high_risk += 1
        cross_dimers.append({
            "primer_a": name_a,
            "primer_b": name_b,
            "dg": dimer.get("dg"),
            "risk": risk,
            "three_prime_involved": bool(dimer.get("involves_a3") or dimer.get("involves_b3")),
        })

    compatible = tm_spread <= max_tm_spread and high_risk == 0
    return {
        "pair_count": len(normalized),
        "tm_range": [round(min(tms), 2), round(max(tms), 2)] if tms else None,
        "tm_spread_c": round(tm_spread, 2),
        "max_tm_spread_c": max_tm_spread,
        "cross_dimer_comparisons": len(cross_dimers),
        "medium_or_high_cross_dimers": high_risk,
        "compatible_screen": compatible,
        "cross_dimers": cross_dimers,
        "evidence_class": "Heuristic",
        "limitation": "Multiplex compatibility is an in-silico screen; empirical multiplex PCR optimization remains required.",
    }

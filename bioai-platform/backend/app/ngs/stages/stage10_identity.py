"""
Stage 10 — Identity / sample concordance (blueprint Stage 10). FAIL-BLOCKING gate.

Guards against the embarrassing, dangerous classes of error: the wrong sample in the well,
the wrong label on the tube, unexpected sex, or a normal/tumor swap.

This stage computes, from the aligned data:
    * a genotype concordance rate against an expected genotype set (identity check),
    * predicted sex from reads on chrX / chrY (sex check),
    * (optionally) a match flag against an expected sex for the sample.

A concordance below threshold or a sex mismatch is treated as a STOP (mislabeled or swapped
sample cannot be analysed downstream).
"""

from __future__ import annotations

from typing import Optional

from app.ngs.contracts import QcStatus, StageContract, ThresholdRule
from app.ngs.sam import cigar_length


def _pileup_at_loci(records: list[dict], loci: set[int]) -> dict[int, list[str]]:
    wanted = set(loci)
    pile: dict[int, list[str]] = {p: [] for p in wanted}
    for r in records:
        if r.get("is_unmapped") or r.get("is_duplicate"):
            continue
        seq = r.get("seq", "")
        start = r.get("pos", 0) - 1
        length = cigar_length(r.get("cigar", ""))
        if r.get("cigar") != f"{length}M":
            continue
        for i in range(length):
            p = start + i + 1
            if p in wanted and i < len(seq):
                pile[p].append(seq[i])
    return pile


def _call_gt(alleles: list[str]) -> Optional[str]:
    if not alleles:
        return None
    counts: dict[str, int] = {}
    for a in alleles:
        counts[a.upper()] = counts.get(a.upper(), 0) + 1
    total = sum(counts.values())
    majors = [a for a, c in counts.items() if c / total >= 0.8]
    if len(majors) == 1:
        return f"{majors[0]}/{majors[0]}" if majors[0] != "N" else None
    if len(majors) == 2:
        return f"{majors[0]}/{majors[1]}"
    return None


def identity_engine(
    records: list[dict],
    expected_gt: Optional[list[dict]] = None,
    chr_x_depth: float = 0.0,
    chr_y_depth: float = 0.0,
    expected_sex: Optional[str] = None,
) -> dict:
    """Compute identity/concordance + sex.

    expected_gt: [{"pos": int, "gt": "A/A"}...]; observed is called from the pileup.
    expected_sex: "male"/"female" if the tube label must be verified.
    """
    concordance = None
    gt_called = 0
    gt_matched = 0
    if expected_gt:
        loci = {g["pos"] for g in expected_gt}
        pile = _pileup_at_loci(records, loci)
        for g in expected_gt:
            called = _call_gt(pile.get(g["pos"], []))
            if called is None:
                continue
            gt_called += 1
            expected = g["gt"].replace("/", "").upper()
            observed = called.replace("/", "").upper()
            if sorted(observed) == sorted(expected):
                gt_matched += 1
        concordance = round(gt_matched / gt_called * 100.0, 2) if gt_called else 0.0

    # Sex prediction from chrX / chrY read burden.
    predicted_sex = None
    sex_match = None
    if chr_y_depth > 0:
        y_frac = chr_y_depth / max(chr_y_depth + chr_x_depth, 1.0)
        predicted_sex = "male" if y_frac > 0.02 else "female"
        if expected_sex:
            sex_match = (predicted_sex == expected_sex)

    return {
        "concordance": concordance,
        "genotypes_typed": gt_called,
        "genotypes_matched": gt_matched,
        "predicted_sex": predicted_sex,
        "expected_sex": expected_sex,
        "sex_match": sex_match,
    }


def _stage10_run(sample: dict, state: dict) -> tuple[dict, dict]:
    records = state.get("aligned_records")
    if records is None:
        return ({"error": "identity needs aligned reads",
                 "unevaluated": "no aligned reads"},
                {"identity_checked": 0.0})   # WARN: cannot assert identity without alignment
    eng = identity_engine(
        records,
        expected_gt=sample.get("expected_gt"),
        chr_x_depth=sample.get("chr_x_depth", state.get("chr_x_depth", 0.0)),
        chr_y_depth=sample.get("chr_y_depth", state.get("chr_y_depth", 0.0)),
        expected_sex=sample.get("expected_sex"),
    )
    state.setdefault("identity", {})["engine"] = eng
    # Without any reference genotype/sex data the check cannot be performed. Flag it as
    # unevaluated (WARN) rather than silently passing or hard-failing the pipeline.
    if eng["concordance"] is None and eng["sex_match"] is None:
        eng["unevaluated"] = ("no expected genotype or sex supplied; sample identity not asserted")
        return eng, {"identity_checked": 0.0}
    metrics = {}
    if eng["concordance"] is not None:
        metrics["concordance_ok"] = eng["concordance"]
    if eng["sex_match"] is not None:
        metrics["sex_ok"] = 100.0 if eng["sex_match"] else 0.0
    metrics["identity_checked"] = 100.0
    return eng, metrics


def stage10_contract() -> StageContract:
    return StageContract(
        step="identity",
        tool="platform-identity (concordance + sex)",
        version="0.1.0",
        inputs=["processed_bam", "expected_genotypes?", "expected_sex?"],
        outputs=["identity_report"],
        rules=[
            ThresholdRule(name="identity_checked", metric="identity_checked",
                          evaluate=lambda v: _checked_rule(v)),
            ThresholdRule(name="concordance_ok", metric="concordance_ok",
                          evaluate=lambda v: _match_rule(v, 99.0), optional=True),
            ThresholdRule(name="sex_ok", metric="sex_ok",
                          evaluate=lambda v: _bool_rule(v), optional=True),
        ],
        fail_blocks=True,   # mislabeled/swapped sample stops the run
        run=_stage10_run,
    )


def _checked_rule(v):
    # 100 = a real check ran; 0 = unevaluated (WARN, not blocking)
    return QcStatus.PASS if float(v) >= 100.0 else QcStatus.WARN


def _match_rule(v, ok):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return QcStatus.FAIL
    return QcStatus.PASS if v >= ok else QcStatus.FAIL


def _bool_rule(v):
    return QcStatus.PASS if float(v) >= 50.0 else QcStatus.FAIL


def run_identity(
    records: list[dict],
    expected_gt: Optional[list[dict]] = None,
    chr_x_depth: float = 0.0,
    chr_y_depth: float = 0.0,
    expected_sex: Optional[str] = None,
) -> dict:
    from app.ngs.contracts import apply_rules, QcResult
    eng = identity_engine(records, expected_gt, chr_x_depth, chr_y_depth, expected_sex)
    metrics = {}
    if eng["concordance"] is None and eng["sex_match"] is None:
        metrics["identity_checked"] = 0.0
    else:
        metrics["identity_checked"] = 100.0
    if eng["concordance"] is not None:
        metrics["concordance_ok"] = eng["concordance"]
    if eng["sex_match"] is not None:
        metrics["sex_ok"] = 100.0 if eng["sex_match"] else 0.0
    contract = stage10_contract()
    result = QcResult.from_metrics(apply_rules(contract.resolve_rules({}), metrics),
                                   fail_blocks=True)
    return {
        "result": {"step": "identity", "qc": result.to_dict(),
                   "decision": result.decision.value, "data": eng},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "concordance": eng["concordance"], "predicted_sex": eng["predicted_sex"],
                    "sex_match": eng["sex_match"]},
    }

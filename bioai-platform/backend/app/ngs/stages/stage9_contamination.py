"""
Stage 9 — Contamination estimate (blueprint Stage 9). FAIL-BLOCKING gate.

Real-world pipelines detect contamination with tools like VerifyBAMID (allele balance at
known SNPs -> freemix), FastQ Screen, or QualiMap. The platform does the same idea with its
own surrogate: at a panel of known homozygous-reference (AF ~ 1.0) SNP sites, any reads
carrying the alternate allele indicate foreign DNA. The alternate-allele fraction at these
sites becomes a contamination rate.

    contam_rate <= 2%   PASS   (pure sample)
    contam_rate <= 5%   WARN
    contam_rate  > 5%   FAIL   -> gate STOPs downstream variant calling
"""

from __future__ import annotations

from typing import Optional

from app.ngs.contracts import QcStatus, StageContract, ThresholdRule
from app.ngs.sam import cigar_length


def _pileup_at_loci(records: list[dict], loci: list[dict]) -> dict[int, list[str]]:
    """Return {pos: [bases...]} for the given loci, from mapped, non-dup records."""
    wanted = {l["pos"] for l in loci}
    pile: dict[int, list[str]] = {p: [] for p in wanted}
    for r in records:
        if r.get("is_unmapped") or r.get("is_duplicate"):
            continue
        seq = r.get("seq", "")
        start = r.get("pos", 0) - 1
        length = cigar_length(r.get("cigar", ""))
        if r.get("cigar") != f"{length}M":   # only handle pure M alignments here
            continue
        for i in range(length):
            p = start + i + 1
            if p in wanted and i < len(seq):
                pile[p].append(seq[i])
    return pile


def contamination_engine(records: list[dict], snp_sites: list[dict]) -> dict:
    """Estimate contamination from a panel of known homozygous-reference SNPs.

    snp_sites: [{"pos": int, "ref": "A"}...] at which the reference panel is homozygous
    for the reference allele; any alt read implies foreign DNA.
    """
    if not snp_sites:
        return {"contam_rate": 0.0, "status": "PASS", "sites": 0,
                "alt_reads": 0, "total_reads": 0}
    pile = _pileup_at_loci(records, snp_sites)
    total_reads = 0
    alt_reads = 0
    for site in snp_sites:
        bases = pile.get(site["pos"], [])
        ref = site["ref"].upper()
        for b in bases:
            total_reads += 1
            if b.upper() != ref:
                alt_reads += 1
    rate = (alt_reads / total_reads) if total_reads else 0.0
    status = "PASS"
    if rate > 0.05:
        status = "FAIL"
    elif rate > 0.02:
        status = "WARN"
    return {
        "contam_rate": round(rate * 100.0, 3),
        "status": status,
        "sites_typed": min(len(snp_sites), len([s for s in snp_sites if pile.get(s["pos"])])),
        "alt_reads": alt_reads,
        "total_reads": total_reads,
    }


def _stage9_run(sample: dict, state: dict) -> tuple[dict, dict]:
    records = state.get("aligned_records")
    sites = sample.get("snp_sites") or state.get("snp_sites") or []
    if records is None:
        return ({"error": "contamination needs aligned records",
                 "unevaluated": "no aligned reads"},
                {"contam_checked": 0.0, "contam_ok": 100.0})
    if not sites:
        return ({"unevaluated": "no SNP panel supplied; contamination not asserted",
                 "contam_rate": 0.0},
                {"contam_checked": 0.0, "contam_ok": 100.0})
    eng = contamination_engine(records, sites)
    state.setdefault("contamination", {})["engine"] = eng
    return eng, {"contam_checked": 100.0, "contam_ok": round(100.0 - eng["contam_rate"], 3)}


def stage9_contract() -> StageContract:
    return StageContract(
        step="contamination",
        tool="platform-contamination (VerifyBAMID-style allele balance)",
        version="0.1.0",
        inputs=["processed_bam", "snp_sites"],
        outputs=["contamination_report"],
        rules=[
            ThresholdRule(name="contam_checked", metric="contam_checked",
                          evaluate=lambda v: _checked_rule(v)),
            ThresholdRule(name="contam_ok", metric="contam_ok",
                          evaluate=lambda v: _invert_pct_rule(v, 98.0, 95.0)),
        ],
        fail_blocks=True,   # contamination FAIL blocks downstream variant calling
        run=_stage9_run,
        evidence_level="SURROGATE",
    )


def _checked_rule(v):
    # 100 = a real SNP-panel check ran; 0 = unevaluated (WARN, not blocking)
    return QcStatus.PASS if float(v) >= 100.0 else QcStatus.WARN


def _invert_pct_rule(v, ok, warn):
    # ok = min "purity" for PASS, warn = min for WARN; below warn -> FAIL
    try:
        v = float(v)
    except (TypeError, ValueError):
        return QcStatus.FAIL
    if v >= ok:
        return QcStatus.PASS
    if v >= warn:
        return QcStatus.WARN
    return QcStatus.FAIL


def run_contamination(
    records: list[dict],
    snp_sites: list[dict],
) -> dict:
    from app.ngs.contracts import apply_rules, QcResult
    eng = contamination_engine(records, snp_sites)
    metrics = {"contam_ok": round(100.0 - eng["contam_rate"], 3),
               "contam_checked": 100.0 if snp_sites else 0.0}
    contract = stage9_contract()
    result = QcResult.from_metrics(apply_rules(contract.resolve_rules({}), metrics),
                                   fail_blocks=True)
    return {
        "result": {"step": "contamination", "qc": result.to_dict(),
                   "decision": result.decision.value, "data": eng},
        "summary": {"status": result.status.value, "decision": result.decision.value,
                    "contam_rate": eng["contam_rate"]},
    }

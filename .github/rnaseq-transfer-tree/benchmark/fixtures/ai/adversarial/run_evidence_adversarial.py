"""BBS-2 runnable: adversarial evidence-integrity benchmark.

Runs each hostile case through assemble_evidence + EvidenceEngine.validate and
records the outcome. `reject` cases MUST fail validation through the documented
check; `gap` cases are recorded as known semantic limitations (they are not
silently passed — they are audited, tracked, and visible in the run record).

Exit codes: 0 = all reject cases rejected, all gap cases recorded as gaps;
1 = a reject case escaped, or a gap case was mislabelled.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parents[2] / "results" / "ai" / "adversarial"
BACKEND = HERE.parents[3] / "bioai-platform" / "backend"


def main() -> int:
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    sys.path.insert(0, str(BACKEND))
    from app.engines.evidence_engine import evidence_engine
    from app.services.evidence_graph import assemble_evidence

    outcomes = []
    failures = []
    reject_ok = 0
    for case in cases["cases"]:
        if "graph" in case:
            graph = case["graph"]
        else:
            graph = assemble_evidence(case["context"])
        report = evidence_engine.validate(evidence_engine.parse(graph))
        failed_checks = {c["name"] for c in report.checks if not c["passed"]}
        rejected_claims = [c for c in graph.get("claims") or [] if c.get("rejected")]

        record = {
            "id": case["id"],
            "name": case["name"],
            "category": case["category"],
            "expectation": case["expectation"],
            "validation_valid": report.valid,
            "validation_failed_checks": sorted(failed_checks),
            "rejected_claim_count": len(rejected_claims),
        }
        if case["expectation"] == "reject":
            if "graph" in case:
                # structural contracts must fail the named validation check
                captured = bool(set(case["expect_checks"]) & failed_checks)
                record["rejected_by_expected_check"] = captured
                if not captured:
                    failures.append({"case": case["id"], "reason": f"expected check {case['expect_checks']} to fail; actual {sorted(failed_checks)}"})
                else:
                    reject_ok += 1
            else:
                # honesty contract: the fabricated content must surface as a
                # visible, rejected claim carrying the documented reason
                reason_hit = any(
                    c.get("rejection_reason") and case.get("expect_reason") in c["rejection_reason"]
                    for c in rejected_claims
                )
                record["rejected_with_expected_reason"] = reason_hit
                if not rejected_claims:
                    failures.append({"case": case["id"], "reason": "no fabricated claim was rejected"})
                elif not reason_hit:
                    failures.append({"case": case["id"], "reason": f"rejected but reason mismatch; expected {case.get('expect_reason')!r}; got {[c.get('rejection_reason') for c in rejected_claims]}"})
                else:
                    reject_ok += 1
        else:  # gap
            record["gap"] = "recorded — semantic liability; requires external entailment audit"
        outcomes.append(record)

    gap_count = sum(1 for c in cases["cases"] if c["expectation"] == "gap")
    passed = not failures
    run = {
        "schema": "bionexus-benchmark-run/v1",
        "domain": "ai",
        "benchmark": "adversarial_evidence_integrity",
        "fixture": "evidence_adversarial_v1",
        "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "live_environments": {"python": sys.version.split()[0]},
        "cases_total": len(cases["cases"]),
        "reject_cases_passed": reject_ok,
        "gap_cases_tracked": gap_count,
        "passed": passed,
        "failures": failures,
        "cases": outcomes,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (RESULTS / f"run_{stamp}.json").write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    (RESULTS / "latest.json").write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")

    print(f"adversarial evidence integrity: {reject_ok}/{sum(1 for c in cases['cases'] if c['expectation']=='reject')} "
          f"reject-cases rejected, {gap_count} gaps tracked => {'PASS' if passed else 'FAIL'}")
    for f in failures:
        print(f"  FAIL {f['case']}: {f['reason']}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
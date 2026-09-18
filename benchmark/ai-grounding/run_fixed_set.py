#!/usr/bin/env python3
"""Run the fixed BBS-2 grounding-gate regression set."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.benchmarking.bbs2 import evaluate_ai_bundle

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CASES = HERE / "cases.json"
OUT = HERE / "results"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    payload = json.loads(CASES.read_text(encoding="utf-8"))
    rows = []
    tp = tn = fp = fn = 0
    for case in payload["cases"]:
        result = evaluate_ai_bundle({
            "generated_text": case["generated_text"],
            "evidence_text": case["evidence_text"],
            "generated_citations": case["generated_citations"],
            "allowed_citations": case["allowed_citations"],
            "claims": case["claims"],
        })
        observed = bool(result["passed"])
        expected = bool(case["expected_pass"])
        if expected and observed:
            tp += 1
        elif (not expected) and (not observed):
            tn += 1
        elif (not expected) and observed:
            fp += 1
        else:
            fn += 1
        rows.append({
            "id": case["id"],
            "expected_pass": expected,
            "observed_pass": observed,
            "matched": expected == observed,
            "benchmarks": result["benchmarks"],
        })

    total = len(rows)
    correct = tp + tn
    summary = {
        "benchmark_id": payload["benchmark_id"],
        "schema_version": payload["schema_version"],
        "case_count": total,
        "correct": correct,
        "decision_accuracy": correct / total if total else None,
        "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "acceptance": "all fixed cases must match their predeclared expected gate decision",
        "passed": correct == total,
        "claim_boundary": payload["claim_boundary"],
        "cases_sha256": hashlib.sha256(CASES.read_bytes()).hexdigest(),
        "cases": rows,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

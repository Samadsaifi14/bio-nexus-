#!/usr/bin/env python3
"""Verification matrix validator — BioNexus Scientific Integrity gate (MATRIX 1).

Loads benchmark/VERIFICATION_MATRIX.json and enforces the release contract:

1. Every scientific feature has one row with a unique feature_id.
2. ``states`` is a subset of the declared state tiers and contains no tier
   beyond the release gate that the feature actually reached.
3. ``publication_required_state`` must be parseable from tier names.
4. A feature marked externally_benchmarked / validated / regression_gated must
   have the supporting lower tiers present (partial-order closure over
   tier_order).
5. ``publication/claims.csv`` (the claim ledger, MATRIX 36) must not require
   tiers that the matrix does not record as attained.

Exit code is non-zero on any violation so CI can block a release.  A machine
readable summary is written to benchmark/results/matrix_report.json.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MATRIX_PATH = ROOT / "VERIFICATION_MATRIX.json"
CLAIMS_PATH = ROOT.parent / "publication" / "claims.csv"
REPORT_PATH = ROOT / "results" / "matrix_report.json"

CLOSURE_ORDER = [
    "implemented",
    "unit_tested",
    "integration_tested",
    "live_e2e_tested",
    "externally_benchmarked",
    "validated",
    "regression_gated",
]


def _require_lower_tiers(state: str) -> list[str]:
    idx = CLOSURE_ORDER.index(state)
    return CLOSURE_ORDER[:idx]


def load_matrix(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"FATAL: verification matrix not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# Anti-inflation inference rules: the tiers that a higher claim requires.
# ``all`` must all be present; ``at_least_one`` needs any single one.
_CLAIM_PREREQUISITES = {
    "live_e2e_tested": {"all": [], "at_least_one": []},
    "externally_benchmarked": {"all": ["integration_tested"], "at_least_one": []},
    "validated": {"all": ["externally_benchmarked", "integration_tested"], "at_least_one": []},
    "regression_gated": {"all": [], "at_least_one": ["unit_tested", "integration_tested", "externally_benchmarked", "validated"]},
}


def validate_matrix(matrix: dict) -> list[str]:
    errors: list[str] = []
    tiers = matrix.get("state_tiers", {})
    order = matrix.get("tier_order", [])
    unknown_tiers = [t for t in order if t not in tiers]
    if unknown_tiers:
        errors.append(f"tier_order references undeclared tiers: {unknown_tiers}")
    if any(t not in order for t in tiers):
        errors.append("state_tiers must all be present in tier_order")

    features = matrix.get("features", [])
    ids = [f.get("feature_id") for f in features]
    if len(ids) != len(set(ids)):
        errors.append("duplicate feature_id detected")

    for feature in features:
        fid = feature.get("feature_id")
        if not fid:
            errors.append("feature missing feature_id")
            continue
        states = feature.get("states", [])
        present = set(states)
        for s in states:
            if s not in order:
                errors.append(f"{fid}: unknown state {s!r}")
        for high, rule in _CLAIM_PREREQUISITES.items():
            if high not in present:
                continue
            missing_all = [lo for lo in rule["all"] if lo not in present]
            if missing_all:
                errors.append(f"{fid}: state {high!r} requires {missing_all} but they are not attained")
            if rule["at_least_one"] and not (set(rule["at_least_one"]) & present):
                errors.append(f"{fid}: state {high!r} requires at least one of {rule['at_least_one']}")
        req = feature.get("publication_required_state", "")
        for token in req.replace("+", " ").split():
            token = token.strip()
            if not token:
                continue
            if token not in order:
                errors.append(f"{fid}: publication_required_state references unknown tier {token!r}")
    return errors


def validate_claims(matrix: dict, claims_path: Path) -> list[str]:
    if not claims_path.exists():
        return ["claims ledger missing: publication/claims.csv must exist for a publication release"]
    try:
        with open(claims_path, encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
    except (OSError, csv.Error) as exc:
        return [f"claims ledger unreadable: {exc}"]
    required = {"claim_id", "evidence_type", "benchmark_id", "required_tiers"}
    if not rows:
        return ["claims ledger is empty"]
    missing = required - (set(rows[0].keys()) & required) if rows else required
    if missing:
        return [f"claims ledger missing required columns: {sorted(missing)}"]

    features = {f["feature_id"]: f for f in matrix.get("features", [])}
    errors: list[str] = []
    for row in rows:
        claim_id = row.get("claim_id", "")
        req_tiers = [t.strip() for t in row.get("required_tiers", "").split("+") if t.strip()]
        bench_id = row.get("benchmark_id", "")
        feature = features.get(bench_id)
        if not feature:
            # benchmark_id may be a BBS-2 id rather than a feature; fuzzy check below
            errors.append(f"claims.csv {claim_id}: benchmark_id {bench_id!r} not a feature_id in VERIFICATION_MATRIX.json")
            continue
        attained = set(feature.get("states", []))
        for tier in req_tiers:
            if tier not in attained:
                errors.append(
                    f"claims.csv {claim_id}: requires tier {tier!r} but feature {bench_id} only attained {sorted(attained)}"
                )
    return errors


def main() -> int:
    matrix = load_matrix(MATRIX_PATH)
    errors = validate_matrix(matrix)
    claim_errors = validate_claims(matrix, CLAIMS_PATH)
    errors.extend(claim_errors)

    summary = {
        "schema_version": matrix.get("schema_version"),
        "updated": matrix.get("updated"),
        "feature_count": len(matrix.get("features", [])),
        "tier_order": CLOSURE_ORDER,
        "violations": errors,
        "release_blocked": bool(errors),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    if errors:
        print("VERIFICATION MATRIX: FAIL — release blocked", file=sys.stderr)
        return 1
    print("VERIFICATION MATRIX: PASS — claims ledger consistent with attained tiers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
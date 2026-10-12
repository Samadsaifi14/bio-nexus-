"""Verification matrix gate (MATRIX 1 / 2 / 36).

The VERIFICATION_MATRIX.json is the single source of truth for what has been
verified about each scientific feature. This test reproduces the release gate
locally and in CI so violations are caught before merge:

* every feature row is structurally valid and its tiers are declared;
* a feature cannot claim `validated` without being externally benchmarked;
* the publication claims ledger cannot require tiers the matrix has not
  attained.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MATRIX_PATH = REPO_ROOT / "benchmark" / "VERIFICATION_MATRIX.json"
VALIDATOR = REPO_ROOT / "benchmark" / "verify_matrix.py"
CLAIMS_PATH = REPO_ROOT / "publication" / "claims.csv"


def _load() -> dict:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def test_matrix_file_exists_and_is_valid_json():
    assert MATRIX_PATH.exists()
    matrix = _load()
    assert matrix["schema_version"]
    assert matrix["tier_order"]


def test_every_tool_card_has_a_matrix_row():
    matrix = _load()
    feature_ids = {f["feature_id"] for f in matrix["features"]}
    tool_to_feature = matrix["tool_to_feature"]
    sys.path.insert(0, str(REPO_ROOT / "bioai-platform" / "backend"))
    from app.tools.tool_cards import get_tool_cards

    # forward: every registered tool id must appear in the mapping and resolve to an existing feature
    missing_mapping = [t["id"] for t in get_tool_cards() if t["id"] not in tool_to_feature]
    assert not missing_mapping, f"tools missing tool_to_feature mapping: {missing_mapping}"
    dangling = [tool for tool, fid in tool_to_feature.items() if fid not in feature_ids]
    assert not dangling, f"tool_to_feature references unknown matrix rows: {dangling}"
    # reverse: every mapped tool must be a registered tool card
    registered = {t["id"] for t in get_tool_cards()}
    phantom = [tool for tool in tool_to_feature if tool not in registered]
    assert not phantom, f"tool_to_feature references tools that are not registered: {phantom}"


def test_validator_script_runs_clean():
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    report = json.loads(Path(REPO_ROOT / "benchmark" / "results" / "matrix_report.json").read_text(encoding="utf-8"))
    assert proc.returncode == 0, proc.stderr[-3000:]
    assert report["release_blocked"] is False
    assert report["violations"] == []


def test_claims_ledger_exists_and_is_wellformed():
    assert CLAIMS_PATH.exists()
    import csv

    with open(CLAIMS_PATH, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert rows
    for row in rows:
        assert row["claim_id"]
        assert row["required_tiers"]
        assert row["benchmark_id"]


def test_claims_never_exceed_attained_tiers():
    matrix = _load()
    features = {f["feature_id"]: set(f["states"]) for f in matrix["features"]}
    import csv

    with open(CLAIMS_PATH, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        fid = row["benchmark_id"]
        assert fid in features, f"claims.csv references unknown feature {fid}"
        for tier in (t.strip() for t in row["required_tiers"].split("+") if t.strip()):
            assert tier in features[fid], (
                f"claim {row['claim_id']} requires {tier!r} but {fid} only attained {sorted(features[fid])}"
            )
#!/usr/bin/env python3
"""Score observed calls against a supplied truth set.

The fixture is a deterministic synthetic positive control. This script reports
exact CHROM/POS/REF/ALT concordance only; it does not evaluate indels, difficult
regions, structural variants, CNVs or clinical significance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def rows(path: Path) -> set[tuple[str, str, str, str]]:
    lines = [line for line in path.read_text(encoding="utf-8").strip().splitlines() if line.strip()]
    if not lines:
        return set()
    return {tuple(line.split("\t")[:4]) for line in lines[1:] if line.strip()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth", required=True, type=Path)
    parser.add_argument("--calls", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    truth = rows(args.truth)
    observed = rows(args.calls)
    tp = len(observed & truth)
    fp = len(observed - truth)
    fn = len(truth - observed)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    payload = {
        "benchmark": "bionexus-tiny-target-v1",
        "classification": "SYNTHETIC_POSITIVE_CONTROL",
        "biological_scope": "one heterozygous SNP in a 200 bp synthetic target",
        "truth_rows": len(truth),
        "observed_rows": len(observed),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "normalized_calls_sha256": hashlib.sha256(args.calls.read_bytes()).hexdigest(),
        "limitations": [
            "Tests deterministic workflow execution, not real-sample accuracy.",
            "Does not validate indels, difficult regions, structural variants, CNVs or annotation.",
            "Cannot support claims of parity with nf-core/sarek as a whole or a public Galaxy server.",
        ],
    }
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

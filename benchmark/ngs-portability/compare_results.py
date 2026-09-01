#!/usr/bin/env python3
"""Compare normalized calls from Bio-Nexus, Nextflow and Galaxy to exact truth."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def rows(path: Path) -> set[tuple[str, str, str, str, str]]:
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return {tuple(line.split("\t")[:5]) for line in lines[1:] if line.strip()}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(observed: set[tuple[str, ...]], truth: set[tuple[str, ...]]) -> dict[str, float | int]:
    tp = len(observed & truth)
    fp = len(observed - truth)
    fn = len(truth - observed)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--truth", required=True, type=Path)
    parser.add_argument("--result", required=True, action="append", type=Path)
    parser.add_argument("--label", required=True, action="append")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if len(args.result) != len(args.label):
        raise SystemExit("--result and --label counts must match")
    truth = rows(args.truth)
    reports = []
    for label, path in zip(args.label, args.result):
        observed = rows(path)
        reports.append({"orchestrator": label, "normalized_sha256": digest(path), **score(observed, truth)})
    parity = len({item["normalized_sha256"] for item in reports}) == 1
    payload = {
        "benchmark": "bionexus-tiny-target-v1",
        "classification": "SYNTHETIC_POSITIVE_CONTROL",
        "workflow_output_parity": parity,
        "biological_scope": "one heterozygous SNP in a 200 bp synthetic target",
        "reports": reports,
        "limitations": [
            "Tests deterministic workflow portability, not real-sample accuracy.",
            "Does not validate indels, difficult regions, structural variants, CNVs or annotation.",
            "Cannot support claims of parity with nf-core/sarek as a whole or a public Galaxy server.",
        ],
    }
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if not parity or any(item["f1"] != 1.0 for item in reports):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

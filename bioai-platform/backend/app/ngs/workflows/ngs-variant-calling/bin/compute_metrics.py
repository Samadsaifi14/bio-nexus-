#!/usr/bin/env python3
"""Compute auditable run metrics for the BioNexus NGS workflow.

Only observed values are written. Tool versions are recorded from the binaries
that actually executed inside the workflow process.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def _run(argv: list[str]) -> str:
    completed = subprocess.run(argv, capture_output=True, check=False)
    return completed.stdout.decode("utf-8", errors="replace").strip()


def _first_line_version(binary: str, program: str) -> str:
    text = _run([binary, "--version"])
    if not text:
        return "unavailable"
    match = re.search(rf"{re.escape(program)}\s+(\S+)", text, re.IGNORECASE)
    return match.group(1) if match else text.splitlines()[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vcf", required=True, type=Path)
    parser.add_argument("--tsv", required=True, type=Path)
    parser.add_argument("--bam", required=True, type=Path)
    parser.add_argument("--fai", required=True, type=Path)
    parser.add_argument("--min-qual", required=True, type=float)
    parser.add_argument("--min-dp", required=True, type=float)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    call_rows = [line for line in args.tsv.read_text(encoding="utf-8").splitlines() if line.strip()][1:]
    reference_length = 0
    for line in args.fai.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) > 1 and fields[1].isdigit():
            reference_length += int(fields[1])

    mapped_reads = int(_run(["samtools", "view", "-c", "-F", "4", str(args.bam)]) or 0)
    depth_text = _run(["samtools", "depth", "-a", str(args.bam)])
    depths = [int(line.split("\t")[2]) for line in depth_text.splitlines() if len(line.split("\t")) > 2]
    mean_depth = round(sum(depths) / len(depths), 4) if depths else 0.0

    payload = {
        "workflow": "bionexus/ngs-variant-calling",
        "called_variants": len(call_rows),
        "mapped_reads": mapped_reads,
        "reference_length": reference_length,
        "mean_depth": mean_depth,
        "filter": f"QUAL>={args.min_qual} && FORMAT/DP>={args.min_dp}",
        "tool_versions": {
            "samtools": _first_line_version("samtools", "samtools"),
            "bcftools": _first_line_version("bcftools", "bcftools"),
        },
        "source_files": {"vcf": args.vcf.name, "tsv": args.tsv.name, "bam": args.bam.name},
    }
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

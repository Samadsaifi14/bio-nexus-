#!/usr/bin/env python3
"""Create a deterministic 20-read targeted benchmark with one known heterozygous SNP."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True, type=Path)
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    reference = "ACGT" * 50
    reference_path = args.outdir / "reference.fa"
    reference_path.write_text(f">chrTiny\n{reference}\n", encoding="utf-8")

    sam_path = args.outdir / "reads.sam"
    with sam_path.open("w", encoding="utf-8") as sam:
        sam.write("@HD\tVN:1.6\tSO:coordinate\n@SQ\tSN:chrTiny\tLN:200\n@RG\tID:rg1\tSM:TINY001\n")
        for index in range(20):
            sequence = list(reference[:100])
            if index >= 10:
                sequence[49] = "G"  # chrTiny:50 C>G, 10/20 reads => heterozygous truth.
            sam.write(
                f"read{index:02d}\t0\tchrTiny\t1\t60\t100M\t*\t0\t0\t"
                f"{''.join(sequence)}\t{'I' * 100}\tRG:Z:rg1\n"
            )

    truth_path = args.outdir / "truth.tsv"
    truth_path.write_text("CHROM\tPOS\tREF\tALT\tGT\nchrTiny\t50\tC\tG\t0/1\n", encoding="utf-8")
    manifest = {
        "benchmark": "bionexus-tiny-target-v1",
        "truth_design": "deterministic synthetic positive control",
        "sample": "TINY001",
        "reference": "chrTiny:1-200",
        "reads": 20,
        "read_length": 100,
        "expected_variants": 1,
        "expected_snp": "chrTiny:50:C>G:0/1",
        "checksums": {path.name: sha256(path) for path in (reference_path, sam_path, truth_path)},
    }
    (args.outdir / "fixture_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

"""BBS-1 NGS truth-set evaluation harness.

For publication claims, prefer GA4GH hap.py/vcfeval output within the matching benchmark
regions.  This script can (a) ingest a hap.py summary CSV and freeze its stratified metrics,
or (b) perform a conservative exact normalized-allele comparison as a smoke-test fallback.
The fallback must not be described as GA4GH benchmarking.
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, order=True)
class Variant:
    chrom: str
    pos: int
    ref: str
    alt: str

    @property
    def kind(self) -> str:
        return "SNP" if len(self.ref) == 1 and len(self.alt) == 1 else "INDEL"


def normalize(chrom: str, pos: int, ref: str, alt: str) -> Variant:
    ref, alt = ref.upper(), alt.upper()
    while len(ref) > 1 and len(alt) > 1 and ref[-1] == alt[-1]:
        ref, alt = ref[:-1], alt[:-1]
    while len(ref) > 1 and len(alt) > 1 and ref[0] == alt[0]:
        ref, alt, pos = ref[1:], alt[1:], pos + 1
    return Variant(chrom, pos, ref, alt)


def parse_vcf(path: Path) -> set[Variant]:
    variants: set[Variant] = set()
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            if not raw or raw.startswith("#"): continue
            parts = raw.rstrip().split("\t")
            if len(parts) < 5: continue
            chrom, pos, _, ref, alts = parts[:5]
            for alt in alts.split(","):
                if alt == "." or alt.startswith("<"): continue
                variants.add(normalize(chrom, int(pos), ref, alt))
    return variants


def parse_bed(path: Path | None) -> dict[str, list[tuple[int, int]]]:
    regions: dict[str, list[tuple[int, int]]] = {}
    if path is None: return regions
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            if not raw.strip() or raw.startswith("#"): continue
            chrom, start, end, *_ = raw.rstrip().split("\t")
            regions.setdefault(chrom, []).append((int(start), int(end)))
    return regions


def in_regions(v: Variant, regions: dict[str, list[tuple[int, int]]]) -> bool:
    if not regions: return True
    # BED is zero-based half-open; VCF POS is one-based.
    p0 = v.pos - 1
    return any(start <= p0 < end for start, end in regions.get(v.chrom, []))


def metrics(truth: set[Variant], query: set[Variant]) -> dict:
    tp = len(truth & query); fp = len(query - truth); fn = len(truth - query)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def fallback_compare(truth_vcf: Path, query_vcf: Path, bed: Path | None) -> dict:
    regions = parse_bed(bed)
    truth = {v for v in parse_vcf(truth_vcf) if in_regions(v, regions)}
    query = {v for v in parse_vcf(query_vcf) if in_regions(v, regions)}
    result = {"ALL": metrics(truth, query)}
    for kind in ("SNP", "INDEL"):
        result[kind] = metrics({v for v in truth if v.kind == kind}, {v for v in query if v.kind == kind})
    return {
        "method": "exact-normalized-allele-fallback",
        "publication_grade": False,
        "metrics": result,
        "warning": "This fallback is not hap.py/vcfeval and does not perform sophisticated representation matching. Use GA4GH benchmarking for publication accuracy claims.",
    }


def ingest_happy_summary(path: Path) -> dict:
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(dict(row))
    if not rows: raise ValueError("hap.py summary contained no rows")
    wanted = []
    for row in rows:
        type_value = (row.get("Type") or row.get("TYPE") or "").upper()
        subset = (row.get("Subset") or row.get("SUBSET") or "").upper()
        if type_value in {"SNP", "INDEL"} and subset in {"*", "ALL", "PASS"}:
            wanted.append(row)
    return {
        "method": "GA4GH-hap.py-summary",
        "publication_grade": True,
        "rows": wanted or rows,
        "source_columns": list(rows[0].keys()),
    }


def main(args) -> int:
    if args.happy_summary:
        evaluation = ingest_happy_summary(args.happy_summary)
    else:
        if not args.truth_vcf or not args.query_vcf:
            raise SystemExit("Provide --happy-summary, or both --truth-vcf and --query-vcf")
        evaluation = fallback_compare(args.truth_vcf, args.query_vcf, args.benchmark_bed)
    result = {
        "suite": "BBS-1 NGS truth-set evaluation",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation": evaluation,
        "inputs": {"truth_vcf": str(args.truth_vcf) if args.truth_vcf else None,
                   "query_vcf": str(args.query_vcf) if args.query_vcf else None,
                   "benchmark_bed": str(args.benchmark_bed) if args.benchmark_bed else None,
                   "happy_summary": str(args.happy_summary) if args.happy_summary else None},
        "claim_boundary": "Only GA4GH-compatible truth evaluation within a matched benchmark region supports publication-grade germline accuracy claims. The exact-allele fallback is a software smoke test only.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True)); return 0

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--truth-vcf", type=Path); p.add_argument("--query-vcf", type=Path)
    p.add_argument("--benchmark-bed", type=Path); p.add_argument("--happy-summary", type=Path)
    p.add_argument("--output", type=Path, default=Path("results/ngs_truthset.json"))
    raise SystemExit(main(p.parse_args()))

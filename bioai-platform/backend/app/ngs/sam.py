"""
Pure-Python SAM layer for the NGS platform's alignment / BAM / coverage / variant stages.

Provides:
  * parse_sam(path)     - stream a text SAM file into lightweight alignment records
  * write_sam(path, recs, header)
  * SAM flag helpers (proper pair, first/second, unmapped, secondary, supplementary)
  * map_reads_exact()   - a tiny exact-seed reference mapper used for tests/demo (NOT production)
                           so the alignment-QC and coverage engines are exercised on real data.

A SAM record is a dict:
    qname, flag, rname, pos (1-based), mapq, cigar, rnext, pnext, tlen, seq, qual,
    is_secondary, is_supplementary, is_unmapped, is_proper_pair, mate_mapped
"""

from __future__ import annotations

import os
from typing import Iterator, Optional

# SAM flag bit masks (https://samtools.github.io/hts-specs/SAMv1.pdf)
FLAG_READ_PAIRED = 0x1
FLAG_READ_MAPPED_PROPER = 0x2
FLAG_READ_UNMAPPED = 0x4
FLAG_MATE_UNMAPPED = 0x8
FLAG_READ_REVERSE = 0x10
FLAG_READ1 = 0x40
FLAG_READ2 = 0x80
FLAG_SECONDARY = 0x100
FLAG_QCFAIL = 0x200
FLAG_DUPLICATE = 0x400
FLAG_SUPPLEMENTARY = 0x800


def is_flag(flag: int, bit: int) -> bool:
    return bool(flag & bit)


def parse_sam(path: str) -> Iterator[dict]:
    """Yield alignment record dicts from a text SAM file."""
    with open(path, "r") as f:
        for line in f:
            if line.startswith("@"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 11:
                continue
            flag = int(parts[1])
            rec = {
                "qname": parts[0],
                "flag": flag,
                "rname": parts[2],
                "pos": int(parts[3]),
                "mapq": int(parts[4]),
                "cigar": parts[5],
                "rnext": parts[6],
                "pnext": parts[7],
                "tlen": int(parts[8]),
                "seq": parts[9],
                "qual": parts[10],
                "is_secondary": is_flag(flag, FLAG_SECONDARY),
                "is_supplementary": is_flag(flag, FLAG_SUPPLEMENTARY),
                "is_unmapped": is_flag(flag, FLAG_READ_UNMAPPED),
                "is_proper_pair": is_flag(flag, FLAG_READ_MAPPED_PROPER),
                "is_duplicate": is_flag(flag, FLAG_DUPLICATE),
                "is_first_in_pair": is_flag(flag, FLAG_READ1),
                "is_second_in_pair": is_flag(flag, FLAG_READ2),
                "mate_unmapped": is_flag(flag, FLAG_MATE_UNMAPPED),
            }
            yield rec


def read_sam(path: str, max_records: Optional[int] = None) -> list[dict]:
    out = []
    for rec in parse_sam(path):
        out.append(rec)
        if max_records is not None and len(out) >= max_records:
            break
    return out


def cigar_length(cigar: str) -> int:
    """Reference-consuming length of a CIGAR (sum of M/D/N/=X)."""
    import re
    total = 0
    for m in re.finditer(r"(\d+)([MIDNSHP=X])", cigar):
        if m.group(2) in "MDN=X":
            total += int(m.group(1))
    return total


def align_read_exact(
    ref_seq: str,
    read: str,
    *,
    start: int = 0,
    seed_len: int = 12,
    min_len: int = 20,
) -> Optional[dict]:
    """Map a read to a reference by exact k-mer seeding + full match extension.

    Returns a raw alignment dict (without SAM flag attributes) or None.
    Only returns alignments that consume >= min_len reference bases (rough, demo/validation).
    """
    read = read.upper()
    ref_seq = ref_seq.upper()
    if len(read) < seed_len:
        return None
    seed = read[:seed_len]
    best = None
    idx = ref_seq.find(seed, start)
    while idx != -1:
        consumed = 0
        rpos = idx
        for i, base in enumerate(read):
            if rpos >= len(ref_seq):
                break
            if ref_seq[rpos] == base or ref_seq[rpos] == "N":
                consumed += 1
                rpos += 1
            else:
                break
        if consumed >= min_len and (best is None or consumed > best["match_bases"]):
            best = {"pos": idx + 1, "match_bases": consumed, "mapq": 60}
        idx = ref_seq.find(seed, idx + 1)
    return best


def map_reads(
    ref_seq: str,
    reads: list[tuple[str, str, str]],   # (qname, seq, qual)
    ref_name: str = "chr1",
    seed_len: int = 12,
    min_len: int = 20,
) -> list[dict]:
    """Map a list of reads to a reference, emitting SAM-like records (demo/validation aligner)."""
    records: list[dict] = []
    for idx, (qname, seq, qual) in enumerate(reads):
        hit = align_read_exact(ref_seq, seq, seed_len=seed_len, min_len=min_len, start=0)
        if hit is None:
            records.append({
                "qname": qname, "flag": 4, "rname": "*", "pos": 0, "mapq": 0,
                "cigar": "*", "rnext": "*", "pnext": 0, "tlen": 0, "seq": seq, "qual": qual,
                "is_unmapped": True, "is_proper_pair": False, "is_secondary": False,
                "is_supplementary": False, "is_duplicate": False,
                "is_first_in_pair": False, "is_second_in_pair": False, "mate_unmapped": False,
            })
        else:
            records.append({
                "qname": qname, "flag": 0, "rname": ref_name, "pos": hit["pos"], "mapq": hit["mapq"],
                "cigar": f"{hit['match_bases']}M", "rnext": "*", "pnext": 0, "tlen": 0,
                "seq": seq, "qual": qual, "is_unmapped": False, "is_proper_pair": True,
                "is_secondary": False, "is_supplementary": False, "is_duplicate": False,
                "is_first_in_pair": False, "is_second_in_pair": False, "mate_unmapped": False,
            })
    return records

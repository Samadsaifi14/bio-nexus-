"""Alignment column statistics — single backend implementation.

This is the authoritative source for the MSA summary metrics that the
frontend renders. The frontend must not recompute scientific numbers; it
renders the values emitted here (the CLUSTAL-style display symbols stay a
pure presentation concern).
"""

from __future__ import annotations

GAP_CHARS = {"-", "."}

# The scientific summary classifies columns exactly as the old client helper did:
#   matched    — every non-gap residue identical (invariant column)
#   gapped     — at least one gap character present
#   mismatched — >= 2 distinct residues and no gaps (variable column)
def alignment_stats(seqs: list[str]) -> dict:
    """Column-wise summary of an already-aligned set of equal-length strings."""
    empty = {
        "length": 0,
        "matched": 0,
        "mismatched": 0,
        "gapped": 0,
        "total_gaps": 0,
        "identity_pct": 0.0,
    }
    if not seqs:
        return empty

    length = max(len(s) for s in seqs)
    if length == 0:
        return empty

    matched = 0
    mismatched = 0
    gapped = 0
    total_gaps = 0

    for i in range(length):
        distinct: set[str] = set()
        col_has_gap = False
        for s in seqs:
            c = (s[i] if i < len(s) else "-").upper()
            if c in GAP_CHARS:
                col_has_gap = True
                total_gaps += 1
            else:
                distinct.add(c)
        if col_has_gap:
            gapped += 1
        elif len(distinct) <= 1:
            matched += 1
        else:
            mismatched += 1

    return {
        "length": length,
        "matched": matched,
        "mismatched": mismatched,
        "gapped": gapped,
        "total_gaps": total_gaps,
        "identity_pct": round(matched / length * 100, 1) if length else 0.0,
    }


def parse_aligned_fasta(fasta: str) -> list[str]:
    """Return the aligned sequence bodies (lowercased headers removed, gaps kept)."""
    if not fasta:
        return []
    seqs: list[str] = []
    current = ""
    for line in (fasta or "").splitlines():
        t = line.strip()
        if t.startswith(">"):
            if current:
                seqs.append(current)
            current = ""
        elif t:
            current += t
    if current:
        seqs.append(current)
    return seqs
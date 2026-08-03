"""
In-process pairwise sequence alignment (Smith-Waterman / Needleman-Wunsch).

Zero external dependencies: sequences are aligned locally with Biopython's
PairwiseAligner plus a BLOSUM62 / PAM250 substitution matrix. No network I/O.

Requires Biopython >= 1.80 (Bio.Align.substitution_matrices).
"""

from __future__ import annotations

from Bio.Align import PairwiseAligner, substitution_matrices

VALID_MODES = ("global", "local")
MATRICES = {
    "blosum62": "BLOSUM62",
    "pam250": "PAM250",
}


class PairwiseAlignError(ValueError):
    pass


def _normalize_sequence(seq: str, label: str) -> str:
    seq = (seq or "").upper()
    seq = "".join(c for c in seq if c.isalpha())
    if not seq:
        raise PairwiseAlignError(f"{label} sequence is empty")
    return seq


def _gap_runs(aligned: str, seq_label: str) -> list[dict]:
    """Gap runs in a single aligned row.

    ``inserted_after`` is the number of residues before the gap in the ORIGINAL
    (ungapped) sequence: 0 means leading gaps, N means trailing gaps after N
    residues.
    """
    runs: list[dict] = []
    residues_seen = 0
    i = 0
    n = len(aligned)
    while i < n:
        if aligned[i] == "-":
            j = i
            while j < n and aligned[j] == "-":
                j += 1
            runs.append({"seq": seq_label, "inserted_after": residues_seen, "length": j - i})
            i = j
        else:
            residues_seen += 1
            i += 1
    return runs


def _covered_region(aligned: str) -> tuple[int, int]:
    """1-based residue coordinates covered by the alignment in the original sequence."""
    count = 0
    start = end = 0
    for ch in aligned:
        if ch != "-":
            count += 1
            if start == 0:
                start = count
            end = count
    return start, end


def pairwise_align(
    seq_a: str,
    seq_b: str,
    mode: str = "global",
    matrix: str = "blosum62",
    open_gap_score: float = -10,
    extend_gap_score: float = -1,
) -> dict:
    """Align two full sequences.

    mode: ``global`` (Needleman-Wunsch, default) or ``local`` (Smith-Waterman).
    matrix: ``blosum62`` (default) or ``pam250``.
    """
    mode = (mode or "global").lower()
    if mode not in VALID_MODES:
        raise PairwiseAlignError(f"mode must be one of {VALID_MODES}, got {mode!r}")
    matrix = (matrix or "blosum62").lower()
    if matrix not in MATRICES:
        raise PairwiseAlignError(f"matrix must be one of {list(MATRICES)}, got {matrix!r}")

    seq_a = _normalize_sequence(seq_a, "query")
    seq_b = _normalize_sequence(seq_b, "subject")

    aligner = PairwiseAligner()
    aligner.mode = mode
    aligner.substitution_matrix = substitution_matrices.load(MATRICES[matrix])
    aligner.open_gap_score = open_gap_score
    aligner.extend_gap_score = extend_gap_score

    alignments = aligner.align(seq_a, seq_b)
    if len(alignments) == 0:
        # No local alignment with a positive score (e.g. two non-homologous
        # sequences). Report a degenerate "no overlap" result instead of failing.
        return {
            "mode": mode,
            "matrix": matrix,
            "score": 0.0,
            "aligned_query": "",
            "aligned_hit": "",
            "alignment_length": 0,
            "identity": 0,
            "pct_identity": 0.0,
            "gaps_total": 0,
            "gap_positions": [],
            "query_start": 0,
            "query_end": 0,
            "hit_start": 0,
            "hit_end": 0,
            "query_length": len(seq_a),
            "hit_length": len(seq_b),
        }

    best = alignments[0]
    aligned_a = str(best[0])
    aligned_b = str(best[1])

    identity = sum(1 for x, y in zip(aligned_a, aligned_b) if x == y and x != "-")
    align_len = len(aligned_a)

    gap_runs = _gap_runs(aligned_a, "query") + _gap_runs(aligned_b, "subject")
    gap_positions = [r for r in gap_runs if r["length"] > 0]
    gaps_total = sum(r["length"] for r in gap_positions)

    q_start, q_end = _covered_region(aligned_a)
    h_start, h_end = _covered_region(aligned_b)

    return {
        "mode": mode,
        "matrix": matrix,
        "score": float(best.score),
        "aligned_query": aligned_a,
        "aligned_hit": aligned_b,
        "alignment_length": align_len,
        "identity": identity,
        "pct_identity": round(identity / align_len * 100, 1) if align_len else 0.0,
        "gaps_total": gaps_total,
        "gap_positions": gap_positions,
        "query_start": q_start,
        "query_end": q_end,
        "hit_start": h_start,
        "hit_end": h_end,
        "query_length": len(seq_a),
        "hit_length": len(seq_b),
    }

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

    ``inserted_after`` is the number of residues of that sequence shown before
    the gap in the ORIGINAL (ungapped) sequence — 0 means a leading gap,
    otherwise it is the 1-based position of the residue before it. Counting
    non-gap characters of the row avoids depending on Biopython's internal
    ``coordinates`` layout (which varies by version).
    """
    runs: list[dict] = []
    residues_before = 0
    i = 0
    n = len(aligned)
    while i < n:
        if aligned[i] == "-":
            j = i
            while j < n and aligned[j] == "-":
                j += 1
            runs.append({
                "seq": seq_label,
                "inserted_after": residues_before,
                "length": j - i,
            })
            i = j
        else:
            residues_before += 1
            i += 1
    return runs


def _covered_region(coordinates_row) -> tuple[int, int]:
    """1-based residue coordinates covered by the alignment, in the ORIGINAL
    sequence. Read straight off the Biopython coordinates row — correct also
    for local mode, where aligned-row gap counting was fragment-relative."""
    return int(coordinates_row[0]) + 1, int(coordinates_row[-1])


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
            "gap_open": float(open_gap_score),
            "gap_extend": float(extend_gap_score),
            "score": 0.0,
            "aligned_query": "",
            "aligned_hit": "",
            "alignment_length": 0,
            "identity": 0,
            "pct_identity": 0.0,
            "mismatches": 0,
            "similarity": 0,
            "pct_similarity": 0.0,
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

    matrix_obj = aligner.substitution_matrix

    identity = 0
    mismatches = 0
    similar = 0
    for x, y in zip(aligned_a, aligned_b):
        if x == "-" or y == "-":
            continue
        if x == y:
            identity += 1
            similar += 1
        else:
            mismatches += 1
            try:
                col_score = float(matrix_obj[x, y])
            except (KeyError, ValueError, TypeError):
                col_score = 0.0
            if col_score > 0:
                similar += 1
    align_len = len(aligned_a)

    coords_q, coords_h = best.coordinates[0], best.coordinates[1]

    gap_runs = _gap_runs(aligned_a, "query") + _gap_runs(aligned_b, "subject")
    gap_positions = [r for r in gap_runs if r["length"] > 0]
    gaps_total = sum(r["length"] for r in gap_positions)

    q_start, q_end = _covered_region(coords_q)
    h_start, h_end = _covered_region(coords_h)

    return {
        "mode": mode,
        "matrix": matrix,
        "gap_open": float(open_gap_score),
        "gap_extend": float(extend_gap_score),
        "score": float(best.score),
        "aligned_query": aligned_a,
        "aligned_hit": aligned_b,
        "alignment_length": align_len,
        "identity": identity,
        "pct_identity": round(identity / align_len * 100, 1) if align_len else 0.0,
        "mismatches": mismatches,
        "similarity": similar,
        "pct_similarity": round(similar / align_len * 100, 1) if align_len else 0.0,
        "gaps_total": gaps_total,
        "gap_positions": gap_positions,
        "query_start": q_start,
        "query_end": q_end,
        "hit_start": h_start,
        "hit_end": h_end,
        "query_length": len(seq_a),
        "hit_length": len(seq_b),
    }

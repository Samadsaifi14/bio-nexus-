"""In-process pairwise alignment (Needleman-Wunsch / Smith-Waterman)."""

from __future__ import annotations

from Bio.Align import PairwiseAligner, substitution_matrices

VALID_MODES = ("global", "local")
MATRICES = {"blosum62": "BLOSUM62", "pam250": "PAM250"}


class PairwiseAlignError(ValueError):
    pass


def _normalize_sequence(seq: str, label: str) -> str:
    body_lines = [line for line in (seq or "").splitlines() if not line.lstrip().startswith(">")]
    body = "".join(body_lines)
    chars: list[str] = []
    position = 0
    for character in body:
        if character.isspace():
            continue
        position += 1
        if not character.isalpha():
            raise PairwiseAlignError(f"{label} contains invalid character {character!r} at position {position}")
        chars.append(character.upper())
    normalized = "".join(chars)
    if not normalized:
        raise PairwiseAlignError(f"{label} sequence is empty")
    return normalized


def _gap_runs(aligned: str, seq_label: str, residue_offset: int = 0) -> list[dict]:
    runs: list[dict] = []
    residues_seen = residue_offset
    index = 0
    while index < len(aligned):
        if aligned[index] == "-":
            end = index
            while end < len(aligned) and aligned[end] == "-":
                end += 1
            runs.append({"seq": seq_label, "inserted_after": residues_seen, "length": end - index})
            index = end
        else:
            residues_seen += 1
            index += 1
    return runs


def pairwise_align(
    seq_a: str,
    seq_b: str,
    mode: str = "global",
    matrix: str = "blosum62",
    open_gap_score: float = -10,
    extend_gap_score: float = -1,
) -> dict:
    mode = (mode or "global").lower()
    if mode not in VALID_MODES:
        raise PairwiseAlignError(f"mode must be one of {VALID_MODES}, got {mode!r}")
    matrix = (matrix or "blosum62").lower()
    if matrix not in MATRICES:
        raise PairwiseAlignError(f"matrix must be one of {list(MATRICES)}, got {matrix!r}")
    if open_gap_score > 0 or extend_gap_score > 0:
        raise PairwiseAlignError("Gap scores must be penalties (zero or negative), not positive rewards")

    seq_a = _normalize_sequence(seq_a, "query")
    seq_b = _normalize_sequence(seq_b, "subject")

    substitution_matrix = substitution_matrices.load(MATRICES[matrix])
    allowed = set(str(substitution_matrix.alphabet)) - {"*"}
    for label, sequence in (("query", seq_a), ("subject", seq_b)):
        invalid = sorted(set(sequence) - allowed)
        if invalid:
            raise PairwiseAlignError(f"{label} contains residues unsupported by {matrix.upper()}: {', '.join(invalid)}")

    aligner = PairwiseAligner()
    aligner.mode = mode
    aligner.substitution_matrix = substitution_matrix
    aligner.open_gap_score = open_gap_score
    aligner.extend_gap_score = extend_gap_score

    alignments = aligner.align(seq_a, seq_b)
    common = {
        "mode": mode,
        "matrix": matrix,
        "open_gap_score": float(open_gap_score),
        "extend_gap_score": float(extend_gap_score),
        "query_length": len(seq_a),
        "hit_length": len(seq_b),
    }
    if len(alignments) == 0:
        return {
            **common,
            "score": 0.0,
            "aligned_query": "",
            "aligned_hit": "",
            "alignment_length": 0,
            "identity": 0,
            "pct_identity": 0.0,
            "similarity": 0,
            "pct_similarity": 0.0,
            "mismatches": 0,
            "gaps_total": 0,
            "gap_positions": [],
            "query_start": 0,
            "query_end": 0,
            "hit_start": 0,
            "hit_end": 0,
        }

    best = alignments[0]
    aligned_a = str(best[0])
    aligned_b = str(best[1])
    alignment_length = len(aligned_a)
    identity = 0
    similarity = 0
    mismatches = 0
    for query_residue, subject_residue in zip(aligned_a, aligned_b):
        if query_residue == "-" or subject_residue == "-":
            continue
        if query_residue == subject_residue:
            identity += 1
        else:
            mismatches += 1
        try:
            if float(substitution_matrix[query_residue, subject_residue]) > 0:
                similarity += 1
        except (KeyError, IndexError):
            pass

    query_blocks, hit_blocks = best.aligned
    if len(query_blocks):
        query_start = int(query_blocks[0][0]) + 1
        query_end = int(query_blocks[-1][1])
        query_offset = int(query_blocks[0][0])
    else:
        query_start = query_end = query_offset = 0
    if len(hit_blocks):
        hit_start = int(hit_blocks[0][0]) + 1
        hit_end = int(hit_blocks[-1][1])
        hit_offset = int(hit_blocks[0][0])
    else:
        hit_start = hit_end = hit_offset = 0

    gap_positions = [
        run for run in _gap_runs(aligned_a, "query", query_offset) + _gap_runs(aligned_b, "subject", hit_offset)
        if run["length"] > 0
    ]
    gaps_total = sum(run["length"] for run in gap_positions)

    return {
        **common,
        "score": float(best.score),
        "aligned_query": aligned_a,
        "aligned_hit": aligned_b,
        "alignment_length": alignment_length,
        "identity": identity,
        "pct_identity": round(identity / alignment_length * 100, 1) if alignment_length else 0.0,
        "similarity": similarity,
        "pct_similarity": round(similarity / alignment_length * 100, 1) if alignment_length else 0.0,
        "mismatches": mismatches,
        "gaps_total": gaps_total,
        "gap_positions": gap_positions,
        "query_start": query_start,
        "query_end": query_end,
        "hit_start": hit_start,
        "hit_end": hit_end,
    }

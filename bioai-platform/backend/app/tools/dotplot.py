"""Dot plot computation for sequence-vs-sequence comparison.

A dot plot marks every pair of positions ``(i, j)`` whose surrounding
``window`` residues are similar at or above ``stringency``. Similarity is
either simple identity (nucleotide sequences) or a substitution-matrix score
(BLOSUM/PAM for proteins). Identical sequences produce the classic diagonal;
repeats and rearrangements show up as off-diagonal lines; inverted repeats as
anti-diagonal lines.

Uses a vectorised (numpy) scan: scores are computed positionally along each
``(i, j)`` diagonal with sliding-window sums, so a 2000 x 2000 comparison
completes in well under a second. Pure local computation — no network calls.
"""

from __future__ import annotations

import functools
import math

import numpy as np

from app.services.sequence_utils import detect_sequence_type


class DotPlotError(ValueError):
    pass


MAX_CELLS = 4_000_000  # ~2000 x 2000
MAX_DOTS = 20_000

SCORING_OPTIONS = ("identity", "blosum62", "blosum50", "blosum45", "pam30", "pam70", "pam250")


@functools.lru_cache(maxsize=8)
def _load_matrix(name: str) -> tuple[np.ndarray, dict[str, int]]:
    """Load a substitution matrix as (data, letter->row index)."""
    from Bio.Align import substitution_matrices

    m = substitution_matrices.load(name.upper())
    letters = list(m.alphabet)
    index = {ch: i for i, ch in enumerate(letters)}
    return np.asarray(m.data, dtype=np.int16), index


def _normalize(seq: str) -> str:
    return "".join(ch for ch in seq.upper() if ch.isalpha())


def _detect_features(ys: np.ndarray, xs: np.ndarray, n: int, m: int, window: int) -> dict:
    """Structurally meaningful signals from the (pre-downsampled) dot set.

    * Main-diagonal coverage: how much of the principal diagonal is lit up,
      measured over the ``diag_len - window + 1`` positions that can actually
      hold a window.
    * Gap runs on the main diagonal: maximal stretches of unlit positions,
      which correspond to insertions/deletions.
    * Off-diagonal lines: dominant constant offsets ``x - y`` -> repeats,
      tandem duplications and translocated segments.
    * Anti-diagonal lines: dominant constant ``x + y`` -> inverted repeats
      (mostly relevant for nucleotide comparisons).
    """
    empty = {"main_diagonal_pct": 0.0, "gaps": {"count": 0, "largest": 0},
             "off_diagonal": [], "anti_diagonal": []}
    if ys.size == 0:
        return empty

    offsets = (xs - ys).astype(np.int64)
    sums = (xs + ys).astype(np.int64)
    diag_len = min(n, m)
    diag_positions = max(1, diag_len - window + 1)
    min_count = max(2, int(0.02 * diag_positions))

    # Main diagonal coverage + gap runs
    on_diag = np.unique(ys[offsets == 0])
    main_pct = round(100.0 * on_diag.size / diag_positions, 1)
    covered = set(on_diag.tolist())
    gap_runs: list[int] = []
    run = 0
    for pos in range(diag_positions):
        if pos in covered:
            if run > 0:
                gap_runs.append(run)
                run = 0
        else:
            run += 1
    if run > 0:
        gap_runs.append(run)

    # Off-diagonal repeat offsets
    off_vals, off_counts = np.unique(offsets[offsets != 0], return_counts=True)
    off_diagonal = [
        {"offset": int(o), "count": int(c)}
        for o, c in zip(off_vals.tolist(), off_counts.tolist())
        if int(c) >= min_count
    ]
    off_diagonal.sort(key=lambda d: -d["count"])
    off_diagonal = off_diagonal[:5]

    # Anti-diagonal (inverted repeat) lines
    anti_vals, anti_counts = np.unique(sums, return_counts=True)
    anti_diagonal = [
        {"sum": int(s), "count": int(c)}
        for s, c in zip(anti_vals.tolist(), anti_counts.tolist())
        if int(c) >= min_count
    ]
    anti_diagonal.sort(key=lambda d: -d["count"])
    anti_diagonal = anti_diagonal[:5]

    return {
        "main_diagonal_pct": main_pct,
        "gaps": {"count": len(gap_runs), "largest": max(gap_runs) if gap_runs else 0},
        "off_diagonal": off_diagonal,
        "anti_diagonal": anti_diagonal,
    }


def compute_dotplot(
    seq_a: str,
    seq_b: str,
    window: int = 10,
    stringency: int = 80,
    scoring: str = "identity",
    max_dots: int = MAX_DOTS,
) -> dict:
    seq_a = _normalize(seq_a)
    seq_b = _normalize(seq_b)
    if not seq_a or not seq_b:
        raise DotPlotError("Both sequences are required")
    n, m = len(seq_a), len(seq_b)
    if n * m > MAX_CELLS:
        raise DotPlotError(
            f"Sequences too large for a dot plot ({n} x {m} cells, max {MAX_CELLS}). "
            "Use shorter sequences or trim the input."
        )
    window = max(1, min(int(window), n, m))
    stringency = max(1, min(100, int(stringency)))
    if scoring not in SCORING_OPTIONS:
        raise DotPlotError(
            f"Unknown scoring scheme '{scoring}'. Use one of: {', '.join(SCORING_OPTIONS)}"
        )

    # Protein substitution matrices only make sense on protein sequences.
    scoring_used = scoring
    if scoring != "identity" and detect_sequence_type(seq_a) != "protein":
        scoring_used = "identity"

    a = np.frombuffer(seq_a.encode("ascii", "ignore"), dtype=np.uint8)
    b = np.frombuffer(seq_b.encode("ascii", "ignore"), dtype=np.uint8)
    if a.size == 0 or b.size == 0:
        raise DotPlotError("Both sequences are required")

    if scoring_used == "identity":
        threshold = max(1, math.ceil(window * stringency / 100.0))
    else:
        data, index = _load_matrix(scoring_used)
        max_score = float(data.max())
        threshold = max(1, math.floor(window * max_score * stringency / 100.0))
        # Map letters to matrix rows; unknown residues (B/Z/U/O/X, ambiguous)
        # get a dedicated zero-scoring row/column.
        rows_a = np.array([index.get(chr(c), len(index)) for c in a.tolist()], dtype=np.intp)
        rows_b = np.array([index.get(chr(c), len(index)) for c in b.tolist()], dtype=np.intp)
        if len(index) < data.shape[0]:
            data = data[: len(index), : len(index)]
        extra = np.zeros((1, data.shape[1]), dtype=np.int16)
        data = np.vstack([data, extra])
        extra = np.zeros((data.shape[0], 1), dtype=np.int16)
        data = np.hstack([data, extra])

    if window == 1:
        if scoring_used == "identity":
            eq = (a[:, None] == b[None, :])
        else:
            eq = data[rows_a[:, None], rows_b[None, :]] >= threshold
        ys, xs = np.nonzero(eq)
    else:
        ys_list: list[np.ndarray] = []
        xs_list: list[np.ndarray] = []
        for d in range(-(n - 1), m):
            i0 = max(0, -d)
            j0 = max(0, d)
            length = min(n - i0, m - j0)
            if length < window:
                continue
            if scoring_used == "identity":
                score_diag = (a[i0:i0 + length] == b[j0:j0 + length]).astype(np.int16)
            else:
                score_diag = data[rows_a[i0:i0 + length], rows_b[j0:j0 + length]]
            csum = np.concatenate([[0], np.cumsum(score_diag)])
            sums = csum[window:] - csum[:-window]
            kk = np.nonzero(sums >= threshold)[0]
            if kk.size:
                ys_list.append(i0 + kk)
                xs_list.append(j0 + kk)
        if ys_list:
            ys = np.concatenate(ys_list)
            xs = np.concatenate(xs_list)
        else:
            ys = np.empty(0, dtype=np.int64)
            xs = np.empty(0, dtype=np.int64)

    total_matches = int(ys.size)
    features = _detect_features(ys, xs, n, m, window)
    downsampled = False
    if total_matches > max_dots:
        step = max(1, int(math.ceil(total_matches / max_dots)))
        ys = ys[::step]
        xs = xs[::step]
        downsampled = True

    dots = [[int(y), int(x)] for y, x in zip(ys.tolist(), xs.tolist())]
    return {
        "sequence_type": detect_sequence_type(seq_a),
        "seq_a_length": n,
        "seq_b_length": m,
        "window": window,
        "stringency": stringency,
        "scoring": scoring,
        "scoring_used": scoring_used,
        "threshold": threshold,
        "total_matches": total_matches,
        "dot_count": len(dots),
        "downsampled": downsampled,
        "features": features,
        "dots": dots,
    }

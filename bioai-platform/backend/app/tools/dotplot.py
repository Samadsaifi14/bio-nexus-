"""Dot plot computation for sequence-vs-sequence comparison.

A dot plot marks every pair of positions ``(i, j)`` whose surrounding
``window`` residues are similar at or above ``stringency`` percent identity.
Identical sequences produce the classic diagonal; repeats and rearrangements
show up as off-diagonal lines.

Uses a vectorised (numpy) scan: matches are computed positionally along each
``(i, j)`` diagonal with sliding-window sums, so a 2000 x 2000 comparison
completes in well under a second. Pure local computation — no network calls.
"""

from __future__ import annotations

import math

import numpy as np

from app.services.sequence_utils import detect_sequence_type


class DotPlotError(ValueError):
    pass


MAX_CELLS = 4_000_000  # ~2000 x 2000
MAX_DOTS = 20_000


def _normalize(seq: str) -> str:
    return "".join(ch for ch in seq.upper() if ch.isalpha())


def compute_dotplot(
    seq_a: str,
    seq_b: str,
    window: int = 10,
    stringency: int = 80,
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
    threshold = max(1, math.ceil(window * stringency / 100.0))

    a = np.frombuffer(seq_a.encode("ascii", "ignore"), dtype=np.uint8)
    b = np.frombuffer(seq_b.encode("ascii", "ignore"), dtype=np.uint8)
    if a.size == 0 or b.size == 0:
        raise DotPlotError("Both sequences are required")

    if window == 1:
        # Single-residue windows are plain character matches.
        eq = (a[:, None] == b[None, :])
        ys, xs = np.nonzero(eq)
    else:
        # Positional window matches: along each anti-diagonal j = i + d, the
        # equality signal is 1-D, so a sliding-window sum flags the dots.
        ys_list: list[np.ndarray] = []
        xs_list: list[np.ndarray] = []
        for d in range(-(n - 1), m):
            i0 = max(0, -d)
            j0 = max(0, d)
            length = min(n - i0, m - j0)
            if length < window:
                continue
            eq_diag = (a[i0:i0 + length] == b[j0:j0 + length]).astype(np.int16)
            csum = np.concatenate([[0], np.cumsum(eq_diag)])
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
        "threshold": threshold,
        "total_matches": total_matches,
        "dot_count": len(dots),
        "downsampled": downsampled,
        "dots": dots,
    }


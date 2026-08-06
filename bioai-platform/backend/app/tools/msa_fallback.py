"""In-process progressive MSA fallback (pure Biopython).

Used when every EBI MSA endpoint is unreachable or times out, so the pipeline
never stalls on the MSA step. Produces a sensible progressive alignment plus an
UPGMA guide-tree Newick. Marked as ``method: "in-process fallback"`` in the
result so the UI can indicate it is not a Clustal Omega alignment.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _aligner(stype: str):
    from Bio.Align import PairwiseAligner
    from Bio.Align import substitution_matrices

    aligner = PairwiseAligner()
    aligner.mode = "global"
    if stype == "protein":
        try:
            aligner.substitution_matrix = substitution_matrices.load("BLOSUM62")
        except Exception:
            aligner.substitution_matrix = None
            aligner.match_score = 1.0
            aligner.mismatch_score = -1.0
        aligner.open_gap_score = -11.0
        aligner.extend_gap_score = -1.0
    else:
        aligner.substitution_matrix = None
        aligner.match_score = 2.0
        aligner.mismatch_score = -1.0
        aligner.open_gap_score = -2.0
        aligner.extend_gap_score = -0.5
    return aligner


def _pairwise(aligner, s1: str, s2: str) -> tuple[str, str]:
    """Return (gapped_s1, gapped_s2) from the best global alignment."""
    aln = aligner.align(s1, s2)[0]
    ncol = int(aln.shape[1])
    return _gapped(s1, aln.aligned[0], ncol), _gapped(s2, aln.aligned[1], ncol)


def _gapped(seq: str, aligned, ncol: int) -> str:
    """Turn an alignment block list (start, end) pairs into a gapped string of
    exactly ``ncol`` columns (pad for un-aligned overhangs)."""
    out: list[str] = []
    prev = 0
    for start, end in aligned:
        out.append("-" * (start - prev))
        out.append(seq[start:end])
        prev = end
    out.append("-" * (ncol - len("".join(out))))
    return "".join(out)


def _identity(g1: str, g2: str) -> float:
    aligned = sum(1 for a, b in zip(g1, g2) if a != "-" and b != "-")
    if aligned == 0:
        return 0.0
    matches = sum(1 for a, b in zip(g1, g2) if a == b and a != "-")
    return matches / aligned


def _upgma_newick(labels: list[str], dist: list[list[float]]) -> str:
    """UPGMA clustering to a Newick tree. Falls back to a star tree on error."""
    try:
        n = len(labels)
        d = {i: {j: dist[i][j] for j in range(n)} for i in range(n)}
        size = {i: 1 for i in range(n)}
        names = {i: _safe_label(labels[i]) for i in range(n)}
        active = set(range(n))
        next_id = n
        while len(active) > 1:
            best = None
            for i in active:
                for j in active:
                    if i < j and (best is None or d[i][j] < best[0]):
                        best = (d[i][j], i, j)
            if best is None:
                break
            _, i, j = best
            si, sj = size[i], size[j]
            merged = next_id
            next_id += 1
            d[merged] = {}
            for k in active:
                if k in (i, j):
                    continue
                d[merged][k] = d[k][merged] = (d[i][k] * si + d[j][k] * sj) / (si + sj)
            names[merged] = f"({names[i]}:{d[i][j]/2:.4f},{names[j]}:{d[i][j]/2:.4f})"
            size[merged] = si + sj
            active.remove(i)
            active.remove(j)
            active.add(merged)
        root = active.pop()
        return names[root] + ";"
    except Exception as e:  # never let a tree build error block the fallback
        logger.warning("UPGMA Newick build failed, using star tree: %s", e)
        return _star_newick(labels)


def _safe_label(label: str) -> str:
    clean = "".join(c for c in label if c.isalnum() or c in "_.")
    return clean or "seq"


def _star_newick(labels: list[str]) -> str:
    leaves = ",".join(_safe_label(l) for l in labels)
    return f"({leaves});" if labels else "(root);"


def _expand(row: str, c_aln: str) -> str:
    """Map an existing profile row (old consensus columns) onto a new alignment
    of the consensus against a new sequence. Every letter in ``c_aln`` consumes
    one old column; every gap inserts a new gap column."""
    out = []
    ci = 0
    for ch in c_aln:
        if ch == "-":
            out.append("-")
        else:
            out.append(row[ci] if ci < len(row) else "-")
            ci += 1
    return "".join(out)


def _consensus(rows: list[str]) -> str:
    L = len(rows[0])
    cons: list[str] = []
    for col in range(L):
        counts: dict[str, int] = {}
        for r in rows:
            c = r[col]
            if c != "-":
                counts[c] = counts.get(c, 0) + 1
        cons.append(max(counts, key=counts.get) if counts else "X")
    return "".join(cons)


def progressive_msa(sequences: list[tuple[str, str]], stype: str = "protein") -> tuple[str, str]:
    """Return ``(fasta, newick)`` from a pure-Biopython progressive MSA."""
    ids = [s[0] for s in sequences]
    seqs = [s[1] for s in sequences]
    n = len(seqs)
    if n == 0:
        raise ValueError("No sequences to align")

    aligner = _aligner(stype)

    if n == 1:
        fasta = _to_fasta([(ids[0], seqs[0])])
        return fasta, _star_newick(ids)

    # Distance matrix (1 - pairwise identity)
    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g1, g2 = _pairwise(aligner, seqs[i], seqs[j])
            dist[i][j] = dist[j][i] = 1.0 - _identity(g1, g2)

    newick = _upgma_newick(ids, dist)

    # Progressive alignment: align each sequence against the current consensus
    # and gap-transfer the result onto every already-added profile row.
    rows = [seqs[0]]
    cons = seqs[0]
    for s in seqs[1:]:
        c_aln, s_aln = _pairwise(aligner, cons, s)
        rows = [_expand(row, c_aln) for row in rows]
        rows.append(s_aln)
        cons = _consensus(rows)

    fasta = _to_fasta([(ids[k], rows[k]) for k in range(n)])
    return fasta, newick


def _to_fasta(seqs: list[tuple[str, str]], width: int = 80) -> str:
    lines: list[str] = []
    for sid, sseq in seqs:
        lines.append(f">{sid}")
        for i in range(0, len(sseq), width):
            lines.append(sseq[i : i + width])
    return "\n".join(lines)

"""Deterministic in-process progressive MSA fallback (Biopython).

This module is used only when the preferred local/remote MSA engines are not
available.  It is intentionally labelled as a fallback: it is not presented as
Clustal Omega or MAFFT parity.  Every input taxon and residue is validated and
preserved, and guide-tree construction fails explicitly rather than silently
substituting a fabricated star topology.
"""

from __future__ import annotations

import re

_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
_DNA_IUPAC = set("ACGTRYSWKMBDHVN")
_PROTEIN_IUPAC = set("ACDEFGHIKLMNPQRSTVWYBXZJUO")


def _validate_sequences(
    sequences: list[tuple[str, str]], stype: str
) -> list[tuple[str, str]]:
    if stype not in ("protein", "dna"):
        raise ValueError("stype must be 'protein' or 'dna'")
    if not sequences:
        raise ValueError("No sequences to align")

    alphabet = _PROTEIN_IUPAC if stype == "protein" else _DNA_IUPAC
    seen: set[str] = set()
    clean: list[tuple[str, str]] = []
    for index, record in enumerate(sequences):
        if not isinstance(record, (tuple, list)) or len(record) != 2:
            raise ValueError(f"Sequence record {index + 1} must be an (id, sequence) pair")
        sid = str(record[0] or "").strip()
        seq = "".join(str(record[1] or "").split()).upper()
        if not sid:
            raise ValueError(f"Sequence record {index + 1} is missing an identifier")
        if not _SAFE_ID.fullmatch(sid):
            raise ValueError(
                f"Sequence identifier {sid!r} is not Newick/FASTA safe; "
                "use letters, digits, underscore, dot or hyphen"
            )
        if sid in seen:
            raise ValueError(f"Duplicate sequence identifier: {sid}")
        if not seq:
            raise ValueError(f"Sequence {sid!r} is empty")
        bad = sorted(set(seq) - alphabet)
        if bad:
            raise ValueError(
                f"Sequence {sid!r} contains characters invalid for {stype}: {', '.join(bad)}"
            )
        seen.add(sid)
        clean.append((sid, seq))
    return clean


def _aligner(stype: str):
    from Bio.Align import PairwiseAligner
    from Bio.Align import substitution_matrices

    aligner = PairwiseAligner()
    aligner.mode = "global"
    if stype == "protein":
        aligner.substitution_matrix = substitution_matrices.load("BLOSUM62")
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
    """Return the two gapped rows from the best global pairwise alignment."""
    alignments = aligner.align(s1, s2)
    if len(alignments) == 0:
        raise ValueError("Pairwise aligner returned no alignment")
    best = alignments[0]
    g1, g2 = str(best[0]), str(best[1])
    if len(g1) != len(g2):
        raise ValueError("Pairwise aligner produced rows of unequal length")
    if g1.replace("-", "") != s1 or g2.replace("-", "") != s2:
        raise ValueError("Pairwise alignment failed residue-preservation check")
    return g1, g2


def _identity(g1: str, g2: str) -> float:
    if len(g1) != len(g2):
        raise ValueError("Identity requires aligned rows of equal length")
    aligned = sum(1 for a, b in zip(g1, g2) if a != "-" and b != "-")
    if aligned == 0:
        return 0.0
    matches = sum(1 for a, b in zip(g1, g2) if a == b and a != "-")
    return matches / aligned


def _upgma_newick(labels: list[str], dist: list[list[float]]) -> str:
    """Build an ultrametric UPGMA tree from a symmetric distance matrix."""
    n = len(labels)
    if n == 0:
        raise ValueError("Cannot build a guide tree with no taxa")
    if len(dist) != n or any(len(row) != n for row in dist):
        raise ValueError("Distance matrix dimensions do not match taxon count")
    if len(labels) != len(set(labels)):
        raise ValueError("Guide-tree taxon identifiers must be unique")

    for label in labels:
        _safe_label(label)
    for i in range(n):
        if abs(float(dist[i][i])) > 1e-12:
            raise ValueError("Distance-matrix diagonal must be zero")
        for j in range(n):
            value = float(dist[i][j])
            if value < 0:
                raise ValueError("Distances must be non-negative")
            if abs(value - float(dist[j][i])) > 1e-12:
                raise ValueError("Distance matrix must be symmetric")

    d: dict[int, dict[int, float]] = {
        i: {j: float(dist[i][j]) for j in range(n)} for i in range(n)
    }
    size = {i: 1 for i in range(n)}
    height = {i: 0.0 for i in range(n)}
    names = {i: labels[i] for i in range(n)}
    active: set[int] = set(range(n))
    next_id = n

    while len(active) > 1:
        ordered = sorted(active)
        candidates = [
            (d[i][j], i, j)
            for pos, i in enumerate(ordered)
            for j in ordered[pos + 1 :]
        ]
        if not candidates:
            raise ValueError("UPGMA could not find a pair of active clusters")
        distance, i, j = min(candidates, key=lambda item: (item[0], item[1], item[2]))
        new_height = distance / 2.0
        branch_i = max(0.0, new_height - height[i])
        branch_j = max(0.0, new_height - height[j])
        merged = next_id
        next_id += 1

        si, sj = size[i], size[j]
        d[merged] = {}
        for k in ordered:
            if k in (i, j):
                continue
            merged_distance = (d[i][k] * si + d[j][k] * sj) / (si + sj)
            d[merged][k] = merged_distance
            d[k][merged] = merged_distance

        names[merged] = (
            f"({names[i]}:{branch_i:.6f},{names[j]}:{branch_j:.6f})"
        )
        size[merged] = si + sj
        height[merged] = new_height
        active.remove(i)
        active.remove(j)
        active.add(merged)

    root = next(iter(active))
    return names[root] + ";"


def _safe_label(label: str) -> str:
    if not label or not _SAFE_ID.fullmatch(label):
        raise ValueError(f"Unsafe Newick taxon identifier: {label!r}")
    return label


def _star_newick(labels: list[str]) -> str:
    if not labels:
        raise ValueError("Cannot build a star tree with no taxa")
    leaves = ",".join(_safe_label(label) for label in labels)
    return f"({leaves});"


def _expand(row: str, c_aln: str) -> str:
    """Transfer consensus gaps into one existing profile row."""
    out: list[str] = []
    consumed = 0
    for ch in c_aln:
        if ch == "-":
            out.append("-")
        else:
            if consumed >= len(row):
                raise ValueError("Consensus-to-profile mapping consumed too many columns")
            out.append(row[consumed])
            consumed += 1
    if consumed != len(row):
        raise ValueError("Consensus-to-profile mapping did not consume every existing column")
    return "".join(out)


def _consensus(rows: list[str]) -> str:
    if not rows:
        raise ValueError("Cannot compute a consensus from an empty profile")
    lengths = {len(row) for row in rows}
    if len(lengths) != 1:
        raise ValueError("Profile rows have unequal alignment lengths")
    length = len(rows[0])
    cons: list[str] = []
    for col in range(length):
        counts: dict[str, int] = {}
        for row in rows:
            char = row[col]
            if char != "-":
                counts[char] = counts.get(char, 0) + 1
        if not counts:
            raise ValueError("Progressive profile contains an all-gap column")
        # Deterministic tie break by residue symbol.
        cons.append(min(counts, key=lambda char: (-counts[char], char)))
    return "".join(cons)


def progressive_msa(
    sequences: list[tuple[str, str]], stype: str = "protein"
) -> tuple[str, str]:
    """Return ``(aligned_fasta, guide_tree_newick)`` for the fallback method.

    This simple consensus-progressive algorithm is a resilience path, not a
    substitute validation target for MAFFT/Clustal Omega. The result is accepted
    only if every original sequence is represented exactly once and all aligned
    rows have the same length.
    """
    clean = _validate_sequences(sequences, stype)
    ids = [record[0] for record in clean]
    seqs = [record[1] for record in clean]
    n = len(seqs)
    aligner = _aligner(stype)

    if n == 1:
        fasta = _to_fasta([(ids[0], seqs[0])])
        return fasta, _star_newick(ids)

    dist = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            g1, g2 = _pairwise(aligner, seqs[i], seqs[j])
            dist[i][j] = dist[j][i] = 1.0 - _identity(g1, g2)

    newick = _upgma_newick(ids, dist)

    rows = [seqs[0]]
    consensus = seqs[0]
    for seq in seqs[1:]:
        consensus_aln, seq_aln = _pairwise(aligner, consensus, seq)
        rows = [_expand(row, consensus_aln) for row in rows]
        rows.append(seq_aln)
        if len({len(row) for row in rows}) != 1:
            raise ValueError("Progressive MSA produced rows of unequal length")
        consensus = _consensus(rows)

    for original, row in zip(seqs, rows):
        if row.replace("-", "") != original:
            raise ValueError("Progressive MSA failed residue-preservation check")
    if len({len(row) for row in rows}) != 1:
        raise ValueError("Progressive MSA final rows have unequal lengths")

    fasta = _to_fasta([(ids[index], rows[index]) for index in range(n)])
    return fasta, newick


def _to_fasta(seqs: list[tuple[str, str]], width: int = 80) -> str:
    lines: list[str] = []
    for sid, sseq in seqs:
        _safe_label(sid)
        lines.append(f">{sid}")
        for i in range(0, len(sseq), width):
            lines.append(sseq[i : i + width])
    return "\n".join(lines)

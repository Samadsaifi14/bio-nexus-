"""Deterministic analysis over an existing multiple-sequence alignment."""
from __future__ import annotations

import math
from collections import Counter

ALPHABET_PROTEIN = set("ACDEFGHIKLMNPQRSTVWY")
ALPHABET_DNA = set("ACGT")


def _clean(seq: str) -> str:
    return "".join(c for c in seq.upper() if not c.isspace())


def _validate(aligned: list[str]) -> list[str]:
    seqs = [_clean(s) for s in aligned if _clean(s)]
    if len(seqs) < 2:
        raise ValueError("at least two aligned sequences are required")
    length = len(seqs[0])
    if length == 0 or any(len(s) != length for s in seqs):
        raise ValueError("all aligned sequences must have identical non-zero length")
    return seqs


def infer_type(seqs: list[str]) -> str:
    chars = set("".join(seqs)) - {"-", ".", "?", "X", "N"}
    return "dna" if chars <= ALPHABET_DNA else "protein"


def alignment_insights(aligned: list[str], reference_index: int = 0, variants: list[dict] | None = None) -> dict:
    seqs = _validate(aligned)
    if reference_index < 0 or reference_index >= len(seqs):
        raise ValueError("reference_index is outside the alignment")
    seq_type = infer_type(seqs)
    alphabet_size = 4 if seq_type == "dna" else 20
    columns = []
    consensus_chars = []
    for col in range(len(seqs[0])):
        values = [s[col] for s in seqs]
        residues = [v for v in values if v not in {"-", ".", "?"}]
        counts = Counter(residues)
        n = len(residues)
        if not n:
            entropy = 0.0
            conservation = 0.0
            consensus = "-"
            logo = []
        else:
            consensus, max_count = counts.most_common(1)[0]
            conservation = max_count / n
            probs = {aa: c / n for aa, c in counts.items()}
            entropy = -sum(p * math.log2(p) for p in probs.values() if p > 0)
            max_entropy = math.log2(alphabet_size)
            information = max(0.0, max_entropy - entropy)
            logo = [
                {"symbol": aa, "frequency": round(p, 6), "information_bits": round(p * information, 6)}
                for aa, p in sorted(probs.items(), key=lambda kv: (-kv[1], kv[0]))
            ]
        gap_fraction = 1.0 - (n / len(values))
        columns.append({
            "alignment_position": col + 1,
            "consensus": consensus,
            "conservation": round(conservation, 6),
            "entropy_bits": round(entropy, 6),
            "gap_fraction": round(gap_fraction, 6),
            "logo": logo,
        })
        consensus_chars.append(consensus)

    ref = seqs[reference_index]
    ref_to_alignment: dict[int, int] = {}
    residue_no = 0
    for i, char in enumerate(ref):
        if char not in {"-", ".", "?"}:
            residue_no += 1
            ref_to_alignment[residue_no] = i + 1

    mapped_variants = []
    for variant in variants or []:
        try:
            position = int(variant.get("position"))
        except (TypeError, ValueError):
            mapped_variants.append({**variant, "status": "invalid_position"})
            continue
        aln_pos = ref_to_alignment.get(position)
        if aln_pos is None:
            mapped_variants.append({**variant, "status": "outside_reference", "alignment_position": None})
            continue
        col = columns[aln_pos - 1]
        mapped_variants.append({
            **variant,
            "status": "mapped",
            "alignment_position": aln_pos,
            "reference_symbol": ref[aln_pos - 1],
            "conservation": col["conservation"],
            "entropy_bits": col["entropy_bits"],
        })

    mean_conservation = sum(c["conservation"] for c in columns) / len(columns)
    mean_entropy = sum(c["entropy_bits"] for c in columns) / len(columns)
    return {
        "sequence_type": seq_type,
        "sequence_count": len(seqs),
        "alignment_length": len(seqs[0]),
        "reference_index": reference_index,
        "reference_ungapped_length": residue_no,
        "consensus": "".join(consensus_chars),
        "mean_conservation": round(mean_conservation, 6),
        "mean_entropy_bits": round(mean_entropy, 6),
        "columns": columns,
        "variant_mapping": mapped_variants,
        "logo_semantics": "Per-symbol stack height equals frequency multiplied by column information content (max entropy minus Shannon entropy).",
    }

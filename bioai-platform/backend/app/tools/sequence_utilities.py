"""Sequence utilities toolkit.

Computes the everyday metrics a biologist needs on a single sequence:

  * GC content (nucleotides)
  * Reverse complement (nucleotides, IUPAC-aware)
  * Transcription (DNA -> U-containing RNA copy, same strand polarity)
  * Molecular weight (ssDNA / ssRNA / protein average-residue)
  * Six-frame translation (forward frames 1-3, reverse frames 4-6) with the
    longest open reading frame (ORF) flagged
  * Amino-acid composition (proteins / translated CDS)
  * Restriction-enzyme site scan against a curated set of common, unambiguous
    (palindromic) recognition sequences

Pure local computation — no network calls. Mirrors the "Sequence Stats"
workflow every bench tool (ExPASy, BioPython scripts) implements.
"""

from __future__ import annotations

import re

from Bio.SeqUtils.ProtParam import ProteinAnalysis

from app.services.sequence_utils import detect_sequence_type


class SequenceUtilitiesError(ValueError):
    pass


# Standard genetic code — stop codons map to '*', ambiguous codons to 'X'.
_CODON_TABLE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

# Monoisotopic-ish single-strand base weights (g/mol).
# U has a DNA-context entry so mixed T/U strings still weigh correctly.
_SSDNA_MW = {"A": 313.21, "C": 289.18, "G": 329.21, "T": 304.20, "U": 304.20}
_SSRNA_MW = {"A": 329.21, "C": 305.18, "G": 345.21, "U": 306.17, "T": 306.17}

# IUPAC ambiguity codes mapped to their constituent bases.
_IUPAC_AMBIG = {
    "R": "AG", "Y": "CT", "S": "GC", "W": "AT", "K": "GT", "M": "AC",
    "B": "CGT", "D": "AGT", "H": "ACT", "V": "ACG", "N": "ACGT",
}

# IUPAC-aware complement maps (DNA and RNA variants).
_IUPAC_COMP_DNA = {
    "A": "T", "T": "A", "U": "A", "G": "C", "C": "G",
    "R": "Y", "Y": "R", "S": "S", "W": "W", "K": "M", "M": "K",
    "B": "V", "D": "H", "H": "D", "V": "B", "N": "N",
}
_IUPAC_COMP_RNA = {
    "A": "U", "U": "A", "T": "A", "G": "C", "C": "G",
    "R": "Y", "Y": "R", "S": "S", "W": "W", "K": "M", "M": "K",
    "B": "V", "D": "H", "H": "D", "V": "B", "N": "N",
}

# Curated common restriction enzymes — all palindromic so a forward-strand
# scan finds every cut site. Recognition site is given 5' -> 3'.
_RESTRICTION_ENZYMES = [
    ("EcoRI", "GAATTC"),
    ("BamHI", "GGATCC"),
    ("HindIII", "AAGCTT"),
    ("SalI", "GTCGAC"),
    ("XbaI", "TCTAGA"),
    ("XhoI", "CTCGAG"),
    ("NotI", "GCGGCCGC"),
    ("KpnI", "GGTACC"),
    ("SmaI", "CCCGGG"),
    ("PstI", "CTGCAG"),
    ("SacI", "GAGCTC"),
]

_RNA_TO_DNA = str.maketrans("Uu", "Tt")
_AA_ALPHABET = "ACDEFGHIKLMNPQRSTVWY"


def _strip_fasta(seq: str) -> str:
    """Return just the sequence body of a raw or FASTA-formatted input."""
    lines = (seq or "").strip().splitlines()
    lines = [ln.strip() for ln in lines if not ln.strip().startswith(">")]
    return "".join(lines)


def _clean_sequence(seq: str, seq_type: str) -> tuple[str, dict[str, list[int]]]:
    """Normalize to uppercase alpha-only and drop unrecognised letters.

    Returns ``(kept, dropped)`` where ``dropped`` maps each discarded letter to
    the 1-based positions (within the alpha-only, FASTA-header-free body) where
    it occurred, so callers can surface strict position-level warnings. Unlike
    the old behaviour, RNA bases (U) are preserved, not silently converted to T.
    """
    body = _strip_fasta(seq)
    letters = "".join(re.findall(r"[A-Za-z]", body)).upper()
    if not letters:
        raise SequenceUtilitiesError("Sequence is empty")
    if seq_type in ("dna", "rna"):
        allowed = set("ACGTRYSWKMBDHVNU")
        if seq_type == "rna":
            allowed = set("ACGURSYKMWBDHVN")
        kept_letters: list[str] = []
        dropped: dict[str, list[int]] = {}
        for i, c in enumerate(letters, start=1):
            if c in allowed:
                kept_letters.append(c)
            else:
                dropped.setdefault(c, []).append(i)
        kept = "".join(kept_letters)
        if not kept:
            raise SequenceUtilitiesError(f"Sequence contains no valid {seq_type.upper()} bases")
        return kept, dropped
    valid = set("ACDEFGHIKLMNPQRSTVWY")
    kept_letters = []
    dropped = {}
    for i, c in enumerate(letters, start=1):
        if c in valid:
            kept_letters.append(c)
        else:
            dropped.setdefault(c, []).append(i)
    kept = "".join(kept_letters)
    if not kept:
        raise SequenceUtilitiesError("Sequence contains no valid amino acids")
    return kept, dropped


def clean_sequence(seq: str, seq_type: str) -> str:
    """Normalize to uppercase alpha-only, dropping ambiguous/invalid letters."""
    kept, _ = _clean_sequence(seq, seq_type)
    return kept


def _translate_frame(seq: str, frame: int) -> str:
    codons = [seq[i:i + 3] for i in range(frame, len(seq) - 2, 3)]
    return "".join(_CODON_TABLE.get(c, "X") for c in codons)


def _best_orf(seq: str, frame: int, translated: str, strand: str) -> dict | None:
    """Longest ORF (M -> stop/end) in a translated frame.

    ``seq`` is the strand actually translated (forward sequence or its reverse
    complement); ``strand`` records which. For reverse-strand ORFs the start is
    converted back to 1-based coordinates on the original forward-strand input.
    """
    best = None
    n = len(seq)
    for m in re.finditer("M[^*]*", translated):
        length = len(m.group(0))
        offset_rc = frame + m.start() * 3
        if strand == "reverse":
            start = n - offset_rc  # 1-based position on the original input
        else:
            start = offset_rc + 1
        if best is None or length > best["length"]:
            best = {
                "frame": (frame + 1) if strand == "forward" else frame + 4,
                "strand": strand,
                "protein": m.group(0),
                "start": start,
                "length": length,
                "has_stop": len(translated) > m.end() and translated[m.end()] == "*",
                "starts_with_m": True,
            }
    return best


def _protein_mw(seq: str) -> float:
    try:
        return round(ProteinAnalysis(seq).molecular_weight(), 2)
    except Exception:
        avg = 110.0
        return round(sum(avg for _ in seq), 2)


def _nucleotide_mw(seq: str, seq_type: str) -> float:
    """Single-strand oligo molecular weight (g/mol), Biopython convention.

    ssDNA/ssRNA weight = sum of the nucleotide monophosphate residue masses
    plus one terminal H2O (18.02) — no per-bond loss term. This matches
    ``Bio.SeqUtils.molecular_weight(..., seq_type='DNA')`` and the conventions
    used by mainstream oligo calculators (IDT, NEB), where a single residue
    reports its free 5'-monophosphate mass.
    """
    table = _SSDNA_MW if seq_type == "dna" else _SSRNA_MW
    if len(seq) == 0:
        return 0.0
    # IUPAC ambiguity codes are weighted by the mean of their constituent
    # bases; unknown letters (should have been dropped) contribute 0 and are
    # counted in the terminal-water term only if the caller kept them.
    weights: list[float] = []
    for c in seq:
        if c in table:
            weights.append(table[c])
        elif c in _IUPAC_AMBIG:
            const = _IUPAC_AMBIG[c]
            weights.append(sum(table.get(b, 0.0) for b in const) / len(const))
        else:
            weights.append(0.0)
    return round(sum(weights) + 18.02, 2)


def _reverse_complement(seq: str, seq_type: str) -> str:
    comp = _IUPAC_COMP_RNA if seq_type == "rna" else _IUPAC_COMP_DNA
    return "".join(comp.get(c, "N") for c in reversed(seq))


def _aa_composition(seq: str) -> list[dict]:
    counts: dict[str, int] = {}
    for c in seq.upper():
        if c in _AA_ALPHABET:
            counts[c] = counts.get(c, 0) + 1
    total = sum(counts.values())
    comp = [
        {"aa": aa, "count": count, "pct": round(count / total * 100, 1) if total else 0.0}
        for aa, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    return comp


def _restriction_scan(seq: str) -> list[dict]:
    sites = []
    for name, recognition in _RESTRICTION_ENZYMES:
        positions = [m.start() + 1 for m in re.finditer(recognition, seq)]
        if positions:
            sites.append({"name": name, "recognition": recognition, "count": len(positions), "positions": positions})
    return sites


def analyze_sequence(sequence: str, seq_type: str = "auto") -> dict:
    """Analyze a single sequence and return a flat report dict.

    ``seq_type`` may be 'auto', 'dna', 'rna' or 'protein'. Auto-detection uses
    the shared alphabet classifier (a pure ACGTN/U string is treated as DNA).
    """
    seq_type = (seq_type or "auto").lower()
    if seq_type not in ("auto", "dna", "rna", "protein"):
        raise SequenceUtilitiesError("seq_type must be auto, dna, rna or protein")

    raw = _strip_fasta(sequence)
    detected = detect_sequence_type(raw) if raw else "unknown"
    effective = seq_type if seq_type != "auto" else detected
    if effective == "unknown":
        letters = "".join(re.findall(r"[A-Za-z]", raw)).upper()
        if letters and set(letters) <= set("ACGTRYSWKMBDHVNU"):
            effective = "dna"
        else:
            raise SequenceUtilitiesError(
                "Could not detect sequence type — expected nucleotide or protein characters"
            )

    seq, dropped = _clean_sequence(raw, effective)
    issues: list[str] = []
    if dropped:
        pieces = []
        for char, positions in sorted(dropped.items()):
            pos_txt = ", ".join(str(p) for p in positions)
            pieces.append(f"{char}@position {pos_txt}")
        issues.append(f"Ignored invalid characters: {'; '.join(pieces)}")
    if "T" in set(seq) and "U" in set(seq):
        issues.append(f"Sequence mixes T and U — analysed as {effective.upper()}")

    report: dict = {
        "sequence_type": effective,
        "detected_type": detected,
        "length": len(seq),
        "gc_content": None,
        "molecular_weight": None,
        "reverse_complement": None,
        "transcription": None,
        "translation": None,
        "aa_composition": None,
        "restriction_sites": None,
        "issues": issues,
    }

    if effective in ("dna", "rna"):
        report["gc_content"] = round((seq.count("G") + seq.count("C")) / len(seq) * 100.0, 1)
        report["molecular_weight"] = _nucleotide_mw(seq, effective)
        report["reverse_complement"] = _reverse_complement(seq, effective)
        if effective == "dna":
            report["transcription"] = seq.replace("T", "U")
        else:
            report["transcription"] = seq  # RNA input is already the transcript

        dna_seq = seq.translate(_RNA_TO_DNA)
        if len(dna_seq) < 3:
            issues.append("Sequence too short for translation (<3 nt)")
        else:
            reverse = _reverse_complement(dna_seq, "dna")
            # Six reading frames: 1–3 on the forward strand, 4–6 on the reverse.
            strand_frames = [
                *[(frame, dna_seq, "forward") for frame in (0, 1, 2)],
                *[(frame, reverse, "reverse") for frame in (0, 1, 2)],
            ]
            frames: dict[str, str] = {}
            best = None
            for frame, strand_seq, strand in strand_frames:
                translated = _translate_frame(strand_seq, frame)
                key = str(frame + 1) if strand == "forward" else str(frame + 4)
                frames[key] = translated
                orf = _best_orf(strand_seq, frame, translated, strand)
                if orf and (best is None or orf["length"] > best["length"]):
                    best = orf
            report["translation"] = {"frames": frames, "best": best}
            if best is None:
                issues.append("No in-frame methionine (ATG) found — no ORF to report")
            else:
                report["aa_composition"] = _aa_composition(best["protein"])

        if effective == "dna":
            report["restriction_sites"] = _restriction_scan(seq)
        else:
            issues.append("Restriction-site scan is DNA-only")
    else:
        report["molecular_weight"] = _protein_mw(seq)
        report["aa_composition"] = _aa_composition(seq)
        if len(seq) < 2:
            issues.append("Protein sequence very short — composition may be uninformative")

    return report

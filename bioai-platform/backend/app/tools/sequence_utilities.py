"""Sequence utilities toolkit.

Computes common single-sequence metrics with explicit claim boundaries:

  * GC content (nucleotides)
  * Reverse complement (nucleotides, IUPAC-aware)
  * Molecular weight (ssDNA / ssRNA / protein)
  * Forward-strand translation in three reading frames with the longest
    methionine-initiated ORF flagged
  * Amino-acid composition (proteins / translated CDS)
  * Restriction-enzyme site scan against a curated set of common, unambiguous
    palindromic recognition sequences

Pure local computation — no network calls.
"""

from __future__ import annotations

import re

from Bio.SeqUtils import molecular_weight
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
_DNA_IUPAC = set("ACGTRYSWKMBDHVN")
_RNA_IUPAC = set("ACGURYSWKMBDHVN")
_DNA_CANONICAL = set("ACGT")
_RNA_CANONICAL = set("ACGU")
_DNA_COMPLEMENT = str.maketrans("ACGTRYSWKMBDHVN", "TGCAYRSWMKVHDBN")
_RNA_COMPLEMENT = str.maketrans("ACGURYSWKMBDHVN", "UGCAYRSWMKVHDBN")


def _strip_fasta(seq: str) -> str:
    """Return just the sequence body of a raw or FASTA-formatted input."""
    lines = (seq or "").strip().splitlines()
    lines = [ln.strip() for ln in lines if not ln.strip().startswith(">")]
    return "".join(lines)


def clean_sequence(seq: str, seq_type: str) -> str:
    """Normalize to uppercase sequence symbols while retaining IUPAC ambiguity.

    Whitespace/FASTA headers and non-alphabetic formatting characters are
    ignored. Alphabetic symbols outside the selected alphabet are rejected
    rather than silently deleted, because silent deletion changes coordinates
    and can fabricate downstream measurements.
    """
    body = _strip_fasta(seq)
    letters = "".join(re.findall(r"[A-Za-z]", body)).upper()
    if not letters:
        raise SequenceUtilitiesError("Sequence is empty")

    if seq_type in ("dna", "rna"):
        allowed = _DNA_IUPAC if seq_type == "dna" else _RNA_IUPAC
        invalid = sorted(set(letters) - allowed)
        if invalid:
            raise SequenceUtilitiesError(
                f"Sequence contains invalid {seq_type.upper()} symbols: {', '.join(invalid)}"
            )
        return letters

    valid = set(_AA_ALPHABET)
    invalid = sorted(set(letters) - valid)
    if invalid:
        raise SequenceUtilitiesError(
            f"Sequence contains non-standard amino-acid symbols: {', '.join(invalid)}"
        )
    return letters


def _translate_frame(seq: str, frame: int) -> str:
    codons = [seq[i:i + 3] for i in range(frame, len(seq) - 2, 3)]
    return "".join(_CODON_TABLE.get(c, "X") for c in codons)


def _best_orf(seq: str, frame: int, translated: str) -> dict | None:
    """Longest ORF (M -> stop/end) in a translated frame, with 1-based start."""
    best = None
    for m in re.finditer("M[^*]*", translated):
        length = len(m.group(0))
        start = frame + m.start() * 3 + 1
        if best is None or length > best["length"]:
            best = {
                "frame": frame + 1,
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


def _nucleotide_mw(seq: str, seq_type: str) -> float | None:
    """Return exact linear ssDNA/ssRNA molecular weight for unambiguous input.

    Ambiguous IUPAC bases do not have a unique mass; returning an arbitrary
    base mass would create a false numerical claim, so such inputs return None
    and the caller records the limitation in ``issues``.
    """
    canonical = _DNA_CANONICAL if seq_type == "dna" else _RNA_CANONICAL
    if set(seq) - canonical:
        return None
    bio_type = "DNA" if seq_type == "dna" else "RNA"
    return round(
        float(molecular_weight(seq, seq_type=bio_type, double_stranded=False, circular=False)),
        2,
    )


def _reverse_complement(seq: str, seq_type: str) -> str:
    table = _DNA_COMPLEMENT if seq_type == "dna" else _RNA_COMPLEMENT
    return seq.translate(table)[::-1]


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

    ``seq_type`` may be 'auto', 'dna', 'rna' or 'protein'. For nucleotide
    inputs, ambiguity symbols are preserved. GC% is reported over unambiguous
    A/C/G/T(U) positions only when ambiguity is present, and exact molecular
    weight is withheld because ambiguous symbols do not specify a unique mass.
    """
    seq_type = (seq_type or "auto").lower()
    if seq_type not in ("auto", "dna", "rna", "protein"):
        raise SequenceUtilitiesError("seq_type must be auto, dna, rna or protein")

    raw = _strip_fasta(sequence)
    detected = detect_sequence_type(raw) if raw else "unknown"
    effective = seq_type if seq_type != "auto" else detected
    if effective == "unknown":
        raise SequenceUtilitiesError(
            "Could not detect sequence type — expected nucleotide or protein characters"
        )

    seq = clean_sequence(raw, effective)
    issues: list[str] = []
    report: dict = {
        "sequence_type": effective,
        "detected_type": detected,
        "length": len(seq),
        "gc_content": None,
        "molecular_weight": None,
        "reverse_complement": None,
        "translation": None,
        "aa_composition": None,
        "restriction_sites": None,
        "issues": issues,
    }

    if effective in ("dna", "rna"):
        canonical = _DNA_CANONICAL if effective == "dna" else _RNA_CANONICAL
        concrete = "".join(base for base in seq if base in canonical)
        if concrete:
            report["gc_content"] = round(
                (concrete.count("G") + concrete.count("C")) / len(concrete) * 100.0,
                1,
            )
        if len(concrete) != len(seq):
            issues.append("Ambiguous IUPAC bases were excluded from the GC-content denominator")

        report["molecular_weight"] = _nucleotide_mw(seq, effective)
        if report["molecular_weight"] is None:
            issues.append("Exact molecular weight is unavailable for ambiguous IUPAC bases")

        report["reverse_complement"] = _reverse_complement(seq, effective)

        dna_seq = seq.translate(_RNA_TO_DNA)
        if len(dna_seq) < 3:
            issues.append("Sequence too short for translation (<3 nt)")
        else:
            frames = {}
            best = None
            for frame in (0, 1, 2):
                translated = _translate_frame(dna_seq, frame)
                frames[str(frame + 1)] = translated
                orf = _best_orf(dna_seq, frame, translated)
                if orf and (best is None or orf["length"] > best["length"]):
                    best = orf
            report["translation"] = {"frames": frames, "best": best}
            if best is None:
                issues.append("No in-frame methionine (ATG/AUG) found — no ORF to report")
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

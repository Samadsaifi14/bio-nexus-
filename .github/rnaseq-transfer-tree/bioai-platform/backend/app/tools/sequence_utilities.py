"""Authoritative sequence-utility library used by every sequence UI.

Scientific operations live here, never in React components.  DNA and RNA remain
distinct; nucleotide IUPAC ambiguity is preserved; invalid symbols fail with a
coordinate instead of being silently removed.
"""

from __future__ import annotations

import re
from typing import Any

from Bio.SeqUtils import molecular_weight
from Bio.SeqUtils.ProtParam import ProteinAnalysis

from app.services.sequence_utils import detect_sequence_type


class SequenceUtilitiesError(ValueError):
    pass


_CODON_TABLE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L", "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*", "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L", "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q", "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M", "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K", "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V", "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E", "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

_RESTRICTION_ENZYMES = [
    ("EcoRI", "GAATTC"), ("BamHI", "GGATCC"), ("HindIII", "AAGCTT"), ("SalI", "GTCGAC"),
    ("XbaI", "TCTAGA"), ("XhoI", "CTCGAG"), ("NotI", "GCGGCCGC"), ("KpnI", "GGTACC"),
    ("SmaI", "CCCGGG"), ("PstI", "CTGCAG"), ("SacI", "GAGCTC"),
]

_RNA_TO_DNA = str.maketrans("Uu", "Tt")
_DNA_TO_RNA = str.maketrans("Tt", "Uu")
_DNA_IUPAC = set("ACGTRYSWKMBDHVN")
_RNA_IUPAC = set("ACGURYSWKMBDHVN")
_DNA_CANONICAL = set("ACGT")
_RNA_CANONICAL = set("ACGU")
_PROTEIN_CANONICAL = set("ACDEFGHIKLMNPQRSTVWY")
_PROTEIN_IUPAC = set("ACDEFGHIKLMNPQRSTVWYBXZJUO")
_DNA_COMPLEMENT = str.maketrans("ACGTRYSWKMBDHVN", "TGCAYRSWMKVHDBN")
_RNA_COMPLEMENT = str.maketrans("ACGURYSWKMBDHVN", "UGCAYRSWMKVHDBN")


def _sequence_body(seq: str) -> str:
    """Remove FASTA header lines only; preserve sequence characters for validation."""
    lines = (seq or "").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith(">"))


def _symbols_with_positions(seq: str) -> list[tuple[str, int]]:
    body = _sequence_body(seq)
    symbols: list[tuple[str, int]] = []
    position = 0
    for character in body:
        if character.isspace():
            continue
        position += 1
        symbols.append((character.upper(), position))
    return symbols


def _strip_fasta(seq: str) -> str:
    """Compatibility helper returning whitespace-free sequence body."""
    return "".join(character for character, _ in _symbols_with_positions(seq))


def clean_sequence(seq: str, seq_type: str) -> str:
    """Validate and normalize one sequence without silently deleting symbols."""
    symbols = _symbols_with_positions(seq)
    if not symbols:
        raise SequenceUtilitiesError("Invalid sequence: sequence is empty")

    if seq_type == "dna":
        allowed = _DNA_IUPAC
    elif seq_type == "rna":
        allowed = _RNA_IUPAC
    elif seq_type == "protein":
        allowed = _PROTEIN_IUPAC
    else:
        raise SequenceUtilitiesError("seq_type must be dna, rna or protein")

    for character, position in symbols:
        if character not in allowed:
            raise SequenceUtilitiesError(
                f"Invalid sequence: character {character!r} at position {position} is not valid {seq_type.upper()}"
            )
    return "".join(character for character, _ in symbols)


def _translate_frame(dna_seq: str, offset: int) -> str:
    return "".join(
        _CODON_TABLE.get(dna_seq[index:index + 3], "X")
        for index in range(offset, len(dna_seq) - 2, 3)
    )


def _reverse_complement(seq: str, seq_type: str) -> str:
    table = _DNA_COMPLEMENT if seq_type == "dna" else _RNA_COMPLEMENT
    return seq.translate(table)[::-1]


def _dna_reverse_complement(dna: str) -> str:
    return dna.translate(_DNA_COMPLEMENT)[::-1]


def _frame_translation(dna: str, signed_frame: int) -> str:
    if signed_frame not in (1, 2, 3, -1, -2, -3):
        raise SequenceUtilitiesError("frame must be one of 1, 2, 3, -1, -2, -3")
    source = dna if signed_frame > 0 else _dna_reverse_complement(dna)
    return _translate_frame(source, abs(signed_frame) - 1)


def _orfs_in_frame(dna: str, signed_frame: int, min_aa: int = 1) -> list[dict[str, Any]]:
    translated = _frame_translation(dna, signed_frame)
    offset = abs(signed_frame) - 1
    n = len(dna)
    orfs: list[dict[str, Any]] = []
    for match in re.finditer(r"M[^*]*", translated):
        protein = match.group(0)
        if len(protein) < min_aa:
            continue
        nt_start = offset + match.start() * 3
        nt_end = offset + match.end() * 3
        has_stop = match.end() < len(translated) and translated[match.end()] == "*"
        if signed_frame > 0:
            start, end = nt_start + 1, min(nt_end, n)
            strand = "+"
        else:
            start, end = max(1, n - nt_end + 1), n - nt_start
            strand = "-"
        orfs.append({
            "frame": signed_frame,
            "strand": strand,
            "start": start,
            "end": end,
            "length": len(protein),
            "protein": protein,
            "has_stop": has_stop,
            "starts_with_m": True,
        })
    return orfs


def six_frame_translation(sequence: str, seq_type: str = "dna") -> dict[str, str]:
    if seq_type not in ("dna", "rna"):
        raise SequenceUtilitiesError("Six-frame translation requires DNA or RNA")
    seq = clean_sequence(sequence, seq_type)
    dna = seq.translate(_RNA_TO_DNA) if seq_type == "rna" else seq
    return {str(frame): _frame_translation(dna, frame) for frame in (1, 2, 3, -1, -2, -3)}


def find_orfs(sequence: str, seq_type: str = "dna", min_aa: int = 1) -> list[dict[str, Any]]:
    if seq_type not in ("dna", "rna"):
        raise SequenceUtilitiesError("ORF finding requires DNA or RNA")
    if min_aa < 1:
        raise SequenceUtilitiesError("min_aa must be >= 1")
    seq = clean_sequence(sequence, seq_type)
    dna = seq.translate(_RNA_TO_DNA) if seq_type == "rna" else seq
    hits: list[dict[str, Any]] = []
    for frame in (1, 2, 3, -1, -2, -3):
        hits.extend(_orfs_in_frame(dna, frame, min_aa=min_aa))
    return sorted(hits, key=lambda item: (-item["length"], item["frame"], item["start"]))


def translate_selected_frame(
    sequence: str,
    *,
    seq_type: str = "dna",
    frame: int = 1,
    stop_at_stop: bool = False,
) -> dict[str, Any]:
    """Translate exactly the selected frame; never search for a first ATG."""
    if seq_type not in ("dna", "rna"):
        raise SequenceUtilitiesError("Translation requires DNA or RNA")
    seq = clean_sequence(sequence, seq_type)
    dna = seq.translate(_RNA_TO_DNA) if seq_type == "rna" else seq
    protein = _frame_translation(dna, frame)
    stop_index = protein.find("*")
    if stop_at_stop and stop_index >= 0:
        protein = protein[:stop_index]
    return {
        "frame": frame,
        "genetic_code": "Standard (NCBI translation table 1)",
        "stop_at_first_stop": bool(stop_at_stop),
        "stop_encountered": stop_index >= 0,
        "protein": protein,
    }


def translate_cds(
    sequence: str,
    *,
    seq_type: str = "dna",
    frame: int = 1,
    require_start: bool = False,
    require_terminal_stop: bool = False,
) -> dict[str, Any]:
    """Translate a declared CDS in the selected frame without ORF guessing."""
    translated = translate_selected_frame(sequence, seq_type=seq_type, frame=frame, stop_at_stop=False)
    protein_full = translated["protein"]
    starts_with_m = protein_full.startswith("M")
    terminal_stop = protein_full.endswith("*")
    if require_start and not starts_with_m:
        raise SequenceUtilitiesError("Declared CDS does not begin with a start codon in the selected frame")
    if require_terminal_stop and not terminal_stop:
        raise SequenceUtilitiesError("Declared CDS does not end with a stop codon in the selected frame")
    internal_stop = "*" in protein_full[:-1]
    return {
        **translated,
        "protein": protein_full[:-1] if terminal_stop else protein_full,
        "starts_with_m": starts_with_m,
        "terminal_stop": terminal_stop,
        "internal_stop": internal_stop,
        "mode": "declared_cds",
    }


def _protein_mw(seq: str) -> float | None:
    if set(seq) - _PROTEIN_CANONICAL:
        return None
    return round(float(ProteinAnalysis(seq).molecular_weight()), 2)


def _nucleotide_mw(seq: str, seq_type: str) -> float | None:
    canonical = _DNA_CANONICAL if seq_type == "dna" else _RNA_CANONICAL
    if set(seq) - canonical:
        return None
    return round(
        float(molecular_weight(seq, seq_type="DNA" if seq_type == "dna" else "RNA", double_stranded=False, circular=False)),
        2,
    )


def _aa_composition(seq: str) -> list[dict]:
    counts: dict[str, int] = {}
    for residue in seq:
        if residue in _PROTEIN_IUPAC:
            counts[residue] = counts.get(residue, 0) + 1
    total = sum(counts.values())
    return [
        {"aa": aa, "count": count, "pct": round(count / total * 100, 1) if total else 0.0}
        for aa, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _restriction_scan(seq: str) -> list[dict]:
    sites = []
    for name, recognition in _RESTRICTION_ENZYMES:
        positions = [match.start() + 1 for match in re.finditer(recognition, seq)]
        if positions:
            sites.append({"name": name, "recognition": recognition, "count": len(positions), "positions": positions})
    return sites


def complement_sequence(sequence: str, seq_type: str) -> str:
    seq = clean_sequence(sequence, seq_type)
    if seq_type == "dna":
        return seq.translate(_DNA_COMPLEMENT)
    if seq_type == "rna":
        return seq.translate(_RNA_COMPLEMENT)
    raise SequenceUtilitiesError("Complement requires DNA or RNA")


def reverse_sequence(sequence: str, seq_type: str) -> str:
    return clean_sequence(sequence, seq_type)[::-1]


def reverse_complement_sequence(sequence: str, seq_type: str) -> str:
    if seq_type not in ("dna", "rna"):
        raise SequenceUtilitiesError("Reverse complement requires DNA or RNA")
    return _reverse_complement(clean_sequence(sequence, seq_type), seq_type)


def transcribe_dna(sequence: str) -> str:
    return clean_sequence(sequence, "dna").translate(_DNA_TO_RNA)


def format_fasta(sequence: str, seq_type: str, name: str = "sequence", width: int = 60) -> str:
    seq = clean_sequence(sequence, seq_type)
    if width < 1 or width > 1000:
        raise SequenceUtilitiesError("FASTA line width must be between 1 and 1000")
    safe_name = " ".join((name or "sequence").replace("\n", " ").replace("\r", " ").split()) or "sequence"
    return f">{safe_name}\n" + "\n".join(seq[i:i + width] for i in range(0, len(seq), width)) + "\n"


def analyze_sequence(sequence: str, seq_type: str = "auto") -> dict:
    seq_type = (seq_type or "auto").lower()
    if seq_type not in ("auto", "dna", "rna", "protein"):
        raise SequenceUtilitiesError("seq_type must be auto, dna, rna or protein")

    raw = _strip_fasta(sequence)
    if not raw:
        raise SequenceUtilitiesError("Invalid sequence: sequence is empty")
    detected = detect_sequence_type(raw)
    effective = seq_type if seq_type != "auto" else detected
    if effective == "unknown":
        raise SequenceUtilitiesError("Could not detect sequence type; specify DNA, RNA or protein explicitly")

    seq = clean_sequence(sequence, effective)
    issues: list[str] = []
    report: dict[str, Any] = {
        "sequence_type": effective,
        "detected_type": detected,
        "length": len(seq),
        "gc_content": None,
        "molecular_weight": None,
        "molecular_weight_assumptions": None,
        "reverse_complement": None,
        "transcription": None,
        "translation": None,
        "aa_composition": None,
        "restriction_sites": None,
        "issues": issues,
    }

    if effective in ("dna", "rna"):
        canonical = _DNA_CANONICAL if effective == "dna" else _RNA_CANONICAL
        concrete = "".join(base for base in seq if base in canonical)
        if concrete:
            report["gc_content"] = round((concrete.count("G") + concrete.count("C")) / len(concrete) * 100.0, 1)
        if len(concrete) != len(seq):
            issues.append("Ambiguous IUPAC bases were excluded from the GC-content denominator")

        report["molecular_weight"] = _nucleotide_mw(seq, effective)
        report["molecular_weight_assumptions"] = (
            f"Biopython average molecular weight; linear single-stranded {effective.upper()}; unambiguous bases required"
        )
        if report["molecular_weight"] is None:
            issues.append("Exact molecular weight is unavailable because ambiguous IUPAC symbols do not specify a unique mass")

        report["reverse_complement"] = _reverse_complement(seq, effective)
        if effective == "dna":
            report["transcription"] = seq.translate(_DNA_TO_RNA)
            report["restriction_sites"] = _restriction_scan(seq)
        else:
            issues.append("Restriction-site scan is DNA-only")

        dna = seq.translate(_RNA_TO_DNA) if effective == "rna" else seq
        if len(dna) < 3:
            issues.append("Sequence too short for translation (<3 nt)")
        else:
            frames = {str(frame): _frame_translation(dna, frame) for frame in (1, 2, 3, -1, -2, -3)}
            orfs = find_orfs(seq, effective)
            best = orfs[0] if orfs else None
            report["translation"] = {
                "frames": frames,
                "best": best,
                "genetic_code": "Standard (NCBI translation table 1)",
                "frame_convention": "+1/+2/+3 forward; -1/-2/-3 reverse-complement",
            }
            if best is None:
                issues.append("No methionine-initiated ORF was found in any of the six frames")
            else:
                report["aa_composition"] = _aa_composition(best["protein"])
    else:
        report["molecular_weight"] = _protein_mw(seq)
        report["molecular_weight_assumptions"] = "Biopython ProteinAnalysis average molecular weight; canonical 20 amino acids required"
        if report["molecular_weight"] is None:
            issues.append("Exact molecular weight is unavailable for ambiguous/non-canonical amino-acid symbols")
        report["aa_composition"] = _aa_composition(seq)
        if len(seq) < 2:
            issues.append("Protein sequence very short; composition may be uninformative")

    return report

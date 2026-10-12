from Bio import SeqIO
from io import StringIO
from dataclasses import dataclass, field
from typing import List

PROTEIN_ALPHABET = "ACDEFGHIKLMNPQRSTVWYUBZXOJ"
NUCLEOTIDE_ALPHABET = "ACGUTNRSWYKMBDHV"


@dataclass
class ValidationResult:
    valid: bool = True
    error: str = ""
    sequences: List = field(default_factory=list)


def _sequence_type_of(seq_str: str) -> str:
    from app.services.sequence_utils import detect_sequence_type

    clean = "".join(c for c in seq_str if c.isalpha()).upper()
    return detect_sequence_type(clean)


def _validate_sequence(seq_str: str) -> tuple[bool, str]:
    if len(seq_str) < 6:
        return False, f"Sequence too short: {len(seq_str)} residues"
    seq_type = _sequence_type_of(seq_str)
    if seq_type == "protein":
        ok = set(seq_str.upper()).issubset(set(PROTEIN_ALPHABET))
        return (ok, "" if ok else "Invalid amino acid characters found")
    if seq_type in ("dna", "rna"):
        ok = set(seq_str.upper()).issubset(set(NUCLEOTIDE_ALPHABET))
        return (ok, "" if ok else "Invalid nucleotide characters found")
    return False, "Sequence contains unrecognized characters"


def validate_fasta(text: str, tool: str = "blast") -> ValidationResult:
    if not text or not text.strip():
        return ValidationResult(valid=False, error="Empty sequence")

    # Try parsing as FASTA
    try:
        records = list(SeqIO.parse(StringIO(text), "fasta"))
    except Exception:
        records = []

    if records:
        for rec in records:
            ok, err = _validate_sequence(str(rec.seq))
            if not ok:
                return ValidationResult(valid=False, error=err)
        return ValidationResult(sequences=records)

    # Plain sequence (no FASTA header)
    clean = "".join(c for c in text if c.isalpha()).upper()
    ok, err = _validate_sequence(clean)
    if not ok:
        return ValidationResult(valid=False, error=err)

    from Bio.Seq import Seq
    from Bio.SeqRecord import SeqRecord

    record = SeqRecord(Seq(clean), id="query", description="")
    return ValidationResult(sequences=[record])

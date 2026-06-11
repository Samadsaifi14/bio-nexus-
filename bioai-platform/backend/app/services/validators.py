from Bio import SeqIO
from io import StringIO
from dataclasses import dataclass, field
from typing import List


@dataclass
class ValidationResult:
    valid: bool = True
    error: str = ""
    sequences: List = field(default_factory=list)


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
            seq_str = str(rec.seq)
            if len(seq_str) < 6:
                return ValidationResult(valid=False, error=f"Sequence too short: {len(seq_str)} residues")
            if not set(seq_str.upper()).issubset(set("ACDEFGHIKLMNPQRSTVWY")):
                return ValidationResult(valid=False, error="Invalid amino acid characters found")
        return ValidationResult(sequences=records)

    # Plain sequence (no FASTA header)
    clean = "".join(c for c in text if c.isalpha()).upper()
    if len(clean) < 6:
        return ValidationResult(valid=False, error=f"Sequence too short: {len(clean)} residues")
    if not set(clean).issubset(set("ACDEFGHIKLMNPQRSTVWY")):
        return ValidationResult(valid=False, error="Invalid amino acid characters found")

    from Bio.Seq import Seq
    from Bio.SeqRecord import SeqRecord
    record = SeqRecord(Seq(clean), id="query", description="")
    return ValidationResult(sequences=[record])

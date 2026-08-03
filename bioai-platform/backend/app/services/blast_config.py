"""BLAST program / database matrix and sequence-type-aware resolution.

Programs map to the NCBI QBLAST PROGRAMS. Databases are validated against the
program's valid target types so a protein-only db (nr) is never sent for a
nucleotide program (blastn) and vice versa.
"""

from app.services.sequence_utils import detect_sequence_type

PROTEIN_PROGRAMS = ["blastp", "tblastn"]
NUCLEOTIDE_PROGRAMS = ["blastn", "blastx", "tblastx"]
ALL_PROGRAMS = ["blastp", "blastn", "blastx", "tblastn", "tblastx"]

PROGRAM_DATABASES = {
    "blastp": ["nr", "swissprot", "pdb", "pdbaa", "refseq_protein", "env_nr"],
    "blastn": ["nt", "refseq_rna", "refseq_genomic", "est", "gss"],
    "blastx": ["nr", "swissprot", "pdb", "pdbaa", "refseq_protein"],
    "tblastn": ["nt", "refseq_rna", "refseq_genomic", "est", "gss"],
    "tblastx": ["nt", "refseq_rna", "refseq_genomic", "est", "gss"],
}

DEFAULT_PROGRAM = {"protein": "blastp", "dna": "blastn", "rna": "blastn"}
DEFAULT_DATABASE = {"protein": "nr", "dna": "nt", "rna": "nt"}
FAST_DATABASE = {"protein": "swissprot", "dna": "refseq_rna", "rna": "refseq_rna"}


def resolve_blast_params(
    sequence: str,
    program: str | None = None,
    database: str | None = None,
    fast_mode: bool = False,
) -> tuple[str, str, str]:
    """Return (program, database, seq_type) with safe normalization.

    An explicitly requested program that doesn't match the query's detected
    type raises ValueError (the caller surfaces it as a clear job error).
    An incompatible or missing database falls back to the program's default so
    the frontend's permissive defaults (e.g. nr sent for a DNA query) degrade
    gracefully instead of erroring.
    """
    seq_type = detect_sequence_type(sequence)
    if seq_type not in ("protein", "dna", "rna"):
        raise ValueError(f"Could not determine sequence type for BLAST (detected: {seq_type})")

    if not program:
        program = DEFAULT_PROGRAM[seq_type]
    program = program.lower().strip()
    if program not in ALL_PROGRAMS:
        raise ValueError(f"Unsupported BLAST program: {program}")

    allowed = PROTEIN_PROGRAMS if seq_type == "protein" else NUCLEOTIDE_PROGRAMS
    if program not in allowed:
        raise ValueError(f"Program '{program}' cannot be used with a {seq_type} query")

    if not database:
        database = FAST_DATABASE[seq_type] if fast_mode else DEFAULT_DATABASE[seq_type]
    database = database.lower().strip()

    valid_dbs = PROGRAM_DATABASES[program]
    if database not in valid_dbs:
        database = FAST_DATABASE[seq_type] if fast_mode else DEFAULT_DATABASE[seq_type]

    return program, database, seq_type

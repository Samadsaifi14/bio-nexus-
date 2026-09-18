"""BLAST program / database matrix and sequence-type-aware resolution.

Programs map to the NCBI QBLAST PROGRAMS. Databases are validated against the
program's valid target types so a protein-only db (nr) is never sent for a
nucleotide-target program and vice versa.
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

# Defaults must follow the TARGET molecule type implied by the program, not the
# query molecule type. For example blastx takes a nucleotide query but searches
# a protein database, while tblastn takes a protein query and searches a
# nucleotide database.
PROGRAM_DEFAULT_DATABASE = {
    "blastp": "nr",
    "blastn": "nt",
    "blastx": "nr",
    "tblastn": "nt",
    "tblastx": "nt",
}

# Fast mode narrows the target database while preserving molecule compatibility.
PROGRAM_FAST_DATABASE = {
    "blastp": "swissprot",
    "blastn": "refseq_rna",
    "blastx": "swissprot",
    "tblastn": "refseq_rna",
    "tblastx": "refseq_rna",
}

# Kept for compatibility with callers/tests that inspect sequence defaults.
DEFAULT_PROGRAM = {"protein": "blastp", "dna": "blastn", "rna": "blastn"}
# Protein defaults to the curated Swiss-Prot DB: EBI's nr equivalent
# (uniprotkb) exceeds the 180s poll budget and NCBI queue estimates run to
# hours, so nr as a default is a guaranteed timeout. nr stays selectable.
DEFAULT_DATABASE = {"protein": "swissprot", "dna": "nt", "rna": "nt"}
FAST_DATABASE = {"protein": "swissprot", "dna": "refseq_rna", "rna": "refseq_rna"}


def resolve_blast_params(
    sequence: str,
    program: str | None = None,
    database: str | None = None,
    fast_mode: bool = False,
) -> tuple[str, str, str]:
    """Return ``(program, database, seq_type)`` with safe normalization.

    The selected program must accept the detected query molecule type. Database
    selection is then validated against that program's target molecule type.
    Missing or incompatible databases fall back to a program-specific default,
    preventing combinations such as ``blastx + nt`` or ``tblastn + nr``.
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

    fallback_database = PROGRAM_FAST_DATABASE[program] if fast_mode else PROGRAM_DEFAULT_DATABASE[program]
    if not database:
        database = fallback_database
    database = database.lower().strip()

    valid_dbs = PROGRAM_DATABASES[program]
    if database not in valid_dbs:
        database = fallback_database

    return program, database, seq_type

"""Deterministic regression tests for the five core BLAST programs.

These tests use the same long nucleotide query that previously produced an
apparent no-result outcome in BioNexus. No external BLAST provider is called.
"""

import asyncio

import pytest


USER_NUCLEOTIDE = (
    "GGCACGAGATCACATTCAACAATGGTTAAGGCTGTGGCAGTTCTTGGTAGCAGTGACACTGTGTCTGGGA"
    "CTATTAACTTCAGTCAGGAGGGAGACGGTCCAACCACTGTAACTGGGAATCTTGCTGGTCTTAAGCCTGG"
    "TCTCCATGGCTTCCATATTCATGCCTTAGGGGACACCACAAATGGCTGCATATCAACCGGACCACATTTC"
    "AATCCTAATGGGAAAGAACATGGTTCCCCTGAGGACCCGATTCGACATGCTGGCGATTTAGGAAATATCA"
    "ATGTCGGTGATGATGGAACTGTAAGCTTCTCTATTACTGACAATCAGATCCCTCTCACTGGACCAAACTC"
    "CATCATAGGAAGGGCTGTTGTTGTTCATGCTGATCCTGATGATCTTGGGAAAGGTGGTCACGAGCTTAGC"
    "AAAACTACTGGAAATGCTGGCGGCAGAGTAGCTTGTGGTATTATTGGGTTGCAAGGATAAACCACCACTC"
    "TCAACTCCGGGATACTTGAAGTTGGAAATGTGTGATGATATATGTTGAAGCTTTAGAAGAATAAAATGCA"
    "TGCATCTCATCACTTGCCTGTTTAGGTCTGATCTGTACTGTTGAATTGTGTGTTTTTCCTTGTAGCGAAA"
    "TTTGCAATTGGTTCTTAATTTAGTACTTTACCTGAAGTTCGTGGTTAAAAAAAAAAAAAAAAAAAAAAAAAA"
)

PROTEIN = "MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKTRR"


def test_reported_query_is_detected_as_dna():
    from app.services.sequence_utils import detect_sequence_type

    assert detect_sequence_type(USER_NUCLEOTIDE) == "dna"


@pytest.mark.parametrize(
    ("program", "database"),
    [
        ("blastn", "nt"),
        ("blastx", "nr"),
        ("tblastx", "nt"),
    ],
)
def test_nucleotide_query_supports_all_valid_core_programs(program, database):
    from app.services.blast_config import resolve_blast_params

    resolved_program, resolved_database, seq_type = resolve_blast_params(
        USER_NUCLEOTIDE,
        program=program,
    )
    assert seq_type == "dna"
    assert resolved_program == program
    assert resolved_database == database


@pytest.mark.parametrize(
    ("program", "database"),
    [
        ("blastp", "swissprot"),
        ("tblastn", "nt"),
    ],
)
def test_protein_query_supports_all_valid_core_programs(program, database):
    from app.services.blast_config import resolve_blast_params

    resolved_program, resolved_database, seq_type = resolve_blast_params(
        PROTEIN,
        program=program,
    )
    assert seq_type == "protein"
    assert resolved_program == program
    assert resolved_database == database


def test_program_specific_database_fallbacks_are_target_correct():
    from app.services.blast_config import resolve_blast_params

    # blastx: nucleotide query -> protein target. ``nt`` must be corrected to nr.
    _, blastx_db, _ = resolve_blast_params(USER_NUCLEOTIDE, program="blastx", database="nt")
    assert blastx_db == "nr"

    # tblastn: protein query -> nucleotide target. ``nr`` must be corrected to nt.
    _, tblastn_db, _ = resolve_blast_params(PROTEIN, program="tblastn", database="nr")
    assert tblastn_db == "nt"


def test_invalid_query_program_pairs_are_rejected():
    from app.services.blast_config import resolve_blast_params

    with pytest.raises(ValueError):
        resolve_blast_params(USER_NUCLEOTIDE, program="blastp")
    with pytest.raises(ValueError):
        resolve_blast_params(USER_NUCLEOTIDE, program="tblastn")
    with pytest.raises(ValueError):
        resolve_blast_params(PROTEIN, program="blastn")
    with pytest.raises(ValueError):
        resolve_blast_params(PROTEIN, program="blastx")
    with pytest.raises(ValueError):
        resolve_blast_params(PROTEIN, program="tblastx")


def test_ebi_submission_stype_matches_query_molecule(monkeypatch):
    from app.tools.blast import BlastTool

    captured = []

    class FakeResp:
        text = "ebi-job-123"

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            captured.append(kwargs["data"])
            return FakeResp()

    monkeypatch.setattr("app.tools.blast.httpx.AsyncClient", lambda **kw: FakeClient())

    async def exercise():
        tool = BlastTool()
        await tool._submit(PROTEIN, "blastp", "uniprotkb_swissprot")
        await tool._submit(PROTEIN, "tblastn", "nt")
        await tool._submit(USER_NUCLEOTIDE, "blastn", "nt")
        await tool._submit(USER_NUCLEOTIDE, "blastx", "uniprotkb")
        await tool._submit(USER_NUCLEOTIDE, "tblastx", "nt")

    asyncio.run(exercise())

    assert [item["stype"] for item in captured] == [
        "protein",
        "protein",
        "dna",
        "dna",
        "dna",
    ]

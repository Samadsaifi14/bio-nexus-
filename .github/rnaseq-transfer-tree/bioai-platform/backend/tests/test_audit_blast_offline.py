"""Publication audit: deterministic/offline BLAST routing and XML parsing.

These tests do not claim biological search accuracy. They validate that BioNexus
routes query types to compatible BLAST programs/databases and preserves NCBI
HSP measurements without inventing or rescaling values.
"""

from __future__ import annotations

import random

import pytest

from app.integrations.ncbi.parser import parse_blast_xml
from app.services.blast_config import PROGRAM_DATABASES, resolve_blast_params


SEED = 20260916


def test_program_database_matrix_respects_query_and_target_molecule_types():
    protein = "MKWVTFISLLFLFSSAYSRGVFRR"
    dna = "ATGCGTACCGTTGATCGTACCGATGCTA"
    rna = dna.replace("T", "U")

    for sequence, expected_type, allowed_programs in (
        (protein, "protein", {"blastp", "tblastn"}),
        (dna, "dna", {"blastn", "blastx", "tblastx"}),
        (rna, "rna", {"blastn", "blastx", "tblastx"}),
    ):
        for program in allowed_programs:
            resolved_program, database, seq_type = resolve_blast_params(sequence, program=program)
            assert resolved_program == program
            assert seq_type == expected_type
            assert database in PROGRAM_DATABASES[program]


def test_incompatible_program_is_rejected_not_silently_rewritten():
    with pytest.raises(ValueError):
        resolve_blast_params("MKWVTFISLLFLFSSAYSRG", program="blastn")
    with pytest.raises(ValueError):
        resolve_blast_params("ATGCGTACCGTTGATCGTAC", program="blastp")


def test_incompatible_database_falls_back_to_program_target_default():
    p, db, _ = resolve_blast_params("MKWVTFISLLFLFSSAYSRG", program="tblastn", database="nr")
    assert p == "tblastn"
    assert db == "nt"
    p, db, _ = resolve_blast_params("ATGCGTACCGTTGATCGTAC", program="blastx", database="nt")
    assert p == "blastx"
    assert db == "nr"


def _xml_for_hsps(hsps: list[dict], query_len: int = 120) -> str:
    hsp_xml = "".join(
        f"""
        <Hsp>
          <Hsp_bit-score>{h['bit']}</Hsp_bit-score>
          <Hsp_score>{h['score']}</Hsp_score>
          <Hsp_evalue>{h['evalue']}</Hsp_evalue>
          <Hsp_query-from>{h['qfrom']}</Hsp_query-from>
          <Hsp_query-to>{h['qto']}</Hsp_query-to>
          <Hsp_hit-from>{h['hfrom']}</Hsp_hit-from>
          <Hsp_hit-to>{h['hto']}</Hsp_hit-to>
          <Hsp_identity>{h['identity']}</Hsp_identity>
          <Hsp_positive>{h['positive']}</Hsp_positive>
          <Hsp_gaps>{h['gaps']}</Hsp_gaps>
          <Hsp_align-len>{h['alen']}</Hsp_align-len>
          <Hsp_qseq>{h['qseq']}</Hsp_qseq>
          <Hsp_hseq>{h['hseq']}</Hsp_hseq>
          <Hsp_midline>{h['mid']}</Hsp_midline>
        </Hsp>
        """
        for h in hsps
    )
    return f"""<?xml version="1.0"?>
<BlastOutput>
  <BlastOutput_query-len>{query_len}</BlastOutput_query-len>
  <BlastOutput_iterations>
    <Iteration>
      <Iteration_hits>
        <Hit>
          <Hit_num>1</Hit_num>
          <Hit_id>ref|XP_123.1|</Hit_id>
          <Hit_def>XP_123.1 Example protein [Homo sapiens]</Hit_def>
          <Hit_accession>XP_123.1</Hit_accession>
          <Hit_len>140</Hit_len>
          <Hit_hsps>{hsp_xml}</Hit_hsps>
        </Hit>
      </Iteration_hits>
    </Iteration>
  </BlastOutput_iterations>
</BlastOutput>"""


def test_seeded_random_hsp_metrics_are_preserved_exactly():
    rng = random.Random(SEED)
    for _ in range(75):
        alen = rng.randint(5, 100)
        identity = rng.randint(0, alen)
        positive = rng.randint(identity, alen)
        gaps = rng.randint(0, max(0, alen - identity))
        hsp = {
            "bit": round(rng.uniform(10, 500), 3),
            "score": rng.randint(10, 1000),
            "evalue": f"{10 ** (-rng.randint(1, 80)):.3e}",
            "qfrom": rng.randint(1, 10),
            "qto": 0,
            "hfrom": rng.randint(1, 10),
            "hto": 0,
            "identity": identity,
            "positive": positive,
            "gaps": gaps,
            "alen": alen,
            "qseq": "A" * alen,
            "hseq": "A" * identity + "C" * (alen - identity),
            "mid": "|" * identity + " " * (alen - identity),
        }
        hsp["qto"] = hsp["qfrom"] + alen - 1
        hsp["hto"] = hsp["hfrom"] + alen - 1
        parsed = parse_blast_xml(_xml_for_hsps([hsp]))
        assert parsed["query_length"] == 120
        assert parsed["count"] == 1
        hit = parsed["hits"][0]
        assert hit["accession"] == "XP_123.1"
        assert hit["organism"] == "Homo sapiens"
        assert hit["alignment_length"] == alen
        assert hit["identity"] == identity
        assert hit["positive"] == positive
        assert hit["gaps"] == gaps
        assert hit["identity_pct"] == round(identity / alen * 100, 1)
        assert hit["evalue_raw"] == hsp["evalue"]
        assert hit["evalue"] == float(hsp["evalue"])
        assert hit["query_from"] == hsp["qfrom"]
        assert hit["query_to"] == hsp["qto"]
        assert hit["hit_from"] == hsp["hfrom"]
        assert hit["hit_to"] == hsp["hto"]


def test_parser_selects_best_hsp_by_bit_score_not_xml_order():
    weak = {
        "bit": 20.0, "score": 40, "evalue": "1e-3", "qfrom": 1, "qto": 10,
        "hfrom": 1, "hto": 10, "identity": 5, "positive": 6, "gaps": 0,
        "alen": 10, "qseq": "AAAAAAAAAA", "hseq": "AAAAACCCCC", "mid": "|||||     ",
    }
    strong = {
        "bit": 120.0, "score": 240, "evalue": "1e-30", "qfrom": 20, "qto": 29,
        "hfrom": 40, "hto": 49, "identity": 10, "positive": 10, "gaps": 0,
        "alen": 10, "qseq": "GGGGGGGGGG", "hseq": "GGGGGGGGGG", "mid": "||||||||||",
    }
    hit = parse_blast_xml(_xml_for_hsps([weak, strong]))["hits"][0]
    assert hit["bit_score"] == 120.0
    assert hit["evalue_raw"] == "1e-30"
    assert hit["identity_pct"] == 100.0
    assert hit["query_from"] == 20


def test_qblast_ready_preamble_is_stripped_without_changing_results():
    xml = _xml_for_hsps([{
        "bit": 50.0, "score": 100, "evalue": "2e-10", "qfrom": 1, "qto": 5,
        "hfrom": 7, "hto": 11, "identity": 4, "positive": 5, "gaps": 0,
        "alen": 5, "qseq": "ABCDE", "hseq": "ABCXE", "mid": "||| |",
    }], query_len=5)
    wrapped = "<!--QBlastInfoBegin\nStatus=READY\nQBlastInfoEnd\n-->\n\n" + xml
    assert parse_blast_xml(wrapped) == parse_blast_xml(xml)


def test_malformed_xml_returns_explicit_error_and_empty_hits():
    result = parse_blast_xml("<BlastOutput><broken>")
    assert result["hits"] == []
    assert "error" in result

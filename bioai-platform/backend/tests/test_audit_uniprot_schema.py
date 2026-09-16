"""Deterministic UniProtKB schema/provenance checks for publication auditing.

The fixture mirrors fields used by the current UniProtKB JSON REST response:
proteinDescription.*Name.ecNumbers use ``value``; GO evidence is keyed by
``GoTerm``/``GoEvidenceType``; entryAudit carries entry/sequence versions.
No network access is required.
"""

from __future__ import annotations

import pytest

from app.tools.uniprot import UniprotTool


@pytest.fixture
def tool() -> UniprotTool:
    return UniprotTool()


@pytest.fixture
def current_schema_fixture() -> dict:
    return {
        "primaryAccession": "P00533",
        "entryType": "UniProtKB reviewed (Swiss-Prot)",
        "proteinDescription": {
            "recommendedName": {
                "fullName": {"value": "Epidermal growth factor receptor"},
                "ecNumbers": [{"value": "2.7.10.1"}],
            }
        },
        "genes": [{"geneName": {"value": "EGFR"}}],
        "organism": {"scientificName": "Homo sapiens"},
        "sequence": {"value": "MKWV", "length": 4},
        "comments": [
            {
                "commentType": "FUNCTION",
                "texts": [{"value": "Receptor tyrosine kinase."}],
            },
            {
                "commentType": "CATALYTIC ACTIVITY",
                "reaction": {"ecNumber": "2.7.10.1"},
            },
        ],
        "uniProtKBCrossReferences": [
            {
                "database": "GO",
                "id": "GO:0005006",
                "properties": [
                    {"key": "GoEvidenceType", "value": "IDA:UniProtKB"},
                    {"key": "GoTerm", "value": "F:epidermal growth factor-activated receptor activity"},
                ],
            },
            {
                "database": "EMBL",
                "id": "X00588",
                "properties": [
                    {"key": "ProteinId", "value": "CAA25240.1"},
                ],
            },
        ],
        "entryAudit": {
            "entryVersion": 210,
            "sequenceVersion": 2,
            "lastAnnotationUpdateDate": "2026-01-01",
        },
    }


def test_current_ec_number_schema_is_read_from_recommended_name(tool, current_schema_fixture):
    assert tool._extract_ec_numbers(current_schema_fixture) == ["2.7.10.1"]


def test_catalytic_activity_ec_is_used_as_fallback_and_deduplicated(tool):
    payload = {
        "proteinDescription": {},
        "comments": [
            {"commentType": "CATALYTIC ACTIVITY", "reaction": {"ecNumber": "1.2.3.4"}},
            {"commentType": "CATALYTIC ACTIVITY", "reaction": {"ecNumber": "1.2.3.4"}},
        ],
    }
    assert tool._extract_ec_numbers(payload) == ["1.2.3.4"]


def test_submission_name_is_preserved_when_recommended_name_is_absent(tool):
    payload = {
        "proteinDescription": {
            "submissionNames": [{"fullName": {"value": "Submitted protein name"}}]
        }
    }
    assert tool._extract_name(payload) == "Submitted protein name"


def test_go_term_uses_named_properties_not_property_order(tool, current_schema_fixture):
    detailed = tool._extract_go_terms_detailed(current_schema_fixture)
    assert detailed == [{
        "id": "GO:0005006",
        "term": "F:epidermal growth factor-activated receptor activity",
        "evidence": "IDA:UniProtKB",
        "source": "UniProtKB cross-reference",
    }]
    assert tool._extract_go_terms(current_schema_fixture) == [
        "F:epidermal growth factor-activated receptor activity"
    ]


def test_cds_cross_reference_preserves_database_accession_and_protein_id(tool, current_schema_fixture):
    assert tool._extract_cds_accessions(current_schema_fixture) == [{
        "database": "EMBL",
        "accession": "X00588",
        "protein_sequence_id": "CAA25240.1",
        "nucleotide_sequence_id": "",
    }]


@pytest.mark.asyncio
async def test_run_preserves_versions_and_all_ec_numbers(monkeypatch, tool, current_schema_fixture):
    async def fake_fetch(accession: str):
        assert accession == "P00533"
        return current_schema_fixture

    monkeypatch.setattr(tool, "_fetch", fake_fetch)
    # Call the undecorated function when exposed by functools; otherwise the
    # cache decorator remains harmless for this unique fixture accession.
    result = await tool.run({"accession": "P00533"})
    assert result["accession"] == "P00533"
    assert result["reviewed"] is True
    assert result["ec_number"] == "2.7.10.1"
    assert result["ec_numbers"] == ["2.7.10.1"]
    assert result["entry_version"] == 210
    assert result["sequence_version"] == 2
    assert result["source"] == "UniProtKB"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["../P00533", "P00533?x=1", "P00533/", "P00533 OR 1=1", ""])
async def test_invalid_accession_is_rejected_before_network(monkeypatch, tool, bad):
    async def forbidden_fetch(accession: str):
        raise AssertionError("network path should not be reached")

    monkeypatch.setattr(tool, "_fetch", forbidden_fetch)
    result = await tool.run({"accession": bad})
    assert "error" in result

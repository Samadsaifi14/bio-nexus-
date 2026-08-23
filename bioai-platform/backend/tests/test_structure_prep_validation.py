"""Tests for structure-prep input validation and integrity tagging (pre-work A1/A4/A5)."""

import pytest
from fastapi import HTTPException

from app.tools.structure_prep import (
    PDB_ID_RE,
    TEMPLATE_RE,
    fetch_pdb_text,
    swissmodel_fetch_pdb,
    swissmodel_fetch_structures,
    validate_pdb_id,
    validate_template,
    validate_uniprot_accession,
)
from app.routers.structure_prep import PipelineRequest, _validate_request


class TestPdbIdValidation:
    def test_accepts_valid_ids(self):
        assert validate_pdb_id("1crn") == "1CRN"
        assert validate_pdb_id(" 4HHB ") == "4HHB"

    @pytest.mark.parametrize("bad", ["", "123", "12345", "1CR!", "../etc/passwd", "1CRN; rm -rf"])
    def test_rejects_invalid_ids(self, bad):
        with pytest.raises(ValueError):
            validate_pdb_id(bad)


class TestUniprotAccessionValidation:
    def test_accepts_valid_accessions(self):
        assert validate_uniprot_accession("p04637") == "P04637"
        assert validate_uniprot_accession("A0A1234567") == "A0A1234567"

    @pytest.mark.parametrize("bad", ["", "not-an-accession", "ZZ9999", "P04637 OR 1=1"])
    def test_rejects_invalid_accessions(self, bad):
        with pytest.raises(ValueError):
            validate_uniprot_accession(bad)


class TestTemplateValidation:
    def test_accepts_alnum_hyphen(self):
        assert validate_template("SMR-p00120-1") == "SMR-p00120-1"

    def test_rejects_path_traversal(self):
        with pytest.raises(ValueError):
            validate_template("../../secret")
        with pytest.raises(ValueError):
            validate_template("")
        with pytest.raises(ValueError):
            validate_template("a b/c")


class TestRequestValidation:
    def test_rejects_empty_request(self):
        with pytest.raises(HTTPException) as exc:
            _validate_request(PipelineRequest())
        assert exc.value.status_code == 400

    def test_rejects_multiple_inputs(self):
        with pytest.raises(HTTPException) as exc:
            _validate_request(PipelineRequest(pdb_id="1CRN", sequence="ACDEFGHIKLM"))
        assert exc.value.status_code == 400

    def test_rejects_bad_pdb_id_before_network(self):
        with pytest.raises(HTTPException) as exc:
            _validate_request(PipelineRequest(pdb_id="DROP TABLE jobs"))
        assert exc.value.status_code == 400

    def test_rejects_bad_sequence_length_and_charset(self):
        with pytest.raises(HTTPException):
            _validate_request(PipelineRequest(sequence="ACDEF"))  # too short
        with pytest.raises(HTTPException):
            _validate_request(PipelineRequest(sequence="ACDEFGHIK1"))  # digit

    def test_normalizes_valid_inputs(self):
        body = _validate_request(
            PipelineRequest(pdb_id="1crn", probe_radius=1.4)
        )
        assert body.pdb_id == "1CRN"


class TestSsrfRouting:
    """A5: outbound URLs must be validated before requests are made."""

    @pytest.mark.asyncio
    async def test_fetch_pdb_text_rejects_injection_without_network_call(self):
        # Path-traversal-style ID must be rejected locally, never fetched.
        with pytest.raises(ValueError):
            await fetch_pdb_text("../../admin")

    @pytest.mark.asyncio
    async def test_swissmodel_fetch_structures_rejects_bad_accession(self):
        with pytest.raises(ValueError):
            await swissmodel_fetch_structures("x'; DROP TABLE x")

    @pytest.mark.asyncio
    async def test_swissmodel_fetch_pdb_rejects_bad_template(self):
        with pytest.raises(ValueError):
            await swissmodel_fetch_pdb("../nope")

    def test_allowlist_contains_pipeline_hosts(self):
        from app.services.ssrf import ALLOWED_HOSTS
        for host in ("swissmodel.expasy.org", "cfold.bme.uic.edu",
                     "files.rcsb.org", "api-inference.huggingface.co",
                     "api.esmatlas.com"):
            assert host in ALLOWED_HOSTS


class TestRegexes:
    def test_pdb_id_regex_shape(self):
        assert PDB_ID_RE.match("9FED")  # numeric-leading IDs exist
        assert not PDB_ID_RE.match("9FEDD")

    def test_template_regex_shape(self):
        assert TEMPLATE_RE.match("AF-P04637-F1-model_v4")
        assert not TEMPLATE_RE.match("-leading-hyphen")

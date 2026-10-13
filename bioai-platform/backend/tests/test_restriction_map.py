import pytest
from app.tools.restriction_map import restriction_map
from app.tools.sequence_utilities import SequenceUtilitiesError


def test_ecori_linear_cuts_and_conservation():
    r = restriction_map("AAAAGAATTCAAAA", ["EcoRI"])
    assert r["sites"][0]["start"] == 5
    assert r["cut_boundaries"] == [5]
    assert r["fragment_lengths"] == [5, 9]
    assert r["fragment_total"] == r["length"]


def test_origin_spanning_site_and_one_cut_linearizes():
    r = restriction_map("AATTCAAAAG", ["EcoRI"], True)
    assert r["sites"][0]["start"] == 10
    assert r["sites"][0]["end"] == 5
    assert r["sites"][0]["spans_origin"]
    assert r["cut_boundaries"] == [0]
    assert r["fragment_lengths"] == [10]
    assert r["product_topology"] == "linear"


def test_both_nonpalindromic_strands_and_linear_end_exclusion():
    r = restriction_map("AAAAAAGGTCTCAAAAAAGAGACCAAAAAA", ["BsaI"])
    assert {hit["strand"] for hit in r["sites"]} == {"+", "-"}
    assert sum(r["fragment_lengths"]) == r["length"]
    r = restriction_map("GGTCTC", ["BsaI"])
    assert r["sites"][0]["complete_cut"] is False
    assert r["cut_boundaries"] == []


def test_overlapping_recognition_sites():
    r = restriction_map("CGTCTCGTCTC", ["BsmBI"], True)
    assert [h["start"] for h in r["sites"]] == [1, 6]
    assert sum(r["fragment_lengths"]) == 11


def test_circular_uncut_remains_circular_and_multi_enzyme_conservation():
    assert restriction_map("AAAAAA", ["EcoRI"], True)["product_topology"] == "circular"
    for circular in (False, True):
        r = restriction_map("GAATTCAAAAGGATCCAAAAGAATTC", ["EcoRI", "BamHI", "EcoRI"], circular)
        assert r["fragment_total"] == r["length"]
        assert len(r["enzymes"]) == 2


def test_ambiguity_and_unknown_enzyme_rejected():
    with pytest.raises(SequenceUtilitiesError):
        restriction_map("GAANTC", ["EcoRI"])
    with pytest.raises(SequenceUtilitiesError):
        restriction_map("GAATTC", ["Unknown"])


def test_forward_and_reverse_type_iis_cuts_match_biopython():
    from Bio import Restriction
    from Bio.Seq import Seq
    for enzyme, sequence in [(Restriction.BsaI, "AAAAAAGGTCTCAAAAAAGAGACCAAAAAA"), (Restriction.BsmBI, "AAAAAACGTCTCAAAAAAGAGACGAAAAAA")]:
        for circular in (False, True):
            mapped = restriction_map(sequence, [str(enzyme)], circular)
            reference = sorted({(cut - 1) % len(sequence) if circular else cut - 1 for cut in enzyme.search(Seq(sequence), linear=not circular)})
            assert mapped["cut_boundaries"] == reference


@pytest.mark.asyncio
async def test_endpoint_preserves_scientific_evidence_and_rejects_ambiguity():
    from fastapi import HTTPException
    from app.routers.seq_tools import RestrictionMapRequest, restriction_map_endpoint
    result = await restriction_map_endpoint(RestrictionMapRequest(sequence="GAATTCAAAA", enzymes=["EcoRI"], circular=True))
    assert result["results"]["fragment_total"] == 10
    assert result["validation"]["experimental_digestion_validated"] is False
    with pytest.raises(HTTPException) as exc:
        await restriction_map_endpoint(RestrictionMapRequest(sequence="NGAATTC"))
    assert exc.value.status_code == 400

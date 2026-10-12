import pytest

from app.tools.alignment_insights import alignment_insights


def test_conserved_column_has_zero_entropy_and_full_conservation():
    result = alignment_insights(["ACGT", "ACGT", "ACGT"])
    first = result["columns"][0]
    assert first["conservation"] == 1.0
    assert first["entropy_bits"] == 0.0
    assert first["logo"][0]["symbol"] == "A"


def test_mixed_column_has_nonzero_entropy():
    result = alignment_insights(["ACGT", "ATGT", "AGGT", "ACGT"])
    column = result["columns"][1]
    assert 0.0 < column["entropy_bits"]
    assert column["conservation"] == 0.5
    assert sum(x["frequency"] for x in column["logo"]) == pytest.approx(1.0)


def test_variant_position_maps_across_reference_gap():
    result = alignment_insights(
        ["AC-GT", "ACAGT", "AC-GT"],
        variants=[{"position": 3, "alt": "A"}],
    )
    mapped = result["variant_mapping"][0]
    assert mapped["status"] == "mapped"
    assert mapped["alignment_position"] == 4
    assert mapped["reference_symbol"] == "G"


def test_alignment_lengths_must_match():
    with pytest.raises(ValueError):
        alignment_insights(["ACGT", "ACG"])

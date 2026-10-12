from app.tools.primer_advanced import multiplex_compatibility, snp_overlap


def test_snp_overlap_marks_three_prime_critical_variant():
    result = snp_overlap(
        "ACGTACGTAC",
        "TGCATGCATG",
        left_pos=100,
        right_pos=160,
        variants=[{"position": 108, "id": "v1"}, {"position": 140, "id": "v2"}],
    )
    assert result["overlap_count"] == 1
    hit = result["overlaps"][0]
    assert hit["primer"] == "left"
    assert hit["three_prime_critical"] is True


def test_snp_overlap_maps_right_primer_interval():
    result = snp_overlap(
        "ACGTACGTAC",
        "TGCATGCATG",
        left_pos=10,
        right_pos=50,
        variants=[{"position": 45}],
    )
    assert result["overlap_count"] == 1
    assert result["overlaps"][0]["primer"] == "right"


def test_multiplex_reports_tm_spread_and_heuristic_boundary():
    result = multiplex_compatibility([
        {"id": "a", "left_seq": "ACGTTGCAACGTTGCAACGT", "right_seq": "TGCACGTTTGCACGTTTGCA", "left_tm": 60.0, "right_tm": 60.5},
        {"id": "b", "left_seq": "GATCGATAGATCGATAGATC", "right_seq": "CTAGCTACCTAGCTACCTAG", "left_tm": 61.0, "right_tm": 61.5},
    ])
    assert result["pair_count"] == 2
    assert result["tm_spread_c"] == 1.5
    assert result["evidence_class"] == "Heuristic"
    assert "empirical multiplex PCR" in result["limitation"]

from app.benchmarking.ai_factuality import score_explanation


def test_supported_numeric_and_identifier_claims_pass():
    result = {"accession": "P68871", "identity_pct": 100.0, "hit_count": 5}
    score = score_explanation("P68871 was recovered at 100% identity among 5 hits.", result)
    assert score.passed
    assert score.numeric_claim_fidelity == 1.0
    assert score.identifier_claim_fidelity == 1.0
    assert score.unsupported_structured_claim_rate == 0.0


def test_unsupported_number_is_retained_and_fails():
    result = {"rmsd_angstrom": 1.8, "threshold_angstrom": 2.0}
    score = score_explanation("The RMSD was 1.8 A and the affinity was -9.7 kcal/mol.", result)
    assert not score.passed
    assert "-9.7" in score.unsupported_numeric_claims
    assert score.numeric_claim_fidelity < 1.0


def test_unsupported_identifier_is_retained_and_fails():
    result = {"accession": "P68871"}
    score = score_explanation("The result corresponds to P69905.", result)
    assert not score.passed
    assert "P69905" in score.unsupported_identifiers


def test_no_structured_claims_is_not_penalised():
    score = score_explanation("The deterministic result should be reviewed with its provenance.", {"status": "WARN"})
    assert score.passed
    assert score.numeric_claim_fidelity == 1.0
    assert score.identifier_claim_fidelity == 1.0

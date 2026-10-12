import copy

import pytest

from app.rnaseq.count_recovery import assemble_counts, review_compatibility
from app.rnaseq.geo_counts import GeoCountsError, parse_matrix
from app.rnaseq.input_contract import CountOrigin
from app.rnaseq.expression import RnaSeqExpressionError


def origin(**changes):
    return CountOrigin(**{"classification": "deposited_raw_counts", "source_uri": "GEO:GSE123 source methods",
        "normalization": "none", "evidence": "Original featureCounts methods section",
        "method": "featureCounts 2.0.6", "annotation": "GENCODE v44", "reviewed": True, **changes})


@pytest.mark.parametrize("classification", ["unknown_origin", "normalized_expression", "verified_count_estimates"])
def test_integer_format_does_not_establish_eligible_origin(classification):
    with pytest.raises(RnaSeqExpressionError, match="classification"):
        origin(classification=classification).check()


def test_raw_label_requires_supporting_source():
    with pytest.raises(RnaSeqExpressionError, match="source"):
        origin(source_uri="").check()
    with pytest.raises(RnaSeqExpressionError, match="source"):
        origin(source_uri="unknown").check()
    record = origin().check()
    assert record["classification"] == "deposited_raw_counts"
    assert record["count_origin_status"] == "ANALYST_ATTESTED"
    assert record["independently_verified"] is False


def test_estimates_require_original_quantifier_evidence():
    with pytest.raises(RnaSeqExpressionError, match="verification evidence"):
        origin(kind="salmon", classification="verified_count_estimates").check()
    assert origin(kind="salmon", classification="verified_count_estimates",
                  verification_evidence="Original quant.sf, transcriptome release and mapping checksums").check()["kind"] == "salmon"


@pytest.mark.parametrize("n_samples", [1, 2, 3])
def test_small_matrices_can_be_inspected_without_design_eligibility(n_samples):
    matrix = "gene," + ",".join(f"s{i}" for i in range(n_samples)) + "\ng1," + ",".join("1" for _ in range(n_samples)) + "\n"
    parsed = parse_matrix(matrix.encode(), "counts.csv", [])
    assert len(parsed["columns"]) == n_samples
    assert parsed["input_provenance"]["classification"] == "unknown_origin"
    assert parsed["genes"] == 1


def test_zero_library_is_inspectable_but_warned():
    parsed = parse_matrix(b"gene,s1\ng1,0\n", "counts.csv", [])
    assert parsed["inspection_warnings"] == ["All-zero sample library: s1"]


def review():
    return {"reviewed": True, "files": {name: {"sample": sample, "reference": "GRCh38",
        "annotation": "GENCODE v44", "counting_method": "featureCounts 2.0.6",
        "strandedness": "reverse", "feature_definition": "gene-level exon union; unique paired fragments"}
        for name, sample in {"a.tsv": "s1", "b.tsv": "s2"}.items()}}


@pytest.mark.parametrize("field", ["reference", "annotation", "counting_method", "strandedness", "feature_definition"])
def test_matching_gene_ids_do_not_override_incompatible_methods(field):
    records = review()
    records["files"]["b.tsv"][field] = "forward" if field == "strandedness" else "different method identity"
    with pytest.raises(GeoCountsError, match="incompatible " + field):
        review_compatibility({"a.tsv": "s1", "b.tsv": "s2"}, records)


@pytest.mark.parametrize("case", ["unreviewed", "missing_file", "wrong_sample", "unknown_annotation"])
def test_assembly_fails_without_complete_source_review(case):
    records = copy.deepcopy(review())
    if case == "unreviewed":
        records["reviewed"] = False
    elif case == "missing_file":
        records["files"].pop("b.tsv")
    elif case == "wrong_sample":
        records["files"]["b.tsv"]["sample"] = "s1"
    else:
        records["files"]["b.tsv"]["annotation"] = "unknown"
    with pytest.raises(GeoCountsError):
        review_compatibility({"a.tsv": "s1", "b.tsv": "s2"}, records)


def test_compatible_assembly_preserves_review_and_missing_value_policy():
    files = {"a.tsv": b"gene\tcount\ng1\t1\ng2\t2\n", "b.tsv": b"gene\tcount\ng2\t4\ng1\t3\n"}
    body, audit = assemble_counts(files, {"a.tsv": "s1", "b.tsv": "s2"}, review())
    assert body == b"gene\ts1\ts2\ng1\t1\t3\ng2\t2\t4\n"
    assert audit["compatibility"]["common"]["strandedness"] == "reverse"
    assert audit["compatibility"]["independently_verified"] is False
    files["b.tsv"] = b"gene\tcount\ng1\t3\ng3\t4\n"
    with pytest.raises(GeoCountsError, match="Gene sets differ"):
        assemble_counts(files, {"a.tsv": "s1", "b.tsv": "s2"}, review())

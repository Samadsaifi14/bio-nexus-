"""Regression tests for scientific reference-comparison contracts.

These tests deliberately use small deterministic fixtures. They verify metric
semantics and the no-fabrication boundary; they are not biological validation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.benchmarking.reference_comparison import comparator_registry, compare_results


def test_registry_declares_reference_and_no_superiority_policy():
    registry = comparator_registry()
    assert registry["schema"] == "bionexus-reference-comparison/v1"
    for name in ("blast", "msa", "rnaseq", "docking", "md", "ngs"):
        assert name in registry["comparators"]
        assert registry["comparators"][name]["reference"]
        assert registry["comparators"][name]["reference_url"].startswith("https://")


def test_blast_exact_ranked_fixture_is_exact_concordance():
    hits = [
        {"accession": "P68871.2", "identity_pct": 100.0, "query_coverage_pct": 100.0, "bit_score": 321.0, "evalue": 0.0},
        {"accession": "P02042", "identity_pct": 88.0, "query_coverage_pct": 96.0, "bit_score": 250.0, "evalue": 1e-75},
        {"accession": "P02100", "identity_pct": 75.0, "query_coverage_pct": 90.0, "bit_score": 190.0, "evalue": 1e-40},
    ]
    result = compare_results("blast", {"hits": hits}, {"hits": hits}, top_n=3)
    assert result["concordance"]["status"] == "EXACT_OR_NEAR_EXACT_CONCORDANCE"
    metrics = {m["id"]: m["value"] for m in result["metrics"]}
    assert metrics["top_hit_agreement"] is True
    assert metrics["top_n_jaccard"] == 1.0
    assert metrics["identity_correlation"] == 1.0
    assert result["claim_boundary"]["superiority_claim_allowed"] is False


def test_blast_missing_reference_measurements_are_not_zero_filled():
    bio = {"hits": [{"accession": "P1", "identity_pct": 99.0, "bit_score": 100.0, "evalue": 1e-10}]}
    ref = {"hits": [{"accession": "P1", "identity_pct": 99.0, "evalue": 1e-10}]}
    result = compare_results("blast", bio, ref)
    metrics = {m["id"]: m["value"] for m in result["metrics"]}
    assert metrics["bit_score_correlation"] is None
    assert metrics["coverage_correlation"] is None
    assert result["claim_boundary"]["missing_measurements_are_not_zero"] is True


def test_msa_identical_normalized_alignment_matches_digest_and_conservation():
    aln = ">A\nACGT-\n>B\nACGTA\n>C\nACCTA\n"
    result = compare_results("msa", {"aln_fasta": aln}, {"aln_fasta": aln})
    metrics = {m["id"]: m["value"] for m in result["metrics"]}
    assert metrics["alignment_sha256_match"] is True
    assert metrics["sequence_set_jaccard"] == 1.0
    assert metrics["pairwise_identity_correlation"] == 1.0
    assert metrics["conservation_correlation"] == 1.0


def test_rnaseq_reference_scatter_uses_real_log2fc_and_padj():
    rows = [
        {"gene": "G1", "log2FoldChange": 2.0, "padj": 0.001},
        {"gene": "G2", "log2FoldChange": -1.5, "padj": 0.02},
        {"gene": "G3", "log2FoldChange": 0.1, "padj": 0.8},
    ]
    result = compare_results("rnaseq", {"results": rows}, {"results": rows})
    metrics = {m["id"]: m["value"] for m in result["metrics"]}
    assert metrics["log2fc_correlation"] == 1.0
    assert metrics["padj_correlation"] == 1.0
    assert metrics["significant_gene_jaccard"] == 1.0
    assert metrics["direction_concordance"] == 1.0
    series = result["series"][0]["points"]
    assert {p["gene"] for p in series} == {"G1", "G2", "G3"}


def test_docking_concordance_does_not_invent_redocking_rmsd():
    poses = [
        {"affinity": -8.2, "rmsd_lb": 0.0, "rmsd_ub": 0.0},
        {"affinity": -7.6, "rmsd_lb": 1.2, "rmsd_ub": 2.1},
        {"affinity": -7.1, "rmsd_lb": 2.0, "rmsd_ub": 3.4},
    ]
    result = compare_results("docking", {"poses": poses}, {"poses": poses})
    metrics = {m["id"]: m["value"] for m in result["metrics"]}
    assert metrics["best_affinity_delta"] == 0.0
    assert metrics["pose_affinity_correlation"] == 1.0
    assert metrics["redocking_rmsd"] is None


def test_unknown_analysis_type_fails_closed():
    try:
        compare_results("invented-tool", {}, {})
    except ValueError as exc:
        assert "Unsupported analysis_type" in str(exc)
    else:
        raise AssertionError("unsupported analysis type must fail closed")

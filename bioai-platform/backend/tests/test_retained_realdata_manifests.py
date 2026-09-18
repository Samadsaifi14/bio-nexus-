"""Integrity checks for compact retained real-data benchmark manifests."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "benchmark" / "real_data" / "GSE67196" / "retained_run_manifest.json"


def _load() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_gse67196_retained_manifest_is_internally_consistent():
    m = _load()
    s = m["result_summary"]
    assert m["schema_version"] == 1
    assert m["benchmark_id"] == "GSE67196-SALS-DESEQ2-FULL-REAL-DATA"
    assert s["genes_input"] == s["genes_kept"] + s["genes_removed"]
    assert s["samples"] == sum(s["replicate_counts"].values())
    assert s["significant"] == s["up"] + s["down"]
    assert s["design_full_rank"] is True
    assert s["design_rank"] == s["design_columns"]
    assert s["experimental_unit_status"] == "NOT_DECLARED"


def test_gse67196_retained_manifest_locks_sources_and_artifact_digest():
    m = _load()
    sources = m["dataset"]["source_files"]
    assert sources["GSE67196_Petrucelli2015_ALS_genes.rawcount.txt.gz"] == "585af2a3cf28bc43dd6785199922e5e928841029353837a0fdfd9516cad0a61a"
    assert sources["GSE67196_family.soft.gz"] == "d2343cffcae301b1064ca1cbc4226b4c0ac02acde6eed4d86840c8d5e4cf0f38"
    digest = m["retained_execution"]["artifact_zip_sha256"]
    assert len(digest) == 64
    int(digest, 16)
    assert m["retained_execution"]["archival_status"] == "WORKFLOW_ARTIFACT_NOT_PERSISTENT_ARCHIVE"


def test_gse67196_retained_manifest_covers_tables_and_plot_sources():
    m = _load()
    outputs = m["core_output_sha256"]
    required = {
        "analysis_summary.json",
        "design_audit.json",
        "deseq2_all_results.tsv",
        "deseq2_significant.tsv",
        "normalized_counts.tsv",
        "size_factors.tsv",
        "pca_coordinates.tsv",
        "sample_distance_matrix.tsv",
        "heatmap_gene_selection.tsv",
        "heatmap_matrix_zscore.tsv",
        "pca.png",
        "pca.svg",
        "volcano.png",
        "volcano.svg",
        "ma_plot.png",
        "ma_plot.svg",
        "sample_distance_heatmap.png",
        "sample_distance_heatmap.svg",
        "expression_heatmap.png",
        "expression_heatmap.svg",
    }
    assert required <= set(outputs)
    for digest in outputs.values():
        assert len(digest) == 64
        int(digest, 16)


def test_gse67196_claim_boundary_blocks_biological_overreach():
    m = _load()
    boundary = m["claim_boundary"].lower()
    for phrase in ("experimental unit", "does not establish", "biomarker", "clinical", "superiority"):
        assert phrase in boundary

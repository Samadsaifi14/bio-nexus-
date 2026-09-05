import pytest
from Bio import Phylo
import io

from app.routers.phylo_insights import consensus_tree, metadata_overlay, root_tree

TREE = "((A:0.1,B:0.1):0.2,(C:0.1,D:0.1):0.2);"


def test_midpoint_root_preserves_terminals():
    result = root_tree(TREE, "midpoint")
    parsed = Phylo.read(io.StringIO(result["newick"]), "newick")
    assert sorted(t.name for t in parsed.get_terminals()) == ["A", "B", "C", "D"]
    assert result["rooting"] == "midpoint"


def test_outgroup_requires_existing_terminal():
    result = root_tree(TREE, "outgroup", "D")
    assert result["rooting"] == "outgroup:D"
    with pytest.raises(ValueError):
        root_tree(TREE, "outgroup", "Z")


def test_majority_consensus_requires_same_taxa():
    result = consensus_tree([
        "((A,B),(C,D));",
        "((A,B),(C,D));",
        "((A,C),(B,D));",
    ], cutoff=0.5)
    assert result["tree_count"] == 3
    assert result["terminal_count"] == 4
    assert "bootstrap/posterior" in result["scientific_boundary"]
    with pytest.raises(ValueError):
        consensus_tree(["((A,B),C);", "((A,B),D);"])


def test_metadata_overlay_reports_missing_and_unknown_labels():
    result = metadata_overlay(TREE, {"A": {"species": "human"}, "X": {"species": "unknown"}})
    coverage = result["metadata_coverage"]
    assert coverage["annotated"] == 1
    assert "B" in coverage["missing"]
    assert coverage["metadata_without_terminal"] == ["X"]

"""Unit tests for the phylo engine — scientific object contract.

No network, no DB.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines import ENGINES, get_engine
from app.engines.phylo_engine import _newick_leaves

NEWICK = "(query:0.142,(P01308:0.05,P01316:0.05):0.092);"


def test_phylo_engine_registered():
    assert "phylo" in ENGINES
    assert get_engine("phylo") is ENGINES["phylo"]


def test_newick_leaves_extracts_labels():
    assert _newick_leaves(NEWICK) == ["query", "P01308", "P01316"]
    assert _newick_leaves("") == []
    assert _newick_leaves("(constsnip:1);") == ["constsnip"]


def test_parse_maps_canonical_result():
    eng = get_engine("phylo")
    res = eng.parse({"phylotree_newick": NEWICK})
    assert res.engine == "phylo"
    assert res.statistics["leaf_count"] == 3
    assert res.statistics["balanced"] is True
    assert res.evidence["leaves"] == ["query", "P01308", "P01316"]


def test_parse_rejects_non_canonical():
    eng = get_engine("phylo")
    for bad in ({"nonsense": 1}, {"tree": "x"}):
        try:
            eng.parse(bad)
            assert False, f"expected ValueError for {bad}"
        except ValueError:
            pass


def test_validate_accepts_good_tree():
    eng = get_engine("phylo")
    assert eng.validate(eng.parse({"phylotree_newick": NEWICK})).valid


def test_validate_flags_missing_tree():
    eng = get_engine("phylo")
    report = eng.validate(eng.parse({"phylotree_newick": None}))
    assert not report.valid
    assert any(c["name"] == "tree_present" and not c["passed"] for c in report.checks)


def test_validate_flags_malformed_newick():
    eng = get_engine("phylo")
    bad = {"phylotree_newick": "(query:0.1,P01308:0.05,P01316:0.05"}  # unbalanced
    report = eng.validate(eng.parse(bad))
    assert not report.valid
    assert any(c["name"] == "newick_well_formed" and not c["passed"] for c in report.checks)

    blank = {"phylotree_newick": ":-("}
    report2 = eng.validate(eng.parse(blank))
    assert not report2.valid
    assert any(c["name"] == "has_leaf_labels" and not c["passed"] for c in report2.checks)


def test_export_newick_and_csv():
    eng = get_engine("phylo")
    res = eng.parse({"phylotree_newick": NEWICK})
    assert eng.export(res, "newick") == NEWICK
    csv_out = eng.export(res, "csv")
    assert csv_out.splitlines()[0] == "tree,leaves,newick"
    assert "query|P01308|P01316" in csv_out


def test_export_rejects_unknown_format():
    eng = get_engine("phylo")
    try:
        eng.export(eng.parse({"phylotree_newick": NEWICK}), "png")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_figure_svg_cladogram():
    eng = get_engine("phylo")
    svg = eng.figure(eng.parse({"phylotree_newick": NEWICK}))
    assert svg.startswith("<?xml")
    assert "3 leaves" in svg
    assert "P01316" in svg


def test_figure_empty_tree():
    eng = get_engine("phylo")
    svg = eng.figure(eng.parse({"phylotree_newick": None}))
    assert "No phylogenetic tree available" in svg


def test_describe_has_scientific_contract():
    eng = get_engine("phylo")
    d = eng.describe()
    assert "PHYLO_GLOBIN_NEWICK_WELLFORMED" in d["benchmarks"]
    assert "newick" in d["export_formats"]
    assert "Felsenstein" in d["citations"][1]
"""Unit tests for the alphafold and pathway engines — scientific object contract.

No network, no DB.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines import ENGINES, get_engine


# --- AlphaFold engine -----------------------------------------------------

AF_AVAILABLE = {
    "uniprot_accession": "P04637",
    "structure_available": True,
    "pdb_url": "https://alphafold.ebi.ac.uk/files/AF-P04637-F1-model_v4.pdb",
    "cif_url": "https://alphafold.ebi.ac.uk/files/AF-P04637-F1-model_v4.cif",
    "confidence": 87.4,
    "model_created_date": "2022-01-01",
    "latest_version": 4,
}

AF_UNAVAILABLE = {
    "uniprot_accession": "P04637",
    "structure_available": False,
    "message": "No AlphaFold prediction available for this protein",
    "pdb_url": None,
    "cif_url": None,
    "confidence": None,
}


def test_alphafold_engine_registered():
    assert "alphafold" in ENGINES
    assert get_engine("alphafold") is ENGINES["alphafold"]


def test_alphafold_parse_maps_available():
    eng = get_engine("alphafold")
    res = eng.parse(AF_AVAILABLE)
    assert res.engine == "alphafold"
    assert res.statistics["structure_available"] is True
    assert res.statistics["confidence"] == 87.4
    assert res.statistics["latest_version"] == 4
    assert "AF-P04637" in res.evidence["pdb_url"]


def test_alphafold_parse_accepts_unavailable():
    eng = get_engine("alphafold")
    res = eng.parse(AF_UNAVAILABLE)
    assert res.statistics["structure_available"] is False
    assert res.evidence["message"] == "No AlphaFold prediction available for this protein"


def test_alphafold_parse_rejects_non_canonical():
    eng = get_engine("alphafold")
    try:
        eng.parse({"looks": "like", "a": "structure"})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_alphafold_validate_available_ok():
    eng = get_engine("alphafold")
    assert eng.validate(eng.parse(AF_AVAILABLE)).valid


def test_alphafold_validate_unavailable_ok():
    eng = get_engine("alphafold")
    assert eng.validate(eng.parse(AF_UNAVAILABLE)).valid


def test_alphafold_validate_flags_bad_confidence_and_url():
    eng = get_engine("alphafold")
    bad_conf = dict(AF_AVAILABLE, confidence=150.0)
    report = eng.validate(eng.parse(bad_conf))
    assert not report.valid
    assert any(c["name"] == "confidence_bounded_0_100" and not c["passed"] for c in report.checks)

    bad_url = dict(AF_AVAILABLE, pdb_url="http://not-af.example/x.pdb")
    report2 = eng.validate(eng.parse(bad_url))
    assert not report2.valid
    assert any(c["name"] == "pdb_url_consistent" and not c["passed"] for c in report2.checks)


def test_alphafold_export_csv():
    eng = get_engine("alphafold")
    out = eng.export(eng.parse(AF_AVAILABLE), "csv")
    assert out.splitlines()[0] == "uniprot_accession,structure_available,confidence,source,pdb_url"
    assert "P04637,True,87.4" in out


def test_alphafold_figure_svg():
    eng = get_engine("alphafold")
    svg = eng.figure(eng.parse(AF_AVAILABLE))
    assert svg.startswith("<?xml")
    assert "Structure available" in svg
    assert "pLDDT 87.4" in svg


def test_alphafold_describe_contract():
    eng = get_engine("alphafold")
    d = eng.describe()
    assert "Jumper" in d["citations"][0]
    assert d["databases"] == ["AlphaFold DB"]


# --- Pathway engine ---------------------------------------------------------

PATHWAYS = {
    "token": "tok123",
    "method": "Reactome over-representation analysis",
    "pathways": [
        {"stId": "R-HSA-109582", "name": "Hemostasis", "species": "Homo sapiens",
         "entitiesFound": 4, "entitiesTotal": 8, "geneRatio": 0.5,
         "reactomePValue": 1e-4, "reactomeFDR": 1e-3,
         "significance_source": "Reactome Analysis Service", "correction_method": "Reactome-provided FDR"},
        {"stId": "R-HSA-73943", "name": "Dna repair", "species": "Homo sapiens",
         "entitiesFound": 2, "entitiesTotal": 5, "geneRatio": 0.4,
         "reactomePValue": 0.05, "reactomeFDR": 0.2,
         "significance_source": "Reactome Analysis Service", "correction_method": "Reactome-provided FDR"},
    ],
    "significance_note": "P-value and FDR are reported exactly as supplied by the Reactome Analysis Service.",
    "from_cache": False,
}


def test_pathway_engine_registered():
    assert "pathway" in ENGINES
    assert get_engine("pathway") is ENGINES["pathway"]


def test_pathway_parse_maps_canonical():
    eng = get_engine("pathway")
    res = eng.parse(PATHWAYS)
    assert res.engine == "pathway"
    assert res.statistics["pathway_count"] == 2
    assert res.evidence["top_pathways"] == ["Hemostasis", "Dna repair"]
    assert res.statistics["input_token"] == "tok123"


def test_pathway_parse_accepts_empty():
    eng = get_engine("pathway")
    res = eng.parse({"pathways": []})
    assert res.statistics["pathway_count"] == 0


def test_pathway_parse_rejects_non_canonical():
    eng = get_engine("pathway")
    try:
        eng.parse({"token": "x"})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_pathway_validate_ok():
    eng = get_engine("pathway")
    assert eng.validate(eng.parse(PATHWAYS)).valid


def test_pathway_validate_flags_bad_bounds_ratio_sort():
    eng = get_engine("pathway")
    bad = dict(PATHWAYS)
    bad["pathways"] = [
        dict(PATHWAYS["pathways"][0], entitiesFound=12, entitiesTotal=8, geneRatio=1.5, reactomeFDR=2.0),
        dict(PATHWAYS["pathways"][1], entitiesFound=5, entitiesTotal=5, geneRatio=0.2),
    ]
    report = eng.validate(eng.parse(bad))
    assert not report.valid
    names = {c["name"] for c in report.checks if not c["passed"]}
    assert "statistical_bounds" in names
    assert "gene_ratio_consistent" in names
    assert "sorted_by_fdr_asc" in names


def test_pathway_export_csv_rows():
    eng = get_engine("pathway")
    out = eng.export(eng.parse(PATHWAYS), "csv")
    lines = out.strip().splitlines()
    assert lines[0] == "stId,name,species,entitiesFound,entitiesTotal,geneRatio,pValue,FDR"
    assert len(lines) == 3


def test_pathway_figure_svg():
    eng = get_engine("pathway")
    svg = eng.figure(eng.parse(PATHWAYS))
    assert svg.startswith("<?xml")
    assert "Hemostasis" in svg
    assert "gene ratio" in svg


def test_pathway_describe_contract():
    eng = get_engine("pathway")
    d = eng.describe()
    assert "reactome" in d["citations"][0].lower()
    assert "Reactome" in d["databases"][0]
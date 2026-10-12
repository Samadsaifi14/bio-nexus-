"""Unit tests for the domains engine — scientific object contract.

No network, no DB.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines import ENGINES, get_engine

CANONICAL = {
    "uniprot_accession": "P04637",
    "sequence_length": 393,
    "domains": [
        {"accession": "PF00870", "name": "P53", "source_db": "PFAM", "start": 92, "end": 293, "score": 2.9e-22},
        {"accession": "SM01372", "name": "p53", "source_db": "SMART", "start": 97, "end": 289, "score": 9.2e-14},
    ],
}


def test_domains_engine_registered():
    assert "domains" in ENGINES
    assert get_engine("domains") is ENGINES["domains"]


def test_parse_maps_canonical_result():
    eng = get_engine("domains")
    res = eng.parse(CANONICAL)
    assert res.engine == "domains"
    assert res.statistics["domain_count"] == 2
    assert res.statistics["sequence_length"] == 393
    assert res.statistics["residues_covered"] == 395  # PFAM 202 + SMART 193
    assert "PFAM" in res.statistics["source_databases"]
    assert res.evidence["uniprot_accession"] == "P04637"


def test_parse_rejects_non_canonical():
    eng = get_engine("domains")
    for bad in ({"nonsense": 1}, {"domains": []}):  # missing uniprot_accession
        try:
            eng.parse(bad)
            assert False, f"expected ValueError for {bad}"
        except ValueError:
            pass


def test_validate_accepts_good_result():
    eng = get_engine("domains")
    assert eng.validate(eng.parse(CANONICAL)).valid


def test_validate_flags_unsorted_and_bad_geometry():
    eng = get_engine("domains")
    unsorted = dict(CANONICAL, domains=list(reversed(CANONICAL["domains"])))
    report = eng.validate(eng.parse(unsorted))
    assert not report.valid
    assert any(c["name"] == "domains_sorted" and not c["passed"] for c in report.checks)

    bad_span = dict(CANONICAL, domains=[
        {"accession": "X", "name": "bad", "source_db": "PFAM", "start": 300, "end": 200, "score": None},
    ])
    report2 = eng.validate(eng.parse(bad_span))
    assert not report2.valid
    assert any(c["name"] == "domain_geometry" and not c["passed"] for c in report2.checks)


def test_validate_flags_failed_step_loudly():
    eng = get_engine("domains")
    failed = {"uniprot_accession": "P04637", "sequence_length": 0, "domains": [], "error": "InterPro timeout"}
    report = eng.validate(eng.parse(failed))
    assert not report.valid
    assert any(c["name"] == "error_free" and not c["passed"] for c in report.checks)


def test_export_csv_domain_rows():
    eng = get_engine("domains")
    out = eng.export(eng.parse(CANONICAL), "csv")
    lines = out.strip().splitlines()
    assert lines[0] == "uniprot_accession,source_db,accession,name,start,end,score"
    assert len(lines) == 3  # header + 2 domains
    assert "P04637,PFAM,PF00870,P53,92,293" in lines[1]


def test_figure_svg_architecture_map():
    eng = get_engine("domains")
    svg = eng.figure(eng.parse(CANONICAL))
    assert svg.startswith("<?xml")
    assert "Domain architecture" in svg
    assert "P04637" in svg
    assert "Sequ" in svg or "Sequence length" in svg


def test_figure_empty_domains():
    eng = get_engine("domains")
    empty = {"uniprot_accession": "P99999", "sequence_length": 0, "domains": []}
    svg = eng.figure(eng.parse(empty))
    assert svg.startswith("<?xml")


def test_describe_has_scientific_contract():
    eng = get_engine("domains")
    d = eng.describe()
    assert "InterPro in 2022" in d["citations"][0]
    assert "Pfam" in d["databases"][0]
    assert "DOMAINS_ANNOTATED" in d["benchmarks"]
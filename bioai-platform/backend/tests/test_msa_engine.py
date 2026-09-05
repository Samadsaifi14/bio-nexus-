"""Unit tests for the MSA engine — scientific object contract.

No network, no DB.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines import ENGINES, get_engine
from app.engines.msa_engine import parse_alignment_fasta

ALN = """>query
MSVSEFLKKA
>P01308
MSVSEFLKKA
>P01316
MSVSEFLKKA
"""


def _canonical(**over):
    payload = {
        "aln_fasta": ALN,
        "phylotree": "(query:0.1,(P01308:0.05,P01316:0.05):0.1);",
        "sequence_count": 3,
        "alignment_mode": "global",
        "method": "clustalo",
        "_fallback": False,
    }
    payload.update(over)
    return payload


def test_msa_engine_registered():
    assert "msa" in ENGINES
    assert get_engine("msa") is ENGINES["msa"]


def test_parse_maps_canonical_result():
    eng = get_engine("msa")
    res = eng.parse(_canonical())
    assert res.engine == "msa"
    assert res.tool == "clustalo"
    assert res.statistics["sequence_count"] == 3
    assert res.statistics["aligned_columns"] == 10
    assert res.statistics["has_phylotree"] is True
    assert res.evidence["error"] is None


def test_parse_rejects_non_canonical():
    eng = get_engine("msa")
    try:
        eng.parse({"nonsense": True})
        assert False, "expected ValueError"
    except ValueError:
        pass
    try:
        eng.parse({"other": 1})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_validate_accepts_good_result():
    eng = get_engine("msa")
    assert eng.validate(eng.parse(_canonical())).valid


def test_validate_flags_ragged_alignment():
    eng = get_engine("msa")
    ragged = _canonical(aln_fasta=">query\nMSVSEFLKKA\n>P01308\nMSVSEFLK\n")
    report = eng.validate(eng.parse(ragged))
    assert not report.valid
    assert any(c["name"] == "aligned_rows_equal_length" and not c["passed"] for c in report.checks)


def test_validate_flags_failed_step_loudly():
    eng = get_engine("msa")
    failed = _canonical(
        aln_fasta=None,
        phylotree=None,
        sequence_count=0,
        method="clustalo",
        error="Not enough sequences for MSA",
    )
    res = eng.parse(failed)
    assert res.evidence["error"] == "Not enough sequences for MSA"
    report = eng.validate(res)
    assert not report.valid
    assert any(c["name"] == "error_free" and not c["passed"] for c in report.checks)
    assert any(c["name"] == "alignment_fasta_present" and not c["passed"] for c in report.checks)


def test_validate_flags_single_sequence():
    eng = get_engine("msa")
    single = _canonical(aln_fasta=">query\nMSVSEFLKKA\n", sequence_count=1)
    report = eng.validate(eng.parse(single))
    assert not report.valid
    assert any(c["name"] == "sequence_count_at_least_2" and not c["passed"] for c in report.checks)


def test_export_csv_rows():
    eng = get_engine("msa")
    out = eng.export(eng.parse(_canonical()), "csv")
    lines = out.strip().splitlines()
    assert lines[0] == "seq_id,aligned_length,aligned_sequence"
    assert len(lines) == 4  # header + 3 rows
    assert "query,10" in lines[1]


def test_export_fasta_matches_alignment():
    eng = get_engine("msa")
    out = eng.export(eng.parse(_canonical()), "fasta")
    records = parse_alignment_fasta(out)
    assert [sid for sid, _ in records] == ["query", "P01308", "P01316"]


def test_export_rejects_unknown_format():
    eng = get_engine("msa")
    try:
        eng.export(eng.parse(_canonical()), "pdf")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_figure_svg():
    eng = get_engine("msa")
    svg = eng.figure(eng.parse(_canonical()))
    assert svg.startswith("<?xml")
    assert "clustalo" in svg
    assert "3 sequences" in svg


def test_describe_has_scientific_contract():
    eng = get_engine("msa")
    d = eng.describe()
    assert d["name"] == "msa"
    assert "MAFFT" in d["citations"][0] or "Clustal" in d["citations"][1]
    assert "MSA_VALID_ALIGNMENT" in d["benchmarks"]
    assert "fasta" in d["export_formats"]
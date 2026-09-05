"""Reproducibility Ledger (Component 16) unit tests — isolated ledger dir, no DB."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.services.reproducibility as rep


def _clean(monkeypatch, tmp_path):
    monkeypatch.setattr(rep, "LEDGER_DIR", str(tmp_path))
    return str(tmp_path)


def test_chain_records_and_validates(monkeypatch, tmp_path):
    _clean(monkeypatch, tmp_path)
    rep.begin_ledger("job-a")
    rep.record_carbon("job-a", "blast", {"seq": "MKTAYIAKQ"}, {"tool": "blast", "db": "swissprot"}, {"top_hit": "X"})
    rep.record_carbon("job-a", "interpret", {"top_hit": "X"}, {"tool": "interpret"}, {"summary": "ok"})

    ledger = rep.get_ledger("job-a")
    assert len(ledger["carbons"]) == 2
    assert ledger["carbons"][0]["prev_hash"] is None
    assert ledger["carbons"][1]["prev_hash"] == ledger["carbons"][0]["carbon_hash"]

    report = rep.enforce(ledger)
    assert report["valid"], [c for c in report["checks"] if not c["passed"]]


def test_tampered_carbon_breaks_chain(monkeypatch, tmp_path):
    _clean(monkeypatch, tmp_path)
    rep.record_carbon("job-t", "blast", {"seq": "AAAA"}, {"tool": "blast"}, {"hits": 3})
    rep.record_carbon("job-t", "msa", {"seq": "AAAA"}, {"tool": "msa"}, {"aln": "x"})

    path = Path(rep._ledger_path("job-t"))
    ledger = json.loads(path.read_text(encoding="utf-8"))
    ledger["carbons"][1]["carbon_hash"] = "deadbeef"
    path.write_text(json.dumps(ledger), encoding="utf-8")

    report = rep.enforce(rep.get_ledger("job-t"))
    names = {c["name"] for c in report["checks"] if not c["passed"]}
    assert "hash_chain_valid" in names
    assert not report["valid"]


def test_missing_output_fails(monkeypatch, tmp_path):
    _clean(monkeypatch, tmp_path)
    rep.record_carbon("job-o", "blast", {"seq": "AAAA"}, {"tool": "blast"}, None)
    report = rep.enforce(rep.get_ledger("job-o"))
    names = {c["name"] for c in report["checks"] if not c["passed"]}
    assert "outputs_recorded" in names


def test_empty_ledger_never_passes(monkeypatch, tmp_path):
    _clean(monkeypatch, tmp_path)
    rep.begin_ledger("job-e")
    assert not rep.enforce(rep.get_ledger("job-e"))["valid"]


def test_missing_ledger_never_passes(monkeypatch, tmp_path):
    _clean(monkeypatch, tmp_path)
    assert not rep.enforce(None)["valid"]
    assert rep.get_ledger("not-there") is None


def test_reordering_breaks_linear_sequence(monkeypatch, tmp_path):
    _clean(monkeypatch, tmp_path)
    rep.record_carbon("job-s", "blast", {"seq": "AAAA"}, {"tool": "blast"}, {"hits": 3})
    rep.record_carbon("job-s", "msa", {"seq": "AAAA"}, {"tool": "msa"}, {"aln": "x"})

    path = Path(rep._ledger_path("job-s"))
    ledger = json.loads(path.read_text(encoding="utf-8"))
    ledger["carbons"].reverse()
    path.write_text(json.dumps(ledger), encoding="utf-8")

    report = rep.enforce(rep.get_ledger("job-s"))
    names = {c["name"] for c in report["checks"] if not c["passed"]}
    assert {"linear_sequence", "hash_chain_valid"} <= names


def test_persist_roundtrip(monkeypatch, tmp_path):
    _clean(monkeypatch, tmp_path)
    rep.record_carbon("job-p", "blast", {"seq": "AAAA"}, {"tool": "blast"}, {"hits": 1})
    assert rep.get_ledger("job-p")["carbons"][0]["step"] == "blast"
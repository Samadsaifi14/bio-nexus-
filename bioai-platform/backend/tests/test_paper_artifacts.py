"""Continuous Paper Generation (Component 18) unit tests — no DB."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.services.paper_artifacts as papers

JOB = "job-paper"
CONTEXT = {
    "sequence": "MVLSPADKTNVKAAWGKVGAHAG",
    "blast": {"top_hit": {"accession": "P68871", "description": "hemoglobin subunit beta"}, "count": 5, "top_hit_identity": 98.5},
    "uniprot": {"accession": "P68871"},
    "steps": {"blast": {"status": "complete"}},
}
SAMPLE_IDS = {"blast": "BLAST", "uniprot": "UNIPROT", "msa": "MSA", "phylo": "PHYLO",
              "domains": "DOMAINS", "pathway_enrichment": "PATHWAY", "alphafold": "ALPHAFOLD"}


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(papers, "ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setattr(papers, "_fetch_job_context", lambda job_id: CONTEXT)
    papers._subscriptions.clear()
    return str(tmp_path)


def test_build_versions_and_hash(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    v1 = papers.build_artifact(JOB, "bmc")
    v2 = papers.build_artifact(JOB, "bmc")
    assert v1["version"] == 1
    assert v2["version"] == 2
    assert v1["content_hash"] == v2["content_hash"]
    assert v1["journal"] == "bmc"


def test_journal_changes_content(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    a = papers.build_artifact(JOB, "bmc")
    b = papers.build_artifact(JOB, "nature")
    assert a["version"] == 1
    assert b["version"] == 2
    assert a["content_hash"] != b["content_hash"]


def test_list_and_latest(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    papers.build_artifact(JOB, "bmc")
    papers.build_artifact(JOB, "nature")
    versions = papers.list_artifacts(JOB)
    assert len(versions) == 2
    latest = papers.latest_artifact(JOB, "bmc")
    assert latest["version"] == 1
    text = papers.read_artifact_text(JOB, latest)
    assert "## Abstract" in text and "BioNexus" in text


def test_unknown_job_raises(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(papers, "_fetch_job_context", lambda job_id: None)
    try:
        papers.build_artifact("ghost", "bmc")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_subscribe_min_interval(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    try:
        papers.subscribe(JOB, "bmc", 5)
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_subscribe_upserts(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    papers.subscribe(JOB, "bmc", 60)
    papers.subscribe(JOB, "bmc", 120)
    papers.subscribe(JOB, "nature", 60)
    assert len(papers.subscriptions()[JOB]) == 2
    entry = next(s for s in papers.subscriptions()[JOB] if s["journal"] == "bmc")
    assert entry["interval_s"] == 120


def test_tick_renders_due_subscription(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    papers.subscribe(JOB, "bmc", 10)
    produced = papers.tick(now=100.0)
    assert len(produced) == 1
    assert produced[0]["version"] == 1
    # Not due yet at +5s (interval 10s).
    produced2 = papers.tick(now=105.0)
    assert produced2 == []
    # Due again at +20s -> version 2.
    produced3 = papers.tick(now=120.0)
    assert len(produced3) == 1
    assert produced3[0]["version"] == 2


def test_tick_no_subs(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert papers.tick() == []
"""Scientific Dashboard (Component 15) unit tests — no DB, isolated custom dir."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.services.dashboard as dashboard
from app.engines import ENGINES


def test_summary_shape(monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard, "_count_supabase", lambda table: 2)
    monkeypatch.setattr(dashboard, "CUSTOM_DIR", str(tmp_path))
    s = dashboard.summary()
    assert s["experiments"] == 2
    assert s["benchmark_runs"] == 2
    assert s["engines"] == len(ENGINES)
    assert s["datasets_catalog"] >= 2
    assert s["datasets_user"] == 0


def test_engine_status_contracts():
    rows = dashboard.engine_status()
    names = [r["name"] for r in rows]
    for required in ("blast", "uniprot", "msa", "phylo", "domains", "alphafold",
                     "pathway", "interpret", "evidence", "ngs", "docking", "md"):
        assert required in names, required
    for r in rows:
        assert r["version"] and r["tool"] and r["export_formats"]


def test_upload_custom_dataset(monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard, "CUSTOM_DIR", str(tmp_path))
    entry = dashboard.upload_custom_dataset("My Cell Lines", "cancer", [{"id": "x", "value": 1}], "demo")
    assert entry["name"] == "my-cell-lines"
    assert entry["type"] == "user"
    assert entry["records_count"] == 1
    stored = json.loads(Path(tmp_path, "my-cell-lines.json").read_text(encoding="utf-8"))
    assert stored["records"] == [{"id": "x", "value": 1}]
    listed = dashboard.list_custom_datasets()
    assert len(listed) == 1
    assert listed[0]["name"] == "my-cell-lines"


def test_upload_rejects_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard, "CUSTOM_DIR", str(tmp_path))
    try:
        dashboard.upload_custom_dataset("  ", "x", [{"a": 1}])
        raised_name = False
    except ValueError:
        raised_name = True
    assert raised_name
    try:
        dashboard.upload_custom_dataset("ok", "x", [])
        raised_records = False
    except ValueError:
        raised_records = True
    assert raised_records


def test_datasets_list_merges_catalog_and_user(monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard, "CUSTOM_DIR", str(tmp_path))
    dashboard.upload_custom_dataset("Uploaded Set", "custom", [{"id": 1}], "")
    out = dashboard.datasets_list()
    assert out["count"] >= 3
    assert any(d["type"] == "user" for d in out["user"])
"""Tenant-scoped dashboard regression tests; no live database."""
import json
from pathlib import Path
import pytest
import app.services.dashboard as dashboard
from app.engines import ENGINES


@pytest.fixture
def custom_root(monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard, "CUSTOM_ROOT", tmp_path)
    return tmp_path


def test_summary_shape(monkeypatch, custom_root):
    calls = []
    def count(user_id):
        calls.append(user_id)
        return 2
    monkeypatch.setattr(dashboard, "_count_owned_jobs", count)
    summary = dashboard.summary("user-a")
    assert summary["experiments"] == 2
    assert summary["engines"] == len(ENGINES)
    assert summary["datasets_catalog"] >= 2
    assert summary["datasets_user"] == 0
    assert summary["scope"] == "authenticated_user"
    assert calls == ["user-a"]


def test_engine_status_contracts():
    rows = dashboard.engine_status()
    names = {row["name"] for row in rows}
    assert {"blast", "uniprot", "msa", "phylo", "domains", "alphafold",
            "pathway", "interpret", "evidence", "ngs", "docking", "md"} <= names
    assert all(row["version"] and row["tool"] and row["export_formats"] for row in rows)


def test_upload_custom_dataset(custom_root):
    entry = dashboard.upload_custom_dataset("user-a", "My Cell Lines", "cancer", [{"id": "x", "value": 1}], "demo")
    assert entry["name"] == "my-cell-lines"
    assert entry["type"] == "user"
    assert entry["records_count"] == 1
    stored = json.loads((custom_root / "user-a" / "my-cell-lines.json").read_text())
    assert stored["records"] == [{"id": "x", "value": 1}]
    assert dashboard.list_custom_datasets("user-a") == [entry]
    assert dashboard.list_custom_datasets("user-b") == []


def test_upload_rejects_empty(custom_root):
    with pytest.raises(ValueError):
        dashboard.upload_custom_dataset("user-a", "  ", "x", [{"a": 1}])
    with pytest.raises(ValueError):
        dashboard.upload_custom_dataset("user-a", "ok", "x", [])


def test_datasets_list_merges_catalog_and_owned_user_data(custom_root):
    dashboard.upload_custom_dataset("user-a", "Uploaded Set", "custom", [{"id": 1}])
    result = dashboard.datasets_list("user-a")
    assert result["count"] == len(result["catalog"]) + 1
    assert result["user"][0]["type"] == "user"
    assert dashboard.datasets_list("user-b")["user"] == []


def test_same_dataset_name_does_not_cross_tenants(custom_root):
    dashboard.upload_custom_dataset("user-a", "Same", "custom", [{"value": 1}])
    dashboard.upload_custom_dataset("user-b", "Same", "custom", [{"value": 2}])
    assert json.loads((custom_root / "user-a" / "same.json").read_text())["records"] == [{"value": 1}]
    assert json.loads((custom_root / "user-b" / "same.json").read_text())["records"] == [{"value": 2}]

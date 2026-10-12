"""Research Dataset Library (Component 14) unit tests — no DB."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.dataset_library import (
    DATASETS_DIR,
    get_dataset,
    list_datasets,
    snapshot_dataset,
)


def test_index_consistent_with_files():
    summaries = list_datasets()
    assert len(summaries) >= 2
    for s in summaries:
        for key in ("name", "category", "type", "date", "version", "records_count", "description"):
            assert key in s and s[key] not in (None, "")
        assert Path(DATASETS_DIR, f"{s['name']}.json").is_file()


def test_get_dataset_returns_records():
    protein = get_dataset("protein_controls")
    assert protein is not None
    assert len(protein["records"]) >= 2
    seq_lengths = [len(r["sequence"]) for r in protein["records"] if r.get("sequence")]
    assert all(l > 50 for l in seq_lengths)


def test_get_dataset_unknown_returns_none():
    assert get_dataset("does_not_exist") is None


def test_snapshot_writes_records_and_manifest(tmp_path):
    snap = snapshot_dataset("clinical_variants", str(tmp_path))
    assert snap["record_count"] == 4
    records = json.loads(Path(snap["records_path"]).read_text(encoding="utf-8"))
    assert len(records) == 4
    manifest = json.loads(Path(snap["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["dataset"] == "clinical_variants"
    assert manifest["source_version"] == 1
    assert manifest["type"] == "curated"
    assert manifest["snapshotted_at"]


def test_snapshot_unknown_raises(tmp_path):
    try:
        snapshot_dataset("nope", str(tmp_path))
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_snapshot_records_immutable_vs_source(tmp_path):
    snap = snapshot_dataset("protein_controls", str(tmp_path))
    records = json.loads(Path(snap["records_path"]).read_text(encoding="utf-8"))
    assert len(records) == 3
    assert records[0]["gene"] == "TP53"
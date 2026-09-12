from pathlib import Path

import pytest
from fastapi import HTTPException

from app.config import settings
from app.routers import ngs_v2


def test_local_fastq_must_be_inside_configured_import_root(tmp_path, monkeypatch):
    root = tmp_path / "imports"
    root.mkdir()
    inside = root / "sample_R1.fastq"
    inside.write_text("@r1\nACGT\n+\nIIII\n", encoding="utf-8")
    outside = tmp_path / "outside_R1.fastq"
    outside.write_text("@r1\nACGT\n+\nIIII\n", encoding="utf-8")
    monkeypatch.setattr(settings, "NGS_INPUT_ROOT", str(root))

    assert ngs_v2._safe_local_fastq(str(inside)) == str(inside.resolve())
    with pytest.raises(HTTPException) as exc:
        ngs_v2._safe_local_fastq(str(outside))
    assert exc.value.status_code == 400
    assert "outside" in str(exc.value.detail).lower()


def test_local_preview_rejects_non_fastq_files(tmp_path, monkeypatch):
    root = tmp_path / "imports"
    root.mkdir()
    text_file = root / "notes.txt"
    text_file.write_text("not sequencing data", encoding="utf-8")
    monkeypatch.setattr(settings, "NGS_INPUT_ROOT", str(root))

    with pytest.raises(HTTPException) as exc:
        ngs_v2._safe_local_fastq(str(text_file))
    assert exc.value.status_code == 400
    assert "fastq" in str(exc.value.detail).lower()


def test_fastq_parse_error_does_not_echo_server_path(tmp_path):
    bad = Path(tmp_path) / "private_sample.fastq.gz"
    bad.write_bytes(b"not-gzip")
    with pytest.raises(HTTPException) as exc:
        ngs_v2._read_fastq(str(bad))
    assert exc.value.status_code == 400
    assert str(bad) not in str(exc.value.detail)


def test_production_capability_catalog_declares_both_pinned_workflows():
    capabilities = ngs_v2.executor_capabilities()
    workflows = {(item["name"], item["revision"]) for item in capabilities["workflows"]}
    assert ("nf-core/sarek", "3.10.0") in workflows
    assert ("nf-core/rnaseq", "3.26.0") in workflows
    assert capabilities["fallback"] is None

"""Execute real BLAST+ on a small declared fixture; never emulate alignments."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from app.tools.blast_local import run_local_blast, _reference
from app.config import settings

pytestmark = pytest.mark.skipif(not shutil.which("makeblastdb") or not shutil.which("blastp"),
                               reason="requires real local NCBI BLAST+ executables")
SEQUENCE = "MVHLTPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRFFESFGDLSTPDAVMGNPKVKAHGKKVLGAFSDGLAHLDNLKGTFATLSELHCDKLHVDPENFRLLGNVLVCVLAHHFGKEFTPPVQAAYQKVVAGVANALAHKYH"


@pytest.fixture
def database(monkeypatch, tmp_path):
    fasta = tmp_path / "source.fasta"
    fasta.write_text(">sp|P68871|HBB_HUMAN fixture beta globin\n" + SEQUENCE + "\n")
    subprocess.run(["makeblastdb", "-in", str(fasta), "-dbtype", "prot",
                    "-parse_seqids", "-out", str(tmp_path / "swissprot")],
                   capture_output=True, check=True, timeout=30)
    manifest = {"database": "swissprot", "release": "test-fixture-1",
        "scope": "one-sequence integration fixture; not a full Swiss-Prot search",
        "fasta_sha256": hashlib.sha256(fasta.read_bytes()).hexdigest(),
        "index_files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in tmp_path.glob("swissprot.*")}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(settings, "BIONEXUS_BLAST_DB_ROOT", str(tmp_path))
    _reference.cache_clear()
    return tmp_path


def test_native_search_recovers_input_accession_and_actual_hsp(database):
    result = run_local_blast(SEQUENCE, "blastp", "swissprot", 5)
    assert result["search_complete"] is True
    assert result["source"] == "local-blast+"
    assert result["database_release"] == "test-fixture-1"
    top = result["hits"][0]
    assert top["accession"] == "P68871"
    assert top["identity_pct"] == 100
    assert top["alignment_length"] == len(SEQUENCE)
    assert top["bit_score"] > 0
    assert top["evalue"] < .01
    assert result["raw_result_xml"].startswith("<?xml")


def test_local_database_never_substitutes_for_nr_or_nt(database):
    assert run_local_blast(SEQUENCE, "blastp", "nr") is None
    assert run_local_blast(SEQUENCE, "blastp", "uniprotkb") is None
    assert run_local_blast("ACGTACGT", "blastn", "nt") is None


def test_missing_reference_is_unavailable_not_completed_zero(monkeypatch):
    monkeypatch.setattr(settings, "BIONEXUS_BLAST_DB_ROOT", "")
    assert run_local_blast(SEQUENCE, "blastp", "swissprot") is None


def test_reference_corruption_fails_closed(database):
    target = next(database.glob("swissprot.psq"))
    target.write_bytes(target.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="checksum"):
        run_local_blast(SEQUENCE, "blastp", "swissprot")


def test_invalid_sequence_is_not_a_completed_no_hit_search(database):
    result = run_local_blast("';bad input'", "blastp", "swissprot")
    assert result["search_complete"] is False
    assert result["error"]


@pytest.mark.asyncio
async def test_production_tool_uses_local_route_without_remote_submission(database, monkeypatch):
    from app.tools.blast import BlastTool
    async def forbidden(*args, **kwargs):
        raise AssertionError("remote submit must not run for the available exact-scope local database")
    monkeypatch.setattr(BlastTool, "_submit", forbidden)
    result = await BlastTool().run_uncached({"sequence": SEQUENCE, "program": "blastp",
                                           "database": "uniprotkb_swissprot", "max_hits": 5})
    assert result["hits"][0]["accession"] == "P68871"


@pytest.mark.asyncio
async def test_pipeline_uses_local_route_and_preserves_reference(database, monkeypatch):
    from app.routers import pipeline_v2
    async def forbidden(*args, **kwargs):
        raise AssertionError("remote provider must not run for local Swiss-Prot")
    monkeypatch.setattr(pipeline_v2, "_run_ebi_blast_fallback", forbidden)
    result = await pipeline_v2._run_blast(SEQUENCE, blast_params={"database": "swissprot", "program": "blastp"})
    assert result["search_complete"] is True
    assert result["database_release"] == "test-fixture-1"
    assert result["hits"][0]["accession"] == "P68871"


def test_native_reference_does_not_claim_an_ncbi_page_was_queried(monkeypatch):
    from app.routers import pipeline_v2
    captured = []
    monkeypatch.setattr("app.services.page_capture.capture_bg",
                        lambda *args, **kwargs: captured.append(args))
    pipeline_v2._capture_run_sources("native-fixture", {
        "blast": {"source": "local-blast+", "top_hit": {"accession": "P68871"}}
    }, "test-user")
    assert captured == []


def test_reference_download_resource_allowlist(monkeypatch, tmp_path):
    import runpy
    module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts" / "provision_local_blast.py"))
    opened = []
    monkeypatch.setattr(module["requests"], "get",
                        lambda *args, **kwargs: opened.append(args))
    for name in ("file:///etc/passwd", "../reldate.txt", "https://example.com", "unexpected"):
        with pytest.raises(ValueError, match="fixed official"):
            module["download"](name, tmp_path / "unused")
    assert opened == []

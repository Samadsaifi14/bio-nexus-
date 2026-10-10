import io
import json
import sqlite3
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.rnaseq import durable
from app.rnaseq.count_recovery import archive_members, assemble_counts
from app.rnaseq.geo_counts import GeoCountsError
from app.rnaseq.input_contract import CountOrigin
from app.rnaseq.expression import ExpressionParameters, RnaSeqExpressionError, validate_artifacts
from app.routers import rnaseq_recovery


def archive(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as handle:
        for name, body in files.items():
            handle.writestr(name, body)
    return stream.getvalue()


def test_safe_archive_and_exact_gene_assembly():
    files = {f"s{i}.tsv": f"gene\tcount\ng1\t{i+1}\ng2\t{i+2}\n".encode() for i in range(4)}
    recovered = archive_members(archive(files), "counts.zip")
    counts, audit = assemble_counts(recovered, {name: f"sample{i}" for i, name in enumerate(files)})
    assert counts.decode().splitlines() == ["gene\tsample0\tsample1\tsample2\tsample3", "g1\t1\t2\t3\t4", "g2\t2\t3\t4\t5"]
    assert audit["missing_value_policy"] == "reject"
    assert set(audit["member_sha256"]) == set(files)
    files["s3.tsv"] = b"gene\tcount\ng1\t4\ng3\t5\n"
    with pytest.raises(GeoCountsError, match="Gene sets differ"):
        assemble_counts(files, {name: name for name in files})


@pytest.mark.parametrize("name", ["../escape.tsv", "/absolute.tsv", "C:\\data.tsv"])
def test_archive_traversal_rejected(name):
    with pytest.raises(GeoCountsError, match="unsafe"):
        archive_members(archive({name: "x"}), "counts.zip")


def test_integer_normalized_values_require_origin_review():
    with pytest.raises(RnaSeqExpressionError, match="origin"):
        CountOrigin(evidence="Original study methods", method="FPKM", annotation="release 1", normalization="normalized", reviewed=True).check()
    record = CountOrigin(evidence="Original study raw count methods", method="featureCounts", annotation="release 1", normalization="none", reviewed=True).check()
    assert record["count_origin_status"] == "ANALYST_ATTESTED"
    assert record["independently_verified"] is False


@pytest.fixture
def queue(tmp_path, monkeypatch):
    monkeypatch.setenv("BIONEXUS_EXPRESSION_ROOT", str(tmp_path / "jobs"))
    monkeypatch.setattr(durable, "readiness", lambda *args: {"available": True, "missing": []})
    counts = tmp_path / "counts.tsv"; counts.write_text("gene\ts1\ts2\ts3\ts4\ng1\t2\t3\t4\t5\n")
    metadata = tmp_path / "meta.tsv"; metadata.write_text("sample\tcondition\texperimental_unit\ns1\ta\tu1\n")
    return durable.enqueue("alice", counts, metadata, ExpressionParameters(), {"normalization": "none"})["job_id"]


def test_claim_atomic_and_owner_scoped(queue):
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(durable.claim, ["a", "b"]))
    assert sum(item is not None for item in claims) == 1
    with pytest.raises(FileNotFoundError):
        durable.status(queue, "bob")


def test_stale_lease_recovers_with_bounded_attempts(queue):
    job = durable.claim("a")
    with durable.db() as connection:
        connection.execute("UPDATE jobs SET heartbeat=? WHERE id=?", (time.time() - 1000, queue))
    recovered = durable.claim("b")
    assert recovered["id"] == queue and recovered["lease"] != job["lease"]
    with durable.db() as connection:
        connection.execute("UPDATE jobs SET heartbeat=?, attempts=3 WHERE id=?", (time.time() - 1000, queue))
    assert durable.claim("c") is None
    assert durable.status(queue, "alice")["state"] == "FAILED"


def test_qc_approval_checksum_and_terminal_inference(queue, monkeypatch):
    def execute(**kwargs):
        if kwargs["stage"] == "qc":
            kwargs["checkpoint_path"].write_bytes(b"retained-dds")
        return {"run_id": kwargs["stage"], "state": "QC_READY" if kwargs["stage"] == "qc" else "SUCCEEDED"}
    monkeypatch.setattr(durable, "execute_expression_analysis", execute)
    monkeypatch.setattr(durable, "load_manifest", lambda user, run: {"run_id": run})
    durable.run_job(durable.claim("worker"))
    observed = durable.status(queue, "alice")
    assert observed["state"] == "QC_REVIEW"
    with pytest.raises(RnaSeqExpressionError, match="changed"):
        durable.approve(queue, "alice", "wrong")
    durable.approve(queue, "alice", observed["result"]["checkpoint_sha256"])
    durable.run_job(durable.claim("worker"))
    assert durable.status(queue, "alice")["state"] == "SUCCEEDED"
    with pytest.raises(RnaSeqExpressionError, match="awaiting"):
        durable.approve(queue, "alice", "wrong")


def test_changed_retained_input_fails_before_r(queue, monkeypatch):
    monkeypatch.setattr(durable, "execute_expression_analysis", lambda **kwargs: pytest.fail("must not execute changed input"))
    (durable.root() / queue / "counts.tsv").write_text("changed")
    durable.run_job(durable.claim("worker"))
    assert durable.status(queue, "alice")["state"] == "FAILED"


def test_missing_artifacts_cannot_be_success(tmp_path):
    (tmp_path / "analysis_summary.json").write_text("{}")
    with pytest.raises(RnaSeqExpressionError, match="Required output artifacts"):
        validate_artifacts(tmp_path, {}, "infer")


def test_recovery_endpoints_auth_and_missing_units(monkeypatch):
    app = FastAPI(); app.include_router(rnaseq_recovery.router)
    client = TestClient(app)
    assert client.get("/api/ngs/v2/rnaseq/recovery/jobs/nope").status_code == 401
    with pytest.raises(GeoCountsError, match="experimental_unit"):
        rnaseq_recovery.require_units(b"sample\tcondition\ns1\ta\n")


def test_production_import_rejects_escape_and_wrong_types(tmp_path):
    with pytest.raises(GeoCountsError, match="unsafe"):
        rnaseq_recovery.production_files(str(tmp_path), {"../quant.sf": "s1"})
    with pytest.raises(GeoCountsError, match="quant.sf"):
        rnaseq_recovery.production_files(str(tmp_path), {"TPM.tsv": "s1"})


def test_http_submission_preserves_reviewed_origin_and_units(monkeypatch):
    app = FastAPI(); app.include_router(rnaseq_recovery.router)
    app.dependency_overrides[rnaseq_recovery.require_user_id] = lambda: "alice"
    captured = {}
    def submit(user, counts, metadata, params, source, input_kind="raw_counts", extras=None):
        captured.update(user=user, counts=counts, metadata=metadata, source=source)
        return {"job_id": "retained-job", "state": "QUEUED"}
    monkeypatch.setattr(rnaseq_recovery, "submit_prepared", submit)
    matrix = b"gene\ts1\ts2\ts3\ts4\ng1\t2\t3\t4\t5\ng2\t5\t6\t7\t8\n"
    metadata = b"sample\tcondition\texperimental_unit\ns1\ta\tu1\ns2\ta\tu2\ns3\tb\tu3\ns4\tb\tu4\n"
    origin = {"kind":"raw_counts", "normalization":"none", "evidence":"GEO source raw count methods", "method":"featureCounts", "annotation":"release 1", "reviewed":True}
    client = TestClient(app)
    response = client.post("/api/ngs/v2/rnaseq/recovery/submit", data={"origin":json.dumps(origin), "parameters":json.dumps({"reference_level":"a","test_level":"b"})}, files={"data":("counts.tsv",matrix),"metadata":("meta.tsv",metadata)})
    assert response.status_code == 200, response.text
    assert captured["source"]["count_origin_status"] == "ANALYST_ATTESTED"
    assert captured["metadata"] == metadata
    assert captured["counts"] == matrix


def test_production_namespaces_reject_other_owner_and_untrusted_config(tmp_path, monkeypatch):
    from app.ngs.rnaseq_resources import namespace, validate_submission, validate_owned_output
    from app.models.responses import NgsRnaSeqProductionPlanRequest
    from app.config import settings
    monkeypatch.setattr(settings, "NGS_RUN_ROOT", str(tmp_path / "runs"))
    monkeypatch.setattr(settings, "NGS_INPUT_ROOT", str(tmp_path / "inputs"))
    inputs = tmp_path / "inputs" / namespace("alice"); inputs.mkdir(parents=True)
    sample = inputs / "samples.csv"
    sample.write_text(f"sample,fastq_1,fastq_2,strandedness\ns1,{inputs}/read1.fastq.gz,,auto\n")
    outdir = str(tmp_path / "runs" / namespace("alice") / "run1")
    request = NgsRnaSeqProductionPlanRequest(samplesheet_path=str(sample), outdir=outdir)
    validate_submission(request, "alice")
    with pytest.raises(RuntimeError, match="private namespace"):
        validate_owned_output(outdir, "bob")
    request.custom_config = str(tmp_path / "arbitrary.config")
    with pytest.raises(RuntimeError, match="administrator-reviewed"):
        validate_submission(request, "alice")


def test_geo_source_change_blocks_assembly(monkeypatch):
    import asyncio
    from fastapi import UploadFile
    async def fetch(accession, names):
        return {}, {"source_sha256":{"counts.zip":"new"}}
    monkeypatch.setattr(rnaseq_recovery, "geo_files", fetch)
    with pytest.raises(Exception, match="changed since inspection"):
        asyncio.run(rnaseq_recovery.submit_geo(source_selection=json.dumps({"accession":"GSE1","filenames":["counts.zip"]}),
            origin=json.dumps({"normalization":"none","evidence":"raw count methods","method":"featureCounts","annotation":"release1","reviewed":True}),
            parameters="{}", metadata=UploadFile(filename="meta.tsv",file=io.BytesIO(b"x")), source_sha256=json.dumps({"counts.zip":"old"}),
            mapping="{}", matrix_member="", user="alice"))

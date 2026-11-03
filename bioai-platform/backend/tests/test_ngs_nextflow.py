"""Contracts for the in-app Docker-backed Nextflow NGS runner.

The important guarantees pinned here:

* capability reporting fails closed and never implies Nextflow ran;
* a run is only labelled as an executed Nextflow run after a real trace exists;
* artifacts are inventoried with observed checksums, never invented; and
* the packaged evidence manifest matches the artifacts committed beside it.
"""

from __future__ import annotations

import hashlib
import json
import subprocess

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.ngs import nextflow_runner as runner
from app.routers import ngs_v2


def _local_persist(monkeypatch):
    def persist(record):
        runner._write_json(runner._record_path(record["run_id"]), record)

    monkeypatch.setattr(runner, "_persist", persist)


def _capability(available: bool) -> dict:
    return {
        "workflow_id": runner.WORKFLOW_ID,
        "workflow": {"name": runner.WORKFLOW_NAME, "revision": "abc123abc123", "processes": runner.PROCESSES},
        "engine": {
            "name": "Nextflow",
            "version": "24.10.5" if available else None,
            "tool_versions": {"samtools": "1.19.2", "bcftools": "1.19"} if available else {},
            "container_image": runner.DEFAULT_IMAGE,
            "container_digest": "sha256:test" if available else None,
        },
        "fixtures": [{"id": "tiny-positive-control"}],
        "executor": {
            "name": "local-docker",
            "available": available,
            "missing": [] if available else ["docker CLI"],
            "requirements": [],
            "reason": None if available else "The Nextflow Docker runner is unavailable on this deployment: docker CLI.",
        },
    }


def test_capabilities_fail_closed_without_docker(monkeypatch):
    monkeypatch.setattr(runner, "_binary", lambda _name: False)
    capability = runner.capabilities()
    assert capability["executor"]["available"] is False
    assert "docker CLI" in capability["executor"]["missing"]
    assert capability["engine"]["version"] is None
    assert "unavailable" in capability["executor"]["reason"].lower()
    assert "only when nextflow run exited 0" in capability["claim"]


def test_capabilities_report_versions_when_image_is_ready(monkeypatch):
    monkeypatch.setattr(runner, "_binary", lambda _name: True)

    def fake_run(argv, timeout=30):
        if argv[:2] == ["docker", "info"]:
            return subprocess.CompletedProcess(argv, 0, "29.7.2\n", "")
        if argv[:3] == ["docker", "image", "inspect"]:
            payload = json.dumps({"Id": "sha256:image", "RepoDigests": ["bionexus/ngs-tools@sha256:digest"], "Size": 1})
            return subprocess.CompletedProcess(argv, 0, payload, "")
        if argv[:2] == ["docker", "run"]:
            return subprocess.CompletedProcess(argv, 0, "nextflow=24.10.5\nsamtools=1.19.2\nbcftools=1.19\n", "")
        return subprocess.CompletedProcess(argv, 1, "", "unexpected")

    monkeypatch.setattr(runner, "_run", fake_run)
    capability = runner.capabilities()
    assert capability["executor"]["available"] is True
    assert capability["engine"]["version"] == "24.10.5"
    assert capability["engine"]["tool_versions"] == {"samtools": "1.19.2", "bcftools": "1.19"}
    assert capability["engine"]["container_digest"].endswith("sha256:digest")


def test_submit_fails_closed_when_executor_is_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "NGS_RUN_ROOT", str(tmp_path))
    monkeypatch.setattr(runner, "capabilities", lambda: _capability(False))
    with pytest.raises(RuntimeError, match="unavailable"):
        runner.submit_run(user_id="u1")
    assert not (tmp_path / "nextflow").exists()


def test_submit_records_engine_only_after_trace_exists(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "NGS_RUN_ROOT", str(tmp_path))
    monkeypatch.setattr(runner, "capabilities", lambda: _capability(True))
    _local_persist(monkeypatch)
    launched: list[list[str]] = []

    def fake_popen(argv, **kwargs):
        launched.append(argv)
        return object()

    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)

    record = runner.submit_run(user_id="u1", min_qual=30, min_dp=12, threads=2)
    assert record["state"] == "SUBMITTED"
    assert record["nextflow_executed"] is False
    assert record["engine"] == "Nextflow"
    assert record["parameters"] == {"min_qual": 30.0, "min_dp": 12, "threads": 2}

    assert len(launched) == 1
    assert launched[0][1].endswith("nextflow_worker.py")
    command = launched[0][4:]
    assert command[:5] == ["docker", "run", "--rm", "--name", f"bionexus-nf-{record['run_id'][:8]}"]
    assert "/opt/workflow/main.nf" in command
    assert "--min_qual" in command and command[command.index("--min_qual") + 1] == "30"
    assert "--min_dp" in command and command[command.index("--min_dp") + 1] == "12"

    run_dir = runner._run_dir(record["run_id"])
    assert (run_dir / "inputs" / "reference.fa").is_file()
    assert (run_dir / "inputs" / "reads.sam").is_file()
    assert (run_dir / "inputs" / "truth.tsv").is_file()

    # A successful worker status without a Nextflow trace must not be labelled
    # as an executed Nextflow run.
    runner._write_json(run_dir / "status.json", {"state": "SUCCEEDED", "exit_code": 0, "message": None, "updated_at": "now"})
    state = runner.get_run(record["run_id"], "u1")
    assert state["state"] == "SUCCEEDED"
    assert state["nextflow_executed"] is False
    assert state["processes"] == []

    trace = run_dir / "results" / "pipeline_info" / "trace.txt"
    trace.parent.mkdir(parents=True)
    trace.write_text(
        "task_id\thash\tname\tstatus\texit\trealtime\n"
        "1\tab/cd\tSORT_BAM (reads.sam)\tCOMPLETED\t0\t74ms\n"
        "    samtools view -bS reads.sam\n",
        encoding="utf-8",
    )
    (run_dir / ".nextflow.log").write_text("N E X T F L O W  ~  version 24.10.5\nLaunching main.nf\n", encoding="utf-8")
    state = runner.get_run(record["run_id"], "u1")
    assert state["nextflow_executed"] is True
    assert state["engine_version"] == "24.10.5"
    assert state["processes"] == [
        {"task_id": "1", "name": "SORT_BAM (reads.sam)", "status": "COMPLETED", "exit": "0", "realtime": "74ms"}
    ]


def test_artifact_manifest_hashes_observed_files(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "NGS_RUN_ROOT", str(tmp_path))
    _local_persist(monkeypatch)
    record = {
        "run_id": "11111111-2222-3333-4444-555555555555",
        "state": "SUCCEEDED",
        "workflow": runner.WORKFLOW_NAME,
        "revision": "abc123abc123",
        "user_id": "u1",
        "nextflow_executed": True,
    }
    runner._write_json(runner._record_path(record["run_id"]), record)
    run_dir = runner._run_dir(record["run_id"])
    (run_dir / "results" / "variants").mkdir(parents=True)
    calls = run_dir / "results" / "variants" / "calls.tsv"
    calls.write_text("CHROM\tPOS\tREF\tALT\tGT\tDP\tAD\nchrTiny\t50\tC\tG\t0/1\t20\t10,10\n", encoding="utf-8")

    manifest = runner.artifact_manifest(record["run_id"], "u1")
    by_id = {item["id"]: item for item in manifest["artifacts"]}
    assert by_id["calls_tsv"]["present"] is True
    assert by_id["calls_tsv"]["sha256"] == hashlib.sha256(calls.read_bytes()).hexdigest()
    assert by_id["calls_vcf"]["present"] is False
    assert "calls_vcf" in manifest["missing_required"]
    assert manifest["required_complete"] is False
    assert by_id["calls_tsv"]["download_url"].endswith("/artifacts/calls_tsv")

    path, spec = runner.artifact_path(record["run_id"], "u1", "calls_tsv")
    assert path == calls and spec["media_type"] == "text/tab-separated-values"
    with pytest.raises(KeyError):
        runner.artifact_path(record["run_id"], "u1", "not_a_real_artifact")


def test_committed_evidence_matches_its_manifest():
    evidence = runner.evidence_report()
    assert evidence["available"] is True
    assert evidence["execution"]["engine"] == "Nextflow"
    assert evidence["execution"]["nextflow_executed"] is True
    assert evidence["execution"]["state"] == "SUCCEEDED"
    assert evidence["execution"]["exit_code"] == 0
    assert evidence["result"]["tp"] == 1
    assert evidence["result"]["fp"] == 0
    assert evidence["result"]["fn"] == 0
    assert evidence["result"]["normalized_calls_sha256"] == (
        "cefef322e336202da82549c1d5c09cf546a70b4aacfe9d1cc7e090a8aa23bbb1"
    )
    assert evidence["inline"]["calls.tsv"].splitlines()[1].split("\t")[:4] == ["chrTiny", "50", "C", "G"]

    for name, metadata in evidence["files"].items():
        blob = (runner.EVIDENCE_DIR / name).read_bytes()
        assert metadata["bytes"] == len(blob)
        assert metadata["sha256"] == hashlib.sha256(blob).hexdigest()


@pytest.fixture()
def client(monkeypatch):
    app = FastAPI(title="Nextflow router tests")
    app.dependency_overrides[ngs_v2.require_user_id] = lambda: "router-user"
    app.include_router(ngs_v2.router)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_nextflow_routes_expose_capabilities_and_committed_evidence(client):
    capability = client.get("/api/ngs/v2/nextflow/capabilities")
    assert capability.status_code == 200
    assert capability.json()["workflow_id"] == runner.WORKFLOW_ID

    evidence = client.get("/api/ngs/v2/nextflow/evidence")
    assert evidence.status_code == 200
    assert evidence.json()["execution"]["engine"] == "Nextflow"

    calls = client.get("/api/ngs/v2/nextflow/evidence/files/calls.tsv")
    assert calls.status_code == 200
    assert "chrTiny\t50\tC\tG\t0/1\t20\t10,10" in calls.text

    missing = client.get("/api/ngs/v2/nextflow/evidence/files/not-in-manifest.txt")
    assert missing.status_code == 404


def test_nextflow_submit_returns_503_when_executor_unavailable(client, monkeypatch):
    monkeypatch.setattr(ngs_v2.nextflow_runner, "capabilities", lambda: _capability(False))
    response = client.post("/api/ngs/v2/nextflow/runs", json={"fixture": "tiny-positive-control"})
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


def test_nextflow_submit_rejects_out_of_range_parameters(client):
    response = client.post(
        "/api/ngs/v2/nextflow/runs",
        json={"fixture": "tiny-positive-control", "min_qual": -1, "threads": 99},
    )
    assert response.status_code == 422

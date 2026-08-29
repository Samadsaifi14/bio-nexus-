import gzip
import os
import random

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import ngs_v2


@pytest.fixture(scope="module")
def client():
    app = FastAPI(title="NGS v2 Router Tests")
    app.include_router(ngs_v2.router)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _write_fastq(tmp_path, name, n, seed=5, read_len=30):
    rng = random.Random(seed)
    path = os.path.join(str(tmp_path), name)
    seqs = set()
    while len(seqs) < n:
        seqs.add("".join(rng.choice("ACGT") for _ in range(read_len)))
    with gzip.open(path, "wt") as fh:
        for i, seq in enumerate(sorted(seqs)):
            fh.write(f"@read{i} 1:N:0:1\n{seq}\n+\n{'I' * read_len}\n")
    return path, sorted(seqs)


def test_stages_lists_contracts(client):
    r = client.get("/api/ngs/v2/stages")
    assert r.status_code == 200
    body = r.json()
    assert body["pipeline"] == "wgs-wes-germline"
    steps = [s["step"] for s in body["stages"]]
    assert steps[0] == "input_validation"
    assert steps[-1] == "final_gate"
    assert len(steps) == 21


def test_detect_returns_evidence(client, tmp_path):
    path, _ = _write_fastq(tmp_path, "HUM0001_R1.fastq.gz", 40)
    r = client.post("/api/ngs/v2/detect", json={"file_paths": [path]})
    assert r.status_code == 200
    body = r.json()
    assert "assay" in body            # no WGS/WES keyword in the name -> UNKNOWN
    assert "confidence" in body
    assert isinstance(body["evidence"], list)
    assert body["library_type"] in ("single-end", "paired-end")


def test_analyze_runs_full_dag_through_final_gate(client, tmp_path):
    r1, _ = _write_fastq(tmp_path, "HUM0001_R1.fastq.gz", 200, seed=1)
    r2, _ = _write_fastq(tmp_path, "HUM0001_R2.fastq.gz", 200, seed=2)
    payload = {
        "file_paths": [r1, r2],
        "reference": "grch38",
        "metadata": {"platform": "illumina"},
        "synthetic_reference": True,
    }
    r = client.post("/api/ngs/v2/analyze", json=payload)
    assert r.status_code == 200
    body = r.json()

    # A synthetic (in-file) reference is loaded by the request itself, not invented.
    assert "detection" in body
    assert body["requested"]["assay"] == "WGS"
    assert body["requested"]["synthetic_reference"] is True

    stages = body["pipeline"]["stages"]
    steps = [s["step"] for s in stages]
    assert len(steps) == 21
    # The pipeline should NOT have hard-stopped on a blocking gate for a genuine read set.
    assert body["pipeline"]["pipeline_status"] in ("PASS", "WARN")

    # The final analysis-readiness gate must have produced a verdict.
    gate = stages[-1]
    assert gate["step"] == "final_gate"
    assert gate["decision"] in ("CONTINUE", "CONTINUE_WITH_WARNING")


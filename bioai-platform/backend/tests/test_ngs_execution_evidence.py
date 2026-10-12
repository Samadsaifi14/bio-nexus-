"""Synthetic integrity controls; these do not execute Sarek or validate variants."""
import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from app.ngs.execution_evidence import verify_execution_bundle, sha256
from app.ngs.production import build_production_plan
from app.models.responses import NgsProductionPlanRequest


def bundle(tmp_path):
    record = {"run_id": "control", "command_sha256": "a" * 64,
              "workflow": "nf-core/sarek", "revision": "3.10.0", "state": "SUCCEEDED", "exit_code": 0}
    outputs = ["pipeline_info/execution_trace.txt", "pipeline_info/execution_report.html", "pipeline_info/execution_timeline.html",
               "multiqc/multiqc_report.html", "multiqc/multiqc_data/data.json", "alignment.bam", "alignment.bai",
               "calls.vcf.gz", "calls.vcf.gz.tbi", "reports/sample/mosdepth.txt", "reports/sample/coverage.txt",
               "reports/sample/contamination.txt", "reports/sample/fingerprint.txt", "reports/sample/sex.txt",
               "run_manifest.json", "checksums.sha256"]
    def members(names):
        result = []
        for name in names:
            path = tmp_path / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic integrity fixture only\n")
            result.append({"path": name, "sha256": sha256(path)})
        return result
    manifest = {key: record[key] for key in ("run_id", "command_sha256", "workflow", "revision")}
    manifest.update(nextflow_version="test-runtime", inputs=members(["inputs/samples.csv"]),
                    references=members(["references/reference.fasta"]), outputs=members(outputs), trace=outputs[0])
    trace = tmp_path / outputs[0]
    trace.write_text("name\tstatus\texit\tcontainer\nALIGN sample1\tCOMPLETED\t0\timage@sha256:" + "b" * 64 + "\n")
    manifest["outputs"][0]["sha256"] = sha256(trace)
    (tmp_path / "execution_evidence.json").write_text(json.dumps(manifest))
    return record, manifest


def test_complete_retained_contract_and_corrupted_outputs(tmp_path):
    record, _ = bundle(tmp_path)
    report = verify_execution_bundle(record, tmp_path)
    assert report["status"] == "RETAINED_EVIDENCE_VERIFIED"
    assert report["biological_validation"] is False
    (tmp_path / "calls.vcf.gz").write_text("corrupted")
    report = verify_execution_bundle(record, tmp_path)
    assert report["status"] == "INSUFFICIENT_EVIDENCE"
    assert any("Checksum mismatch" in item for item in report["errors"])


@pytest.mark.parametrize("case", ["plan", "missing_reference", "wrong_run", "unhashed_trace", "tag_only_container", "failed_process", "escape"])
def test_plans_or_incomplete_execution_evidence_cannot_pass(tmp_path, case):
    record, manifest = bundle(tmp_path)
    if case == "plan":
        record["state"] = "PLANNED"
    elif case == "missing_reference":
        manifest["references"] = []
    elif case == "wrong_run":
        manifest["run_id"] = "another-run"
    elif case == "unhashed_trace":
        manifest["outputs"] = manifest["outputs"][1:]
    elif case in {"tag_only_container", "failed_process"}:
        trace = tmp_path / manifest["trace"]
        trace.write_text(trace.read_text().replace("image@sha256:" + "b" * 64, "image:latest") if case == "tag_only_container" else trace.read_text().replace("COMPLETED\t0", "FAILED\t1"))
        manifest["outputs"][0]["sha256"] = sha256(trace)
    else:
        manifest["references"][0]["path"] = "../escape"
    (tmp_path / "execution_evidence.json").write_text(json.dumps(manifest))
    assert verify_execution_bundle(record, tmp_path)["status"] == "INSUFFICIENT_EVIDENCE"


def test_production_plan_is_explicitly_not_execution():
    plan = build_production_plan(NgsProductionPlanRequest(assay="WGS", samplesheet_path="/inputs/samples.csv", outdir="/results"))
    assert plan["evidence_class"] == "workflow_plan"
    assert plan["sequencing_execution_verified"] is False


@pytest.mark.parametrize("exit_code,expected", [(0, "SUCCEEDED"), (7, "FAILED")])
def test_real_wrapper_process_retains_history_and_log_hash(tmp_path, exit_code, expected):
    # Match the production contract: each worker receives a fresh run directory.
    tmp_path = tmp_path / str(uuid.uuid4())
    tmp_path.mkdir()
    worker = Path(__file__).resolve().parents[1] / "app/ngs/nextflow_worker.py"
    command = [sys.executable, "-c", f"print('synthetic worker lifecycle control'); raise SystemExit({exit_code})"]
    status, log = tmp_path / "status.json", tmp_path / "nextflow.log"
    completed = subprocess.run([sys.executable, str(worker), str(status), str(log), *command], timeout=30)
    assert completed.returncode == exit_code
    assert json.loads(status.read_text())["state"] == expected
    assert json.loads(status.read_text())["exit_code"] == exit_code
    history = [json.loads(line) for line in (tmp_path / "worker_history.jsonl").read_text().splitlines()]
    assert [item["state"] for item in history] == ["RUNNING", expected]
    assert (tmp_path / "worker_log_sha256.txt").read_text().strip() == sha256(log)
    argv = json.loads((tmp_path / "worker_command.json").read_text())
    assert argv["command_sha256"] == hashlib.sha256(json.dumps(command, separators=(",", ":")).encode()).hexdigest()
    assert argv["sequencing_execution_verified"] is False

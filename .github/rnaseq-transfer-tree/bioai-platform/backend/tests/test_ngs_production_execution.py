from pathlib import Path

from app.config import settings
from app.ngs import execution


def test_capabilities_never_offer_preview_fallback(monkeypatch):
    monkeypatch.setattr(settings, "NGS_LOCAL_EXECUTION_ENABLED", False)
    monkeypatch.setattr(settings, "NGS_SLURM_EXECUTION_ENABLED", False)
    monkeypatch.setattr(settings, "NGS_AWS_BATCH_EXECUTION_ENABLED", False)
    result = execution.executor_capabilities()
    assert result["fallback"] is None
    assert all(not item["available"] for item in result["executors"].values())
    assert "never fall back" in result["note"]
    assert {item["name"] for item in result["workflows"]} == {"nf-core/sarek", "nf-core/rnaseq"}


def test_disabled_executor_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "NGS_LOCAL_EXECUTION_ENABLED", False)
    try:
        execution.submit_run("local", ["nextflow", "run", "nf-core/sarek"], "/results", "user-1")
    except RuntimeError as exc:
        assert "executor unavailable" in str(exc)
    else:
        raise AssertionError("disabled executor accepted a production run")


def test_owned_run_record_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "NGS_RUN_ROOT", str(tmp_path))
    monkeypatch.setattr("app.services.supabase.get_supabase", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    record = {
        "run_id": "11111111-1111-1111-1111-111111111111",
        "state": "SUBMITTED", "executor": "local", "executor_job_id": "123",
        "workflow": "nf-core/sarek", "revision": "3.10.0", "outdir": "/results",
        "submitted_at": "2026-09-02T00:00:00+00:00", "updated_at": "2026-09-02T00:00:00+00:00",
        "exit_code": None, "message": None, "user_id": "user-1", "command_sha256": "a" * 64,
    }
    execution._persist_record(record)
    assert Path(tmp_path, f"{record['run_id']}.json").is_file()
    assert execution._load_record(record["run_id"], "user-1")["workflow"] == "nf-core/sarek"
    try:
        execution._load_record(record["run_id"], "user-2")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("run record was visible to another user")


def test_rnaseq_artifact_contract_does_not_require_variant_files():
    files = [
        "/results/pipeline_info/execution_trace.txt",
        "/results/fastqc/sample_fastqc.html",
        "/results/multiqc/multiqc_report.html",
        "/results/star_salmon/sample.bam",
        "/results/salmon/sample/quant.sf",
        "/results/deseq2/pca.pdf",
        "/results/checksums.sha256",
    ]
    groups = execution._artifact_groups("nf-core/rnaseq", files)
    assert "small_variants" not in groups
    assert "quantification" in groups and groups["quantification"]
    assert "expression_qc" in groups and groups["expression_qc"]


def test_sarek_artifact_contract_requires_variant_and_identity_evidence():
    groups = execution._artifact_groups("nf-core/sarek", ["/results/pipeline_info/execution_trace.txt"])
    assert "small_variants" in groups
    assert "identity_qc" in groups

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
        "exit_code": None, "message": None, "user_id": "user-1",
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

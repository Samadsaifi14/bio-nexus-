import asyncio
import hashlib
import json

import pytest
from fastapi import HTTPException

from app.services.workflow_manifest import build_workflow_manifest


def test_states_versions_dependencies_and_canonical_integrity():
    exp = {"experiment_id": "e", "job_id": "j", "input_hash": "abc", "parameters": {"seed": 7}}
    provenance = [{"node_id": "blast", "status": "complete", "tool": "BLAST", "tool_version": "2.16.0",
                   "database": "nr", "deps": ["input"], "params": {"evalue": 1e-5}},
                  {"node_id": "msa", "status": "skipped"},
                  {"node_id": "phylo", "status": "failed"},
                  {"node_id": "ai", "status": "running"}, {"node_id": "unknown"}]
    manifest = build_workflow_manifest(exp, provenance)
    assert [n["state"] for n in manifest["steps"]] == ["COMPLETED", "SKIPPED", "FAILED", "RUNNING", "UNKNOWN"]
    assert manifest["steps"][0]["tool_version"] == "2.16.0"
    assert manifest["steps"][0]["database_version"] is None
    assert manifest["edges"] == [{"from": "input", "to": "blast"}]
    assert any(g["reason"] == "UNRECORDED_DEPENDENCY" for g in manifest["reproducibility_gaps"])
    assert manifest["execution"]["executable"] is False
    assert manifest == build_workflow_manifest(exp, provenance)
    digest = manifest.pop("manifest_sha256")
    assert digest == hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def test_empty_evidence_cannot_imply_execution():
    result = build_workflow_manifest({"status": "complete"}, [])
    assert result["steps"] == []
    assert any(g["field"] == "steps" for g in result["reproducibility_gaps"])
    assert result["input_sha256"] is None


def test_export_rejects_other_tenant_before_reading_experiment(monkeypatch):
    from app.routers import experiments
    monkeypatch.setattr(experiments, "owns_job", lambda job, user: False)
    monkeypatch.setattr(experiments, "get_experiment", lambda _: pytest.fail("Unauthorized experiment read"))
    with pytest.raises(HTTPException) as error:
        asyncio.run(experiments.export_workflow_manifest("foreign-job", "user"))
    assert error.value.status_code == 404


def test_export_owned_job_preserves_explicit_empty_provenance(monkeypatch):
    from app.routers import experiments
    monkeypatch.setattr(experiments, "owns_job", lambda job, user: True)
    monkeypatch.setattr(experiments, "get_experiment", lambda _: {"experiment_id": "e", "provenance": []})
    monkeypatch.setattr(experiments, "provenance_for_experiment", lambda _: pytest.fail("Unexpected fallback"))
    result = asyncio.run(experiments.export_workflow_manifest("j", "user"))
    assert result["steps"] == []

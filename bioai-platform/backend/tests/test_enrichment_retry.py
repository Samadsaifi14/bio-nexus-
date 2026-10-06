import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from app.rnaseq import enrichment_retry as er
from app.rnaseq import expression as ex

RUN = "11111111-1111-1111-1111-111111111111"


def parent(data=b"gene\tpadj\tdirection\nTP53\t0.01\tUP\n"):
    return {"run_id": RUN, "summary": {"alpha": .05, "samples": 18}, "provenance": {},
            "artifacts": [{"name": "deseq2_all_results.tsv", "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)},
                          {"name": "go_enrichment.svg", "sha256": "old"}]}


def test_options_require_documented_custom_annotation():
    er.EnrichmentOptions().validate()
    with pytest.raises(ex.RnaSeqExpressionError, match="source/release"):
        er.EnrichmentOptions(database="CUSTOM").validate(True)
    er.EnrichmentOptions(database="CUSTOM", organism="Arabidopsis thaliana", database_label="TAIR release X", namespace="TAIR").validate(True)
    with pytest.raises(ex.RnaSeqExpressionError):
        er.EnrichmentOptions(method="choose_best_pvalue").validate()
    with pytest.raises(ex.RnaSeqExpressionError):
        er.EnrichmentOptions().validate(has_mapping=True)


def test_owner_scoped_download_checks_hash_and_ignores_urls(monkeypatch):
    data = b"gene\tpadj\tdirection\nTP53\t0.01\tUP\n"
    sb = MagicMock(); sb.storage.from_().download.return_value = data
    monkeypatch.setattr(ex, "get_supabase", lambda: sb)
    manifest = parent(data); manifest["artifacts"][0]["url"] = "https://attacker.invalid/anything"
    assert er._download_results("alice", RUN, manifest) == data
    sb.storage.from_().download.assert_called_with(f"{ex._safe_user_key('alice')}/{RUN}/deseq2_all_results.tsv")
    manifest["artifacts"][0]["sha256"] = "changed"
    with pytest.raises(ex.RnaSeqExpressionError, match="checksum"):
        er._download_results("alice", RUN, manifest)
    manifest["artifacts"][0]["source_run_id"] = "../../bob"
    with pytest.raises(ex.RnaSeqExpressionError, match="source run"):
        er._download_results("alice", RUN, manifest)


def test_retry_retains_original_artifacts_and_removes_stale_enrichment(monkeypatch):
    original = parent(); stored = {}
    original["provenance"]["enrichment_gene_sets.gmt_sha256"] = "previous-database"
    monkeypatch.setattr(ex, "load_manifest", lambda user, run: original)
    monkeypatch.setattr(er, "_download_results", lambda *args: b"results")
    def execute(results, options, out):
        assert json.loads(options.read_text())["alpha"] == .05
        (out / "go_enrichment_summary.json").write_text('{"status":"NO_SIGNIFICANT_TERMS"}')
        return {"status": "NO_SIGNIFICANT_TERMS"}
    monkeypatch.setattr(er, "_execute", execute)
    monkeypatch.setattr(ex, "_upload_bytes", lambda path, data, mime: stored.setdefault(path, data))
    monkeypatch.setattr(ex, "_signed_url", lambda path: "signed:" + path)
    result = er.rerun_enrichment(user_id="alice", run_id=RUN, options=er.EnrichmentOptions())
    assert result["run_id"] != RUN
    assert result["provenance"]["parent_run_id"] == RUN
    assert result["summary"]["samples"] == 18
    assert "enrichment_gene_sets.gmt_sha256" not in result["provenance"]
    assert original["summary"] == {"alpha": .05, "samples": 18}
    assert not any(x["name"] == "go_enrichment.svg" for x in result["artifacts"])
    retained = next(x for x in result["artifacts"] if x["name"] == "deseq2_all_results.tsv")
    assert retained["source_run_id"] == RUN
    assert f"/{RUN}/deseq2_all_results.tsv" in retained["url"]
    assert not any(path.endswith("deseq2_all_results.tsv") for path in stored)


def test_rerun_cannot_load_another_users_manifest(monkeypatch):
    def deny(user, run):
        assert user == "bob"
        raise ex.RnaSeqExpressionError("RNA-seq result was not found for this user.")
    monkeypatch.setattr(ex, "load_manifest", deny)
    with pytest.raises(ex.RnaSeqExpressionError, match="this user"):
        er.rerun_enrichment(user_id="bob", run_id=RUN, options=er.EnrichmentOptions())


def test_enrichment_route_auth_and_multipart_handoff(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers import rnaseq_expression as route
    app = FastAPI(); app.include_router(route.router)
    client = TestClient(app)
    url = f"/api/ngs/v2/rnaseq/expression/runs/{RUN}/enrichment"
    assert client.post(url).status_code == 401
    app.dependency_overrides[route.require_user_id] = lambda: "alice"
    monkeypatch.setattr(route, "_with_study_scope", lambda value: value)
    def execute(**kwargs):
        assert kwargs["user_id"] == "alice"
        assert kwargs["options"].aliases is False
        assert kwargs["gmt"].read_text() == "t\td\tg1\n"
        return {"run_id": "new-run"}
    monkeypatch.setattr(route, "rerun_enrichment", execute)
    fields = {"organism": "Test species", "database": "CUSTOM", "method": "ora", "aliases": "false",
              "database_label": "Fixture v1", "namespace": "locus_tag"}
    assert client.post(url, data=fields).status_code == 422
    response = client.post(url, data=fields, files={"gmt": ("sets.gmt", b"t\td\tg1\n")})
    assert response.status_code == 200, response.text
    assert response.json()["run_id"] == "new-run"
    monkeypatch.setattr(route, "MAX_ANNOTATION_BYTES", 5)
    assert client.post(url, data=fields, files={"gmt": ("sets.gmt", b"t\td\tg1\n")}).status_code == 413

import gzip
import hashlib
import hmac
import os
import random

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import ngs_v2
from app.models.responses import NgsClinicalEvidenceRequest
from app.ngs.production import clinical_signature_payload
from app.config import settings


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


def test_portable_benchmark_reports_scoped_execution_parity(client):
    response = client.get("/api/ngs/v2/benchmarks/portable")
    assert response.status_code == 200
    report = response.json()
    assert report["status"] == "PASS"
    assert report["workflow_output_parity"] is True
    assert report["expected_call"] == {
        "chrom": "chrTiny", "pos": 50, "ref": "C", "alt": "G",
        "genotype": "0/1", "depth": 20, "allelic_depth": "10,10",
    }
    assert len({row["normalized_sha256"] for row in report["reports"]}) == 1
    assert all(row["f1"] == 1.0 for row in report["reports"])
    galaxy = next(row for row in report["reports"] if row["orchestrator"].startswith("Galaxy"))
    assert galaxy["execution"] == "EXECUTED_WITHOUT_GALAXY_SERVER"


def test_production_capabilities_are_explicit_and_have_no_preview_fallback(client):
    response = client.get("/api/ngs/v2/production/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert set(body["executors"]) == {"local", "slurm", "awsbatch"}
    assert body["fallback"] is None
    assert body["workflow"] == {"name": "nf-core/sarek", "revision": "3.10.0"}


def test_clean_demo_uses_explicit_not_evaluated_states(client):
    response = client.post("/api/ngs/v2/analyze", json={"demo_profile": "wgs-clean"})
    assert response.status_code == 200
    body = response.json()
    stages = {stage["step"]: stage for stage in body["pipeline"]["stages"]}

    assert body["requested"]["reference"] == "synthetic-positive-control"
    assert body["requested"]["reference_template_requested"] == "grch38"
    assert body["detection"]["sample_type"] == "synthetic-positive-control"
    reference = body["pipeline"]["provenance"]["reference"]
    assert reference["id"] == "synthetic-positive-control"
    assert reference["reference_kind"] == "SYNTHETIC"
    assert reference["build"] == "NOT_APPLICABLE"
    assert reference["artifacts"] == [{"name": "In-memory synthetic reference", "present": True}]

    assert stages["coverage"]["qc"]["status"] == "PASS"
    assert stages["variant_filter"]["qc"]["status"] == "PASS"
    assert stages["variant_filter"]["data"]["n_final"] == 0
    assert stages["annotation"]["qc"]["status"] == "PASS"
    assert stages["annotation"]["data"]["n_annotated"] == 0
    assert stages["annotation"]["data"]["status"] == "NOT_APPLICABLE"
    assert stages["contamination"]["data"]["status"] == "NOT_EVALUATED"
    assert stages["contamination"]["qc"]["metrics"][0]["value"] is None
    assert stages["identity"]["data"]["status"] == "NOT_EVALUATED"
    assert len(stages["identity"]["qc"]["metrics"]) == 1
    assert stages["final_gate"]["qc"]["metrics"][0]["value"] == "ANALYSIS_READY_WITH_WARNINGS"

    warnings = body["pipeline"]["warnings"]
    assert len(warnings) == 2
    assert all("Not evaluated:" in warning for warning in warnings)
    assert not any("(None)" in warning for warning in warnings)
    assert not any(name in " ".join(warnings) for name in (
        "contam_checked", "identity_checked", "candidate_frac", "gate_ok",
    ))
    assert all(tool["implementation"] for tool in body["pipeline"]["provenance"]["tools"])


def test_production_plan_pins_sarek_and_emits_auditable_argv(client):
    response = client.post("/api/ngs/v2/production/plan", json={
        "assay": "WGS",
        "sample_model": "trio",
        "input_type": "FASTQ",
        "samplesheet_path": "/staged/family.csv",
        "outdir": "/results/family",
        "genome": "GRCh38",
        "execution_profile": "docker",
        "caller": "haplotypecaller",
        "clinical_intent": True,
    })
    assert response.status_code == 200
    plan = response.json()
    assert plan["ready_to_launch"] is True
    assert plan["state"] == "PLANNED"
    assert plan["workflow"]["name"] == "nf-core/sarek"
    assert plan["workflow"]["revision"] == "3.10.0"
    assert plan["command_argv"][:5] == ["nextflow", "run", "nf-core/sarek", "-r", "3.10.0"]
    assert ["--genome", "GATK.GRCh38"] == plan["command_argv"][plan["command_argv"].index("--genome"):plan["command_argv"].index("--genome") + 2]
    assert "--joint_germline" in plan["command_argv"]
    assert plan["clinical_boundary"]["current_status"] == "NOT_CLINICALLY_RELEASABLE"
    assert {item["id"] for item in plan["required_artifacts"]} >= {"execution", "multiqc", "alignment", "small_variants", "provenance"}


def test_production_wes_and_remote_executor_fail_closed(client):
    response = client.post("/api/ngs/v2/production/plan", json={
        "assay": "WES",
        "samplesheet_path": "/staged/case.csv",
        "outdir": "/results/case",
        "execution_profile": "slurm",
    })
    assert response.status_code == 200
    plan = response.json()
    assert plan["state"] == "BLOCKED"
    assert plan["ready_to_launch"] is False
    assert any("target BED" in item for item in plan["blockers"])
    assert any("custom configuration" in item for item in plan["blockers"])


def test_clinical_gate_rejects_claims_without_evidence(client):
    response = client.post("/api/ngs/v2/clinical/evaluate", json={})
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "NOT_CLINICALLY_RELEASABLE"
    assert result["clinically_validated"] is False
    assert result["missing_or_failed"]
    signature_gate = next(gate for gate in result["gates"] if gate["id"] == "evidence_signature")
    assert signature_gate["status"] == "FAIL"


def test_clinical_gate_passes_only_complete_signed_external_evidence(client, monkeypatch):
    sha = "a" * 64
    payload = {
        "evidence_bundle_sha256": "d" * 64,
        "assay_validation_id": "VAL-WGS-2026-04",
        "workflow_status": "COMPLETED",
        "sarek_revision": "3.10.0",
        "reference_build": "GRCh38",
        "reference_manifest_sha256": sha,
        "samplesheet_sha256": "b" * 64,
        "container_digests_complete": True,
        "complete_input_processed": True,
        "required_artifacts_present": True,
        "qc_pass": True,
        "sample_identity_pass": True,
        "contamination_pass": True,
        "sex_ploidy_reviewed": True,
        "truthset_name": "GIAB HG002 v4.2.1",
        "benchmark_protocol_id": "SOP-BENCH-07",
        "benchmark_acceptance_pass": True,
        "confident_regions_sha256": "c" * 64,
        "same_sample_reference_regions": True,
        "snv_precision": 0.999,
        "snv_recall": 0.998,
        "indel_precision": 0.995,
        "indel_recall": 0.994,
        "human_reviewed": True,
        "reviewer_id": "reviewer-17",
        "release_signature_id": "sig-2026-09-01-001",
    }
    signing_key = "test-only-clinical-attestation-key"
    monkeypatch.setattr(settings, "NGS_CLINICAL_EVIDENCE_HMAC_KEY", signing_key)
    evidence = NgsClinicalEvidenceRequest(**payload)
    payload["evidence_signature"] = hmac.new(
        signing_key.encode("utf-8"), clinical_signature_payload(evidence), hashlib.sha256,
    ).hexdigest()
    response = client.post("/api/ngs/v2/clinical/evaluate", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "SOFTWARE_GATE_PASSED"
    assert result["clinically_validated"] is False
    assert result["missing_or_failed"] == []

    payload["truthset_name"] = "synthetic positive control"
    rejected = client.post("/api/ngs/v2/clinical/evaluate", json=payload).json()
    assert rejected["status"] == "NOT_CLINICALLY_RELEASABLE"


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
    assert all(isinstance(s["inputs"], list) for s in stages)
    assert all(isinstance(s["outputs"], list) for s in stages)
    assert all("input" not in s and "output" not in s for s in stages)
    # The pipeline should NOT have hard-stopped on a blocking gate for a genuine read set.
    assert body["pipeline"]["pipeline_status"] in ("PASS", "WARN")

    # The final analysis-readiness gate must have produced a verdict.
    gate = stages[-1]
    assert gate["step"] == "final_gate"
    assert gate["decision"] in ("CONTINUE", "CONTINUE_WITH_WARNING")

    provenance = body["pipeline"]["provenance"]
    assert provenance["schema_version"] == "1.0"
    assert provenance["pipeline"] == {"name": "WGS-germline", "version": "0.1.0"}
    assert provenance["analysis"]["synthetic_reference"] is True
    assert len(provenance["inputs"]) == 2
    assert all(item["checksum"]["algorithm"] == "md5" for item in provenance["inputs"])
    assert len(provenance["tools"]) == 21
    assert all("implementation" in item for item in provenance["tools"])
    assert all("evidence_level" in stage for stage in stages)

    validation = body["pipeline"]["validation"]
    assert validation["claim"] == "NO_ACCURACY_CLAIM"
    assert validation["same_or_better_supported"] is False
    assert len(validation["comparisons"]) >= 3
    assert all(item["status"] != "EVALUATED" for item in validation["comparisons"])
    assert all(item["metrics"] is None for item in validation["comparisons"])
    assert validation["analysis_grade"] == "EXPLORATORY_PREVIEW"
    assert validation["research_ready"] is False
    assert all(item["status"] == "MISSING" for item in validation["production_requirements"])
    assert body["requested"]["all_records_processed"] is True


def test_analyze_discloses_fastq_sampling(client, tmp_path):
    r1, _ = _write_fastq(tmp_path, "HG002_R1.fastq.gz", 2001, seed=21)
    r2, _ = _write_fastq(tmp_path, "HG002_R2.fastq.gz", 2001, seed=22)
    response = client.post("/api/ngs/v2/analyze", json={
        "file_paths": [r1, r2], "reference": "grch38", "assay": "WGS",
        "synthetic_reference": True,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["requested"]["record_cap_per_file"] == 2000
    assert body["requested"]["all_records_processed"] is False
    assert sorted(body["requested"]["truncated_files"]) == ["HG002_R1.fastq.gz", "HG002_R2.fastq.gz"]
    assert body["pipeline"]["validation"]["input_sampling"]["mode"] == "SAMPLED_PREVIEW"


def test_analyze_emits_igv_tracks(client, tmp_path):
    r1, _ = _write_fastq(tmp_path, "HUM0001_R1.fastq.gz", 200, seed=7)
    r2, _ = _write_fastq(tmp_path, "HUM0001_R2.fastq.gz", 200, seed=8)
    payload = {
        "file_paths": [r1, r2],
        "reference": "grch38",
        "metadata": {"platform": "illumina"},
        "synthetic_reference": True,
    }
    r = client.post("/api/ngs/v2/analyze", json=payload)
    assert r.status_code == 200
    viz = r.json()["visualization"]

    # SAM track: real aligned_records serialized (read lines, not just headers).
    assert "sam" in viz and viz["sam"].startswith("@HD")
    read_lines = [ln for ln in viz["sam"].splitlines() if not ln.startswith("@")]
    assert read_lines
    assert viz["n_reads"] == len(read_lines)
    assert viz["n_mapped"] > 0

    # VCF track: header present; variant lines carry the real ref/alt columns.
    assert "vcf" in viz and "##fileformat=VCFv4.2" in viz["vcf"]
    var_lines = [ln for ln in viz["vcf"].splitlines() if not ln.startswith("#")]
    if var_lines:
        cols = var_lines[0].split("\t")
        assert len(cols) == 8
    assert viz["n_variants"] == len(var_lines)
    assert viz["locus"]

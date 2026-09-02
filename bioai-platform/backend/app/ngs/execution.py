"""Real nf-core/sarek executor adapters.

No adapter falls back to the exploratory Python pipeline. Disabled or incomplete
infrastructure is reported as unavailable before a job is accepted.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from urllib.parse import urlparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _binary(name: str) -> bool:
    return shutil.which(name) is not None


def executor_capabilities() -> dict[str, Any]:
    local_missing = [name for name in ("nextflow", "java") if not _binary(name)]
    if not (_binary("docker") or _binary("singularity") or _binary("apptainer")):
        local_missing.append("docker, singularity, or apptainer")
    slurm_missing = [name for name in ("nextflow", "java", "sbatch", "sacct") if not _binary(name)]
    aws_missing = [
        name for name, value in (
            ("NGS_AWS_REGION", settings.NGS_AWS_REGION),
            ("NGS_AWS_BATCH_JOB_QUEUE", settings.NGS_AWS_BATCH_JOB_QUEUE),
            ("NGS_AWS_BATCH_JOB_DEFINITION", settings.NGS_AWS_BATCH_JOB_DEFINITION),
        ) if not value
    ]
    try:
        import boto3  # noqa: F401
    except ImportError:
        aws_missing.append("boto3")
    return {
        "workflow": {"name": "nf-core/sarek", "revision": "3.10.0"},
        "executors": {
            "local": {
                "available": settings.NGS_LOCAL_EXECUTION_ENABLED and not local_missing,
                "enabled": settings.NGS_LOCAL_EXECUTION_ENABLED,
                "missing": local_missing,
                "requirements": ["Nextflow", "Java", "Docker/Apptainer/Singularity", "durable local result directory"],
            },
            "slurm": {
                "available": settings.NGS_SLURM_EXECUTION_ENABLED and not slurm_missing,
                "enabled": settings.NGS_SLURM_EXECUTION_ENABLED,
                "missing": slurm_missing,
                "requirements": ["Nextflow head node", "sbatch/sacct", "shared samplesheet/reference/work/result paths"],
            },
            "awsbatch": {
                "available": settings.NGS_AWS_BATCH_EXECUTION_ENABLED and not aws_missing,
                "enabled": settings.NGS_AWS_BATCH_EXECUTION_ENABLED,
                "missing": aws_missing,
                "requirements": ["AWS Batch queue", "Nextflow driver job definition", "IAM role", "S3 inputs/results"],
            },
        },
        "fallback": None,
        "note": "Production executors never fall back to the exploratory preview.",
    }


def _require(executor: str) -> None:
    capability = executor_capabilities()["executors"][executor]
    if not capability["available"]:
        reasons = list(capability["missing"])
        if not capability["enabled"]:
            reasons.insert(0, f"NGS_{'AWS_BATCH' if executor == 'awsbatch' else executor.upper()}_EXECUTION_ENABLED")
        raise RuntimeError("executor unavailable: " + ", ".join(reasons))


def _run_dir(run_id: str) -> Path:
    path = Path(settings.NGS_RUN_ROOT).resolve() / run_id
    path.mkdir(parents=True, exist_ok=False)
    return path


def submit_run(executor: str, command_argv: list[str], outdir: str, user_id: str) -> dict[str, Any]:
    if executor not in {"local", "slurm", "awsbatch"}:
        raise ValueError(f"unsupported executor: {executor}")
    _require(executor)
    if executor == "local" and "-profile" in command_argv:
        profile_index = command_argv.index("-profile") + 1
        profile = command_argv[profile_index] if profile_index < len(command_argv) else ""
        runtime = {"docker": "docker", "singularity": "singularity", "apptainer": "apptainer"}.get(profile)
        if runtime and not _binary(runtime):
            raise RuntimeError(f"executor unavailable: selected {runtime} runtime is not installed")
    run_id = str(uuid.uuid4())
    submitted_at = _now()

    if executor == "local":
        run_dir = _run_dir(run_id)
        status_path = run_dir / "status.json"
        log_path = run_dir / "nextflow.log"
        worker_path = Path(__file__).with_name("nextflow_worker.py")
        process = subprocess.Popen(
            [sys.executable, str(worker_path), str(status_path), str(log_path), *command_argv],
            cwd=str(run_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )
        executor_job_id = str(process.pid)
    elif executor == "slurm":
        run_dir = _run_dir(run_id)
        script_path = run_dir / "launch.sh"
        import shlex
        script_path.write_text("#!/bin/sh\nset -eu\n" + shlex.join(command_argv) + "\n", encoding="utf-8")
        script_path.chmod(0o700)
        result = subprocess.run(["sbatch", "--parsable", str(script_path)], capture_output=True, text=True, timeout=30, check=True)
        executor_job_id = result.stdout.strip().split(";")[0]
    else:
        import boto3
        client = boto3.client("batch", region_name=settings.NGS_AWS_REGION)
        response = client.submit_job(
            jobName=f"bionexus-sarek-{run_id[:8]}",
            jobQueue=settings.NGS_AWS_BATCH_JOB_QUEUE,
            jobDefinition=settings.NGS_AWS_BATCH_JOB_DEFINITION,
            containerOverrides={"command": command_argv, "environment": [{"name": "BIONEXUS_RUN_ID", "value": run_id}]},
            tags={"BioNexusRunId": run_id, "Workflow": "nf-core-sarek-3.10.0"},
        )
        executor_job_id = response["jobId"]

    record = {
        "run_id": run_id, "state": "SUBMITTED", "executor": executor,
        "executor_job_id": executor_job_id, "workflow": "nf-core/sarek", "revision": "3.10.0",
        "outdir": outdir, "submitted_at": submitted_at, "updated_at": submitted_at,
        "exit_code": None, "message": None, "user_id": user_id,
    }
    _persist_record(record)
    return record


def _record_path(run_id: str) -> Path:
    root = Path(settings.NGS_RUN_ROOT).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{run_id}.json"


def _persist_record(record: dict[str, Any]) -> None:
    path = _record_path(record["run_id"])
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
    try:
        from app.services.supabase import get_supabase
        get_supabase().table("ngs_production_runs").upsert(record, on_conflict="run_id").execute()
    except Exception:
        # The executor-local record keeps self-hosted operation functional; hosted
        # deployments should apply migration 011 for durable cross-restart status.
        pass


def _load_record(run_id: str, user_id: str) -> dict[str, Any]:
    if not run_id or any(char not in "0123456789abcdef-" for char in run_id.lower()):
        raise FileNotFoundError(run_id)
    try:
        from app.services.supabase import get_supabase
        rows = get_supabase().table("ngs_production_runs").select("*").eq("run_id", run_id).eq("user_id", user_id).execute().data
        if rows:
            return dict(rows[0])
    except Exception:
        pass
    path = _record_path(run_id)
    if not path.is_file():
        raise FileNotFoundError(run_id)
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("user_id") != user_id:
        raise FileNotFoundError(run_id)
    return record


def get_run(run_id: str, user_id: str) -> dict[str, Any]:
    record = _load_record(run_id, user_id)
    executor = record["executor"]
    try:
        if executor == "local":
            status_path = Path(settings.NGS_RUN_ROOT).resolve() / run_id / "status.json"
            if status_path.is_file():
                status = json.loads(status_path.read_text(encoding="utf-8"))
                record.update({key: status.get(key) for key in ("state", "exit_code", "message")})
        elif executor == "slurm":
            result = subprocess.run(
                ["sacct", "-j", record["executor_job_id"], "--noheader", "--parsable2", "--format=State,ExitCode"],
                capture_output=True, text=True, timeout=20, check=True,
            )
            line = next((line for line in result.stdout.splitlines() if line.strip()), "")
            raw_state, _, exit_code = line.partition("|")
            record["state"] = _slurm_state(raw_state)
            record["exit_code"] = int(exit_code.split(":")[0]) if exit_code else None
        else:
            import boto3
            client = boto3.client("batch", region_name=settings.NGS_AWS_REGION)
            jobs = client.describe_jobs(jobs=[record["executor_job_id"]]).get("jobs", [])
            if jobs:
                job = jobs[0]
                record["state"] = _aws_state(job.get("status", "UNKNOWN"))
                record["exit_code"] = job.get("container", {}).get("exitCode")
                record["message"] = job.get("statusReason")
    except Exception as exc:
        record["message"] = f"Status refresh failed: {type(exc).__name__}"
    record["updated_at"] = _now()
    _persist_record(record)
    return record


def _slurm_state(state: str) -> str:
    state = state.upper().split()[0] if state else "UNKNOWN"
    if state in {"PENDING", "CONFIGURING"}: return "PENDING"
    if state in {"RUNNING", "COMPLETING"}: return "RUNNING"
    if state == "COMPLETED": return "SUCCEEDED"
    if state in {"FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL"}: return "FAILED"
    return "UNKNOWN"


def _aws_state(state: str) -> str:
    return {"SUBMITTED": "SUBMITTED", "PENDING": "PENDING", "RUNNABLE": "PENDING", "STARTING": "PENDING", "RUNNING": "RUNNING", "SUCCEEDED": "SUCCEEDED", "FAILED": "FAILED"}.get(state, "UNKNOWN")


def artifact_manifest(run_id: str, user_id: str) -> dict[str, Any]:
    """Inventory actual output objects; never synthesize missing artifact evidence."""
    record = _load_record(run_id, user_id)
    outdir = record["outdir"]
    if outdir.startswith("s3://"):
        parsed = urlparse(outdir)
        import boto3
        client = boto3.client("s3", region_name=settings.NGS_AWS_REGION or None)
        paginator = client.get_paginator("list_objects_v2")
        files = [
            f"s3://{parsed.netloc}/{item['Key']}"
            for page in paginator.paginate(Bucket=parsed.netloc, Prefix=parsed.path.lstrip("/"))
            for item in page.get("Contents", [])
        ]
    else:
        root = Path(outdir).resolve()
        if not root.is_dir():
            files = []
        else:
            files = [str(path) for path in root.rglob("*") if path.is_file()]

    lower = {path: path.lower() for path in files}
    groups = {
        "execution": [path for path, value in lower.items() if "pipeline_info/execution_" in value],
        "multiqc": [path for path, value in lower.items() if "multiqc" in value],
        "alignment": [path for path, value in lower.items() if value.endswith((".bam", ".cram", ".bai", ".crai"))],
        "small_variants": [path for path, value in lower.items() if value.endswith((".vcf.gz", ".vcf.gz.tbi", ".g.vcf.gz", ".g.vcf.gz.tbi"))],
        "coverage": [path for path, value in lower.items() if "mosdepth" in value or "coverage" in value],
        "identity_qc": [path for path, value in lower.items() if any(token in value for token in ("contamination", "fingerprint", "verifybamid", "sex"))],
        "provenance": [path for path, value in lower.items() if value.endswith(("run_manifest.json", "checksums.sha256"))],
    }
    missing = [name for name, evidence in groups.items() if not evidence]
    return {
        "run_id": run_id, "workflow": record["workflow"], "revision": record["revision"],
        "source": outdir, "observed_file_count": len(files), "groups": groups,
        "required_groups_complete": not missing, "missing_groups": missing,
        "claim": "Observed artifact inventory only; presence does not imply QC or clinical validity.",
    }

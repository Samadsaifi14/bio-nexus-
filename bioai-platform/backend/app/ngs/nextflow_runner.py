"""Docker-backed Nextflow runner for the BioNexus NGS workflow.

Provenance contract
-------------------
A run is described as a Nextflow execution only when the ``nextflow run``
process produced a Nextflow trace and exited successfully. Before that evidence
exists the run is reported as SUBMITTED/RUNNING, never as a completed Nextflow
execution. If Docker, the daemon or the tool image is unavailable the API fails
closed with an explanatory 503 instead of silently falling back to the
exploratory Python preview.

The workflow definition lives in ``app/ngs/workflows/ngs-variant-calling`` and is
shipped with the backend so the executed definition is always auditable.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import settings

WORKFLOW_ID = "bionexus-ngs-variant-calling"
WORKFLOW_NAME = "bionexus/ngs-variant-calling"
DEFAULT_IMAGE = os.getenv("NGS_NEXTFLOW_IMAGE", "bionexus/ngs-tools:1.0")

WORKFLOW_DIR = Path(__file__).resolve().with_name("workflows") / "ngs-variant-calling"
EVIDENCE_DIR = Path(__file__).resolve().with_name("nextflow_evidence")

RUN_ID_PATTERN = re.compile(r"^[0-9a-f-]{36}$")

PROCESSES = [
    "INDEX_REFERENCE",
    "SORT_BAM",
    "INDEX_BAM",
    "CALL_VARIANTS",
    "FILTER_VARIANTS",
    "VARIANT_METRICS",
    "EVALUATE_TRUTH",
]

FIXTURES: dict[str, dict[str, Any]] = {
    "tiny-positive-control": {
        "label": "Tiny synthetic positive control",
        "description": "20 x 100 bp reads over a 200 bp reference with one declared heterozygous SNP (chrTiny:50 C>G, 0/1, DP 20).",
        "reference": "fixtures/reference.fa",
        "sam": "fixtures/reads.sam",
        "truth": "fixtures/truth.tsv",
        "expected_snp": "chrTiny:50 C>G (0/1)",
        "classification": "SYNTHETIC_POSITIVE_CONTROL",
    },
}

_REQUIRED_ARTIFACTS = {"trace", "report", "dag", "calls_vcf", "calls_tsv", "metrics", "benchmark"}

ARTIFACT_SPECS: list[dict[str, Any]] = [
    {"id": "trace", "label": "Nextflow trace", "path": "results/pipeline_info/trace.txt", "category": "execution", "media_type": "text/plain", "required": True},
    {"id": "report", "label": "Nextflow report", "path": "results/pipeline_info/report.html", "category": "execution", "media_type": "text/html", "required": True},
    {"id": "dag", "label": "Nextflow DAG", "path": "results/pipeline_info/dag.html", "category": "execution", "media_type": "text/html", "required": True},
    {"id": "timeline", "label": "Nextflow timeline", "path": "results/pipeline_info/timeline.html", "category": "execution", "media_type": "text/html", "required": False},
    {"id": "calls_vcf", "label": "Filtered calls (VCF)", "path": "results/variants/calls.vcf", "category": "variants", "media_type": "text/vcf", "required": True},
    {"id": "calls_tsv", "label": "Call table (TSV)", "path": "results/variants/calls.tsv", "category": "variants", "media_type": "text/tab-separated-values", "required": True},
    {"id": "raw_vcf", "label": "Raw calls before filtering (VCF)", "path": "results/variants/raw.vcf", "category": "variants", "media_type": "text/vcf", "required": False},
    {"id": "metrics", "label": "Run metrics", "path": "results/metrics/metrics.json", "category": "metrics", "media_type": "application/json", "required": True},
    {"id": "benchmark", "label": "Truth concordance", "path": "results/benchmark/benchmark.json", "category": "metrics", "media_type": "application/json", "required": True},
    {"id": "bam", "label": "Sorted alignment (BAM)", "path": "results/alignment/reads.bam", "category": "alignment", "media_type": "application/octet-stream", "required": False},
    {"id": "bam_index", "label": "BAM index", "path": "results/alignment/reads.bam.bai", "category": "alignment", "media_type": "application/octet-stream", "required": False},
    {"id": "container_log", "label": "nextflow run log (stdout/stderr)", "path": "nextflow.log", "category": "execution", "media_type": "text/plain", "required": False},
    {"id": "nextflow_log", "label": "Nextflow internal log", "path": ".nextflow.log", "category": "execution", "media_type": "text/plain", "required": False},
    {"id": "run_meta", "label": "Run metadata", "path": "run_meta.json", "category": "provenance", "media_type": "application/json", "required": False},
]

EVIDENCE_FILE_LABELS = {
    "calls.vcf": ("Filtered calls (VCF)", "text/vcf"),
    "calls.tsv": ("Call table (TSV)", "text/tab-separated-values"),
    "metrics.json": ("Run metrics", "application/json"),
    "benchmark.json": ("Truth concordance", "application/json"),
    "trace.txt": ("Nextflow trace", "text/plain"),
    "report.html": ("Nextflow report", "text/html"),
    "dag.html": ("Nextflow DAG", "text/html"),
    "timeline.html": ("Nextflow timeline", "text/html"),
    "container.log": ("nextflow run log (stdout/stderr)", "text/plain"),
    "nextflow.log": ("Nextflow internal log", "text/plain"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _binary(name: str) -> bool:
    return shutil.which(name) is not None


def _run(argv: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)


@lru_cache(maxsize=1)
def workflow_revision() -> str:
    digest = hashlib.sha256()
    for path in sorted(
        [
            WORKFLOW_DIR / "main.nf",
            WORKFLOW_DIR / "nextflow.config",
            WORKFLOW_DIR / "bin" / "compute_metrics.py",
            WORKFLOW_DIR / "bin" / "evaluate_truth.py",
        ]
    ):
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def _image_metadata(image: str) -> dict[str, Any] | None:
    completed = _run(["docker", "image", "inspect", image, "--format", "{{json .}}"])
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    digests = data.get("RepoDigests") or []
    return {"id": data.get("Id"), "digest": digests[0] if digests else None, "size": data.get("Size")}


def _engine_versions(image: str) -> dict[str, str]:
    script = (
        "nextflow -version 2>&1 | awk '/version/{print \"nextflow=\" $2; exit}'; "
        "samtools --version | awk 'NR==1{print \"samtools=\" $2}'; "
        "bcftools --version | awk 'NR==1{print \"bcftools=\" $2}'"
    )
    completed = _run(["docker", "run", "--rm", image, "bash", "-lc", script], timeout=120)
    versions: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        key, _, value = line.strip().partition("=")
        if key in {"nextflow", "samtools", "bcftools"} and value:
            versions[key] = value
    return versions


def capabilities() -> dict[str, Any]:
    """Report the honest execution capability of this deployment."""
    missing: list[str] = []
    docker_cli = _binary("docker")
    daemon_ok = False
    image_meta: dict[str, Any] | None = None
    versions: dict[str, str] = {}

    if not docker_cli:
        missing.append("docker CLI")
    else:
        info = _run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=20)
        daemon_ok = info.returncode == 0 and bool(info.stdout.strip())
        if not daemon_ok:
            missing.append("Docker daemon")
        else:
            image_meta = _image_metadata(DEFAULT_IMAGE)
            if image_meta is None:
                missing.append(f"tool image {DEFAULT_IMAGE}")
            else:
                versions = _engine_versions(DEFAULT_IMAGE)

    workflow_present = (WORKFLOW_DIR / "main.nf").is_file()
    if not workflow_present:
        missing.append("workflow definition")

    available = not missing
    reason = None
    if missing:
        reason = (
            "The Nextflow Docker runner is unavailable on this deployment: "
            + ", ".join(missing)
            + ". Build it from app/ngs/workflows/ngs-variant-calling/Dockerfile and start Docker."
        )

    return {
        "workflow_id": WORKFLOW_ID,
        "workflow": {
            "name": WORKFLOW_NAME,
            "revision": workflow_revision(),
            "definition": "app/ngs/workflows/ngs-variant-calling/main.nf",
            "processes": PROCESSES,
            "truth_control": True,
        },
        "engine": {
            "name": "Nextflow",
            "version": versions.get("nextflow"),
            "tool_versions": {key: versions[key] for key in ("samtools", "bcftools") if key in versions},
            "container_image": DEFAULT_IMAGE,
            "container_digest": image_meta.get("digest") if image_meta else None,
            "executor": "local (Docker)",
        },
        "fixtures": [
            {
                "id": fixture_id,
                **{key: value for key, value in fixture.items() if key not in {"reference", "sam", "truth"}},
            }
            for fixture_id, fixture in FIXTURES.items()
        ],
        "parameters": {
            "min_qual": {"default": 20, "minimum": 0, "maximum": 1000},
            "min_dp": {"default": 10, "minimum": 0, "maximum": 10000},
            "threads": {"default": 1, "minimum": 1, "maximum": 8},
        },
        "executor": {
            "name": "local-docker",
            "available": available,
            "missing": missing,
            "requirements": [
                "Docker CLI and running daemon",
                f"tool image {DEFAULT_IMAGE}",
                "workflow definition packaged with the backend",
            ],
            "reason": reason,
        },
        "claim": (
            "A run is labelled as a Nextflow execution only when nextflow run exited 0 and "
            "produced a Nextflow trace. Presence of files alone does not imply biological or clinical validity."
        ),
    }


def _run_dir(run_id: str) -> Path:
    return Path(settings.NGS_RUN_ROOT).resolve() / "nextflow" / run_id


def _record_path(run_id: str) -> Path:
    return _run_dir(run_id) / "run_meta.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _persist(record: dict[str, Any]) -> None:
    _write_json(_record_path(record["run_id"]), record)
    try:
        from app.services.supabase import get_supabase

        get_supabase().table("ngs_nextflow_runs").upsert(record, on_conflict="run_id").execute()
    except Exception:
        # The executor-local record keeps self-hosted operation functional. The
        # hosted Space cannot execute Docker, so this table is optional.
        pass


def _load_record(run_id: str, user_id: str) -> dict[str, Any]:
    if not RUN_ID_PATTERN.match(run_id or ""):
        raise FileNotFoundError(run_id)
    path = _record_path(run_id)
    if not path.is_file():
        raise FileNotFoundError(run_id)
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("user_id") != user_id:
        raise FileNotFoundError(run_id)
    return record


def _docker_command(*, run_dir: Path, min_qual: float, min_dp: int, threads: int) -> list[str]:
    return [
        "docker", "run", "--rm",
        "--name", f"bionexus-nf-{run_dir.name[:8]}",
        "-v", f"{WORKFLOW_DIR}:/opt/workflow:ro",
        "-v", f"{run_dir}:/work",
        "-w", "/work",
        DEFAULT_IMAGE,
        "nextflow", "run", "/opt/workflow/main.nf",
        "-c", "/opt/workflow/nextflow.config",
        "--reference", "/work/inputs/reference.fa",
        "--sam", "/work/inputs/reads.sam",
        "--truth", "/work/inputs/truth.tsv",
        "--outdir", "/work/results",
        "--min_qual", str(min_qual),
        "--min_dp", str(min_dp),
        "--threads", str(threads),
        "-ansi-log", "false",
    ]


def submit_run(
    *,
    user_id: str,
    fixture: str = "tiny-positive-control",
    min_qual: float = 20,
    min_dp: int = 10,
    threads: int = 1,
    sample_name: str | None = None,
) -> dict[str, Any]:
    """Validate and launch a real ``nextflow run`` inside the tool image."""
    if fixture not in FIXTURES:
        raise ValueError(f"unsupported fixture: {fixture}")
    if not 0 <= float(min_qual) <= 1000:
        raise ValueError("min_qual must be between 0 and 1000")
    if not 0 <= int(min_dp) <= 10000:
        raise ValueError("min_dp must be between 0 and 10000")
    if not 1 <= int(threads) <= 8:
        raise ValueError("threads must be between 1 and 8")

    capability = capabilities()
    if not capability["executor"]["available"]:
        raise RuntimeError(capability["executor"]["reason"])

    run_id = str(uuid.uuid4())
    run_dir = _run_dir(run_id)
    inputs_dir = run_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=False)

    selected = FIXTURES[fixture]
    for key, filename in (("reference", "reference.fa"), ("sam", "reads.sam"), ("truth", "truth.tsv")):
        source = WORKFLOW_DIR / selected[key]
        shutil.copyfile(source, inputs_dir / filename)

    parameters = {"min_qual": float(min_qual), "min_dp": int(min_dp), "threads": int(threads)}
    command = _docker_command(run_dir=run_dir, min_qual=min_qual, min_dp=min_dp, threads=threads)
    command_sha256 = hashlib.sha256(
        json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    submitted_at = _now()
    record = {
        "run_id": run_id,
        "state": "SUBMITTED",
        "workflow_id": WORKFLOW_ID,
        "workflow": WORKFLOW_NAME,
        "revision": workflow_revision(),
        "engine": "Nextflow",
        "engine_version": capability["engine"]["version"],
        "container_image": DEFAULT_IMAGE,
        "container_digest": capability["engine"]["container_digest"],
        "executor": "local-docker",
        "fixture": fixture,
        "sample_name": sample_name or f"TINY-{run_id[:8]}",
        "parameters": parameters,
        "outdir": "/work/results",
        "submitted_at": submitted_at,
        "updated_at": submitted_at,
        "exit_code": None,
        "message": None,
        "user_id": user_id,
        "command_sha256": command_sha256,
        "command_argv": command,
        "nextflow_executed": False,
    }
    _write_json(run_dir / "params.json", {"fixture": fixture, **parameters})
    _persist(record)

    worker_path = Path(__file__).with_name("nextflow_worker.py")
    status_path = run_dir / "status.json"
    log_path = run_dir / "nextflow.log"
    subprocess.Popen(
        [sys.executable, str(worker_path), str(status_path), str(log_path), *command],
        cwd=str(run_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return record


def _trace_rows(trace_path: Path) -> list[dict[str, Any]]:
    if not trace_path.is_file():
        return []
    lines = trace_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return []
    header = lines[0].split("\t")
    rows: list[dict[str, Any]] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = line.split("\t")
        row = dict(zip(header, fields))
        if not str(row.get("task_id", "")).strip().isdigit():
            # Older traces included the multi-line task script; continuation
            # lines are not task records.
            continue
        rows.append(
            {
                "task_id": row.get("task_id"),
                "name": row.get("name"),
                "status": row.get("status"),
                "exit": row.get("exit"),
                "realtime": row.get("realtime"),
            }
        )
    return rows


_NEXTFLOW_VERSION_PATTERN = re.compile(r"Nextflow\s+([0-9]+\.[0-9]+\.[0-9]+)", re.IGNORECASE)


def _nextflow_log_version(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    match = _NEXTFLOW_VERSION_PATTERN.search(text)
    return match.group(1) if match else None


def get_run(run_id: str, user_id: str) -> dict[str, Any]:
    record = _load_record(run_id, user_id)
    run_dir = _run_dir(run_id)
    status_path = run_dir / "status.json"
    if status_path.is_file():
        status = json.loads(status_path.read_text(encoding="utf-8"))
        record["state"] = status.get("state", record["state"])
        record["exit_code"] = status.get("exit_code")
        record["message"] = status.get("message")
        record["updated_at"] = status.get("updated_at") or record["updated_at"]

    trace_path = run_dir / "results" / "pipeline_info" / "trace.txt"
    nextflow_log = run_dir / ".nextflow.log"
    trace_rows = _trace_rows(trace_path)
    nextflow_executed = bool(trace_rows) and record.get("state") == "SUCCEEDED"
    record["nextflow_executed"] = nextflow_executed
    record["engine_version"] = _nextflow_log_version(nextflow_log) or record.get("engine_version")
    record["processes"] = trace_rows
    record["process_count"] = len(trace_rows)
    record["artifacts_ready"] = trace_path.is_file()
    record["evidence"] = {
        "trace": "results/pipeline_info/trace.txt",
        "dag": "results/pipeline_info/dag.html",
        "report": "results/pipeline_info/report.html",
    }
    _persist(record)
    return record


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_manifest(run_id: str, user_id: str) -> dict[str, Any]:
    record = _load_record(run_id, user_id)
    run_dir = _run_dir(run_id)
    artifacts: list[dict[str, Any]] = []
    for spec in ARTIFACT_SPECS:
        path = run_dir / spec["path"]
        present = path.is_file()
        artifacts.append(
            {
                "id": spec["id"],
                "label": spec["label"],
                "category": spec["category"],
                "media_type": spec["media_type"],
                "required": spec["required"],
                "path": spec["path"],
                "present": present,
                "bytes": path.stat().st_size if present else None,
                "sha256": _sha256(path) if present and path.stat().st_size <= 50 * 1024 * 1024 else None,
                "download_url": f"/api/ngs/v2/nextflow/runs/{run_id}/artifacts/{spec['id']}" if present else None,
            }
        )
    by_id = {item["id"]: item for item in artifacts}
    missing_required = sorted(
        artifact_id for artifact_id in _REQUIRED_ARTIFACTS if not by_id[artifact_id]["present"]
    )
    return {
        "run_id": run_id,
        "workflow": record["workflow"],
        "revision": record["revision"],
        "state": record["state"],
        "nextflow_executed": bool(record.get("nextflow_executed")),
        "source": "executor run directory",
        "observed_file_count": sum(1 for item in artifacts if item["present"]),
        "artifacts": artifacts,
        "required_complete": not missing_required,
        "missing_required": missing_required,
        "claim": (
            "Observed artifact inventory only. A present VCF is not proof of biological or clinical validity."
        ),
    }


def artifact_path(run_id: str, user_id: str, artifact_id: str) -> tuple[Path, dict[str, Any]]:
    _load_record(run_id, user_id)
    spec = next((item for item in ARTIFACT_SPECS if item["id"] == artifact_id), None)
    if spec is None:
        raise KeyError(artifact_id)
    run_root = _run_dir(run_id).resolve()
    path = (run_root / spec["path"]).resolve()
    if run_root not in path.parents or not path.is_file():
        raise FileNotFoundError(artifact_id)
    return path, spec


def evidence_report() -> dict[str, Any]:
    manifest_path = EVIDENCE_DIR / "manifest.json"
    if not manifest_path.is_file():
        return {"available": False, "reason": "No committed Nextflow evidence run is packaged with this backend."}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    inline: dict[str, Any] = {}
    for name in ("metrics.json", "benchmark.json"):
        path = EVIDENCE_DIR / name
        if path.is_file():
            try:
                inline[name] = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
    calls_path = EVIDENCE_DIR / "calls.tsv"
    if calls_path.is_file():
        inline["calls.tsv"] = calls_path.read_text(encoding="utf-8")
    manifest["inline"] = inline
    manifest["available"] = True
    return manifest


def evidence_file(name: str) -> tuple[Path, str]:
    manifest_path = EVIDENCE_DIR / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(name)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files", {})
    if name not in files:
        raise FileNotFoundError(name)
    path = (EVIDENCE_DIR / name).resolve()
    if EVIDENCE_DIR.resolve() not in path.parents or not path.is_file():
        raise FileNotFoundError(name)
    label, media_type = EVIDENCE_FILE_LABELS.get(name, (name, "application/octet-stream"))
    return path, files[name].get("media_type", media_type)


def export_evidence(run_id: str, user_id: str, *, note: str | None = None) -> dict[str, Any]:
    """Copy a completed local run into the packaged evidence directory.

    This is an operator action, not something a user request triggers. The
    resulting manifest is committed so the hosted UI can display a real
    executed run even where Docker is unavailable.
    """
    record = get_run(run_id, user_id)
    if record.get("state") != "SUCCEEDED" or not record.get("nextflow_executed"):
        raise RuntimeError("only a SUCCEEDED run with a Nextflow trace can be exported")

    run_dir = _run_dir(run_id)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    copies = {
        "calls.vcf": run_dir / "results" / "variants" / "calls.vcf",
        "calls.tsv": run_dir / "results" / "variants" / "calls.tsv",
        "metrics.json": run_dir / "results" / "metrics" / "metrics.json",
        "benchmark.json": run_dir / "results" / "benchmark" / "benchmark.json",
        "trace.txt": run_dir / "results" / "pipeline_info" / "trace.txt",
        "report.html": run_dir / "results" / "pipeline_info" / "report.html",
        "dag.html": run_dir / "results" / "pipeline_info" / "dag.html",
        "timeline.html": run_dir / "results" / "pipeline_info" / "timeline.html",
        "container.log": run_dir / "nextflow.log",
        "nextflow.log": run_dir / ".nextflow.log",
    }
    files: dict[str, Any] = {}
    for name, source in copies.items():
        if not source.is_file():
            continue
        target = EVIDENCE_DIR / name
        shutil.copyfile(source, target)
        label, media_type = EVIDENCE_FILE_LABELS.get(name, (name, "application/octet-stream"))
        files[name] = {
            "label": label,
            "media_type": media_type,
            "bytes": target.stat().st_size,
            "sha256": _sha256(target),
            "download_url": f"/api/ngs/v2/nextflow/evidence/files/{name}",
        }

    metrics = json.loads((EVIDENCE_DIR / "metrics.json").read_text(encoding="utf-8"))
    benchmark = json.loads((EVIDENCE_DIR / "benchmark.json").read_text(encoding="utf-8"))
    fixture = FIXTURES.get(record.get("fixture", ""), {})
    raw_command = record.get("command_argv") or []
    container_image = record.get("container_image")
    # Commit only the container-side command, not host mount paths.
    command = raw_command[raw_command.index(container_image) + 1:] if container_image in raw_command else raw_command
    manifest = {
        "workflow_id": WORKFLOW_ID,
        "workflow": WORKFLOW_NAME,
        "revision": record["revision"],
        "generated_at": _now(),
        "execution": {
            "engine": "Nextflow",
            "engine_version": record.get("engine_version"),
            "executor": "local Docker (Nextflow local executor inside the tool image)",
            "container_image": record.get("container_image"),
            "container_digest": record.get("container_digest"),
            "state": record.get("state"),
            "exit_code": record.get("exit_code"),
            "nextflow_executed": True,
            "command_sha256": record.get("command_sha256"),
            "command": command,
            "evidence_note": note
            or "Executed on the development workstation; the hosted backend reports the runner as unavailable and serves this committed evidence.",
        },
        "fixture": {
            "id": record.get("fixture"),
            "label": fixture.get("label"),
            "classification": fixture.get("classification"),
            "expected_snp": fixture.get("expected_snp"),
        },
        "parameters": record.get("parameters"),
        "result": {
            "called_variants": metrics.get("called_variants"),
            "mean_depth": metrics.get("mean_depth"),
            "mapped_reads": metrics.get("mapped_reads"),
            "reference_length": metrics.get("reference_length"),
            "tp": benchmark.get("tp"),
            "fp": benchmark.get("fp"),
            "fn": benchmark.get("fn"),
            "precision": benchmark.get("precision"),
            "recall": benchmark.get("recall"),
            "f1": benchmark.get("f1"),
            "normalized_calls_sha256": benchmark.get("normalized_calls_sha256"),
        },
        "tool_versions": metrics.get("tool_versions"),
        "processes": record.get("processes"),
        "files": files,
        "claim": (
            "This evidence records an actual Nextflow run that exited successfully and produced a trace. "
            "It is a synthetic positive control; it does not establish real-sample accuracy, clinical validity, "
            "or parity with nf-core/sarek as a whole."
        ),
    }
    _write_json(EVIDENCE_DIR / "manifest.json", manifest)
    return manifest

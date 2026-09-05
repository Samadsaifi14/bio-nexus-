"""Scientific experiment manager and reproducibility ledger.

Every analysis becomes an immutable experiment with a human-readable ID and a
write-once reproducibility fingerprint.  Version lineage, checksums, archival
metadata, comparison and DOI-ready metadata are handled here so every result can
be traced back to the exact code, environment, parameters and inputs that made it.

Persistence is best-effort: scientific pipelines must not crash merely because a
metadata table is temporarily unavailable.  Failures are logged and callers can
surface degraded provenance explicitly.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import subprocess
import uuid
from datetime import datetime, timezone
from importlib import metadata
from typing import Any

from app.services.supabase import get_supabase

logger = logging.getLogger(__name__)

FINGERPRINTED_PACKAGES = [
    "fastapi", "supabase", "httpx", "pydantic", "biopython", "numpy",
    "openmm", "pytest", "litellm", "matplotlib",
]

KNOWN_DATABASE_RELEASES: dict[str, str] = {}

TRACKED_TOOLS = {
    "blast": {"tool": "BLAST (EBI/NCBI)", "database": "swissprot"},
    "uniprot": {"tool": "UniProt API", "database": "UniProtKB"},
    "interpro": {"tool": "InterProScan", "database": "InterPro"},
    "go": {"tool": "QuickGO", "database": "Gene Ontology"},
    "reactome": {"tool": "Reactome", "database": "Reactome Pathways"},
    "alphafold": {"tool": "AlphaFold DB", "database": "AlphaFold"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: Any) -> str:
    """Stable JSON used for checksums across Python/process boundaries."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _git_commit() -> str | None:
    """Best-effort HEAD commit SHA of the repository the worker is running from."""
    for root in ("/app", "/workspace", "."):
        try:
            out = subprocess.run(
                ["git", "-C", root, "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=5,
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except Exception:
            continue
    # Vercel/Railway/Render commonly expose the deployment commit this way.
    return os.getenv("VERCEL_GIT_COMMIT_SHA") or os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("RENDER_GIT_COMMIT")


def _software_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for pkg in FINGERPRINTED_PACKAGES:
        try:
            versions[pkg] = metadata.version(pkg)
        except Exception:
            versions[pkg] = "unknown"
    return versions


def _environment() -> dict:
    env: dict[str, str | int] = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "os": platform.system(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count() or 0,
    }
    try:
        if os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal"):
                        env["ram_mb"] = int(line.split()[1]) // 1024
                        break
    except Exception:
        pass
    env["hostname"] = os.uname().nodename if hasattr(os, "uname") else platform.node()
    for key in ("CUDA_VISIBLE_DEVICES", "NVIDIA_VISIBLE_DEVICES"):
        if os.getenv(key):
            env[key.lower()] = os.getenv(key) or ""
    return env


def _container_hash() -> str | None:
    """Best-effort container/runtime identifier; prefer an explicit immutable image digest."""
    explicit = os.getenv("CONTAINER_IMAGE_DIGEST") or os.getenv("IMAGE_DIGEST")
    if explicit:
        return explicit
    marker: str | None = None
    try:
        if os.path.exists("/.dockerenv"):
            marker = os.getenv("HOSTNAME") or "docker"
        elif os.path.exists("/proc/1/cgroup"):
            with open("/proc/1/cgroup", encoding="utf-8") as f:
                marker = f.read(1024)
    except Exception:
        marker = None
    return hashlib.sha256(marker.encode()).hexdigest() if marker else None


def _input_sha256(sequence: str) -> str:
    return hashlib.sha256(sequence.strip().upper().encode()).hexdigest()


def deterministic_seed(sequence: str, parameters: dict | None = None) -> int:
    payload = sequence.strip().upper() + _canonical_json(parameters or {})
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], "big") & 0x7FFFFFFFFFFFFFFF


def make_experiment_id() -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"BNX-{today}-{uuid.uuid4().hex[:8]}"


def build_fingerprint(sequence: str, parameters: dict | None = None) -> dict:
    """Assemble the full reproducibility fingerprint for an experiment."""
    params = parameters or {}
    fp = {
        "input_hash": _input_sha256(sequence),
        "git_commit": _git_commit(),
        "software_versions": _software_versions(),
        "container_hash": _container_hash(),
        "database_versions": dict(KNOWN_DATABASE_RELEASES),
        "environment": _environment(),
        "random_seed": deterministic_seed(sequence, params),
        "parameters": params,
        "captured_at_utc": utc_now(),
    }
    fp["fingerprint_hash"] = sha256_json(fp)
    return fp


def _find_by_experiment_id(experiment_id: str) -> dict | None:
    try:
        resp = get_supabase().table("experiments").select("*").eq("experiment_id", experiment_id).limit(1).execute()
        return resp.data[0] if resp.data else None
    except Exception as exc:
        logger.warning("Experiment lookup failed (%s): %s", experiment_id, exc)
        return None


def begin_experiment(
    job_id: str,
    sequence: str,
    pipeline: str,
    parameters: dict | None = None,
    *,
    parent_experiment_id: str | None = None,
) -> str | None:
    """Register a new experiment and its immutable fingerprint.

    If ``parent_experiment_id`` is supplied, the new run becomes the next
    version in that lineage.  The input checksum is still recomputed and stored
    independently, so cloned experiments cannot silently change their input.
    """
    if not job_id or not sequence:
        return None
    fp = build_fingerprint(sequence, parameters)
    version = 1
    if parent_experiment_id:
        parent = _find_by_experiment_id(parent_experiment_id)
        if parent:
            version = int(parent.get("version") or 1) + 1
    experiment_id = make_experiment_id()
    row = {
        "experiment_id": experiment_id,
        "job_id": job_id,
        "pipeline": pipeline,
        "version": version,
        "parent_experiment_id": parent_experiment_id,
        "input_hash": fp["input_hash"],
        "git_commit": fp["git_commit"],
        "software_versions": fp["software_versions"],
        "container_hash": fp["container_hash"],
        "database_versions": fp["database_versions"],
        "environment": fp["environment"],
        "random_seed": fp["random_seed"],
        "parameters": fp["parameters"],
        "status": "running",
        "started_at": fp["captured_at_utc"],
    }
    try:
        get_supabase().table("experiments").insert(row).execute()
        audit_event(experiment_id, "experiment.created", {
            "version": version,
            "parent_experiment_id": parent_experiment_id,
            "fingerprint_hash": fp["fingerprint_hash"],
        })
        return experiment_id
    except Exception as exc:
        logger.warning("Experiment begin failed (job %s): %s", job_id, exc)
        return None


def _find_experiment(job_id: str) -> dict | None:
    try:
        resp = get_supabase().table("experiments").select("*").eq("job_id", job_id).order("created_at", desc=True).limit(1).execute()
        return resp.data[0] if resp.data else None
    except Exception as exc:
        logger.warning("Experiment lookup failed (job %s): %s", job_id, exc)
        return None


def audit_event(experiment_id: str, event_type: str, payload: dict | None = None) -> None:
    try:
        get_supabase().table("experiment_audit_events").insert({
            "experiment_id": experiment_id,
            "event_type": event_type,
            "payload": payload or {},
        }).execute()
    except Exception as exc:
        logger.warning("Experiment audit event degraded (%s/%s): %s", experiment_id, event_type, exc)


def finalize_experiment(job_id: str, status: str, error: str | None = None, output: Any | None = None) -> None:
    """Finalize without mutating the original fingerprint.

    The canonical SHA-256 of the final structured output is recorded whenever
    an output is supplied.  This lets users prove that two exported results are
    byte-semantically identical even when formatting differs.
    """
    exp = _find_experiment(job_id)
    if not exp:
        return
    try:
        payload: dict[str, Any] = {"status": status, "finished_at": utc_now()}
        if error:
            payload["error"] = error
        if output is not None:
            payload["output_hash"] = sha256_json(output)
        get_supabase().table("experiments").update(payload).eq("id", exp["id"]).execute()
        audit_event(exp["experiment_id"], "experiment.finalized", {
            "status": status,
            "output_hash": payload.get("output_hash"),
            "has_error": bool(error),
        })
    except Exception as exc:
        logger.warning("Experiment finalize failed (job %s): %s", job_id, exc)


def provenance_for_experiment(experiment_id: str) -> list[dict]:
    try:
        resp = get_supabase().table("experiment_steps").select("*").eq("experiment_id", experiment_id).order("completed_at").execute()
        return resp.data or []
    except Exception as exc:
        logger.warning("Provenance lookup degraded (%s): %s", experiment_id, exc)
        return []


def get_experiment(job_id: str) -> dict | None:
    exp = _find_experiment(job_id)
    if not exp:
        return None
    exp["provenance"] = provenance_for_experiment(exp["experiment_id"])
    return exp


def get_experiment_by_id(experiment_id: str) -> dict | None:
    exp = _find_by_experiment_id(experiment_id)
    if not exp:
        return None
    exp["provenance"] = provenance_for_experiment(experiment_id)
    return exp


def search_experiments(*, query: str | None = None, pipeline: str | None = None,
                       status: str | None = None, limit: int = 50) -> list[dict]:
    """Server-side experiment search over identifiers, pipeline and status."""
    limit = min(max(limit, 1), 200)
    sb = get_supabase()
    q = sb.table("experiments").select("*").order("created_at", desc=True).limit(limit)
    if pipeline:
        q = q.eq("pipeline", pipeline)
    if status:
        q = q.eq("status", status)
    if query:
        safe = query.replace(",", " ").strip()
        q = q.or_(f"experiment_id.ilike.%{safe}%,pipeline.ilike.%{safe}%,git_commit.ilike.%{safe}%")
    return q.execute().data or []


def compare_experiments(left: dict, right: dict) -> dict:
    """Deterministic field-level comparison suitable for UI and publication appendices."""
    fields = [
        "pipeline", "version", "input_hash", "output_hash", "git_commit",
        "container_hash", "database_versions", "software_versions", "environment",
        "random_seed", "parameters", "status",
    ]
    differences = {}
    for field in fields:
        if left.get(field) != right.get(field):
            differences[field] = {"left": left.get(field), "right": right.get(field)}
    return {
        "left_experiment_id": left.get("experiment_id"),
        "right_experiment_id": right.get("experiment_id"),
        "same_input": left.get("input_hash") == right.get("input_hash"),
        "same_output": bool(left.get("output_hash")) and left.get("output_hash") == right.get("output_hash"),
        "same_code": bool(left.get("git_commit")) and left.get("git_commit") == right.get("git_commit"),
        "difference_count": len(differences),
        "differences": differences,
    }


def archive_manifest(experiment: dict) -> dict:
    """Build a content-addressed manifest for long-term experiment archiving."""
    provenance = experiment.get("provenance") or provenance_for_experiment(experiment["experiment_id"])
    manifest = {
        "schema": "https://bionexus.dev/schemas/experiment-archive/v1",
        "experiment_id": experiment["experiment_id"],
        "version": experiment.get("version", 1),
        "parent_experiment_id": experiment.get("parent_experiment_id"),
        "pipeline": experiment.get("pipeline"),
        "input_sha256": experiment.get("input_hash"),
        "output_sha256": experiment.get("output_hash"),
        "git_commit": experiment.get("git_commit"),
        "container_hash": experiment.get("container_hash"),
        "software_versions": experiment.get("software_versions") or {},
        "database_versions": experiment.get("database_versions") or {},
        "environment": experiment.get("environment") or {},
        "random_seed": experiment.get("random_seed"),
        "parameters": experiment.get("parameters") or {},
        "started_at": experiment.get("started_at"),
        "finished_at": experiment.get("finished_at"),
        "provenance": provenance,
        "generated_at_utc": utc_now(),
    }
    manifest["manifest_sha256"] = sha256_json(manifest)
    return manifest


def persist_archive(job_id: str) -> dict | None:
    exp = get_experiment(job_id)
    if not exp:
        return None
    manifest = archive_manifest(exp)
    try:
        get_supabase().table("experiments").update({
            "archive_manifest": manifest,
            "archived_at": utc_now(),
        }).eq("id", exp["id"]).execute()
        audit_event(exp["experiment_id"], "experiment.archived", {"manifest_sha256": manifest["manifest_sha256"]})
    except Exception as exc:
        logger.warning("Archive persistence degraded (%s): %s", job_id, exc)
    return manifest


def doi_export_metadata(experiment: dict, *, title: str | None = None,
                        creators: list[dict] | None = None) -> dict:
    """Zenodo/DataCite-ready metadata.  This does not mint a DOI by itself."""
    metadata_payload = {
        "metadata": {
            "title": title or f"BioNexus experiment {experiment['experiment_id']}",
            "upload_type": "dataset",
            "description": "Reproducible BioNexus computational experiment archive.",
            "creators": creators or [{"name": "BioNexus user"}],
            "keywords": ["BioNexus", "bioinformatics", "reproducibility", experiment.get("pipeline") or "analysis"],
            "version": str(experiment.get("version") or 1),
            "related_identifiers": ([{
                "identifier": experiment.get("git_commit"),
                "relation": "isSupplementTo",
                "resource_type": "software",
            }] if experiment.get("git_commit") else []),
        },
        "experiment_id": experiment["experiment_id"],
        "manifest_sha256": archive_manifest(experiment)["manifest_sha256"],
        "generated_at_utc": utc_now(),
    }
    return metadata_payload

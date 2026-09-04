"""Milestone 1 — Experiment Manager.

Every analysis becomes an experiment with an immutable experiment ID and a
one-time-written fingerprint: git commit, software versions, container hash,
database release, environment (CPU/RAM/OS), random seed and parameter snapshot.

All persistence is best-effort and never raises into the calling pipeline: if
the experiments table is missing or Supabase is unreachable, a warning is logged
and the run continues (same philosophy as _capture_run_sources).
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import subprocess
import uuid
from datetime import datetime, timezone
from importlib import metadata

from app.services.supabase import get_supabase

logger = logging.getLogger(__name__)

# Packages whose versions make up the software fingerprint.
FINGERPRINTED_PACKAGES = [
    "fastapi", "supabase", "httpx", "pydantic", "biopython", "numpy",
    "openmm", "pytest", "litellm", "matplotlib",
]

# Reference database releases observed for each major namespace.
KNOWN_DATABASE_RELEASES: dict[str, str] = {}

TRACKED_TOOLS = {
    "blast": {"tool": "BLAST (EBI/NCBI)", "database": "swissprot"},
    "uniprot": {"tool": "UniProt API", "database": "UniProtKB"},
    "interpro": {"tool": "InterProScan", "database": "InterPro"},
    "go": {"tool": "QuickGO", "database": "Gene Ontology"},
    "reactome": {"tool": "Reactome", "database": "Reactome Pathways"},
    "alphafold": {"tool": "AlphaFold DB", "database": "AlphaFold"},
}


def _git_commit() -> str | None:
    """Best-effort HEAD commit sha of the repository the worker is running from."""
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
    return None


def _software_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for pkg in FINGERPRINTED_PACKAGES:
        try:
            versions[pkg] = metadata.version(pkg)
        except Exception:
            versions[pkg] = "unknown"
    return versions


def _environment() -> dict:
    """CPU / RAM / OS / Python environment fingerprint."""
    env: dict[str, str | int] = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "os": platform.system(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count() or 0,
    }
    try:
        if os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal"):
                        kb = int(line.split()[1])
                        env["ram_mb"] = kb // 1024
                        break
    except Exception:
        pass
    env["hostname"] = os.uname().nodename if hasattr(os, "uname") else platform.node()
    return env


def _container_hash() -> str | None:
    """A stable pseudo-identifier for the runtime container (best-effort)."""
    if os.path.exists("/.dockerenv"):
        marker = "/.dockerenv"
    else:
        try:
            with open("/proc/1/cgroup") as f:
                head = f.read(512)
            # cgroup line e.g. 0::/system.slice/docker-<id>.scope
            if "docker" in head:
                import re
                m = re.search(r"([0-9a-f]{64})", head)
                marker = m.group(1) if m else "docker"
            else:
                marker = "host"
        except Exception:
            return None
    try:
        return hashlib.sha256(marker.encode()).hexdigest()[:16]
    except Exception:
        return None


def _input_sha256(sequence: str) -> str:
    return hashlib.sha256(sequence.strip().upper().encode()).hexdigest()


def deterministic_seed(sequence: str, parameters: dict | None = None) -> int:
    """Deterministic random seed derived from input + params so a rerun with
    identical inputs reproduces identical stochastic behavior."""
    payload = sequence.strip().upper() + repr(sorted((parameters or {}).items()))
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], "big")


def make_experiment_id() -> str:
    """Human-readable immutable experiment id: BNX-YYYYMMDD-<8 hex>."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"BNX-{today}-{uuid.uuid4().hex[:8]}"


def build_fingerprint(sequence: str, parameters: dict | None = None) -> dict:
    """Assemble the full reproducibility fingerprint for an experiment."""
    return {
        "input_hash": _input_sha256(sequence),
        "git_commit": _git_commit(),
        "software_versions": _software_versions(),
        "container_hash": _container_hash(),
        "database_versions": dict(KNOWN_DATABASE_RELEASES),
        "environment": _environment(),
        "random_seed": deterministic_seed(sequence, parameters),
        "parameters": parameters or {},
    }


def begin_experiment(
    job_id: str,
    sequence: str,
    pipeline: str,
    parameters: dict | None = None,
) -> str | None:
    """Register a new experiment for a job. Returns the experiment id or None.

    Writes the fingerprint exactly once — subsequent finalize_experiment() only
    flips status/finished_at so the immutable fields are never overwritten.
    """
    if not job_id or not sequence:
        return None
    fp = build_fingerprint(sequence, parameters)
    experiment_id = make_experiment_id()
    row = {
        "experiment_id": experiment_id,
        "job_id": job_id,
        "pipeline": pipeline,
        "input_hash": fp["input_hash"],
        "git_commit": fp["git_commit"],
        "software_versions": fp["software_versions"],
        "container_hash": fp["container_hash"],
        "database_versions": fp["database_versions"],
        "environment": fp["environment"],
        "random_seed": fp["random_seed"],
        "parameters": fp["parameters"],
        "status": "running",
    }
    try:
        get_supabase().table("experiments").insert(row).execute()
        return experiment_id
    except Exception as e:
        logger.warning("Experiment begin failed (job %s): %s", job_id, e)
        return None


def _find_experiment(job_id: str) -> dict | None:
    try:
        resp = get_supabase().table("experiments").select("*").eq("job_id", job_id).limit(1).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        logger.warning("Experiment lookup failed (job %s): %s", job_id, e)
        return None


def finalize_experiment(job_id: str, status: str, error: str | None = None) -> None:
    """Mark an experiment complete/failed. Only mutates status/finished_at."""
    exp = _find_experiment(job_id)
    if not exp:
        return
    try:
        payload = {
            "status": status,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        if error:
            payload["error"] = error
        get_supabase().table("experiments").update(payload).eq("id", exp["id"]).execute()
    except Exception as e:
        logger.warning("Experiment finalize failed (job %s): %s", job_id, e)


def get_experiment(job_id: str) -> dict | None:
    exp = _find_experiment(job_id)
    if not exp:
        return None
    try:
        exp["provenance"] = provenance_for_experiment(exp["experiment_id"])
    except Exception:
        exp["provenance"] = None
    return exp


def provenance_for_experiment(experiment_id: str) -> list[dict]:
    """All provenance step records for an experiment, ordered by completed_at."""
    resp = get_supabase().table("experiment_steps") \
        .select("*") \
        .eq("experiment_id", experiment_id) \
        .order("completed_at") \
        .execute()
    return resp.data or []
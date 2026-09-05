"""Continuous Paper Generation (BioNexus 2.0, Component 18 / E3).

Keeps a registered paper artifact "alive": while an experiment is subscribed
for continuous generation, its manuscript is re-rendered from the latest
recorded context and appended as a new immutable version per interval
(hash-addressed) — so the paper tracks the experiment as new data lands. The
loop runs in-process (main lifespan daemon thread), the tick triggers is
callable on demand.

Artifacts are versioned files under BIONEXUS_PAPER_ARTIFACTS_DIR (default
data/artifacts/), one manifest per version.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

from app.services.benchmarks import _fetch_job_context
from app.services.publication import render_markdown, render_paper

logger = logging.getLogger(__name__)

ARTIFACT_DIR = os.environ.get("BIONEXUS_PAPER_ARTIFACTS_DIR")
if not ARTIFACT_DIR:
    ARTIFACT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "artifacts")

#: job_id -> list of {journal, interval_s, last_rendered_at}
_subscriptions: dict[str, list[dict[str, Any]]] = {}
_subscriptions_lock = threading.Lock()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _job_dir(job_id: str) -> str:
    return os.path.join(ARTIFACT_DIR, job_id)


# --- Artifact operations ----------------------------------------------------

def build_artifact(job_id: str, journal: str = "bmc") -> dict:
    """Render the current manuscript for a job+journal and append a new version.

    Versions are 1..N manifest files named {version}.json in the job artifact
    folder; the manuscript text lives as {version}.md. Re-rendering identical
    content bumps the version and records the same content hash (a no-op edit).
    """
    context = _fetch_job_context(job_id)
    if not context:
        raise ValueError(f"no context recorded for job {job_id}")
    paper = render_paper(context, job_id)
    markdown = render_markdown(paper, journal)
    content_hash = _sha256(markdown)

    folder = _job_dir(job_id)
    os.makedirs(folder, exist_ok=True)
    version = len([f for f in os.listdir(folder) if f.endswith(".json")]) + 1

    manifest = {
        "job_id": job_id,
        "journal": journal,
        "version": version,
        "title": paper.get("title"),
        "content_hash": content_hash,
        "rendered_at": _iso_now(),
        "experiment_id": paper.get("experiment_id"),
    }
    with open(os.path.join(folder, f"{version}.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    with open(os.path.join(folder, f"{version}.md"), "w", encoding="utf-8") as f:
        f.write(markdown)
    return manifest


def list_artifacts(job_id: str) -> list[dict]:
    folder = _job_dir(job_id)
    if not os.path.isdir(folder):
        return []
    versions = []
    for fname in sorted(os.listdir(folder)):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(folder, fname), encoding="utf-8") as f:
                    versions.append(json.load(f))
            except Exception as e:
                logger.warning("artifact %s read failed: %s", fname, e)
    return versions


def latest_artifact(job_id: str, journal: str = "bmc") -> Optional[dict]:
    versions = list_artifacts(job_id)
    pick = [v for v in versions if v.get("journal") == journal]
    if not pick:
        return None
    return max(pick, key=lambda v: v.get("version", 0))


def read_artifact_text(job_id: str, manifest: dict) -> str:
    path = os.path.join(_job_dir(job_id), f"{manifest['version']}.md")
    with open(path, encoding="utf-8") as f:
        return f.read()


# --- Continuous loop ---------------------------------------------------------

def subscribe(job_id: str, journal: str, interval_s: int) -> dict:
    if interval_s < 10:
        raise ValueError("interval_seconds must be >= 10")
    with _subscriptions_lock:
        subs = _subscriptions.setdefault(job_id, [])
        entry = next((s for s in subs if s["journal"] == journal), None)
        if entry is None:
            entry = {"journal": journal, "interval_s": interval_s, "last_rendered_at": 0.0}
            subs.append(entry)
        else:
            entry["interval_s"] = interval_s
    return {"job_id": job_id, "journal": journal, "interval_s": interval_s, "subscribed": True}


def subscriptions() -> dict[str, list[dict]]:
    with _subscriptions_lock:
        return {k: [dict(s) for s in v] for k, v in _subscriptions.items()}


def tick(now: float | None = None) -> list[dict]:
    """Regenerate every due subscription; returns the artifacts produced."""
    seen_at = now if now is not None else time.time()
    produced: list[dict] = []
    with _subscriptions_lock:
        items = [(k, s) for k, subs in _subscriptions.items() for s in subs]
    for job_id, sub in items:
        if seen_at - sub["last_rendered_at"] < sub["interval_s"]:
            continue
        sub["last_rendered_at"] = seen_at
        try:
            produced.append({"job_id": job_id, **build_artifact(job_id, sub["journal"])})
        except Exception as e:
            logger.warning("continuous paper regenerate failed for %s: %s", job_id, e)
    return produced


def continuous_loop(stop_event: threading.Event, poll_s: float = 30.0) -> None:
    """Daemon loop: every poll_s, regenerate due subscriptions."""
    while not stop_event.is_set():
        try:
            tick()
        except Exception as e:  # noqa: BLE001
            logger.warning("continuous paper loop tick failed: %s", e)
        stop_event.wait(poll_s)


def start_continuous_thread(stop_event: threading.Event, poll_s: float = 30.0) -> threading.Thread:
    thread = threading.Thread(target=continuous_loop, args=(stop_event, poll_s), daemon=True, name="continuous-papers")
    thread.start()
    return thread
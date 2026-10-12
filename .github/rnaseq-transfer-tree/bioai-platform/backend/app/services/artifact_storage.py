"""
Supabase Storage wrapper for job and scientific artifacts.

Text and binary artifacts are stored without changing their scientific content.
Existing callers that use kinds such as ``result`` continue to receive a
``result.json`` object path; callers that provide a filename (for example
``consensus.fasta`` or ``alignment.bam``) keep that extension.
"""

from __future__ import annotations

import json
import logging
from pathlib import PurePosixPath
from typing import Optional

from app.services.supabase import get_client

logger = logging.getLogger(__name__)

BUCKET = "job-artifacts"


def _ensure_bucket() -> None:
    """Create the bucket if it does not exist (idempotent)."""
    try:
        sb = get_client()
        buckets = sb.storage.list_buckets()
        names = [b.name for b in buckets] if buckets else []
        if BUCKET not in names:
            sb.storage.create_bucket(BUCKET, options={"public": True})
            logger.info("Created Supabase Storage bucket: %s", BUCKET)
    except Exception:
        logger.warning("Could not ensure bucket %s — uploads may fail", BUCKET)


def _artifact_path(job_id: str, kind: str) -> str:
    safe = PurePosixPath(str(kind).replace("\\", "/")).name
    if not safe:
        safe = "artifact"
    if "." not in safe:
        safe = f"{safe}.json"
    return f"{job_id}/{safe}"


def upload_bytes_artifact(job_id: str, kind: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload exact bytes and return the Storage public URL."""
    _ensure_bucket()
    path = _artifact_path(job_id, kind)
    sb = get_client()
    sb.storage.from_(BUCKET).upload(
        path,
        data,
        {"content-type": content_type, "upsert": "true"},
    )
    return sb.storage.from_(BUCKET).get_public_url(path)


def upload_artifact(job_id: str, kind: str, data: str, content_type: str = "application/json") -> str:
    """Upload a UTF-8 text artifact without modifying its content."""
    return upload_bytes_artifact(job_id, kind, data.encode("utf-8"), content_type)


def upload_json(job_id: str, kind: str, payload: dict) -> str:
    """Upload a dict as canonical JSON and return its public URL."""
    return upload_artifact(
        job_id,
        kind,
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        "application/json",
    )


def download_artifact(url_or_path: str) -> Optional[str]:
    """Download a UTF-8 artifact from a Storage URL or relative path."""
    if not url_or_path:
        return None

    path = url_or_path
    if "storage/v1" in url_or_path:
        parts = url_or_path.split(f"{BUCKET}/", 1)
        if len(parts) > 1:
            path = parts[1]

    try:
        sb = get_client()
        res = sb.storage.from_(BUCKET).download(path)
        if isinstance(res, bytes):
            return res.decode("utf-8")
        return str(res)
    except Exception:
        logger.warning("Failed to download artifact: %s", url_or_path)
        return None


def download_json(url_or_path: str) -> Optional[dict]:
    raw = download_artifact(url_or_path)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

"""
Supabase Storage wrapper for large job artifacts.

Uploads large payloads (docking PDBQT, pipeline context, sequencing consensus)
to a Supabase Storage bucket and returns a public URL reference. The DB row
stores only the URL, not the payload itself.

Buckets must be created manually in the Supabase dashboard or via migration:
  - 'job-artifacts' (private, with public read for authenticated users)
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from app.services.supabase import get_client

logger = logging.getLogger(__name__)

BUCKET = "job-artifacts"


def _ensure_bucket() -> None:
    """Create the bucket if it doesn't exist (idempotent)."""
    try:
        sb = get_client()
        buckets = sb.storage.list_buckets()
        names = [b.name for b in buckets] if buckets else []
        if BUCKET not in names:
            sb.storage.create_bucket(BUCKET, options={"public": True})
            logger.info("Created Supabase Storage bucket: %s", BUCKET)
    except Exception:
        logger.warning("Could not ensure bucket %s — uploads may fail", BUCKET)


def upload_artifact(job_id: str, kind: str, data: str, content_type: str = "application/json") -> str:
    """Upload a string payload to Storage and return its public URL.

    Args:
        job_id: The job UUID.
        kind: Artifact type (e.g. 'result', 'context', 'consensus').
        data: The string content to upload.
        content_type: MIME type.

    Returns:
        Public URL of the uploaded artifact.
    """
    _ensure_bucket()
    path = f"{job_id}/{kind}.json"
    sb = get_client()
    # Upsert (overwrite if exists)
    sb.storage.from_(BUCKET).upload(
        path,
        data.encode("utf-8"),
        {"content-type": content_type, "upsert": "true"},
    )
    url = sb.storage.from_(BUCKET).get_public_url(path)
    return url


def upload_json(job_id: str, kind: str, payload: dict) -> str:
    """Upload a dict as JSON to Storage and return its public URL."""
    return upload_artifact(job_id, kind, json.dumps(payload), "application/json")


def download_artifact(url_or_path: str) -> Optional[str]:
    """Download artifact content from a Storage URL or path.

    If the input is a full URL, extracts the path and downloads from Storage.
    If it's a relative path, downloads directly.
    Returns the content as a string, or None on failure.
    """
    if not url_or_path:
        return None

    # Extract path from full URL: https://xxx.supabase.co/storage/v1/object/public/bucket/path
    path = url_or_path
    if "storage/v1" in url_or_path:
        # Extract everything after '/object/public/bucket-name/'
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
    """Download and parse a JSON artifact."""
    raw = download_artifact(url_or_path)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

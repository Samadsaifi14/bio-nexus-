"""Version + commit stamping for exports and reports (MATRIX 34).

Best-effort and never fatal: APP_VERSION is a constant; PLATFORM_COMMIT is the
short git HEAD revision resolved once per process when the repo is available,
otherwise None. Callers must render None as 'unknown' rather than fabricating.
"""

from __future__ import annotations

import functools
import subprocess
from pathlib import Path

APP_VERSION = "0.2.0"

_BACKEND_DIR = Path(__file__).resolve().parents[1]


@functools.lru_cache(maxsize=1)
def platform_commit() -> str | None:
    """Short HEAD revision of the repo containing this package, or None."""
    for base in (_BACKEND_DIR, _BACKEND_DIR.parents[1]):
        git_dir = base / ".git"
        if not git_dir.exists():
            continue
        try:
            proc = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(base), capture_output=True, text=True, timeout=5,
            )
        except Exception:
            return None
        if proc.returncode == 0:
            rev = proc.stdout.strip()
            return rev or None
        return None
    return None


def export_stamp() -> dict:
    """Machine-auditable stamp embedded in every export (version + commit)."""
    commit = platform_commit()
    return {
        "bio_nexus_version": APP_VERSION,
        "bio_nexus_commit": commit or "unknown",
        "schema": "bionexus-export-stamp/v1",
    }
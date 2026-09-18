"""MATRIX 34 — export stamping tests.

RO-Crate exports (and every export via export_stamp) must carry a visible
version + commit and never fabricate one when the repo is unavailable.
"""

from __future__ import annotations

from app.routers.export import _build_ro_crate
from app.services.version import APP_VERSION, export_stamp, platform_commit


def _sample_job_context():
    job = {
        "id": "01234567-abcd-ef01-2345-6789abcdef01",
        "query_preview": "P69905",
        "created_at": "2026-09-06T00:00:00Z",
        "completed_at": "2026-09-06T00:01:00Z",
        "user_id": None,
        "context_json": {
            "steps": {"blast": {"status": "complete", "data": {"hits": []}}},
        },
    }
    context = job["context_json"]
    return job, context


def test_ro_crate_platform_application_has_version_and_commit():
    job, context = _sample_job_context()
    crate = _build_ro_crate(job, context)
    app_node = next(
        n for n in crate["@graph"] if n.get("@id") == "#bio-nexus-platform"
    )
    assert app_node["version"] == APP_VERSION
    # commit is a string: a real short sha when available, else literally 'unknown'
    commit = app_node["commit"]
    assert commit == "unknown" or (len(commit) > 0 and not commit.isspace())


def test_ro_crate_metadata_carries_export_stamp():
    job, context = _sample_job_context()
    crate = _build_ro_crate(job, context)
    stamp = crate["_metadata"]["export_stamp"]
    assert stamp["bio_nexus_version"] == APP_VERSION
    assert stamp["schema"] == "bionexus-export-stamp/v1"
    assert stamp["bio_nexus_commit"]
    # never fabricated: stamp value must be identical to whatever resolving gives
    assert stamp["bio_nexus_commit"] == (platform_commit() or "unknown")


def test_export_stamp_is_self_consistent():
    stamp = export_stamp()
    assert stamp["bio_nexus_version"] == APP_VERSION
    assert stamp["bio_nexus_commit"] == (platform_commit() or "unknown")
    # commit value shape is a short git sha or the literal 'unknown'
    c = stamp["bio_nexus_commit"]
    if c != "unknown":
        import re
        assert re.fullmatch(r"[0-9a-f]{7,40}", c), c
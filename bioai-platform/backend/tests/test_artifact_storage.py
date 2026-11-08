"""Tests for Supabase Storage artifact wrapper and encryption-at-rest
observability.

Supabase Storage encrypts all objects at rest by the platform. This module does
not implement a homemade encryption scheme; it only reports what the backend
can observe.
"""

from app.services import artifact_storage


class _FakeBucket:
    def __init__(self, name, public=False):
        self.name = name
        self.public = public


class _FakeStorage:
    def __init__(self, buckets):
        self._buckets = buckets

    def list_buckets(self):
        return self._buckets


class _FakeClient:
    def __init__(self, buckets):
        self.storage = _FakeStorage(buckets)


def test_storage_encryption_at_rest_reports_bucket(monkeypatch):
    monkeypatch.setattr(
        artifact_storage,
        "get_client",
        lambda: _FakeClient([_FakeBucket("job-artifacts", public=False)]),
    )
    report = artifact_storage.storage_encryption_at_rest()
    assert report["bucket"] == "job-artifacts"
    assert report["encrypted_at_rest"] is True
    assert report["public"] is False


def test_storage_encryption_at_rest_bucket_missing(monkeypatch):
    monkeypatch.setattr(
        artifact_storage,
        "get_client",
        lambda: _FakeClient([_FakeBucket("other-bucket", public=False)]),
    )
    report = artifact_storage.storage_encryption_at_rest()
    assert report["bucket"] == "job-artifacts"
    assert report["encrypted_at_rest"] is None
    assert report["source"] == "bucket-not-found"

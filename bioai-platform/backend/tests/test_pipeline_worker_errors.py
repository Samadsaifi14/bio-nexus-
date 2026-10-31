"""Failure messages must stay diagnosable without leaking secrets.

A production wizard job (50ee96cf-...) failed with the fixed sentence
"Protein annotation could not be completed for this result." even though the
real exception carried the UniProt status/detail. That erased the only evidence
of what went wrong. These tests lock in the bounded, redacted detail path.
"""

from __future__ import annotations

from app.workers.pipeline_worker import _public_error, _sanitize_detail


class TestPublicError:
    def test_uniprot_detail_is_preserved(self):
        message = _public_error(
            RuntimeError("UniProt mapping failed for P04637 with status 503")
        )
        assert message.startswith("Protein annotation failed:")
        assert "status 503" in message

    def test_provider_url_is_redacted(self):
        message = _public_error(
            RuntimeError(
                "UniProt request to https://rest.uniprot.org/uniprotkb?api_key=SECRET123 failed"
            )
        )
        assert "SECRET123" not in message
        assert "https://" not in message
        assert "[url]" in message

    def test_credentials_are_redacted(self):
        detail = _sanitize_detail(RuntimeError("api_key=abcd1234 token: deadbeef"))
        assert "abcd1234" not in detail
        assert "deadbeef" not in detail
        assert "[redacted]" in detail

    def test_long_sequence_is_redacted(self):
        sequence = "ACDEFGHIKLMNPQRSTVWY" * 3
        detail = _sanitize_detail(RuntimeError(f"bad input {sequence}"))
        assert sequence not in detail
        assert "[sequence]" in detail

    def test_blast_detail_is_preserved(self):
        message = _public_error(RuntimeError("NCBI BLAST returned 429: Too Many Requests"))
        assert message.startswith("BLAST search failed:")
        assert "429" in message

    def test_timeout_has_actionable_message(self):
        message = _public_error(RuntimeError("upstream timed out after 120s"))
        assert "longer than expected" in message
        assert "timed out after 120s" not in message

    def test_unknown_failure_still_carries_detail(self):
        message = _public_error(RuntimeError("ESMFold returned an empty model"))
        assert "ESMFold returned an empty model" in message

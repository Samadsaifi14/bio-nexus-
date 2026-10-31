"""UniProt transient-failure retry.

A single 500 from UniProt used to bubble straight out of the annotation step and
fail the whole wizard run (job 50ee96cf-..., "UniProt returned 500 for P61260").
A bounded retry distinguishes a transient blip from a permanent rejection.
"""

from __future__ import annotations

import pytest

from app.tools import uniprot as uniprot_module
from app.tools.uniprot import UniprotTool


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class FakeClient:
    def __init__(self, responses: list[FakeResponse], calls: list[str]):
        self.responses = responses
        self.calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def get(self, url, params=None):
        response = self.responses[min(len(self.calls), len(self.responses) - 1)]
        self.calls.append(url)
        return response


@pytest.fixture
def harness(monkeypatch):
    calls: list[str] = []

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(uniprot_module.asyncio, "sleep", no_sleep)

    def install(responses: list[FakeResponse]):
        monkeypatch.setattr(
            uniprot_module.httpx,
            "AsyncClient",
            lambda **_kwargs: FakeClient(responses, calls),
        )

    return install, calls


class TestUniprotRetry:
    @pytest.mark.asyncio
    async def test_transient_500_is_retried(self, harness):
        install, calls = harness
        install([
            FakeResponse(500),
            FakeResponse(200, {"primaryAccession": "P61260"}),
        ])

        payload = await UniprotTool()._fetch("P61260")

        assert payload == {"primaryAccession": "P61260"}
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_404_is_not_retried(self, harness):
        install, calls = harness
        install([FakeResponse(404)])

        result = await UniprotTool()._fetch("XXXXXX")

        assert "not found" in result["error"]
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_persistent_500_reports_accession_and_status(self, harness):
        install, calls = harness
        install([FakeResponse(500)])

        result = await UniprotTool()._fetch("P61260")

        assert "500" in result["error"]
        assert "P61260" in result["error"]
        assert len(calls) == uniprot_module._FETCH_ATTEMPTS

    @pytest.mark.asyncio
    async def test_malformed_json_is_not_retried(self, harness):
        install, calls = harness
        install([FakeResponse(200, None)])

        result = await UniprotTool()._fetch("P61260")

        assert "malformed JSON" in result["error"]
        assert len(calls) == 1

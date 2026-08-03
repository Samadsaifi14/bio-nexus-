"""
Tests for 3d ScanProsite raw-sequence motif scanning:

- scan_prosite_sequence parses the verified ScanProsite JSON contract
- short sequences return a clear error
- empty matchset -> count 0
- POST /api/domains/scan router: success + 400 on short sequence

Network calls are mocked; these run fully offline.
"""

import pytest
from fastapi import HTTPException

from app.tools import domain_analysis as da
from app.routers import domains as domains_router
from app.routers.domains import ScanPrositeRequest, scan_prosite


class FakeResp:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, data=None, **kwargs):
        self.calls.append((url, data))
        return FakeResp(200, {
            "n_match": 1,
            "n_seq": 1,
            "matchset": [
                {"sequence_ac": "USERSEQ1", "start": 237, "stop": 249,
                 "signature_ac": "PS00348", "level_tag": "(0)"},
            ],
        })


class TestScanPrositeSequence:
    @pytest.mark.asyncio
    async def test_parses_json_contract(self, monkeypatch):
        fake = FakeClient()
        monkeypatch.setattr(da.httpx, "AsyncClient", lambda *a, **k: fake)
        monkeypatch.setattr(da, "_prosite_signature_name",
                            lambda sig: _fake_name(sig))

        seq = "M" * 250
        result = await da.scan_prosite_sequence(seq)
        assert result["sequence_length"] == 250
        assert result["count"] == 1
        m = result["matches"][0]
        assert m["signature_ac"] == "PS00348"
        assert m["start"] == 237 and m["stop"] == 249
        assert m["name"] == "p53 family signature"

    @pytest.mark.asyncio
    async def test_empty_matchset(self, monkeypatch):
        class FakeClientEmpty(FakeClient):
            async def post(self, url, data=None, **kwargs):
                self.calls.append((url, data))
                return FakeResp(200, {"n_match": 0, "n_seq": 1})

        monkeypatch.setattr(da.httpx, "AsyncClient", lambda *a, **k: FakeClientEmpty())
        result = await da.scan_prosite_sequence("M" * 50)
        assert result["count"] == 0
        assert result["matches"] == []

    @pytest.mark.asyncio
    async def test_short_sequence_rejected(self):
        result = await da.scan_prosite_sequence("MEEPQ")
        assert "error" in result
        assert "too short" in result["error"]

    @pytest.mark.asyncio
    async def test_http_error(self, monkeypatch):
        class FakeClientFail(FakeClient):
            async def post(self, url, data=None, **kwargs):
                return FakeResp(500, {})

        monkeypatch.setattr(da.httpx, "AsyncClient", lambda *a, **k: FakeClientFail())
        result = await da.scan_prosite_sequence("M" * 50)
        assert "error" in result
        assert "HTTP 500" in result["error"]


class TestScanPrositeEndpoint:
    @pytest.mark.asyncio
    async def test_success(self, monkeypatch):
        async def fake_scan(sequence, email=""):
            assert email == "bioflow@example.com"
            return {"sequence_length": 10, "count": 1, "matches": [
                {"signature_ac": "PS00001", "name": "N-glycosylation site",
                 "start": 2, "stop": 5, "level_tag": "(0)"},
            ]}

        monkeypatch.setattr(domains_router, "scan_prosite_sequence", fake_scan)
        resp = await scan_prosite(ScanPrositeRequest(sequence="MEEPQSDPSV"))
        assert resp.sequence_length == 10
        assert resp.count == 1
        assert resp.matches[0].name == "N-glycosylation site"

    @pytest.mark.asyncio
    async def test_short_sequence_400(self, monkeypatch):
        async def fake_scan(sequence, email=""):
            return {"error": "Sequence too short (min 10 amino acids)"}

        monkeypatch.setattr(domains_router, "scan_prosite_sequence", fake_scan)
        with pytest.raises(HTTPException) as exc:
            await scan_prosite(ScanPrositeRequest(sequence="MEEPQ"))
        assert exc.value.status_code == 400
        assert "too short" in exc.value.detail


async def _fake_name(sig: str) -> str:
    return "p53 family signature"

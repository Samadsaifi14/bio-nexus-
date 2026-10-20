"""Upstream network errors return a bounded response without private URLs."""
import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_upstream_failure_is_502_without_url_or_query(monkeypatch):
    def fail(request):
        raise httpx.ConnectError("secret-query-token/private-sequence", request=request)
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(
        **{**kwargs, "transport": httpx.MockTransport(fail)}))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/structures/search", json={"query": "lysozyme"})
    assert response.status_code == 502
    assert response.json()["detail"] == "Upstream service unavailable. Please retry."
    assert "request_id" in response.json()
    assert "secret-query-token" not in response.text
    assert "private-sequence" not in response.text

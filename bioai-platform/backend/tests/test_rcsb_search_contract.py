"""RCSB keyword searches use full_text, not attribute-search text service."""
import httpx
import pytest
from app.routers.structures import search_pdb, StructureSearchRequest


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [200, 204])
async def test_keyword_search_and_no_results(monkeypatch, status):
    original = httpx.AsyncClient
    def upstream(request):
        import json
        query = json.loads(request.content)['query']
        assert query['service'] == 'full_text'
        assert query['parameters'] == {'value': 'insulin'}
        return httpx.Response(status, json={'result_set': [{'identifier': '4INS', 'score': 1.2}]} if status == 200 else None)
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(
        **{**kwargs, 'transport': httpx.MockTransport(upstream)}))
    result = await search_pdb(StructureSearchRequest(query='insulin'))
    assert result['count'] == (1 if status == 200 else 0)
    assert result['results'] == ([{'pdb_id': '4INS', 'score': 1.2}] if status == 200 else [])

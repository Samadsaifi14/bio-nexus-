"""Distinguish explicit readiness and BLAST XML from unrelated HTML."""
import httpx
import pytest
from app.integrations.ncbi import blast


@pytest.mark.asyncio
@pytest.mark.parametrize('body,expected', [('Status=WAITING', 'WAITING'),
    ('Status = READY', 'READY'), ('<BlastOutput/>', 'READY'), ('<html>Service unavailable</html>', 'UNKNOWN')])
async def test_status_requires_explicit_status_or_blast_xml(monkeypatch, body, expected):
    async def request(method, url, **kwargs):
        assert method == 'get'
        assert kwargs['params']['FORMAT_TYPE'] == 'XML'
        assert kwargs['params']['RID'] == 'RID-CONTRACT'
        return httpx.Response(200, text=body)
    monkeypatch.setattr(blast, '_request_with_retry', request)
    assert (await blast.check_status('RID-CONTRACT'))['status'] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('sequence', ['', '12345!@#$%^&*()'])
async def test_invalid_query_never_submits_or_becomes_no_hit(monkeypatch, sequence):
    async def forbidden(*args, **kwargs):
        pytest.fail('Invalid input must not reach NCBI')
    monkeypatch.setattr(blast, '_request_with_retry', forbidden)
    result = await blast.run_blast_with_retry(sequence, retries=0)
    assert result['error']
    assert result.get('search_complete') is not True
    assert 'raw' not in result

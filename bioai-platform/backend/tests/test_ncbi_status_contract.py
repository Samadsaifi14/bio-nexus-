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
        assert kwargs['params']['FORMAT_TYPE'] == 'XML2_S'
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


@pytest.mark.asyncio
@pytest.mark.parametrize('api_key', ['', 'configured-key'])
async def test_each_rid_is_polled_at_most_once_per_minute(monkeypatch, api_key):
    clock = [0.0]
    starts = []

    async def sleep(seconds):
        clock[0] += seconds

    async def status(rid):
        starts.append(clock[0])
        clock[0] += 9  # HTTP time must count against the budget.
        return {'status': 'READY' if len(starts) == 3 else 'WAITING', 'rid': rid}

    monkeypatch.setattr(blast, 'NCBI_API_KEY', api_key)
    monkeypatch.setattr(blast, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(blast.asyncio, 'sleep', sleep)
    monkeypatch.setattr(blast, 'check_status', status)
    result = await blast.check_status_until_ready('RID', max_wait_seconds=240, estimated_seconds=80)
    assert result['status'] == 'READY'
    assert starts[0] >= 80
    assert all(b - a >= 60 for a, b in zip(starts, starts[1:]))
    assert clock[0] < 240


@pytest.mark.asyncio
async def test_poll_request_is_cancelled_at_remaining_wall_clock_budget(monkeypatch):
    import asyncio
    from time import monotonic
    cancelled = []

    async def sleep(seconds):
        pass  # Exercise request cancellation without a real minute-long wait.

    async def status(rid):
        try:
            await asyncio.Future()
        finally:
            cancelled.append(True)

    monkeypatch.setattr(blast.asyncio, 'sleep', sleep)
    monkeypatch.setattr(blast, 'check_status', status)
    start = monotonic()
    result = await blast.check_status_until_ready('RID', max_wait_seconds=0.03)
    assert result['status'] == 'TIMEOUT'
    assert cancelled == [True]
    assert monotonic() - start < 0.5


@pytest.mark.asyncio
async def test_ready_xml_is_reused_without_duplicate_result_get(monkeypatch):
    from pathlib import Path
    raw = (Path(__file__).parent / 'fixtures/blast_xml2/hbb-xml2.xml').read_text()

    async def submit(*args, **kwargs):
        return {'rid': 'RID', 'estimated_seconds': 1}

    async def poll(*args, **kwargs):
        return {'status': 'READY', 'rid': 'RID', 'raw': raw}

    async def forbidden(*args, **kwargs):
        pytest.fail('A ready XML response must not cause a duplicate GET')

    monkeypatch.setattr(blast, 'submit_blast', submit)
    monkeypatch.setattr(blast, 'check_status_until_ready', poll)
    monkeypatch.setattr(blast, 'fetch_results', forbidden)
    result = await blast.run_blast_with_retry('TTCCPSIVARSNFNVCRLPG', retries=0)
    assert result == {'raw': raw, 'rid': 'RID'}


@pytest.mark.asyncio
async def test_waiting_timeout_preserves_rid_without_resubmitting(monkeypatch):
    submissions = []

    async def submit(*args, **kwargs):
        submissions.append(True)
        return {'rid': 'ACCEPTED-RID', 'estimated_seconds': 22}

    async def poll(*args, **kwargs):
        return {'status': 'TIMEOUT', 'rid': 'ACCEPTED-RID'}

    monkeypatch.setattr(blast, 'submit_blast', submit)
    monkeypatch.setattr(blast, 'check_status_until_ready', poll)
    result = await blast.run_blast_with_retry('TTCCPSIVARSNFNVCRLPG', retries=2)
    assert submissions == [True]
    assert result['rid'] == 'ACCEPTED-RID'
    assert result['search_complete'] is False
    assert result['status'] == 'TIMEOUT'
    assert result['error']


@pytest.mark.asyncio
@pytest.mark.parametrize('recovered', [True, False])
async def test_http_200_outage_is_retried_without_fabricating_a_result(monkeypatch, recovered):
    real_client = httpx.AsyncClient
    attempts = []
    delays = []

    def response(request):
        attempts.append(True)
        body = 'RID = RECOVERED\nRTOE = 22' if recovered and len(attempts) == 3 else 'Temporarily unavailable\n'
        return httpx.Response(200, text=body)

    async def sleep(seconds):
        delays.append(seconds)

    monkeypatch.setattr(blast.httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(response), **kwargs))
    monkeypatch.setattr(blast.asyncio, 'sleep', sleep)
    if recovered:
        result = await blast.submit_blast('TTCCPSIVARSNFNVCRLPG')
        assert result == {'rid': 'RECOVERED', 'estimated_seconds': 22}
    else:
        with pytest.raises(blast.NCBIUnavailableError, match='temporarily unavailable'):
            await blast.submit_blast('TTCCPSIVARSNFNVCRLPG')
    assert len(attempts) == 3
    assert delays == [10, 20]


@pytest.mark.asyncio
async def test_submission_uses_supported_gap_and_short_query_parameters(monkeypatch):
    async def request(method, url, **kwargs):
        params = kwargs['data']
        assert params['GAPCOSTS'] == '11 1'
        assert params['SHORT_QUERY_ADJUST'] == 'true'
        assert params['FORMAT_TYPE'] == 'XML2_S'
        assert params['tool'] == 'bio-nexus'
        assert not {'GAPOPEN', 'GAPEXTEND', 'ASYNC', 'api_key'} & params.keys()
        return httpx.Response(200, text='RID = CONTRACT\nRTOE = 22')
    monkeypatch.setattr(blast, '_request_with_retry', request)
    result = await blast.submit_blast('TTCCPSIVARSNFNVCRLPG', gapopen=11, gapextend=1)
    assert result['rid'] == 'CONTRACT'

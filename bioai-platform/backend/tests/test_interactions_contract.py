"""PPI confidence contract with fixed provider payloads, no network."""
import pytest
from fastapi import HTTPException
from app.routers import interactions as module


@pytest.fixture
def provider(monkeypatch):
    state = {"rows": [{"preferredName_B": "MDM2", "stringId_B": "9606.mdm2", "score": .99,
                       **{key: .4 for key in ("nscore","fscore","pscore","ascore","escore","dscore","tscore")}}]}
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        async def get(self, url, params):
            state["params"] = params
            class Response:
                status_code = 200
                def json(self): return state["rows"]
            return Response()
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kw: Client())
    async def no_summary(*args, **kwargs): return None
    monkeypatch.setattr("app.ai.tool_interpreter.interpret_tool_result", no_summary)
    return state


@pytest.mark.asyncio
async def test_native_confidence_and_plain_defaults(provider):
    result = await module.get_interactions("TP53")
    assert result["interaction_count"] == len(result["interactions"])
    row = result["interactions"][0]
    assert row["combined_score"] == .99
    assert row["escore"] == .4
    assert row["physical_evidence_avg"] == .4
    assert provider["params"]["species"] == 9606
    assert provider["params"]["limit"] == 15
    assert result["network_type"] == "functional"


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [None, -1, 999, float("nan"), float("inf")])
async def test_invalid_source_confidence_is_not_fabricated_as_zero(provider, value):
    provider["rows"][0]["score"] = value
    with pytest.raises(HTTPException) as error:
        await module.get_interactions("TP53")
    assert error.value.status_code == 502


@pytest.mark.asyncio
async def test_measured_zero_is_preserved(provider):
    provider["rows"][0]["score"] = 0
    result = await module.get_interactions("TP53")
    assert result["interactions"][0]["combined_score"] == 0

@pytest.mark.asyncio
async def test_interpretation_sees_serializable_partners_and_exact_count(provider, monkeypatch):
    import json
    provider['rows'] *= 12
    observed = []
    async def inspect(tool_name, payload):
        observed.append(tool_name)
        assert payload['interaction_count'] == len(payload['interactions']) == 12
        assert isinstance(payload['interactions'][0], dict)
        json.dumps(payload)
        from app.ai.tool_interpreter import _summarize_result
        summary = _summarize_result(payload)
        assert 'interaction_count: 12' in summary
        assert '"combined_score": 0.99' in summary
        return None
    monkeypatch.setattr('app.ai.tool_interpreter.interpret_tool_result', inspect)
    result = await module.get_interactions('TP53')
    assert result['interaction_count'] == 12
    assert observed == ['interactions']

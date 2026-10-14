"""No network or provider credentials: exercise interpretation admission and fallback."""
import json
from types import SimpleNamespace

import pytest

from app.ai import interpreter
from app.ai.llm_client import llm_client


@pytest.fixture
def candidate(monkeypatch):
    monkeypatch.setattr(llm_client, "get_all_candidates", lambda: [
        {"name": "test", "model": "test/model", "api_key": "fixture"}])
    async def no_delay(*args): pass
    monkeypatch.setattr(interpreter.asyncio, "sleep", no_delay)


def response(text):
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text))])


async def events(context):
    return [json.loads(event.removeprefix("data: ").strip())
            async for event in interpreter.interpret_stream("protein_analysis", context)]


@pytest.mark.asyncio
async def test_split_provider_reply_is_admitted_only_after_numeric_check(candidate, monkeypatch):
    async def chunks():
        yield response("There are ")
        yield response("3 recorded hits.")
    async def complete(**kwargs): return chunks()
    monkeypatch.setattr(interpreter, "_get_acompletion", lambda: complete)
    output = await events({"count": 3})
    assert [x["chunk"] for x in output if "chunk" in x] == ["There are 3 recorded hits."]
    assert output[-1]["done"] is True
    assert output[-1]["meta"]["grounding"]["status"] == "numeric_fidelity_passed"


@pytest.mark.asyncio
async def test_invented_number_never_reaches_client(candidate, monkeypatch):
    async def chunks(): yield response("There are 42 recorded hits.")
    async def complete(**kwargs): return chunks()
    monkeypatch.setattr(interpreter, "_get_acompletion", lambda: complete)
    output = await events({"count": 3})
    assert not any("chunk" in x or "done" in x for x in output)
    assert any("error" in x for x in output)


@pytest.mark.asyncio
async def test_partial_failure_does_not_mix_provider_outputs(monkeypatch):
    monkeypatch.setattr(llm_client, "get_all_candidates", lambda: [
        {"name": "first", "model": "test/first", "api_key": "fixture"},
        {"name": "backup", "model": "test/backup", "api_key": "fixture"}])
    async def no_delay(*args): pass
    monkeypatch.setattr(interpreter.asyncio, "sleep", no_delay)
    async def broken():
        yield response("PARTIAL SHOULD NOT BE DISPLAYED")
        raise RuntimeError("provider disconnected")
    async def good(): yield response("3 recorded hits.")
    async def complete(**kwargs): return broken() if kwargs["model"] == "test/first" else good()
    monkeypatch.setattr(interpreter, "_get_acompletion", lambda: complete)
    output = await events({"count": 3})
    assert [x["chunk"] for x in output if "chunk" in x] == ["3 recorded hits."]
    assert output[-1]["meta"]["model"] == "test/backup"


@pytest.mark.asyncio
async def test_missing_provider_has_explicit_failure_without_fake_summary(monkeypatch):
    monkeypatch.setattr(llm_client, "get_all_candidates", lambda: [])
    async def complete(**kwargs): raise AssertionError("No provider must be called")
    monkeypatch.setattr(interpreter, "_get_acompletion", lambda: complete)
    output = await events({"count": 3})
    assert output == [{"error": "No LLM API keys configured. AI interpretation unavailable."}]


def test_numeric_gate_preserves_missing_evidence():
    with pytest.raises(ValueError, match="numeric claims"):
        interpreter._numeric_grounding("There are 0 variants.", {"variants": None})
    result = interpreter._numeric_grounding("Variants were not reported.", {"variants": None})
    assert len(result["evidence_sha256"]) == 64

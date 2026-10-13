"""Deterministic tests for tool interpretation resilience.

A single flaky provider reply (empty content or non-JSON) must NOT kill
interpretation — it should retry, then fall back to the next provider.
No network, no DB.
"""

import json

from app.ai import interpreter, tool_interpreter
from app.ai.llm_client import llm_client


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Msg(content)
        self.delta = self.message


class _Resp:
    def __init__(self, content):
        self.choices = [_Choice(content)]


def _candidate(monkeypatch):
    monkeypatch.setattr(
        llm_client,
        "api_key",
        "test-key",
    )
    monkeypatch.setattr(
        llm_client,
        "fallback_key",
        "test-key",
    )
    return {"model": "gemini/test", "api_key": "test-key"}


def _monkeypatch_acompletion(monkeypatch, fake):
    def _get():
        return fake

    monkeypatch.setattr(interpreter, "_get_acompletion", _get)


class TestToolInterpretResilience:
    async def test_empty_then_valid_json_recovers(self, monkeypatch):
        _candidate(monkeypatch)
        calls = []

        async def fake_acompletion(model, messages, **kwargs):
            calls.append(model)
            if len(calls) == 1:
                return _Resp("")
            return _Resp(json.dumps({"headline": "h", "summary": "s", "findings": ["f"], "caveats": []}))

        _monkeypatch_acompletion(monkeypatch, fake_acompletion)

        result = await tool_interpreter.interpret_tool_result("blast", {"count": 1})

        assert result is not None
        assert result["summary"] == "s"

    async def test_non_json_then_valid_json_recovers(self, monkeypatch):
        _candidate(monkeypatch)
        calls = []

        async def fake_acompletion(model, messages, **kwargs):
            calls.append(model)
            if len(calls) == 1:
                return _Resp("Here is a nice paragraph of prose.")
            return _Resp(json.dumps({"headline": "h", "summary": "s", "findings": ["f"], "caveats": []}))

        _monkeypatch_acompletion(monkeypatch, fake_acompletion)

        result = await tool_interpreter.interpret_tool_result("blast", {"count": 1})

        assert result is not None
        assert result["summary"] == "s"

    async def test_all_empty_returns_none(self, monkeypatch):
        _candidate(monkeypatch)
        calls = []

        async def fake_acompletion(model, messages, **kwargs):
            calls.append(model)
            return _Resp("")

        _monkeypatch_acompletion(monkeypatch, fake_acompletion)

        result = await tool_interpreter.interpret_tool_result("blast", {"count": 1})

        assert result is None
        assert len(calls) > 1, "should retry more than once before giving up"

    async def test_unknown_tool_returns_none(self, monkeypatch):
        _candidate(monkeypatch)

        async def fake_acompletion(model, messages, **kwargs):
            raise AssertionError("should not call provider for unknown tool")

        _monkeypatch_acompletion(monkeypatch, fake_acompletion)

        result = await tool_interpreter.interpret_tool_result("not_a_tool", {"x": 1})

        assert result is None

    async def test_invented_number_rejected_then_grounded_retry_accepted(self, monkeypatch):
        _candidate(monkeypatch)
        calls = []
        async def fake_acompletion(**kwargs):
            calls.append(kwargs)
            value = "42" if len(calls) == 1 else "3"
            return _Resp(json.dumps({"headline": "Recorded hits", "summary": f"There are {value} hits.", "findings": [], "caveats": []}))
        _monkeypatch_acompletion(monkeypatch, fake_acompletion)
        result = await tool_interpreter.interpret_tool_result("blast", {"count": 3})
        assert result["summary"] == "There are 3 hits."
        assert result["grounding"]["status"] == "numeric_fidelity_passed"
        assert len(result["grounding"]["evidence_sha256"]) == 64
        assert len(calls) == 2

    async def test_number_in_omitted_result_field_is_not_evidence(self, monkeypatch):
        _candidate(monkeypatch)
        async def fake_acompletion(**kwargs):
            return _Resp(json.dumps({"headline": "Hits", "summary": "There are 98765 hits.", "findings": [], "caveats": []}))
        _monkeypatch_acompletion(monkeypatch, fake_acompletion)
        result = {f"key_{chr(65+i)}": "available" for i in range(15)}
        result["omitted"] = 98765
        assert await tool_interpreter.interpret_tool_result("blast", result) is None

    async def test_invalid_list_schema_not_coerced_into_letters(self, monkeypatch):
        _candidate(monkeypatch)
        async def fake_acompletion(**kwargs):
            return _Resp(json.dumps({"headline": "Hits", "summary": "Recorded hits.", "findings": "fake list", "caveats": []}))
        _monkeypatch_acompletion(monkeypatch, fake_acompletion)
        assert await tool_interpreter.interpret_tool_result("blast", {"count": 3}) is None

    async def test_failed_or_empty_result_never_calls_provider(self, monkeypatch):
        _candidate(monkeypatch)
        async def fake_acompletion(**kwargs):
            raise AssertionError("Unavailable results must not be interpreted")
        _monkeypatch_acompletion(monkeypatch, fake_acompletion)
        for payload in ({}, {"status": "failed"}, {"status": "running"}):
            assert await tool_interpreter.interpret_tool_result("blast", payload) is None

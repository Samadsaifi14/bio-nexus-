"""
Unit tests for the ProTox 3.0 client (app.tools.protox).

These mock the upstream HTTP calls so no network access is required.
Covers: request validation, enqueue/retrieve/fetch flow, tolerant TSV
parsing, and graceful error mapping for quota / rate-limit / outage.
"""

import pytest
import httpx

from app.tools.protox import (
    ALL_MODELS,
    DEFAULT_MODELS,
    ProToxError,
    _parse_tsv,
    predict_toxicity,
)


class FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code}", request=httpx.Request("GET", "http://x"), response=self
            )


TOX_CLASS_CSV = (
    'LD50\ttox_class\tsimilarity\n'
    '100\t3\t78.9\n'
)
MODELS_CSV = (
    'Target\tPrediction\tProbability\n'
    'dili\t1\t0.93\n'
    'carcino\t0\t0.12\n'
)
TARGETS_CSV = (
    'Target\tPrediction\tProbability\n'
    'Membrane alpha-2 receptor\t1\t0.81\n'
)


def make_client_side_effect(enqueue_status=200, enqueue_text="abc123"):
    """Return an httpx.AsyncClient whose post/get follow the ProTox flow."""

    async def _post(url, data=None, **kwargs):
        if url.endswith("api_enqueue.php"):
            return FakeResponse(enqueue_status, enqueue_text)
        if url.endswith("api_retrieve.php"):
            # Non-empty body on first poll => ready immediately.
            return FakeResponse(200, "done")
        raise AssertionError(f"unexpected POST url: {url}")

    async def _get(url, **kwargs):
        if url.endswith("_tox_class.csv"):
            return FakeResponse(200, TOX_CLASS_CSV)
        if url.endswith("_result.csv"):
            return FakeResponse(200, MODELS_CSV)
        if url.endswith("_tox_targets.csv"):
            return FakeResponse(200, TARGETS_CSV)
        raise AssertionError(f"unexpected GET url: {url}")

    return _post, _get


class FakeAsyncClient:
    def __init__(self, post_fn, get_fn):
        self._post = post_fn
        self._get = get_fn

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, data=None, **kwargs):
        return await self._post(url, data=data, **kwargs)

    async def get(self, url, **kwargs):
        return await self._get(url, **kwargs)


def test_parse_tsv_normalizes_headers():
    rows = _parse_tsv('Target\tPrediction\tProbability\nDILI\t1\t0.9\n')
    assert rows == [{"target": "DILI", "prediction": "1", "probability": "0.9"}]


def test_parse_tsv_handles_quoted_headers_and_blank_lines():
    rows = _parse_tsv('"Target"\tPrediction\nx\t1\n\n')
    assert rows == [{"target": "x", "prediction": "1"}]


def test_parse_tsv_empty():
    assert _parse_tsv("") == []
    assert _parse_tsv("no tabs here\n") == []


def test_request_validation():
    with pytest.raises(ProToxError):
        asyncio_run(predict_toxicity())
    with pytest.raises(ProToxError):
        asyncio_run(predict_toxicity(smiles="CCO", name="ethanol"))


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)


def test_successful_flow(monkeypatch):
    post, get = make_client_side_effect()
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeAsyncClient(post, get))

    result = asyncio_run(predict_toxicity(smiles="CCO"))

    assert result["input"] == "CCO"
    assert result["input_type"] == "smiles"
    assert result["task_id"] == "abc123"
    assert result["acute_toxicity"]["ld50"] == "100"
    assert result["acute_toxicity"]["tox_class"] == "3"
    assert result["model_results"] == [
        {"target": "dili", "prediction": "1", "probability": "0.93"},
        {"target": "carcino", "prediction": "0", "probability": "0.12"},
    ]
    assert result["toxicity_targets"][0]["target"] == "Membrane alpha-2 receptor"
    assert result["methodology"]["tier"] == "3a"


def test_name_input_flow(monkeypatch):
    post, get = make_client_side_effect()
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeAsyncClient(post, get))

    result = asyncio_run(predict_toxicity(name="aspirin", models="acute_tox dili"))
    assert result["input_type"] == "name"
    assert result["requested_models"] == "acute_tox dili"


def test_quota_exceeded_raises(monkeypatch):
    post, get = make_client_side_effect(enqueue_status=403)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeAsyncClient(post, get))

    with pytest.raises(ProToxError) as exc:
        asyncio_run(predict_toxicity(smiles="CCO"))
    assert "quota" in str(exc.value).lower()


def test_rate_limited_raises(monkeypatch):
    post, get = make_client_side_effect(enqueue_status=429)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeAsyncClient(post, get))

    with pytest.raises(ProToxError) as exc:
        asyncio_run(predict_toxicity(smiles="CCO"))
    assert "throttl" in str(exc.value).lower()


def test_outage_raises_graceful(monkeypatch):
    post, get = make_client_side_effect(enqueue_status=404)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeAsyncClient(post, get))

    with pytest.raises(ProToxError) as exc:
        asyncio_run(predict_toxicity(smiles="CCO"))
    assert "unavailable" in str(exc.value) or "404" in str(exc.value)


def test_empty_task_id_raises(monkeypatch):
    post, get = make_client_side_effect(enqueue_status=200, enqueue_text=" ")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeAsyncClient(post, get))

    with pytest.raises(ProToxError) as exc:
        asyncio_run(predict_toxicity(smiles="CCO"))
    assert "task id" in str(exc.value).lower()


def test_model_constant_sanity():
    assert ALL_MODELS.split()[0] == "dili"
    assert "CYP3A4" in ALL_MODELS
    assert "acute_tox" in DEFAULT_MODELS
    assert "tox_targets" in DEFAULT_MODELS


@pytest.mark.parametrize("models", [None, "acute_tox", "ALL_MODELS"])
def test_model_arg_variants(monkeypatch, models):
    post, get = make_client_side_effect()
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeAsyncClient(post, get))

    kwargs = {"smiles": "CCO"}
    if models:
        kwargs["models"] = models
    result = asyncio_run(predict_toxicity(**kwargs))
    assert result["requested_models"]

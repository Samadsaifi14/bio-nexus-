"""Scientific-integrity tests for pathway enrichment statistics."""

import pytest

from app.services import pathway_enrichment as pe


class _Response:
    status_code = 200

    def json(self):
        return {
            "result": [
                {
                    "significant": True,
                    "source": "REAC",
                    "native": "R-HSA-123",
                    "name": "Example pathway",
                    "p_value": 0.0042,
                    "p_value_intersections": [0.9, 0.8],
                    "intersection_size": 4,
                    "term_size": 20,
                    "query_size": 8,
                    "effective_domain_size": 18000,
                    "source_order": 1,
                }
            ]
        }


class _Client:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, *args, **kwargs):
        assert kwargs["json"]["significance_threshold_method"] == "g_SCS"
        return _Response()


@pytest.mark.asyncio
async def test_gprofiler_gscs_value_is_not_labelled_fdr(monkeypatch):
    monkeypatch.setattr(pe, "cache_get", lambda *_: None)
    monkeypatch.setattr(pe, "cache_set", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(pe.httpx, "AsyncClient", _Client)

    result = await pe.run_gprofiler_enrichment(["TP53", "BRCA1"])
    assert result is not None
    term = result["results"][0]
    assert term["adjusted_p_value"] == 0.0042
    assert term["correction_method"] == "g_SCS"
    assert "fdr" not in term
    assert "p_value_intersections" not in term


def test_cross_validation_contract_does_not_define_combined_significance():
    # The public contract must keep source-specific statistics separate.
    source = pe.run_cross_validated_enrichment.__doc__ or ""
    assert "does not combine p-values" in source

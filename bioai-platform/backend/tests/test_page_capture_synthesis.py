"""Tests for techspec.md §3 — page capture + final synthesis."""

import asyncio

import pytest

from app.services.page_capture import extract_page_content, capture_page, _last_hit
from app.services import final_synthesis as fs


# ── HTML extraction (stdlib-only parser) ─────────────────────────────────────

_FIXTURE = """
<html><head><title>UniProt | P04637 test</title>
<meta property="og:image" content="https://img.example.org/og.png">
</head><body>
<script>var junk = "<h2>not a heading</h2>";</script>
<h2>Function</h2><p>Tumor suppressor with <b>many</b> roles.</p>
<h3>Subcellular location</h3><p>Nucleus.</p>
<figure><img src="https://img.example.org/fig1.png"></figure>
</body></html>
"""


def test_extract_title_sections_figures():
    out = extract_page_content(_FIXTURE)
    assert out["title"] == "UniProt | P04637 test"
    assert "Tumor suppressor" in out["text_sections"][0]["text"]
    assert out["text_sections"][0]["heading"] == "Function"
    assert any("Subcellular" in (s["heading"] or "") for s in out["text_sections"])
    assert "https://img.example.org/og.png" in out["figure_urls"]
    assert "https://img.example.org/fig1.png" in out["figure_urls"]
    # script-tag contents must not leak into sections
    assert all("junk" not in s["text"] for s in out["text_sections"])


def test_extract_handles_empty_html():
    out = extract_page_content("<html><body></body></html>")
    assert out["title"] is None
    assert out["text_sections"] == []
    assert out["figure_urls"] == []


# ── Capture persistence + failure honesty ────────────────────────────────────


class _FakeTable:
    def __init__(self, store):
        self.store = store

    def upsert(self, row, on_conflict=None):
        self.row = row
        return self

    def execute(self):
        self.store.append(self.row)
        return self


@pytest.mark.asyncio
async def test_capture_success_persists_row(monkeypatch):
    class _Resp:
        status_code = 200
        text = _FIXTURE

        def raise_for_status(self):
            pass

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            return _Resp()

    rows = []
    monkeypatch.setattr("app.services.page_capture._get_supabase", lambda: type("SB", (), {"table": staticmethod(lambda name: _FakeTable(rows))})())
    monkeypatch.setattr("app.services.page_capture.httpx.AsyncClient", _Client)
    monkeypatch.setattr("app.services.page_capture.MIN_INTERVAL_S", 0.0)
    _last_hit.clear()

    row = await capture_page("11111111-2222-3333-4444-555555555555", "uniprot", "https://www.uniprot.org/uniprotkb/P04637", user_id="u1")
    assert row["fetch_status"] == "captured"
    assert row["source"] == "uniprot"
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_capture_failure_still_records_honest_row(monkeypatch):
    class _Boom:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            raise ConnectionError("down")

        async def __aexit__(self, *a):
            return False

    rows = []
    monkeypatch.setattr("app.services.page_capture._get_supabase", lambda: type("SB", (), {"table": staticmethod(lambda name: _FakeTable(rows))})())
    monkeypatch.setattr("app.services.page_capture.httpx.AsyncClient", _Boom)
    monkeypatch.setattr("app.services.page_capture.MIN_INTERVAL_S", 0.0)

    row = await capture_page("11111111-2222-3333-4444-555555555555", "rcsb", "https://www.rcsb.org/structure/1UBQ")
    assert row["fetch_status"] == "failed"
    assert "down" in row["error_note"]
    assert len(rows) == 1  # the attempt is still recorded


@pytest.mark.asyncio
async def test_per_host_rate_limit_enforced(monkeypatch):
    intervals = []

    async def fake_sleep(s):
        intervals.append(s)

    monkeypatch.setattr("app.services.page_capture.asyncio.sleep", fake_sleep)
    from app.services.page_capture import _throttle
    _last_hit.clear()

    await _throttle("example.org")          # first hit: no wait
    assert intervals == []
    await _throttle("example.org")          # immediate repeat: must be throttled
    assert len(intervals) >= 1 and intervals[0] > 0
    n_after_second = len(intervals)
    await _throttle("other.example.org")    # different host: not throttled
    assert len(intervals) == n_after_second


# ── Final synthesis ───────────────────────────────────────────────────────────


def test_findings_thread_confidence_tier():
    context = {
        "query": {"confidence": "homolog"},
        "blast": {"count": 1, "top_hit": {"accession": "P04637", "description": "Cellular tumor antigen"}},
        "uniprot": {"accession": "P04637", "full_name": "Cellular tumor antigen p53"},
    }
    report = fs.synthesize_sync(context)
    tiers = {f["confidence_tier"] for f in report["findings"]}
    assert tiers == {"homolog"}
    assert any("Cellular tumor antigen p53" in f["claim"] for f in report["findings"])
    assert any("homolog" in c.lower() for c in report["caveats"])


def test_denovo_report_is_explicit_about_predictions():
    context = {
        "query": {"confidence": "de_novo"},
        "blast": {"count": 0, "top_hit": None},
        "uniprot": {"_de_novo": True, "composition": {"sequence_type": "protein", "length": 120}},
    }
    report = fs.synthesize_sync(context)
    assert "de novo" in report["headline"].lower()
    joined = " ".join(report["caveats"]).lower()
    assert "prediction" in joined
    findings_tools = [f["source_tool"] for f in report["findings"]]
    assert "blast" in findings_tools and "uniprot" in findings_tools


def test_findings_reference_real_pages():
    context = {
        "query": {"confidence": "identified"},
        "blast": {"count": 1, "top_hit": {"accession": "P04637", "description": "p53"}},
        "uniprot": {"accession": "P04637", "full_name": "p53", "pdb_ids": ["1TUP"]},
        "alphafold": {"structure_available": True, "pdb_url": "https://files.rcsb.org/x.pdb", "mean_plddt": 91.2},
    }
    report = fs.synthesize_sync(context)
    by_tool = {f["source_tool"]: f for f in report["findings"]}
    assert by_tool["uniprot"]["page_url"].startswith("https://www.uniprot.org/")
    assert by_tool["blast"]["page_url"].startswith("https://www.ncbi.nlm.nih.gov/protein/P04637")


@pytest.mark.asyncio
async def test_synthesis_mode_is_deterministic_without_llm(monkeypatch):
    async def no_llm(*a, **k):
        return None

    monkeypatch.setattr(fs, "_polish_with_llm", no_llm)
    context = {"query": {"confidence": "identified"}, "blast": {"count": 0, "top_hit": None}}
    report = await fs.synthesize(context)
    assert report["_mode"] == "deterministic"
    assert report["findings"][0]["claim"].startswith("No significant similarity")

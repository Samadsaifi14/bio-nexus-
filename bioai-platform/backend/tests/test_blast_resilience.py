"""Unit tests for BLAST pipeline resilience.

Covers:
- check_status_until_ready: jobs are not declared STUCK before they get a
  meaningful share of their poll budget (NCBI routinely exceeds RTOE).
- _run_blast (pipeline_v2): NCBI failure falls back to EBI BLAST instead of
  failing the whole pipeline; result shape is normalized across providers.
- BlastTool._submit stype mapping for blastx/tblastn.

Network calls are mocked; these tests never touch the real providers.
"""

import pytest

from app.integrations.ncbi import blast as ncbi_blast


SAMPLE_XML = """<?xml version="1.0"?>
<!DOCTYPE BlastOutput PUBLIC "-//NCBI//NCBI BlastOutput/EN" "http://www.ncbi.nlm.nih.gov/dtd/NCBI_BlastOutput.dtd">
<BlastOutput>
  <BlastOutput_program>blastp</BlastOutput_program>
  <BlastOutput_query-len>7</BlastOutput_query-len>
  <BlastOutput_iterations>
    <Iteration>
      <Iteration_iter-num>1</Iteration_iter-num>
      <Iteration_hits>
        <Hit>
          <Hit_num>1</Hit_num>
          <Hit_id>sp|P12345|FOO_HUMAN</Hit_id>
          <Hit_def>sp|P12345|FOO_HUMAN Foo protein [Homo sapiens]</Hit_def>
          <Hit_accession>P12345</Hit_accession>
          <Hit_len>100</Hit_len>
          <Hit_hsps>
            <Hsp>
              <Hsp_num>1</Hsp_num>
              <Hsp_bit-score>50.0</Hsp_bit-score>
              <Hsp_score>100</Hsp_score>
              <Hsp_evalue>1e-5</Hsp_evalue>
              <Hsp_query-from>1</Hsp_query-from>
              <Hsp_query-to>7</Hsp_query-to>
              <Hsp_hit-from>10</Hsp_hit-from>
              <Hsp_hit-to>16</Hsp_hit-to>
              <Hsp_query-frame>1</Hsp_query-frame>
              <Hsp_hit-frame>1</Hsp_hit-frame>
              <Hsp_identity>5</Hsp_identity>
              <Hsp_positive>6</Hsp_positive>
              <Hsp_gaps>1</Hsp_gaps>
              <Hsp_align-len>8</Hsp_align-len>
              <Hsp_qseq>AAAAA--</Hsp_qseq>
              <Hsp_hseq>AAAAA--</Hsp_hseq>
              <Hsp_midline>AAAAA  </Hsp_midline>
            </Hsp>
          </Hit_hsps>
        </Hit>
      </Iteration_hits>
    </Iteration>
  </BlastOutput_iterations>
</BlastOutput>
"""

PROTEIN_SEQ = "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEA"


class _FakeClock:
    """Deterministic clock: asyncio.sleep() advances it instead of waiting."""

    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now


@pytest.fixture
def fake_clock(monkeypatch):
    clock = _FakeClock()

    async def _fake_sleep(seconds):
        clock.now += seconds

    monkeypatch.setattr(ncbi_blast.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(ncbi_blast.asyncio, "get_event_loop", lambda: clock)
    return clock


async def _always_waiting(rid, fmt="XML"):
    return {"status": "WAITING", "raw": "Status=WAITING", "rid": rid}


async def _ready_after(rid, threshold, fmt="XML"):
    clock = ncbi_blast.asyncio.get_event_loop()
    if clock.time() > threshold:
        return {"status": "READY", "raw": "Status=READY", "rid": rid}
    return {"status": "WAITING", "raw": "Status=WAITING", "rid": rid}


class TestStuckThreshold:
    def test_slow_job_is_not_abandoned_before_half_budget(self, monkeypatch, fake_clock):
        # Regression: a job WAITING for ~188s used to be declared STUCK with a
        # 900s budget (old threshold max(RTOE*5, 180)). It must keep polling.
        async def waiting_then_ready(rid, fmt="XML"):
            return await _ready_after(rid, threshold=300)

        monkeypatch.setattr(ncbi_blast, "check_status", waiting_then_ready)
        result = asyncio_run(ncbi_blast.check_status_until_ready(
            "RID1", max_wait_seconds=900, estimated_seconds=10,
        ))
        assert result["status"] == "READY", result
        assert fake_clock.now >= 300

    def test_truly_stuck_job_declared_stuck_after_half_budget(self, monkeypatch, fake_clock):
        monkeypatch.setattr(ncbi_blast, "check_status", _always_waiting)
        result = asyncio_run(ncbi_blast.check_status_until_ready(
            "RID2", max_wait_seconds=900, estimated_seconds=10,
        ))
        assert result["status"] == "STUCK", result
        assert fake_clock.now >= 450, f"STUCK fired too early at {fake_clock.now:.0f}s"

    def test_budget_exhaustion_returns_timeout_before_stuck(self, monkeypatch, fake_clock):
        # With a small budget, TIMEOUT (end of budget) must win over STUCK.
        monkeypatch.setattr(ncbi_blast, "check_status", _always_waiting)
        result = asyncio_run(ncbi_blast.check_status_until_ready(
            "RID3", max_wait_seconds=120, estimated_seconds=1000,
        ))
        assert result["status"] == "TIMEOUT", result
        assert fake_clock.now >= 120


class TestPipelineBlastFallback:
    def test_ncbi_success_shape(self, monkeypatch):
        from app.routers import pipeline_v2

        async def fake_run_blast_with_retry(*args, **kwargs):
            return {"raw": SAMPLE_XML, "rid": "RID-X"}

        monkeypatch.setattr(pipeline_v2.ncbi_blast, "run_blast_with_retry", fake_run_blast_with_retry)
        result = asyncio_run(pipeline_v2._run_blast(PROTEIN_SEQ))
        assert result["source"] == "ncbi"
        assert result["count"] == 1
        assert result["query_sequence_type"] == "protein"
        assert result["database"] == "nr"
        assert result["top_hit"]["accession"] == "P12345"
        assert result["top_hit"]["evalue"] == 1e-5
        assert result["hits"][0]["hit_alignment"] == "AAAAA--"
        assert result["hits"][0]["query_alignment"] == "AAAAA--"
        assert result["hits"][0]["midline"] == "AAAAA  "

    def test_ncbi_failure_falls_back_to_ebi(self, monkeypatch):
        from app.routers import pipeline_v2

        async def fake_run_blast_with_retry(*args, **kwargs):
            return {"error": "BLAST STUCK after polling (attempt 3/3): Job stuck in WAITING for 188.75s"}

        class FakeEbiTool:
            async def run_uncached(self, input):
                assert input["database"] == "uniprotkb"  # nr mapped to EBI db
                assert input["program"] == "blastp"
                return {
                    "hits": [{
                        "accession": "Q9H2H9",
                        "id": "tr|Q9H2H9|Q9H2H9_HUMAN",
                        "description": "CCHC-type zinc finger protein 3",
                        "organism": "Homo sapiens",
                        "evalue": 1e-30,
                        "bit_score": 210.0,
                        "identity_pct": 98.7,
                        "alignment_length": 152,
                        "query_coverage_pct": 0,
                        "query_from": 1,
                        "query_to": 152,
                        "hit_from": 1,
                        "hit_to": 152,
                    }],
                    "count": 1,
                    "source": "EBI BLAST",
                    "database": "uniprotkb",
                }

        monkeypatch.setattr(pipeline_v2.ncbi_blast, "run_blast_with_retry", fake_run_blast_with_retry)
        monkeypatch.setattr(pipeline_v2, "BlastTool", FakeEbiTool)
        result = asyncio_run(pipeline_v2._run_blast(PROTEIN_SEQ))
        assert result["source"] == "ebi"
        assert result["count"] == 1
        assert result["top_hit"]["accession"] == "Q9H2H9"
        assert result["database"] == "nr"  # reports the requested db, not EBI's
        assert result["hits"][0]["organism"] == "Homo sapiens"
        assert result["hits"][0]["hit_alignment"] == ""  # EBI lacks alignment text
        assert result["hits"][0]["query_coverage_pct"] == pytest.approx(round(152 / len(PROTEIN_SEQ) * 100, 1))

    def test_both_providers_fail_returns_error(self, monkeypatch):
        from app.routers import pipeline_v2

        async def fake_run_blast_with_retry(*args, **kwargs):
            return {"error": "BLAST STUCK after polling (attempt 3/3): Job stuck in WAITING for 188.75s"}

        class EmptyEbiTool:
            async def run_uncached(self, input):
                return {"error": "EBI down", "hits": []}

        monkeypatch.setattr(pipeline_v2.ncbi_blast, "run_blast_with_retry", fake_run_blast_with_retry)
        monkeypatch.setattr(pipeline_v2, "BlastTool", EmptyEbiTool)
        result = asyncio_run(pipeline_v2._run_blast(PROTEIN_SEQ))
        assert result["error"]
        assert "STUCK" in result["error"]
        assert result["count"] == 0
        assert result["hits"] == []

    def test_ebi_fallback_skips_unmapped_database(self):
        from app.routers.pipeline_v2 import _run_ebi_blast_fallback

        result = asyncio_run(_run_ebi_blast_fallback(PROTEIN_SEQ, "blastp", "no_such_db", "protein", 10))
        assert result is None


class TestEbiToolSubmit:
    async def test_stype_mapping(self, monkeypatch):
        from app.tools.blast import BlastTool

        captured = {}

        class FakeResp:
            text = "RID=abc\nRTOE=5"

            def raise_for_status(self):
                pass

        class FakeClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, **kwargs):
                captured["data"] = kwargs["data"]
                return FakeResp()

        monkeypatch.setattr("app.tools.blast.httpx.AsyncClient", lambda **kw: FakeClient())
        tool = BlastTool()
        await tool._submit("MKTAYIAKQRQISFVKSHFSRQDIL", "blastx", "nr")
        assert captured["data"]["stype"] == "protein"  # blastx queries a protein
        await tool._submit("ATGCATGC", "tblastn", "nt")
        assert captured["data"]["stype"] == "dna"


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)

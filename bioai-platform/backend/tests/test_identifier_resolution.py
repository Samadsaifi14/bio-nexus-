"""
Unit tests for the multi-database UniProt identifier resolver.

Offline logic (regex, gene hints, query building, strategy ordering) runs
with mocked HTTP; the strategy ladder against the live UniProt REST API is
covered by a small, marked, network-dependent suite.
"""

import pytest

from app.services import identifier_resolution as ir


# ---------------------------------------------------------------------------
# Offline: accession format detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("acc,expected", [
    ("P04637", True),
    ("Q9H3D4", True),
    ("O88898", True),
    ("A0A0S2Z4N5", True),
    ("A0A024RBG1", True),
    ("p04637", True),          # case-insensitive
    ("NP_003713", False),
    ("4X0Z", False),
    ("ENSP00000269305", False),
    ("", False),
    ("BOGUS", False),
    ("P0463", False),          # too short
    ("P046370", False),        # too long
])
def test_is_uniprot_accession(acc, expected):
    assert ir.is_uniprot_accession(acc) is expected


# ---------------------------------------------------------------------------
# Offline: description parsing helpers
# ---------------------------------------------------------------------------

def test_extract_organism_from_ncbi_bracket():
    assert ir.extract_organism("tumor protein p63 isoform 1 [Homo sapiens]") == "Homo sapiens"
    assert ir.extract_organism("no organism tag here") == ""


def test_extract_gene_hint_variants():
    assert ir.extract_gene_hint("gene=TP63") == "TP63"
    assert ir.extract_gene_hint("recName: Full=foo; short=TP63") == "TP63"
    assert ir.extract_gene_hint("tumor protein p63 isoform 1 [Homo sapiens]") == "p63"
    assert ir.extract_gene_hint("hypothetical protein [Mus musculus]") == ""
    assert ir.extract_gene_hint("") == ""


# ---------------------------------------------------------------------------
# Offline: clean fasta / query hygiene
# ---------------------------------------------------------------------------

def test_clean_fasta():
    assert ir._clean_fasta(">hdr\nMSQSI-HQS\nlower") == "MSQSIHQSLOWER"
    assert ir._clean_fasta(">sp|P04637|TP53_HUMAN p53\nMEQPSDK") == "MEQPSDK"


@pytest.mark.parametrize("seq,expected", [
    ("ACGTACGTACGTTGAC", True),
    ("AUGCGAUGCGA", True),
    ("ATGCNNN", True),
    ("MSQSIHQSLOWER", False),
    ("", False),
    ("---ACGT---", True),
])
def test_looks_nucleotide(seq, expected):
    assert ir._looks_nucleotide(seq) is expected


def test_pick_best_prefers_reviewed():
    rows = [
        {"entryType": "UniProtKB unreviewed (TrEMBL)", "primaryAccession": "A0A111"},
        {"entryType": "UniProtKB reviewed (Swiss-Prot)", "primaryAccession": "P04637"},
    ]
    assert ir._pick_best(rows) == "P04637"
    assert ir._pick_best([]) is None
    assert ir._pick_best([{"entryType": "x", "primaryAccession": ""}]) is None


# ---------------------------------------------------------------------------
# Offline: strategy ladder ordering + mocked HTTP
# ---------------------------------------------------------------------------

class FakeResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeClient:
    """Serves xref:XX -> P99999, but nothing else."""

    def __init__(self, *args, **kwargs):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, params=None, **kwargs):
        self.calls.append((url, params))
        if "idmapping/status" in url:
            # End the (normally slow) polling immediately in tests.
            return FakeResp(200, {"jobStatus": "ERROR"})
        q = (params or {}).get("query", "")
        if "xref:TP63HIT" in q:
            return FakeResp(200, {"results": [
                {"entryType": "UniProtKB reviewed (Swiss-Prot)", "primaryAccession": "Q9H3D4"}
            ]})
        return FakeResp(200, {"results": []})

    async def post(self, url, **kwargs):
        return FakeResp(200, {"jobId": "job-1"})

    async def put(self, url, **kwargs):
        return FakeResp(200, {})


@pytest.mark.asyncio
async def test_direct_accession_short_circuits(monkeypatch):
    called = []

    async def boom(*a, **k):
        called.append(True)
        raise AssertionError("should not hit network")

    monkeypatch.setattr(ir.httpx, "AsyncClient", boom)
    r = await ir.resolve_to_uniprot(accession="P04637")
    assert r == {"accession": "P04637", "method": "direct"}
    assert not called


@pytest.mark.asyncio
async def test_xref_strategy_resolves_refseq(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(ir.httpx, "AsyncClient", lambda *a, **k: fake)
    r = await ir.resolve_to_uniprot(accession="TP63HIT", description="tumor protein p63 [Homo sapiens]")
    assert r["method"] == "xref"
    assert r["accession"] == "Q9H3D4"


@pytest.mark.asyncio
async def test_sequence_strategy_only_when_requested(monkeypatch):
    """try_sequence=False must skip the EBI BLAST fallback entirely."""
    fake = FakeClient()

    def boom(*a, **k):
        raise AssertionError("sequence fallback must be skipped")

    monkeypatch.setattr(ir.httpx, "AsyncClient", lambda *a, **k: fake)
    monkeypatch.setattr(ir, "resolve_by_sequence", boom)
    # ZZ9999 isn't matched by FakeClient's xref stub, so xref+name both fail.
    r = await ir.resolve_to_uniprot(accession="ZZ9999", description="nothing", try_sequence=False)
    assert r is None


@pytest.mark.asyncio
async def test_pdb_chain_suffix_stripped(monkeypatch):
    """4X0Z:A must be searched as xref:4X0Z (parent entry only)."""
    queries = []

    async def fake_search(query, **kwargs):
        queries.append(query)
        return [{"entryType": "UniProtKB reviewed (Swiss-Prot)", "primaryAccession": "P04637"}]

    monkeypatch.setattr(ir, "search_uniprot", fake_search)
    acc = await ir.resolve_by_xref("4X0Z:A")
    assert acc == "P04637"
    assert any("xref:4X0Z" in q for q in queries)
    assert all("4X0Z:A" not in q for q in queries)


@pytest.mark.asyncio
async def test_nucleotide_sequence_skips_sequence_blast(monkeypatch):
    """A nucleotide query must never trigger the protein BLAST fallback."""

    def boom(*a, **k):
        raise AssertionError("nucleotide query must not run protein BLAST")

    # If the guard fails, the real implementation would import and run BlastTool.
    monkeypatch.setattr("app.tools.blast.BlastTool", boom)
    acc = await ir.resolve_by_sequence("ACGTACGTACGTTGACGG")
    assert acc is None


@pytest.mark.asyncio
async def test_no_input_returns_none():
    assert (await ir.resolve_to_uniprot()) is None
    assert (await ir.resolve_to_uniprot(accession="")) is None

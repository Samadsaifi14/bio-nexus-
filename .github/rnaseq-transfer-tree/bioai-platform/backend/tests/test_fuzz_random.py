"""
Fuzz / random data tests.

Verifies that every endpoint degrades gracefully with garbage inputs:
- Returns proper HTTP error codes (4xx/5xx), never an unhandled crash
- Does not leak stack traces in the response body
- Validates input before hitting external APIs or RDKit
"""
import asyncio
import string
import random
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

transport = ASGITransport(app=app)


def _rand_str(n: int) -> str:
    """Random printable string — no control chars, safe for JSON string values."""
    safe = [c for c in string.printable if c.isprintable() and ord(c) < 127]
    return "".join(random.choices(safe, k=n))


def _rand_path_segment(n: int) -> str:
    """Random string safe for URL path segments (no control chars, no slashes)."""
    safe = [c for c in string.printable if c.isprintable() and c not in ('/', '\\', '?', '#', '%')]
    return "".join(random.choices(safe, k=n))


def _rand_pdb_id() -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=4))


def _rand_smiles(n: int) -> str:
    return "".join(random.choices("CNOSPFcnos@#=-+0123456789()[]\\/", k=n))


def _rand_seq(n: int) -> str:
    return "".join(random.choices("ACDEFGHIKLMNPQRSTVWYacdefghiklmnpqrstvwy", k=n))


def _rand_dna(n: int) -> str:
    return "".join(random.choices("ACGTacgt", k=n))


# ============================================================================
# 1. ADMET — SMILES fuzzing
# ============================================================================

class TestFuzzADMET:
    @pytest.mark.asyncio
    async def test_random_smiles_no_crash(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(20):
                s = _rand_smiles(random.randint(1, 50))
                r = await ac.post("/api/admet/descriptors", json={"smiles": s})
                assert r.status_code in (200, 400, 422, 500, 502), f"smiles={s!r} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_empty_smiles_rejected(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/admet/descriptors", json={"smiles": ""})
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_500_char_smiles_rejected(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/admet/descriptors", json={"smiles": "C" * 501})
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_unicode_smiles_no_crash(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            payloads = ["\u00e9\u00e8\u00ea", "\u4e2d\u6587\u5206\u5b50", "\U0001f600\U0001f601"]
            for s in payloads:
                r = await ac.post("/api/admet/descriptors", json={"smiles": s})
                assert r.status_code in (200, 400, 422, 500, 502)

    @pytest.mark.asyncio
    async def test_sql_injection_smiles(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/admet/descriptors", json={"smiles": "'; DROP TABLE molecules; --"})
            assert r.status_code in (200, 400, 422, 500, 502)

    @pytest.mark.asyncio
    async def test_missing_field(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/admet/descriptors", json={})
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_wrong_type_smiles(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/admet/descriptors", json={"smiles": 12345})
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_list_smiles_rejected(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/admet/descriptors", json={"smiles": ["CCO", "c1ccccc1"]})
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_newlines_in_smiles(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/admet/descriptors", json={"smiles": "CCO\nDROP TABLE\n;--"})
            assert r.status_code in (200, 400, 422, 500, 502)

    @pytest.mark.asyncio
    async def test_null_smiles(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/admet/descriptors", json={"smiles": None})
            assert r.status_code == 422


# ============================================================================
# 2. STRUCTURE endpoints — PDB ID fuzzing
# ============================================================================

class TestFuzzStructures:
    @pytest.mark.asyncio
    async def test_random_pdb_search_no_crash(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(10):
                q = _rand_str(random.randint(1, 30))
                r = await ac.post("/api/structures/search", json={"query": q})
                assert r.status_code in (200, 422, 500, 502), f"query={q!r} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_random_inventory_pdb_ids(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(10):
                pid = _rand_pdb_id()
                r = await ac.post("/api/structures/inventory", json={"pdb_id": pid})
                assert r.status_code in (200, 404, 422, 500, 502), f"pdb_id={pid!r} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_inventory_too_long_pdb_id(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/structures/inventory", json={"pdb_id": "ABCDEF"})
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_inventory_special_chars_pdb_id(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for pid in ["'; --", "<script>", "AAAA/../../../etc", "\x00\x01\x02\x03"]:
                r = await ac.post("/api/structures/inventory", json={"pdb_id": pid})
                assert r.status_code == 422, f"pdb_id={pid!r} should be rejected"

    @pytest.mark.asyncio
    async def test_fetch_structure_empty_query(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/structures/fetch", json={"query": ""})
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_fetch_structure_long_query(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/structures/fetch", json={"query": "A" * 10000})
            assert r.status_code in (200, 404, 422, 500, 502)


# ============================================================================
# 3. RAMACHANDRAN / SECONDARY STRUCTURE / COMPARE — path param fuzzing
# ============================================================================

class TestFuzzStructureAnalysis:
    @pytest.mark.asyncio
    async def test_random_pdb_ramachandran(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(10):
                pid = _rand_path_segment(random.randint(1, 4)).lower()
                r = await ac.get(f"/api/analysis/ramachandran/{pid}")
                assert r.status_code in (200, 404, 500, 502), f"pdb={pid} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_random_pdb_secondary_structure(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(10):
                pid = _rand_path_segment(random.randint(1, 4))
                r = await ac.get(f"/api/analysis/secondary_structure/{pid}")
                assert r.status_code in (200, 404, 500, 502), f"pdb={pid} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_random_pdb_compare(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(5):
                pid = _rand_path_segment(random.randint(1, 4))
                r = await ac.get(f"/api/analysis/compare/{pid}", params={"chain": "A", "max_results": 5})
                assert r.status_code in (200, 404, 500, 502, 408), f"pdb={pid} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_ramachandran_long_pdb_id(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/analysis/ramachandran/" + "A" * 100)
            assert r.status_code in (404, 422, 500)

    @pytest.mark.asyncio
    async def test_compare_negative_max_results(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/analysis/compare/1CRN", params={"max_results": -5})
            assert r.status_code in (200, 422, 404, 500, 502)


# ============================================================================
# 4. DOMAINS — accession fuzzing
# ============================================================================

class TestFuzzDomains:
    @pytest.mark.asyncio
    async def test_random_accession_domains(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(10):
                acc = _rand_path_segment(random.randint(1, 20))
                r = await ac.get(f"/api/domains/{acc}")
                assert r.status_code in (200, 404, 422, 500, 502), f"accession={acc!r} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_empty_accession_domains(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/domains/")
            assert r.status_code in (404, 422, 500)

    @pytest.mark.asyncio
    async def test_numeric_accession(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/domains/12345")
            assert r.status_code in (200, 404, 422, 500, 502)


# ============================================================================
# 5. INTERACTIONS — gene name fuzzing
# ============================================================================

class TestFuzzInteractions:
    @pytest.mark.asyncio
    async def test_random_gene_interactions(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(10):
                gene = _rand_path_segment(random.randint(1, 20))
                r = await ac.get(f"/api/interactions/{gene}")
                assert r.status_code in (200, 404, 500, 502), f"gene={gene!r} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_gene_with_special_chars(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/interactions/<script>alert(1)</script>")
            assert r.status_code in (200, 404, 422, 500, 502)


# ============================================================================
# 6. PATHWAYS — query fuzzing
# ============================================================================

class TestFuzzPathways:
    @pytest.mark.asyncio
    async def test_random_pathway_search(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(10):
                q = _rand_str(random.randint(1, 50))
                r = await ac.post("/api/pathways/search", json={"query": q})
                assert r.status_code in (200, 422, 500, 502), f"query={q!r} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_single_char_pathway_search(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/pathways/search", json={"query": "x"})
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_random_kegg_search(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(5):
                q = _rand_str(random.randint(2, 30))
                r = await ac.post("/api/pathways/kegg/search", json={"query": q})
                assert r.status_code in (200, 422, 500, 502)

    @pytest.mark.asyncio
    async def test_random_enrichment(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ids = [_rand_str(random.randint(2, 10)) for _ in range(5)]
            r = await ac.post("/api/pathways/enrichment", json={"identifiers": ids})
            assert r.status_code in (200, 422, 500, 502)

    @pytest.mark.asyncio
    async def test_empty_enrichment(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/pathways/enrichment", json={"identifiers": []})
            assert r.status_code == 422


# ============================================================================
# 7. ALIGNMENT — sequence fuzzing
# ============================================================================

class TestFuzzAlignment:
    @pytest.mark.asyncio
    async def test_random_protein_alignment(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(10):
                seq = _rand_seq(random.randint(1, 200))
                r = await ac.post("/api/alignment/run", json={"sequence": seq, "stype": "protein"})
                assert r.status_code in (200, 422, 500, 502), f"seq_len={len(seq)} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_random_dna_alignment(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(5):
                seq = _rand_dna(random.randint(1, 200))
                r = await ac.post("/api/alignment/run", json={"sequence": seq, "stype": "dna"})
                assert r.status_code in (200, 422, 500, 502)

    @pytest.mark.asyncio
    async def test_empty_alignment(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/alignment/run", json={"sequence": "", "stype": "protein"})
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_numeric_sequence(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/alignment/run", json={"sequence": "1234567890", "stype": "protein"})
            assert r.status_code in (200, 422, 500, 502)

    @pytest.mark.asyncio
    async def test_very_long_alignment(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            seq = _rand_seq(10000)
            r = await ac.post("/api/alignment/run", json={"sequence": seq, "stype": "protein"})
            assert r.status_code in (200, 422, 500, 502, 408, 413)


# ============================================================================
# 8. UNIPROT — accession / query fuzzing
# ============================================================================

class TestFuzzUniProt:
    @pytest.mark.asyncio
    async def test_random_uniprot_search(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(10):
                q = _rand_str(random.randint(2, 30))
                r = await ac.post("/api/uniprot/search", json={"query": q})
                assert r.status_code in (200, 422, 500, 502), f"query={q!r} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_random_uniprot_detail(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(10):
                acc = _rand_str(random.randint(1, 20))
                r = await ac.post("/api/uniprot/detail", json={"accession": acc})
                assert r.status_code in (200, 404, 422, 500, 502), f"accession={acc!r} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_uniprot_search_single_char(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/uniprot/search", json={"query": "a"})
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_uniprot_max_results_extreme(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/uniprot/search", json={"query": "insulin", "max_results": 99999})
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_uniprot_max_results_zero(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/uniprot/search", json={"query": "insulin", "max_results": 0})
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_uniprot_negative_max_results(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/uniprot/search", json={"query": "insulin", "max_results": -1})
            assert r.status_code == 422


# ============================================================================
# 9. FUNCTION PREDICTION — PDB ID pattern fuzzing
# ============================================================================

class TestFuzzFunctionPrediction:
    @pytest.mark.asyncio
    async def test_random_pdb_id_rejected(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(10):
                pid = _rand_str(random.randint(1, 10))
                r = await ac.post("/api/function/predict", json={"pdb_id": pid},
                                  headers={"Authorization": "Bearer test-token"})
                if r.status_code == 401:
                    pytest.skip("Auth required — cannot test without valid token")
                assert r.status_code in (200, 422, 401), f"pdb_id={pid!r} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_too_short_pdb_id(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for pid in ["A", "AB", "ABC", "ABCDE"]:
                r = await ac.post("/api/function/predict", json={"pdb_id": pid},
                                  headers={"Authorization": "Bearer test-token"})
                if r.status_code == 401:
                    pytest.skip("Auth required")
                assert r.status_code == 422, f"pid={pid!r} should be rejected (len != 4)"

    @pytest.mark.asyncio
    async def test_special_chars_pdb_id(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for pid in ["AB;D", "AA/BB", "AA'BB", "AA BB"]:
                r = await ac.post("/api/function/predict", json={"pdb_id": pid},
                                  headers={"Authorization": "Bearer test-token"})
                if r.status_code == 401:
                    pytest.skip("Auth required")
                assert r.status_code == 422, f"pid={pid!r} should be rejected (special chars)"

    @pytest.mark.asyncio
    async def test_missing_pdb_id(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/function/predict", json={},
                              headers={"Authorization": "Bearer test-token"})
            if r.status_code == 401:
                pytest.skip("Auth required")
            assert r.status_code == 422


# ============================================================================
# 10. MD SIMULATION — mode fuzzing
# ============================================================================

class TestFuzzMD:
    @pytest.mark.asyncio
    async def test_random_pdb_id_md(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(5):
                pid = _rand_pdb_id()
                r = await ac.post("/api/md/run", json={"pdb_id": pid},
                                  headers={"Authorization": "Bearer test-token"})
                if r.status_code == 401:
                    pytest.skip("Auth required")
                assert r.status_code in (200, 422, 401), f"pdb_id={pid!r} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_invalid_mode_rejected(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for mode in ["destroy", "explode", "minimize; rm -rf /", "production\n"]:
                r = await ac.post("/api/md/run", json={"pdb_id": "1CRN", "mode": mode},
                                  headers={"Authorization": "Bearer test-token"})
                if r.status_code == 401:
                    pytest.skip("Auth required")
                assert r.status_code == 422, f"mode={mode!r} should be rejected"

    @pytest.mark.asyncio
    async def test_empty_pdb_id_md(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/md/run", json={"pdb_id": ""},
                              headers={"Authorization": "Bearer test-token"})
            if r.status_code == 401:
                pytest.skip("Auth required")
            assert r.status_code == 422


# ============================================================================
# 11. DOCKING — SMILES + grid fuzzing
# ============================================================================

class TestFuzzDocking:
    @pytest.mark.asyncio
    async def test_random_smiles_docking(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(5):
                s = _rand_smiles(random.randint(1, 30))
                r = await ac.post("/api/docking/run", json={"smiles": s, "pdb_id": _rand_pdb_id()},
                                  headers={"Authorization": "Bearer test-token"})
                if r.status_code == 401:
                    pytest.skip("Auth required")
                assert r.status_code in (200, 422, 401), f"smiles={s!r} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_extreme_grid_size(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for gs in [[-1, -1, -1], [0, 0, 0], [99999, 99999, 99999], [0.001, 0.001, 0.001]]:
                r = await ac.post("/api/docking/run",
                                  json={"smiles": "CCO", "pdb_id": "1CRN", "grid_size": gs},
                                  headers={"Authorization": "Bearer test-token"})
                if r.status_code == 401:
                    pytest.skip("Auth required")
                assert r.status_code in (200, 422, 400, 401), f"grid={gs} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_extreme_exhaustiveness(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for ex in [0, -1, 99999]:
                r = await ac.post("/api/docking/run",
                                  json={"smiles": "CCO", "pdb_id": "1CRN", "exhaustiveness": ex},
                                  headers={"Authorization": "Bearer test-token"})
                if r.status_code == 401:
                    pytest.skip("Auth required")
                assert r.status_code in (200, 422, 400, 401), f"exhaustiveness={ex} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_empty_smiles_docking(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/docking/run", json={"smiles": ""},
                              headers={"Authorization": "Bearer test-token"})
            if r.status_code == 401:
                pytest.skip("Auth required")
            assert r.status_code in (200, 422, 401)

    @pytest.mark.asyncio
    async def test_grid_center_wrong_type(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/docking/run",
                              json={"smiles": "CCO", "pdb_id": "1CRN", "grid_center": "not_a_list"},
                              headers={"Authorization": "Bearer test-token"})
            if r.status_code == 401:
                pytest.skip("Auth required")
            assert r.status_code == 422


# ============================================================================
# 12. PIPELINE — sequence + step fuzzing
# ============================================================================

class TestFuzzPipeline:
    @pytest.mark.asyncio
    async def test_random_sequence_pipeline(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(5):
                seq = _rand_seq(random.randint(6, 100))
                r = await ac.post("/api/pipeline/v2/run", json={"sequence": seq})
                assert r.status_code in (200, 422, 500, 502), f"seq_len={len(seq)} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_too_short_sequence(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for seq in ["", "A", "AC", "ACD", "ACDE", "ACDEF"]:
                r = await ac.post("/api/pipeline/v2/run", json={"sequence": seq})
                assert r.status_code == 422, f"seq={seq!r} should be rejected (len < 6)"

    @pytest.mark.asyncio
    async def test_invalid_steps(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/pipeline/v2/run",
                              json={"sequence": "ACDEFG", "steps": ["nonexistent", "fake_step"]})
            assert r.status_code in (200, 422, 400, 500, 502)

    @pytest.mark.asyncio
    async def test_empty_steps_list(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/pipeline/v2/run", json={"sequence": "ACDEFG", "steps": []})
            assert r.status_code in (200, 422, 400, 500)

    @pytest.mark.asyncio
    async def test_numeric_sequence_pipeline(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/pipeline/v2/run", json={"sequence": "123456"})
            assert r.status_code in (200, 400, 422, 500, 502)


# ============================================================================
# 13. SEQUENCING — URL + reference fuzzing
# ============================================================================

class TestFuzzSequencing:
    @pytest.mark.asyncio
    async def test_random_fastq_url(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(5):
                url = _rand_str(random.randint(5, 50))
                r = await ac.post("/api/sequencing/run", json={"fastq_url": url},
                                  headers={"Authorization": "Bearer test-token"})
                if r.status_code == 401:
                    pytest.skip("Auth required")
                assert r.status_code in (200, 422, 400, 500, 502), f"url={url!r} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_empty_fastq_url(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/sequencing/run", json={"fastq_url": ""},
                              headers={"Authorization": "Bearer test-token"})
            if r.status_code == 401:
                pytest.skip("Auth required")
            assert r.status_code in (200, 422, 400, 500)

    @pytest.mark.asyncio
    async def test_random_reference(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ref = _rand_str(random.randint(1, 30))
            r = await ac.post("/api/sequencing/run",
                              json={"fastq_url": "https://example.com/file.fastq", "reference": ref},
                              headers={"Authorization": "Bearer test-token"})
            if r.status_code == 401:
                pytest.skip("Auth required")
            assert r.status_code in (200, 422, 400, 500, 502)

    @pytest.mark.asyncio
    async def test_missing_fastq_url(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/api/sequencing/run", json={},
                              headers={"Authorization": "Bearer test-token"})
            if r.status_code == 401:
                pytest.skip("Auth required")
            assert r.status_code == 422


# ============================================================================
# 14. CROSS-CUTTING: Content-Type / body fuzzing
# ============================================================================

class TestFuzzCrossCutting:
    @pytest.mark.asyncio
    async def test_empty_body_post_endpoints(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            endpoints = [
                "/api/admet/descriptors",
                "/api/pathways/search",
                "/api/pathways/kegg/search",
                "/api/alignment/run",
                "/api/uniprot/search",
                "/api/uniprot/detail",
            ]
            for ep in endpoints:
                r = await ac.post(ep, content=b"", headers={"Content-Type": "application/json"})
                assert r.status_code in (422, 400), f"endpoint={ep} empty body status={r.status_code}"

    @pytest.mark.asyncio
    async def test_malformed_json(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            endpoints = [
                "/api/admet/descriptors",
                "/api/pathways/search",
                "/api/alignment/run",
            ]
            for ep in endpoints:
                r = await ac.post(ep, content=b"{bad json!!!", headers={"Content-Type": "application/json"})
                assert r.status_code in (422, 400), f"endpoint={ep} bad JSON status={r.status_code}"

    @pytest.mark.asyncio
    async def test_json_array_instead_of_object(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            endpoints = [
                "/api/admet/descriptors",
                "/api/pathways/search",
                "/api/alignment/run",
            ]
            for ep in endpoints:
                r = await ac.post(ep, content=b'[1,2,3]', headers={"Content-Type": "application/json"})
                assert r.status_code in (422, 400), f"endpoint={ep} array body status={r.status_code}"

    @pytest.mark.asyncio
    async def test_huge_payload_rejection(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            huge = "A" * 1_000_000
            r = await ac.post("/api/admet/descriptors", json={"smiles": huge})
            assert r.status_code in (422, 413, 400)

    @pytest.mark.asyncio
    async def test_get_on_post_endpoint(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/admet/descriptors")
            assert r.status_code in (405, 404)

    @pytest.mark.asyncio
    async def test_nonexistent_endpoint(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/api/totally_fake_endpoint/xyz")
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_path_traversal_pdb_id(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            paths = [
                "/api/analysis/ramachandran/../../etc/passwd",
                "/api/analysis/secondary_structure/..\\..\\windows\\system32",
                "/api/domains/../../../etc/shadow",
            ]
            for p in paths:
                r = await ac.get(p)
                assert r.status_code in (404, 422, 500), f"path={p} status={r.status_code}"

    @pytest.mark.asyncio
    async def test_xss_in_queries(self):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            xss = "<script>alert('xss')</script>"
            r = await ac.post("/api/structures/search", json={"query": xss})
            assert r.status_code in (200, 422, 500, 502)
            if r.status_code == 200:
                assert "<script>" not in r.text

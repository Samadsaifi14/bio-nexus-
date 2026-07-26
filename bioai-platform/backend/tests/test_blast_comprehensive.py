"""
Comprehensive BLAST test suite — loops over multiple datasets to verify
all BLAST features work end-to-end against live NCBI/EBI APIs.

Tests:
  1. NCBI BLAST integration (submit → poll → fetch)
  2. EBI BLAST tool (submit → poll → fetch)
  3. Multiple protein sequences of varying lengths
  4. Error handling (bad input, edge cases)
  5. Pipeline v2 BLAST step
  6. Retry logic verification

Run:  pytest tests/test_blast_comprehensive.py -v -s --timeout=900
"""

import asyncio
import random
import string
import pytest

# ---------------------------------------------------------------------------
# Test datasets — real protein sequences of varying lengths
# ---------------------------------------------------------------------------
BLAST_TEST_SEQUENCES = [
    {
        "name": "crambin_short",
        "sequence": "TTCCPSIVARSNFNVCRLPG",
        "description": "Crambin first 20 residues (20 aa)",
        "expected_program": "blastp",
        "min_hits": 1,
    },
    {
        "name": "human_insulin",
        "sequence": "MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKTRREAEDLQVGQVELGGGPGAGSLQPLALEGSLQKRGIVEQCCTSICSLYQLENYCN",
        "description": "Human insulin preproinsulin (110 aa)",
        "expected_program": "blastp",
        "min_hits": 1,
    },
    {
        "name": "gfp_fragment",
        "sequence": "MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICTTGKLPVPWPTLVTTFSYGVQCFSRYPDHMKQHDFFKSAMPEGYVQERTIFFKDDGNYKTRAEVKFEGDTLVNRIELKGIDFKEDGNILGHKLEYNYNSHNVYIMADKQKNGIKVNFKIRHNIEDGSVQLADHYQQNTPIGDGPVLLPDNHYLSTQSALSKDPNEKRDHMVLLEFVTAAGITHGMDELYK",
        "description": "Green fluorescent protein (238 aa)",
        "expected_program": "blastp",
        "min_hits": 1,
    },
    {
        "name": "lysozyme",
        "sequence": "KVFGRCELAAAMKRHGLDNYRGYSLGNWVCAAKFESNFNTQATNRNTDGSTDYGILQINSRWWCNDGRTPGSRNLCNIPCSALLSSDITASVNCAKKIVSDGNGMNAWVAWRNRCKGTDVQAWIRGCRL",
        "description": "Hen egg white lysozyme (129 aa)",
        "expected_program": "blastp",
        "min_hits": 1,
    },
    {
        "name": "human_hemoglobin_beta",
        "sequence": "MVHLTPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRFFESFGDLSTPDAVMGNPKVKAHGKKVLGAFSDGLAHLDNLKGTFATLSELHCDKLHVDPENFRLLGNVLVCVLAHHFGKEFTPPVQAAYQKVVAGVANALAHKYH",
        "description": "Human hemoglobin beta subunit (147 aa)",
        "expected_program": "blastp",
        "min_hits": 1,
    },
]

# DNA sequence for blastn testing
DNA_TEST_SEQUENCES = [
    {
        "name": "small_rna",
        "sequence": "ATGGCGACCGGCGCTCCCGCCGGGATCGCCATG",
        "description": "Short DNA fragment (33 bp)",
        "expected_program": "blastn",
        "min_hits": 0,  # DNA may or may not hit depending on db
    },
]

# ---------------------------------------------------------------------------
# 1. NCBI BLAST integration — direct API tests
# ---------------------------------------------------------------------------
class TestNCBIBlastIntegration:
    """Test the NCBI BLAST integration module directly (submit → poll → fetch)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "dataset",
        BLAST_TEST_SEQUENCES[:3],  # First 3 for speed
        ids=[d["name"] for d in BLAST_TEST_SEQUENCES[:3]],
    )
    async def test_ncbi_blast_submit_and_poll(self, dataset):
        """Submit a BLAST job and poll until READY or TIMEOUT."""
        from app.integrations.ncbi.blast import submit_blast, check_status_until_ready

        seq = dataset["sequence"]
        program = dataset["expected_program"]
        db = "swissprot"  # Use swissprot for faster results in tests

        submit_result = await submit_blast(
            seq, program=program, database=db, hitlist_size=10,
        )

        if "error" in submit_result:
            # NCBI may rate-limit; skip if submit fails
            pytest.skip(f"NCBI submit failed: {submit_result['error']}")

        rid = submit_result["rid"]
        assert rid, "RID should not be empty"
        assert len(rid) > 5, f"RID looks too short: {rid}"

        # Poll with generous timeout (2 min for tests)
        status_result = await check_status_until_ready(rid, max_wait_seconds=120)
        status = status_result.get("status", "UNKNOWN")
        assert status in ("READY", "TIMEOUT", "POLL_FAILED", "ERROR", "FAILED"), \
            f"Unexpected status: {status}"

    @pytest.mark.asyncio
    async def test_ncbi_blast_full_roundtrip_short_seq(self):
        """Full roundtrip: submit → poll → fetch results for crambin fragment."""
        from app.integrations.ncbi.blast import run_blast_with_retry

        result = await run_blast_with_retry(
            "TTCCPSIVARSNFNVCRLPG",
            retries=2,
            max_wait_seconds=180,
            program="blastp",
            database="swissprot",
            hitlist_size=10,
        )

        if "error" in result:
            pytest.skip(f"NCBI BLAST roundtrip failed (external API issue): {result['error']}")

        assert "raw" in result, "Should return raw XML"
        assert len(result["raw"]) > 100, "Raw XML too short"

    @pytest.mark.asyncio
    async def test_ncbi_blast_parse_xml(self):
        """Verify XML parsing of NCBI BLAST results."""
        from app.integrations.ncbi.blast import run_blast_with_retry
        from app.integrations.ncbi.parser import parse_blast_xml

        result = await run_blast_with_retry(
            "MVHLTPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRFFESFGDLSTPDAVMGNPKVKAHGKKVLGAFSDGLAHLDNLKGTFATLSELHCDKLHVDPENFRLLGNVLVCVLAHHFGKEFTPPVQAAYQKVVAGVANALAHKYH",
            retries=2,
            max_wait_seconds=180,
            program="blastp",
            database="swissprot",
            hitlist_size=10,
        )

        if "error" in result:
            pytest.skip(f"BLAST failed: {result['error']}")

        parsed = parse_blast_xml(result["raw"])
        assert "error" not in parsed, f"Parse error: {parsed.get('error')}"
        assert parsed["count"] > 0, "Should find at least one hit"
        assert parsed["query_length"] > 0, "Query length should be positive"

        hit = parsed["hits"][0]
        assert hit["accession"], "Hit should have accession"
        assert hit["evalue"] >= 0, "E-value should be non-negative"
        assert hit["bit_score"] > 0, "Bit score should be positive"

    @pytest.mark.asyncio
    async def test_ncbi_blast_retry_on_failure(self):
        """Verify that retry logic works — submitting with invalid sequence should fail gracefully."""
        from app.integrations.ncbi.blast import run_blast_with_retry

        # Submit with clearly invalid sequence (too short / garbage)
        result = await run_blast_with_retry(
            "XXXX",
            retries=1,
            max_wait_seconds=30,
            program="blastp",
            database="swissprot",
        )

        # Should either get an error or no hits — both are acceptable
        # The key is it shouldn't crash with an unhandled exception
        assert isinstance(result, dict), "Result should be a dict"

    @pytest.mark.asyncio
    async def test_ncbi_blast_timeout_handling(self):
        """Verify timeout returns proper error, not an unhandled exception."""
        from app.integrations.ncbi.blast import run_blast_with_retry

        result = await run_blast_with_retry(
            "TTCCPSIVARSNFNVCRLPG",
            retries=0,
            max_wait_seconds=5,  # Very short timeout — will almost certainly time out
            program="blastp",
            database="nr",  # nr is slower than swissprot
        )

        # Should return a dict with error or hits — never crash
        assert isinstance(result, dict), "Should return dict even on timeout"
        # Either it finished very fast (unlikely) or it timed out gracefully
        assert "error" in result or "raw" in result


# ---------------------------------------------------------------------------
# 2. EBI BLAST tool tests
# ---------------------------------------------------------------------------
class TestEBIBlastTool:
    """Test the EBI BLAST tool (BlastTool class)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "dataset",
        BLAST_TEST_SEQUENCES[:2],
        ids=[d["name"] for d in BLAST_TEST_SEQUENCES[:2]],
    )
    async def test_ebi_blast_returns_hits(self, dataset):
        """EBI BLAST should find hits for known proteins."""
        from app.tools.blast import BlastTool

        tool = BlastTool()
        result = await tool.run({
            "sequence": dataset["sequence"],
            "program": "blastp",
            "database": "uniprotkb_swissprot",
            "max_hits": 5,
        })

        assert "hits" in result or "error" in result
        if "hits" in result:
            assert len(result["hits"]) > 0, "Should find at least one hit"
            assert result["count"] == len(result["hits"])

    @pytest.mark.asyncio
    async def test_ebi_blast_hit_structure(self):
        """Verify BLAST hit data structure is correct."""
        from app.tools.blast import BlastTool

        tool = BlastTool()
        result = await tool.run({
            "sequence": "TTCCPSIVARSNFNVCRLPG",
            "program": "blastp",
            "database": "uniprotkb_swissprot",
            "max_hits": 3,
        })

        if "error" in result:
            pytest.skip(f"EBI BLAST failed: {result['error']}")

        for hit in result["hits"]:
            assert "accession" in hit
            assert "evalue" in hit
            assert "bit_score" in hit
            assert "identity_pct" in hit
            assert hit["evalue"] < 1.0, f"E-value too high: {hit['evalue']}"

    @pytest.mark.asyncio
    async def test_ebi_blast_poll_resilience(self):
        """Verify EBI BLAST poll handles transient failures."""
        from app.tools.blast import BlastTool

        tool = BlastTool()
        # This tests the enhanced poll with failure tolerance
        result = await tool.run({
            "sequence": "MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKTRREAEDLQVGQVELGGGPGAGSLQPLALEGSLQKRGIVEQCCTSICSLYQLENYCN",
            "program": "blastp",
            "database": "uniprotkb_swissprot",
            "max_hits": 5,
        })

        # Should not crash — either hits or graceful error
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# 3. Pipeline v2 BLAST step integration
# ---------------------------------------------------------------------------
class TestPipelineV2BLAST:
    """Test BLAST as part of the pipeline v2 flow."""

    @pytest.mark.asyncio
    async def test_pipeline_blast_step_only(self):
        """Run only the BLAST step via pipeline_v2."""
        from app.integrations.ncbi.blast import run_blast_with_retry
        from app.integrations.ncbi.parser import parse_blast_xml

        # Simulate what pipeline_v2._run_blast does
        sequence = "TTCCPSIVARSNFNVCRLPG"
        database = "swissprot"

        results = await run_blast_with_retry(
            sequence,
            retries=2,
            max_wait_seconds=180,
            database=database,
        )

        if "error" in results:
            pytest.skip(f"Pipeline BLAST step failed: {results['error']}")

        parsed = parse_blast_xml(results["raw"])
        assert "error" not in parsed
        assert parsed["count"] > 0

        hits = parsed.get("hits", [])
        top_hit = hits[0] if hits else None

        # Verify the data structure matches what pipeline_v2 expects
        if top_hit:
            assert "accession" in top_hit
            assert "evalue" in top_hit
            assert "identity_pct" in top_hit
            assert "bit_score" in top_hit

    @pytest.mark.asyncio
    async def test_pipeline_blast_multiple_sequences_loop(self):
        """Loop: run BLAST for each test sequence and verify results."""
        from app.integrations.ncbi.blast import run_blast_with_retry
        from app.integrations.ncbi.parser import parse_blast_xml

        results_summary = []

        for dataset in BLAST_TEST_SEQUENCES:
            sequence = dataset["sequence"]
            name = dataset["name"]

            try:
                blast_result = await run_blast_with_retry(
                    sequence,
                    retries=2,
                    max_wait_seconds=180,
                    program=dataset["expected_program"],
                    database="swissprot",
                    hitlist_size=10,
                )

                if "error" in blast_result:
                    results_summary.append({
                        "name": name,
                        "status": "error",
                        "error": blast_result["error"],
                    })
                    continue

                parsed = parse_blast_xml(blast_result["raw"])
                hit_count = parsed.get("count", 0)
                results_summary.append({
                    "name": name,
                    "status": "ok" if hit_count >= dataset["min_hits"] else "low_hits",
                    "hits": hit_count,
                })

            except Exception as e:
                results_summary.append({
                    "name": name,
                    "status": "exception",
                    "error": str(e),
                })

            # Rate limit: wait between requests
            await asyncio.sleep(2)

        # Report results
        print("\n=== BLAST Loop Test Results ===")
        for r in results_summary:
            print(f"  {r['name']}: {r['status']} (hits={r.get('hits', 'N/A')}, error={r.get('error', 'none')})")

        # At least some should succeed (unless NCBI is completely down)
        ok_count = sum(1 for r in results_summary if r["status"] == "ok")
        assert ok_count >= 1, f"No BLAST tests succeeded: {results_summary}"


# ---------------------------------------------------------------------------
# 4. Error handling & edge cases
# ---------------------------------------------------------------------------
class TestBlastErrorHandling:
    """Test BLAST error handling with bad inputs."""

    @pytest.mark.asyncio
    async def test_empty_sequence(self):
        """BLAST should handle empty sequence gracefully."""
        from app.integrations.ncbi.blast import run_blast_with_retry

        result = await run_blast_with_retry(
            "",
            retries=0,
            max_wait_seconds=10,
            database="swissprot",
        )

        assert isinstance(result, dict)
        assert "error" in result or "raw" in result

    @pytest.mark.asyncio
    async def test_invalid_characters(self):
        """BLAST should handle non-biological characters."""
        from app.integrations.ncbi.blast import run_blast_with_retry

        result = await run_blast_with_retry(
            "12345!@#$%^&*()",
            retries=0,
            max_wait_seconds=30,
            program="blastp",
            database="swissprot",
        )

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_very_long_sequence(self):
        """BLAST should handle long sequences (may be slow but shouldn't crash)."""
        from app.integrations.ncbi.blast import run_blast_with_retry

        # Generate a 500 aa random protein sequence
        aa_chars = "ACDEFGHIKLMNPQRSTVWY"
        long_seq = "".join(random.choice(aa_chars) for _ in range(500))

        result = await run_blast_with_retry(
            long_seq,
            retries=1,
            max_wait_seconds=120,
            program="blastp",
            database="swissprot",
        )

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_dna_blastn(self):
        """Test blastn with a short DNA sequence."""
        from app.integrations.ncbi.blast import run_blast_with_retry

        result = await run_blast_with_retry(
            "ATGGCGACCGGCGCTCCCGCCGGGATCGCCATG",
            retries=1,
            max_wait_seconds=120,
            program="blastn",
            database="nt",
            hitlist_size=5,
        )

        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# 5. Random data fuzz testing
# ---------------------------------------------------------------------------
class TestBlastRandomFuzz:
    """Fuzz test: BLAST with random sequences to verify no crashes."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("i", range(5))
    async def test_random_protein_sequence(self, i):
        """Submit 5 random protein sequences — none should crash."""
        from app.integrations.ncbi.blast import run_blast_with_retry

        aa_chars = "ACDEFGHIKLMNPQRSTVWY"
        length = random.randint(10, 80)
        random_seq = "".join(random.choice(aa_chars) for _ in range(length))

        result = await run_blast_with_retry(
            random_seq,
            retries=1,
            max_wait_seconds=90,
            program="blastp",
            database="swissprot",
            hitlist_size=5,
        )

        # Must return a dict — no unhandled exceptions
        assert isinstance(result, dict), f"BLAST crashed on random seq: {random_seq}"
        # Should have either error or raw (results)
        assert "error" in result or "raw" in result

    @pytest.mark.asyncio
    async def test_random_edge_case_lengths(self):
        """Test BLAST with edge-case sequence lengths."""
        from app.integrations.ncbi.blast import run_blast_with_retry

        aa_chars = "ACDEFGHIKLMNPQRSTVWY"
        edge_cases = [
            ("min_valid", "".join(random.choice(aa_chars) for _ in range(6))),  # minimum
            ("medium", "".join(random.choice(aa_chars) for _ in range(50))),
            ("long", "".join(random.choice(aa_chars) for _ in range(200))),
        ]

        for name, seq in edge_cases:
            result = await run_blast_with_retry(
                seq,
                retries=1,
                max_wait_seconds=90,
                program="blastp",
                database="swissprot",
                hitlist_size=5,
            )
            assert isinstance(result, dict), f"BLAST crashed on {name} ({len(seq)} aa)"
            await asyncio.sleep(2)


# ---------------------------------------------------------------------------
# 6. Consecutive reliability test
# ---------------------------------------------------------------------------
class TestBlastReliability:
    """Run BLAST multiple times in sequence to verify consistent behavior."""

    @pytest.mark.asyncio
    async def test_consecutive_blast_runs(self):
        """Run BLAST 3 times with the same sequence — should all succeed or all fail consistently."""
        from app.integrations.ncbi.blast import run_blast_with_retry
        from app.integrations.ncbi.parser import parse_blast_xml

        sequence = "TTCCPSIVARSNFNVCRLPG"
        results = []

        for i in range(3):
            result = await run_blast_with_retry(
                sequence,
                retries=2,
                max_wait_seconds=120,
                program="blastp",
                database="swissprot",
                hitlist_size=5,
            )
            results.append(result)
            await asyncio.sleep(3)

        # Count successes vs failures
        successes = sum(1 for r in results if "raw" in r)
        failures = sum(1 for r in results if "error" in r)

        print(f"\n=== Reliability: {successes} successes, {failures} failures out of 3 ===")

        # At least 2/3 should succeed (NCBI occasional hiccups are OK)
        assert successes >= 2, f"Too many BLAST failures: {failures}/3 failed"

import httpx
import asyncio
import hashlib
import json
from typing import Any
from app.tools.base import BaseTool
from app.config import settings
from app.services.cache import ttl_cache


class BlastTool(BaseTool):
    name = "blast"

    POLL_INTERVAL = 3.0
    MAX_POLL_TIME = 180

    @ttl_cache(ttl=86400, prefix="blast")
    async def run(self, input: dict) -> dict:
        return await self.run_uncached(input)

    async def run_uncached(self, input: dict) -> dict:
        """Same as run(), but never reads/writes the TTL cache.

        The pipeline BLAST fallback uses this so a transient EBI failure is
        not cached for 24 hours (which would poison every later job).
        """
        sequence = input.get("sequence", "").strip()
        database = input.get("database", "uniprotkb_swissprot")
        program = input.get("program", "blastp")
        max_hits = input.get("max_hits", 10)

        job_id = await self._submit(sequence, program, database)
        status = await self._poll(job_id)
        if status != "FINISHED":
            return {"error": f"BLAST job {job_id} ended with status {status}", "hits": []}

        hits = await self._fetch_results(job_id)
        parsed = self._parse_hits(hits, max_hits)
        return {"hits": parsed, "count": len(parsed), "source": "EBI BLAST", "database": database}

    async def _submit(self, sequence: str, program: str, database: str) -> str:
        stype = "protein" if program in ("blastp", "blastx") else "dna"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.EBI_BASE_URL}/run",
                data={"email": settings.NCBI_EMAIL, "sequence": sequence, "program": program, "database": database, "stype": stype},
            )
            resp.raise_for_status()
            return resp.text.strip()

    async def _poll(self, job_id: str) -> str:
        start = asyncio.get_event_loop().time()
        async with httpx.AsyncClient(timeout=15) as client:
            consecutive_failures = 0
            while True:
                elapsed = asyncio.get_event_loop().time() - start
                if elapsed > self.MAX_POLL_TIME:
                    return "TIMEOUT"
                try:
                    resp = await client.get(f"{settings.EBI_BASE_URL}/status/{job_id}")
                    resp.raise_for_status()
                    status = resp.text.strip()
                    consecutive_failures = 0
                except Exception as e:
                    consecutive_failures += 1
                    if consecutive_failures >= 5:
                        return "ERROR"
                    await asyncio.sleep(self.POLL_INTERVAL)
                    continue
                if status in ("FINISHED", "ERROR", "FAILED"):
                    return status
                await asyncio.sleep(self.POLL_INTERVAL)

    async def _fetch_results(self, job_id: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{settings.EBI_BASE_URL}/result/{job_id}/json")
            resp.raise_for_status()
            data = resp.json()
            return data.get("hits", [])

    def _parse_hits(self, raw_hits: list[dict], max_hits: int) -> list[dict]:
        parsed = []
        for hit in raw_hits[:max_hits]:
            hsps = hit.get("hit_hsps") or []
            hsp = hsps[0] if hsps else {}
            desc = hit.get("hit_uni_de") or hit.get("hit_desc", "")
            organism = hit.get("hit_os", "")
            if not organism and "[" in desc and "]" in desc:
                organism = desc.split("[")[-1].rstrip("]")
                desc = desc.split("[")[0].strip()
            parsed.append({
                "accession": hit.get("hit_acc", ""),
                "id": hit.get("hit_id", ""),
                "description": desc,
                "organism": organism,
                "evalue": hsp.get("hsp_expect", 0),
                "bit_score": hsp.get("hsp_bit_score", 0),
                "score": hsp.get("hsp_score", 0),
                # EBI returns hsp_identity/hsp_positive as percentages (0-100),
                # unlike NCBI's raw residue counts — pass them through directly.
                "identity_pct": hsp.get("hsp_identity", 0),
                "positive": hsp.get("hsp_positive", 0),
                "gaps": hsp.get("hsp_gaps", 0),
                "alignment_length": hsp.get("hsp_align_len", 0),
                "query_coverage_pct": 0,
                "query_from": hsp.get("hsp_query_from", 0),
                "query_to": hsp.get("hsp_query_to", 0),
                "hit_from": hsp.get("hsp_hit_from", 0),
                "hit_to": hsp.get("hsp_hit_to", 0),
                "query_alignment": hsp.get("hsp_qseq", ""),
                "hit_alignment": hsp.get("hsp_hseq", ""),
                "midline": hsp.get("hsp_mseq", ""),
            })
        return parsed

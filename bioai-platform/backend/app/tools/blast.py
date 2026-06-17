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

    POLL_INTERVAL = 2.0
    MAX_POLL_TIME = 120

    @ttl_cache(ttl=86400, prefix="blast")
    async def run(self, input: dict) -> dict:
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
        stype = "protein" if program == "blastp" else "dna"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.EBI_BASE_URL}/run",
                data={"email": settings.NCBI_EMAIL, "sequence": sequence, "program": program, "database": database, "stype": stype},
            )
            resp.raise_for_status()
            return resp.text.strip()

    async def _poll(self, job_id: str) -> str:
        start = asyncio.get_event_loop().time()
        async with httpx.AsyncClient(timeout=10) as client:
            while True:
                elapsed = asyncio.get_event_loop().time() - start
                if elapsed > self.MAX_POLL_TIME:
                    return "TIMEOUT"
                resp = await client.get(f"{settings.EBI_BASE_URL}/status/{job_id}")
                resp.raise_for_status()
                status = resp.text.strip()
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
            hsps = hit.get("hsps", [{}])[0] if hit.get("hsps") else {}
            parsed.append({
                "accession": hit.get("hit_acc", ""),
                "id": hit.get("hit_id", ""),
                "description": hit.get("hit_desc", ""),
                "evalue": hsps.get("hsp_expect", 0),
                "bit_score": hsps.get("hsp_bit_score", 0),
                "identity_pct": hsps.get("hsp_identity", 0),
                "alignment_length": hsps.get("hsp_align_len", 0),
                "query_from": hsps.get("hsp_query_from", 0),
                "query_to": hsps.get("hsp_query_to", 0),
                "hit_from": hsps.get("hsp_hit_from", 0),
                "hit_to": hsps.get("hsp_hit_to", 0),
            })
        return parsed

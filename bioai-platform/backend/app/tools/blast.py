import asyncio
import logging
import re

import httpx

from app.config import settings
from app.integrations.ncbi.parser import parse_blast_xml
from app.services.cache import ttl_cache
from app.tools.base import BaseTool

logger = logging.getLogger(__name__)


class BlastTool(BaseTool):
    name = "blast"

    POLL_INTERVAL = 4.0
    BASE_MAX_POLL_TIME = 180
    LONG_QUERY_MAX_POLL_TIME = 480

    @ttl_cache(ttl=86400, prefix="blast")
    async def run(self, input: dict) -> dict:
        return await self.run_uncached(input)

    async def run_uncached(self, input: dict) -> dict:
        """Run an EBI BLAST job without caching transient provider failures.

        Long protein queries can legitimately take longer than three minutes,
        so the polling budget scales with query length instead of treating a
        slow provider as a biological no-hit result.
        """
        sequence = self._clean_sequence(str(input.get("sequence", "")))
        database = input.get("database", "uniprotkb_swissprot")
        program = input.get("program", "blastp")
        try:
            max_hits = max(1, min(int(input.get("max_hits", 10)), 100))
        except (TypeError, ValueError):
            max_hits = 10

        if not sequence:
            return {"error": "BLAST query sequence is empty after normalization", "hits": [], "count": 0}

        job_id = await self._submit(sequence, program, database)
        poll_budget = self.LONG_QUERY_MAX_POLL_TIME if len(sequence) >= 500 else self.BASE_MAX_POLL_TIME
        status = await self._poll(job_id, poll_budget)
        if status != "FINISHED":
            return {
                "error": f"EBI BLAST job ended with status {status}",
                "hits": [],
                "count": 0,
                "provider_status": status,
            }

        hits = await self._fetch_results(job_id)
        parsed = self._parse_hits(hits, max_hits)
        if not parsed:
            xml_hits = await self._fetch_xml_fallback(job_id, max_hits)
            if xml_hits:
                parsed = xml_hits

        return {
            "hits": parsed,
            "count": len(parsed),
            "source": "EBI BLAST",
            "database": database,
            "program": program,
        }

    @staticmethod
    def _clean_sequence(sequence: str) -> str:
        lines = []
        for line in sequence.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(">"):
                continue
            lines.append(stripped)
        joined = "".join(lines) if lines else sequence
        return re.sub(r"[^A-Za-z*]", "", joined).upper().rstrip("*")

    async def _submit(self, sequence: str, program: str, database: str) -> str:
        stype = "protein" if program in ("blastp", "blastx") else "dna"
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(
                f"{settings.EBI_BASE_URL}/run",
                data={
                    "email": settings.NCBI_EMAIL,
                    "sequence": sequence,
                    "program": program,
                    "database": database,
                    "stype": stype,
                },
            )
            resp.raise_for_status()
            job_id = resp.text.strip()
            if not job_id or " " in job_id or "\n" in job_id:
                raise RuntimeError("EBI BLAST did not return a valid job identifier")
            return job_id

    async def _poll(self, job_id: str, max_poll_time: int) -> str:
        start = asyncio.get_running_loop().time()
        async with httpx.AsyncClient(timeout=20) as client:
            consecutive_failures = 0
            while True:
                elapsed = asyncio.get_running_loop().time() - start
                if elapsed > max_poll_time:
                    return "TIMEOUT"
                try:
                    resp = await client.get(f"{settings.EBI_BASE_URL}/status/{job_id}")
                    resp.raise_for_status()
                    status = resp.text.strip().upper()
                    consecutive_failures = 0
                except Exception as exc:
                    consecutive_failures += 1
                    logger.warning("EBI BLAST status check failed for %s (%d/5): %s", job_id, consecutive_failures, exc)
                    if consecutive_failures >= 5:
                        return "ERROR"
                    await asyncio.sleep(self.POLL_INTERVAL)
                    continue

                if status in ("FINISHED", "ERROR", "FAILED", "NOT_FOUND"):
                    return status
                await asyncio.sleep(self.POLL_INTERVAL)

    async def _fetch_results(self, job_id: str) -> list[dict]:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=45) as client:
                    resp = await client.get(f"{settings.EBI_BASE_URL}/result/{job_id}/json")
                    resp.raise_for_status()
                    data = resp.json()
                    hits = self._extract_hits(data)
                    if hits:
                        return hits
                    return []
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(2 * (attempt + 1))
        if last_error:
            logger.warning("EBI BLAST JSON retrieval failed for %s: %s", job_id, last_error)
        return []

    @staticmethod
    def _extract_hits(data: object) -> list[dict]:
        if not isinstance(data, dict):
            return []
        direct = data.get("hits")
        if isinstance(direct, list):
            return [hit for hit in direct if isinstance(hit, dict)]
        for key in ("result", "results", "search"):
            nested = data.get(key)
            if isinstance(nested, dict):
                hits = nested.get("hits")
                if isinstance(hits, list):
                    return [hit for hit in hits if isinstance(hit, dict)]
        return []

    async def _fetch_xml_fallback(self, job_id: str, max_hits: int) -> list[dict]:
        """Parse the provider's XML representation if JSON has no usable hits."""
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                resp = await client.get(f"{settings.EBI_BASE_URL}/result/{job_id}/xml")
                resp.raise_for_status()
            parsed = parse_blast_xml(resp.text)
            if parsed.get("error"):
                logger.warning("EBI BLAST XML fallback parse failed for %s: %s", job_id, parsed["error"])
                return []
            return list(parsed.get("hits", []))[:max_hits]
        except Exception as exc:
            logger.warning("EBI BLAST XML fallback failed for %s: %s", job_id, exc)
            return []

    def _parse_hits(self, raw_hits: list[dict], max_hits: int) -> list[dict]:
        parsed = []
        for hit in raw_hits[:max_hits]:
            hsps = hit.get("hit_hsps") or hit.get("hsps") or []
            hsp = hsps[0] if isinstance(hsps, list) and hsps else {}
            if not isinstance(hsp, dict):
                hsp = {}
            desc = hit.get("hit_uni_de") or hit.get("hit_desc") or hit.get("description") or ""
            organism = hit.get("hit_os") or hit.get("organism") or ""
            if not organism and "[" in desc and "]" in desc:
                organism = desc.split("[")[-1].rstrip("]")
                desc = desc.split("[")[0].strip()

            accession = hit.get("hit_acc") or hit.get("accession") or ""
            if not accession:
                continue

            identity = hsp.get("hsp_identity", hsp.get("identity_pct", hsp.get("identity", 0)))
            align_len = hsp.get("hsp_align_len", hsp.get("alignment_length", 0)) or 0
            if isinstance(identity, (int, float)) and align_len and identity <= align_len:
                identity_pct = round(float(identity) / float(align_len) * 100, 1)
            else:
                identity_pct = identity or 0

            parsed.append({
                "accession": accession,
                "id": hit.get("hit_id", hit.get("id", "")),
                "description": desc,
                "organism": organism,
                "evalue": hsp.get("hsp_expect", hsp.get("evalue", 0)),
                "bit_score": hsp.get("hsp_bit_score", hsp.get("bit_score", 0)),
                "score": hsp.get("hsp_score", hsp.get("score", 0)),
                "identity_pct": identity_pct,
                "positive": hsp.get("hsp_positive", hsp.get("positive", 0)),
                "gaps": hsp.get("hsp_gaps", hsp.get("gaps", 0)),
                "alignment_length": align_len,
                "query_coverage_pct": 0,
                "query_from": hsp.get("hsp_query_from", hsp.get("query_from", 0)),
                "query_to": hsp.get("hsp_query_to", hsp.get("query_to", 0)),
                "hit_from": hsp.get("hsp_hit_from", hsp.get("hit_from", 0)),
                "hit_to": hsp.get("hsp_hit_to", hsp.get("hit_to", 0)),
                "query_alignment": hsp.get("hsp_qseq", hsp.get("query_alignment", "")),
                "hit_alignment": hsp.get("hsp_hseq", hsp.get("hit_alignment", "")),
                "midline": hsp.get("hsp_mseq", hsp.get("midline", "")),
            })
        return parsed

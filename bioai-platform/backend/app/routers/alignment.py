import asyncio
import logging
import xml.etree.ElementTree as ET

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

EBI_BASE = "https://www.ebi.ac.uk/Tools/services/rest/clustalo"
POLL_INTERVAL = 2
MAX_POLLS = 120


class AlignRequest(BaseModel):
    sequence: str = Field(..., min_length=1, description="Two or more sequences in FASTA format")
    stype: str = Field("protein", description="Sequence type: protein or dna")


async def _get_available_types(client: httpx.AsyncClient, job_id: str) -> list[str]:
    """Query EBI for available result types for this job."""
    try:
        resp = await client.get(f"{EBI_BASE}/result/{job_id}/", headers={"Accept": "text/plain, application/xml"})
        if resp.status_code == 200:
            text = resp.text.strip()
            # Try parsing as XML first
            if text.startswith("<"):
                root = ET.fromstring(text)
                found = [t.text for t in root.iter() if t.text and t.tag == "type"]
                if found:
                    return found
            # Fall back to plain text (one type per line)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if lines:
                return lines
    except Exception:
        pass
    return []


async def _fetch_result(client: httpx.AsyncClient, job_id: str, type_name: str) -> str | None:
    """Try to fetch a specific result type from EBI."""
    for attempt in range(3):
        try:
            resp = await client.get(
                f"{EBI_BASE}/result/{job_id}/{type_name}",
                headers={"Accept": "text/plain"},
            )
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
        if attempt < 2:
            await asyncio.sleep(1)
    return None


@router.post("/run")
async def run_alignment(req: AlignRequest):
    email = settings.NCBI_EMAIL or "bioflow@example.com"

    async with httpx.AsyncClient(timeout=30) as client:
        submit_resp = await client.post(
            f"{EBI_BASE}/run",
            data={"email": email, "stype": req.stype, "sequence": req.sequence},
            headers={"Accept": "text/plain"},
        )
        if submit_resp.status_code != 200:
            detail = submit_resp.text[:200] if submit_resp.text else "EBI alignment submission failed"
            raise HTTPException(status_code=502, detail=f"EBI submission failed: {detail}")
        job_id = submit_resp.text.strip()
        logger.info(f"EBI alignment job submitted: {job_id}")

        for _ in range(MAX_POLLS):
            await asyncio.sleep(POLL_INTERVAL)
            try:
                status_resp = await client.get(f"{EBI_BASE}/status/{job_id}")
                status = status_resp.text.strip()
            except Exception as e:
                logger.warning(f"EBI status poll failed: {e}")
                continue
            logger.info(f"EBI alignment status ({job_id}): {status}")
            if status == "FINISHED":
                break
            if status == "ERROR":
                raise HTTPException(status_code=502, detail="EBI alignment job failed")
        else:
            raise HTTPException(status_code=504, detail="EBI alignment timed out")

        await asyncio.sleep(1)

        # Get available result types from EBI
        available = await _get_available_types(client, job_id)
        logger.info(f"Available result types for {job_id}: {available}")

        if not available:
            raise HTTPException(status_code=502, detail="No result types available from EBI")

        # Find the best alignment type (FASTA-like), then Clustal, then tree
        fasta_type = next((t for t in available if "fasta" in t.lower()), available[0])
        clustal_type = next((t for t in available if "clustal" in t.lower()), None)
        tree_type = next((t for t in available if "phylotree" in t.lower() or "guide" in t.lower() or "tree" in t.lower()), None)

        fasta_text = await _fetch_result(client, job_id, fasta_type)
        if fasta_text is None:
            raise HTTPException(status_code=502, detail=f"Failed to fetch result type '{fasta_type}' from EBI")

        clustal_text = None
        if clustal_type:
            clustal_text = await _fetch_result(client, job_id, clustal_type)

        tree_text = None
        if tree_type:
            tree_text = await _fetch_result(client, job_id, tree_type)

    return {
        "job_id": job_id,
        "aln_fasta": fasta_text,
        "aln_clustal": clustal_text or "",
        "phylotree": tree_text or "",
        "stype": req.stype,
    }

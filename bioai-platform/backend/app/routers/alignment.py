import asyncio
import logging

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

EBI_BASE = "https://www.ebi.ac.uk/Tools/services/rest/clustalo"
POLL_INTERVAL = 2
MAX_POLLS = 120

# Valid result type names for Clustal Omega (confirmed via live API testing)
# `fa` = FASTA alignment, `out` = stdout log, `phylotree` = Newick tree
TREE_TYPES = ["phylotree"]


class AlignRequest(BaseModel):
    sequence: str = Field(..., min_length=1, description="Two or more sequences in FASTA format")
    stype: str = Field("protein", description="Sequence type: protein or dna")


async def _fetch_result(client: httpx.AsyncClient, job_id: str, type_name: str) -> str | None:
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

        # Fetch FASTA alignment (result type `fa` — NOT `aln-fasta`)
        fasta_text = await _fetch_result(client, job_id, "fa")
        if fasta_text is None:
            raise HTTPException(status_code=502, detail="Failed to fetch alignment result from EBI")

        # Try phylogenetic tree (best-effort)
        tree_text = None
        for t in TREE_TYPES:
            tree_text = await _fetch_result(client, job_id, t)
            if tree_text:
                break

    return {
        "job_id": job_id,
        "aln_fasta": fasta_text,
        "aln_clustal": "",
        "phylotree": tree_text or "",
        "stype": req.stype,
    }

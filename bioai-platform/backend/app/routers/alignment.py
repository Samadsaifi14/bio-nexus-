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
MAX_POLLS = 60


class AlignRequest(BaseModel):
    sequence: str = Field(..., min_length=1, description="Two or more sequences in FASTA format")
    stype: str = Field("protein", description="Sequence type: protein or dna")


@router.post("/run")
async def run_alignment(req: AlignRequest):
    email = settings.NCBI_EMAIL or "bioflow@example.com"
    async with httpx.AsyncClient(timeout=30) as client:
        submit_resp = await client.post(
            f"{EBI_BASE}/run",
            data={
                "email": email,
                "stype": req.stype,
                "sequence": req.sequence,
            },
        )
        if submit_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="EBI alignment submission failed")
        job_id = submit_resp.text.strip()

        for _ in range(MAX_POLLS):
            await asyncio.sleep(POLL_INTERVAL)
            status_resp = await client.get(f"{EBI_BASE}/status/{job_id}")
            status = status_resp.text.strip()
            if status == "FINISHED":
                break
            if status == "ERROR":
                raise HTTPException(status_code=502, detail="EBI alignment job failed")
        else:
            raise HTTPException(status_code=504, detail="EBI alignment timed out")

        fasta_resp = await client.get(f"{EBI_BASE}/result/{job_id}/aln-fasta")
        if fasta_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch alignment result")
        fasta = fasta_resp.text

        clustal_resp = await client.get(f"{EBI_BASE}/result/{job_id}/aln-clustal")
        clustal = clustal_resp.text if clustal_resp.status_code == 200 else ""

        tree_resp = await client.get(f"{EBI_BASE}/result/{job_id}/phylotree")
        tree = tree_resp.text if tree_resp.status_code == 200 else ""

    return {
        "job_id": job_id,
        "aln_fasta": fasta,
        "aln_clustal": clustal,
        "phylotree": tree,
        "stype": req.stype,
    }

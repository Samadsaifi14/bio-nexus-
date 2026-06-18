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
RESULT_RETRIES = 5


class AlignRequest(BaseModel):
    sequence: str = Field(..., min_length=1, description="Two or more sequences in FASTA format")
    stype: str = Field("protein", description="Sequence type: protein or dna")


@router.post("/run")
async def run_alignment(req: AlignRequest):
    email = settings.NCBI_EMAIL or "bioflow@example.com"
    headers = {"Accept": "text/plain"}

    async with httpx.AsyncClient(timeout=30) as client:
        submit_resp = await client.post(
            f"{EBI_BASE}/run",
            data={"email": email, "stype": req.stype, "sequence": req.sequence},
            headers=headers,
        )
        if submit_resp.status_code != 200:
            detail = submit_resp.text[:200] if submit_resp.text else "EBI alignment submission failed"
            raise HTTPException(status_code=502, detail=f"EBI submission failed: {detail}")
        job_id = submit_resp.text.strip()
        logger.info(f"EBI alignment job submitted: {job_id}")

        for _ in range(MAX_POLLS):
            await asyncio.sleep(POLL_INTERVAL)
            status_resp = await client.get(f"{EBI_BASE}/status/{job_id}", headers=headers)
            status = status_resp.text.strip()
            logger.info(f"EBI alignment status ({job_id}): {status}")
            if status == "FINISHED":
                break
            if status == "ERROR":
                raise HTTPException(status_code=502, detail="EBI alignment job failed")
        else:
            raise HTTPException(status_code=504, detail="EBI alignment timed out")

        # Small delay after FINISHED before fetching results
        await asyncio.sleep(1)

        # Fetch results with retry — EBI sometimes needs a moment after FINISHED
        for attempt in range(RESULT_RETRIES):
            fasta_resp = await client.get(f"{EBI_BASE}/result/{job_id}/aln-fasta", headers=headers)
            if fasta_resp.status_code == 200:
                break
            if attempt < RESULT_RETRIES - 1:
                await asyncio.sleep(1)
        else:
            detail = fasta_resp.text[:200] if fasta_resp.text else "unknown"
            raise HTTPException(status_code=502, detail=f"Failed to fetch alignment result: {detail}")

        fasta = fasta_resp.text

        # Fetch optional results (Clustal, tree) — best-effort
        clustal = ""
        try:
            c_resp = await client.get(f"{EBI_BASE}/result/{job_id}/aln-clustal", headers=headers)
            if c_resp.status_code == 200:
                clustal = c_resp.text
        except Exception:
            pass

        tree = ""
        try:
            t_resp = await client.get(f"{EBI_BASE}/result/{job_id}/phylotree", headers=headers)
            if t_resp.status_code == 200:
                tree = t_resp.text
        except Exception:
            pass

    return {
        "job_id": job_id,
        "aln_fasta": fasta,
        "aln_clustal": clustal,
        "phylotree": tree,
        "stype": req.stype,
    }

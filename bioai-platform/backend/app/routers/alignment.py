import asyncio
import logging
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.tools.pairwise_alignment import PairwiseAlignError, pairwise_align
from app.tools.sequence_fetch import fetch_sequence_by_accession

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


class PairwiseAlignRequest(BaseModel):
    hit_accession: str = Field(..., min_length=1, description="Subject accession to fetch and align against")
    query_sequence: str = Field("", description="Full query sequence (overrides query_accession)")
    query_accession: str = Field("", description="Query accession; used when query_sequence is empty")
    mode: str = Field("global", description="global (Needleman-Wunsch, default) or local (Smith-Waterman)")
    matrix: str = Field("blosum62", description="blosum62 (default) or pam250")
    open_gap_score: float = Field(-10, description="Gap-open penalty")
    extend_gap_score: float = Field(-1, description="Gap-extension penalty")
    source: str = Field("auto", description="auto|ncbi|uniprot — where to fetch sequences")


class PairwiseAlignResponse(BaseModel):
    mode: str
    matrix: str
    score: float
    aligned_query: str
    aligned_hit: str
    alignment_length: int
    identity: int
    pct_identity: float
    gaps_total: int
    gap_positions: list[dict[str, Any]]
    query_start: int
    query_end: int
    hit_start: int
    hit_end: int
    query_length: int
    hit_length: int
    hit_source: str


@router.post("/pairwise", response_model=PairwiseAlignResponse)
async def run_pairwise(req: PairwiseAlignRequest):
    if req.mode not in ("global", "local"):
        raise HTTPException(status_code=400, detail="mode must be 'global' or 'local'")
    if req.matrix not in ("blosum62", "pam250"):
        raise HTTPException(status_code=400, detail="matrix must be 'blosum62' or 'pam250'")

    query_seq = (req.query_sequence or "").strip()
    if not query_seq:
        if not req.query_accession:
            raise HTTPException(status_code=400, detail="Provide a query_sequence or query_accession")
        query = await fetch_sequence_by_accession(req.query_accession, req.source)
        if "error" in query:
            raise HTTPException(status_code=400, detail=f"Query fetch failed: {query['error']}")
        query_seq = query["sequence"]

    hit = await fetch_sequence_by_accession(req.hit_accession, req.source)
    if "error" in hit:
        raise HTTPException(
            status_code=400,
            detail=f"Could not fetch subject sequence for {req.hit_accession}: {hit['error']}",
        )

    try:
        result = pairwise_align(
            seq_a=query_seq,
            seq_b=hit["sequence"],
            mode=req.mode,
            matrix=req.matrix,
            open_gap_score=req.open_gap_score,
            extend_gap_score=req.extend_gap_score,
        )
    except PairwiseAlignError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result["hit_source"] = hit.get("source", "")
    return result


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

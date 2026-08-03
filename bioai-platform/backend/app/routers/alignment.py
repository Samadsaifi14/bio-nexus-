import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.tools.ebi_msa import EBI_TOOLS, run_ebi_msa
from app.tools.pairwise_alignment import PairwiseAlignError, pairwise_align
from app.tools.sequence_fetch import fetch_sequence_by_accession

logger = logging.getLogger(__name__)
router = APIRouter()


class AlignRequest(BaseModel):
    sequence: str = Field(..., min_length=1, description="Two or more sequences in FASTA format")
    stype: str = Field("protein", description="Sequence type: protein or dna")
    method: str = Field(
        "clustalo",
        description="MSA method: clustalo, muscle, kalign, mafft, or tcoffee",
    )


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


@router.post("/run")
async def run_alignment(req: AlignRequest):
    if req.method not in EBI_TOOLS:
        raise HTTPException(
            status_code=400,
            detail=f"method must be one of: {', '.join(sorted(EBI_TOOLS))}",
        )
    email = settings.NCBI_EMAIL or "bioflow@example.com"

    try:
        result = await run_ebi_msa(
            base_url=EBI_TOOLS[req.method],
            sequence=req.sequence,
            stype=req.stype,
            email=email,
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {
        "job_id": result["job_id"],
        "aln_fasta": result["aln_fasta"],
        "aln_clustal": "",
        "phylotree": result["phylotree"],
        "stype": req.stype,
        "method": result["method"],
    }

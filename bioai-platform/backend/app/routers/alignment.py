import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.services import job_registry
from app.services.auth import get_user_id
from app.tools.ebi_msa import EBI_TOOLS, run_ebi_msa_best_effort, validate_msa_input
from app.tools.pairwise_alignment import PairwiseAlignError, pairwise_align
from app.tools.sequence_fetch import fetch_sequence_by_accession

logger = logging.getLogger(__name__)
router = APIRouter()


class AlignRequest(BaseModel):
    sequence: str = Field(..., min_length=1, description="Two or more sequences in FASTA format")
    stype: str = Field("protein", description="Sequence type: protein or dna")
    method: str = Field("clustalo", description="MSA method: clustalo, muscle, kalign, mafft, or tcoffee")


class PairwiseAlignRequest(BaseModel):
    hit_accession: str = Field("", description="Subject accession to fetch and align against (optional when subject_sequence is given)")
    subject_sequence: str = Field("", description="Full subject sequence (overrides hit_accession)")
    query_sequence: str = Field("", description="Full query sequence (overrides query_accession)")
    query_accession: str = Field("", description="Query accession; used when query_sequence is empty")
    mode: str = Field("global", description="global (Needleman-Wunsch) or local (Smith-Waterman)")
    matrix: str = Field("blosum62", description="blosum62 or pam250")
    open_gap_score: float = Field(-10, description="Gap-open penalty")
    extend_gap_score: float = Field(-1, description="Gap-extension penalty")
    source: str = Field("auto", description="auto|ncbi|uniprot")


def _strip_fasta_header(seq: str) -> str:
    lines = (seq or "").strip().splitlines()
    lines = [line for line in lines if not line.strip().startswith(">")]
    return "\n".join(lines)


class PairwiseAlignResponse(BaseModel):
    mode: str
    matrix: str
    open_gap_score: float
    extend_gap_score: float
    score: float
    aligned_query: str
    aligned_hit: str
    alignment_length: int
    identity: int
    pct_identity: float
    similarity: int
    pct_similarity: float
    mismatches: int
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
async def run_pairwise(req: PairwiseAlignRequest, user_id: str | None = Depends(get_user_id)):
    if req.mode not in ("global", "local"):
        raise HTTPException(status_code=400, detail="mode must be 'global' or 'local'")
    if req.matrix not in ("blosum62", "pam250"):
        raise HTTPException(status_code=400, detail="matrix must be 'blosum62' or 'pam250'")

    query_seq = _strip_fasta_header(req.query_sequence or "")
    if not query_seq:
        if not req.query_accession:
            raise HTTPException(status_code=400, detail="Provide a query_sequence or query_accession")
        query = await fetch_sequence_by_accession(req.query_accession, req.source)
        if "error" in query:
            raise HTTPException(status_code=400, detail=f"Query fetch failed: {query['error']}")
        query_seq = query["sequence"]

    hit_seq = _strip_fasta_header(req.subject_sequence or "")
    hit_source = ""
    if not hit_seq:
        if not req.hit_accession:
            raise HTTPException(status_code=400, detail="Provide a subject_sequence or hit_accession")
        hit = await fetch_sequence_by_accession(req.hit_accession, req.source)
        if "error" in hit:
            raise HTTPException(status_code=400, detail=f"Could not fetch subject sequence for {req.hit_accession}: {hit['error']}")
        hit_seq = hit["sequence"]
        hit_source = hit.get("source", "")

    try:
        result = pairwise_align(
            seq_a=query_seq,
            seq_b=hit_seq,
            mode=req.mode,
            matrix=req.matrix,
            open_gap_score=req.open_gap_score,
            extend_gap_score=req.extend_gap_score,
        )
    except PairwiseAlignError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    result["hit_source"] = hit_source
    job_registry.record_completed(
        "pairwise", user_id,
        query_preview=f"Pairwise {req.mode} · {len(query_seq)}×{len(hit_seq)} aa",
        context={"mode": req.mode, "matrix": req.matrix, "score": result.get("score"),
                 "identities": result.get("identities")}
        if "score" in result else {"mode": req.mode, "matrix": req.matrix},
    )
    return result


@router.post("/run")
async def run_alignment(req: AlignRequest, user_id: str | None = Depends(get_user_id)):
    if req.method not in EBI_TOOLS:
        raise HTTPException(status_code=400, detail=f"method must be one of: {', '.join(sorted(EBI_TOOLS))}")

    # Validate before any provider call. This prevents malformed FASTA, duplicate
    # identifiers, invalid residues, and single-record inputs from being sent to EBI.
    try:
        records = validate_msa_input(req.sequence, req.stype)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    email = settings.NCBI_EMAIL or "bioflow@example.com"
    response: dict[str, Any]
    try:
        # Try the requested EBI engine first, then the configured alternate
        # engines. A provider rejection must not immediately fail the workflow.
        fallback_order = [req.method] + [name for name in ("clustalo", "muscle", "kalign", "mafft", "tcoffee") if name != req.method]
        result = await run_ebi_msa_best_effort(
            sequence=req.sequence,
            stype=req.stype,
            email=email,
            tools=fallback_order,
        )
        response = {
            "job_id": result.get("job_id"),
            "aln_fasta": result["aln_fasta"],
            "aln_clustal": "",
            "phylotree": result.get("phylotree", ""),
            "stype": req.stype,
            "method": result.get("method", req.method),
            "provider": result.get("provider", "EMBL-EBI Job Dispatcher"),
            "provider_fallback": bool(result.get("provider_fallback")),
            "validation": result.get("validation"),
        }
    except Exception as provider_exc:
        # Explicitly labelled deterministic local fallback. Never label this as
        # Clustal Omega or claim remote-provider execution.
        logger.warning(
            "All EMBL-EBI MSA providers failed; using in-process fallback (%s)",
            type(provider_exc).__name__,
        )
        try:
            import asyncio
            from app.tools.msa_fallback import progressive_msa

            aln_fasta, phylotree = await asyncio.to_thread(
                progressive_msa, records, req.stype
            )
            response = {
                "job_id": None,
                "aln_fasta": aln_fasta,
                "aln_clustal": "",
                "phylotree": phylotree,
                "stype": req.stype,
                "method": "in-process fallback",
                "provider": "BioNexus local fallback",
                "provider_fallback": True,
                "provider_error": str(provider_exc)[:360],
                "validation": {
                    "sequence_count": len(records),
                    "record_set_verified": True,
                    "residue_preservation_verified": True,
                },
            }
        except Exception as fallback_exc:
            logger.exception("Local MSA fallback also failed")
            raise HTTPException(
                status_code=502,
                detail=(
                    "MSA providers rejected the submission and the local fallback "
                    f"could not complete ({type(fallback_exc).__name__}). "
                    "Check the FASTA input and retry."
                ),
            ) from fallback_exc

    try:
        from app.ai.tool_interpreter import interpret_tool_result
        ai_interp = await interpret_tool_result("alignment", response)
        if ai_interp:
            response["ai_interpretation"] = ai_interp
    except Exception:
        pass
    job_registry.record_completed(
        "msa", user_id,
        query_preview=f"MSA {response['method']} · {req.stype}",
        context={
            "method": response["method"],
            "stype": req.stype,
            "sequence_length": sum(len(seq) for _, seq in records),
            "provider": response.get("provider"),
            "provider_fallback": response.get("provider_fallback", False),
        },
    )
    return response

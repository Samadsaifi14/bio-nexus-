from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from app.services.auth import require_user_id
from app.services.local_similarity import EngineUnavailable, SimilarityError, search

router = APIRouter(prefix='/api/similarity', tags=['local-similarity'])

class CustomProteinSearch(BaseModel):
    query_fasta: str = Field(min_length=1, max_length=20000)
    reference_fasta: str = Field(min_length=1, max_length=5 * 1024 * 1024)
    max_hits: int = Field(default=20, ge=1, le=100)

@router.post('/custom-protein-database')
async def custom_protein_search(payload: CustomProteinSearch, user_id: str = Depends(require_user_id)):
    try:
        return await run_in_threadpool(search, payload.query_fasta, payload.reference_fasta, payload.max_hits)
    except SimilarityError as exc:
        raise HTTPException(422, str(exc)) from exc
    except EngineUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc

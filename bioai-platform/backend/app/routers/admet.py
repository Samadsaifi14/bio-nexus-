"""ADMET descriptor computation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.deps import limiter
from app.services.auth import get_user_id

router = APIRouter(prefix="/api/admet", tags=["ADMET"])


class ADMETRequest(BaseModel):
    smiles: str = Field(..., min_length=1, max_length=500, description="SMILES string")


class ADMETResponse(BaseModel):
    job_id: str | None = None
    status: str = "complete"
    result: dict | None = None
    error: str | None = None


@router.post("/descriptors", response_model=ADMETResponse)
@limiter.limit("10/minute")
async def compute_descriptors(request, body: ADMETRequest, user_id: str | None = Depends(get_user_id)):
    """Compute molecular descriptors from SMILES using RDKit.

    Returns Lipinski/Veber compliance, QED score, and key properties.
    """
    try:
        from app.tools.admet import compute_descriptors as _compute
        result = _compute(body.smiles)
        return ADMETResponse(result=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Descriptor computation failed: {e}")

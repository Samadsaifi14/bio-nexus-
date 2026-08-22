"""CASTp pocket/cavity analysis endpoints."""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/castp", tags=["CASTp"])


class CastpRequest(BaseModel):
    pdb_id: str = Field(..., description="4-character PDB ID")
    probe_radius: float = Field(default=1.4, ge=0.0, le=5.0, description="Probe radius in Angstroms")


class PocketInfo(BaseModel):
    id: int
    area_sa: float
    volume_sa: float
    num_residues: int
    residues: list[str]
    centroid: list[float]
    radius: float


class CastpResponse(BaseModel):
    pdb_id: str
    probe_radius: float
    total_residues: int
    pockets: list[PocketInfo]


@router.post("/analyze", response_model=CastpResponse)
async def analyze_castp(body: CastpRequest):
    pdb_id = body.pdb_id.strip().upper()
    if len(pdb_id) != 4 or not pdb_id.isalnum():
        raise HTTPException(status_code=400, detail="Invalid PDB ID — must be 4 alphanumeric characters")

    try:
        from app.tools.castp import analyze_pockets_pdb_id
        result = await analyze_pockets_pdb_id(pdb_id, body.probe_radius)
    except Exception as e:
        logger.exception("CASTp analysis failed for %s", pdb_id)
        raise HTTPException(status_code=500, detail=f"CASTp analysis failed: {e}")

    return CastpResponse(
        pdb_id=result["pdb_id"],
        probe_radius=result["probe_radius"],
        total_residues=result["total_residues"],
        pockets=[PocketInfo(**p) for p in result["pockets"]],
    )

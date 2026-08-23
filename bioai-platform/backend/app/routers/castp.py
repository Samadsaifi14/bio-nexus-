"""CASTp pocket/cavity analysis endpoints."""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/castp", tags=["CASTp"])


class CastpRequest(BaseModel):
    pdb_id: str = Field(default="", description="4-character PDB ID (mutually exclusive with sequence)")
    sequence: str = Field(default="", description="Amino acid sequence for structure prediction + analysis")
    pdb_text: str = Field(default="", description="Raw PDB text content")
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
    sequence_source: str = ""


@router.post("/analyze", response_model=CastpResponse)
async def analyze_castp(body: CastpRequest):
    from app.tools.castp import analyze_pockets_pdb_id, analyze_pockets_pdb_text

    probe = body.probe_radius
    source = ""

    if body.pdb_text.strip():
        result = await analyze_pockets_pdb_text(body.pdb_text.strip(), "custom", probe)
        source = "pdb_text"
    elif body.pdb_id.strip():
        pdb_id = body.pdb_id.strip().upper()
        if len(pdb_id) != 4 or not pdb_id.isalnum():
            raise HTTPException(status_code=400, detail="Invalid PDB ID — must be 4 alphanumeric characters")
        try:
            result = await analyze_pockets_pdb_id(pdb_id, probe)
        except Exception as e:
            logger.exception("CASTp analysis failed for %s", pdb_id)
            raise HTTPException(status_code=500, detail=f"CASTp analysis failed: {e}")
        source = "pdb_id"
    elif body.sequence.strip():
        seq = body.sequence.strip().upper().replace("\n", "").replace(" ", "").replace("-", "")
        if len(seq) < 10:
            raise HTTPException(status_code=400, detail="Sequence too short (min 10 residues)")
        if len(seq) > 768:
            raise HTTPException(status_code=400, detail="Sequence too long (max 768 residues for ESMFold)")
        try:
            import httpx as _httpx
            import os
            hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
            headers = {}
            if hf_token:
                headers["Authorization"] = f"Bearer {hf_token}"

            async with _httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(
                    "https://api-inference.huggingface.co/models/facebook/esmfold_v1",
                    json={"inputs": seq},
                    headers=headers,
                )
                if resp.status_code == 503:
                    import asyncio
                    data = resp.json()
                    await asyncio.sleep(min(data.get("estimated_time", 30), 120))
                    resp = await client.post(
                        "https://api-inference.huggingface.co/models/facebook/esmfold_v1",
                        json={"inputs": seq},
                        headers=headers,
                    )
                resp.raise_for_status()
                data = resp.json()

            pdb_text = data.get("pdb", "") if isinstance(data, dict) else ""
            if not pdb_text or len(pdb_text) < 50:
                raise HTTPException(status_code=400, detail="ESMFold could not predict a valid structure for this sequence")

            result = await analyze_pockets_pdb_text(pdb_text, "predicted", probe)
            source = "sequence_esmfold"
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("CASTp ESMFold prediction failed")
            raise HTTPException(status_code=500, detail=f"Structure prediction failed: {e}")
    else:
        raise HTTPException(status_code=400, detail="Provide pdb_id, sequence, or pdb_text")

    return CastpResponse(
        pdb_id=result["pdb_id"],
        probe_radius=result["probe_radius"],
        total_residues=result["total_residues"],
        pockets=[PocketInfo(**p) for p in result["pockets"]],
        sequence_source=source,
    )

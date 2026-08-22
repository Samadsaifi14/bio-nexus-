"""SWISS-MODEL homology modelling endpoints — proxies to the SMR Repository API."""

import logging
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/swissmodel", tags=["swissmodel"])

SMR_BASE = "https://swissmodel.expasy.org/repository"


class SwissModelRequest(BaseModel):
    accession: str = Field(..., description="UniProt accession (e.g. P07900)")


class ModelInfo(BaseModel):
    template: str | None = None
    provider: str | None = None
    method: str | None = None
    coverage: float | None = None
    oligo_state: str | None = None
    from_res: int | None = None
    to_res: int | None = None
    created_date: str | None = None
    coordinates_url: str | None = None
    qmean_score: float | None = None
    ligands: list[dict[str, Any]] = []
    complex_with: list[dict[str, Any]] = []


class SwissModelResponse(BaseModel):
    accession: str
    sequence: str = ""
    sequence_length: int = 0
    models: list[ModelInfo]
    experimental: list[ModelInfo]


@router.post("/repository", response_model=SwissModelResponse)
async def query_repository(body: SwissModelRequest):
    accession = body.accession.strip().upper()
    if not accession:
        raise HTTPException(status_code=400, detail="Accession is required")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{SMR_BASE}/uniprot/{accession}.json")
            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail=f"No SWISS-MODEL data for {accession}")
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError:
        raise
    except Exception as e:
        logger.exception("SWISS-MODEL request failed for %s", accession)
        raise HTTPException(status_code=500, detail=f"SWISS-MODEL request failed: {e}")

    result = data.get("result", {})
    structures = result.get("structures", [])
    sequence = result.get("sequence", "")

    models: list[ModelInfo] = []
    experimental: list[ModelInfo] = []

    for s in structures:
        info = ModelInfo(
            template=s.get("template"),
            provider=s.get("provider"),
            method=s.get("method"),
            coverage=s.get("coverage"),
            oligo_state=s.get("oligo-state"),
            from_res=s.get("from"),
            to_res=s.get("to"),
            created_date=s.get("created_date"),
            coordinates_url=s.get("coordinates"),
        )
        if s.get("ligand_chains"):
            for lc in s["ligand_chains"]:
                for lig in lc.get("ligands", []):
                    info.ligands.append({
                        "hetid": lig.get("hetid", ""),
                        "description": lig.get("description", ""),
                    })

        if s.get("in_complex_with"):
            for chain_id, partners in s["in_complex_with"].items():
                for p in partners:
                    info.complex_with.append({
                        "chain": chain_id,
                        "uniprot_ac": p.get("uniprot_ac", ""),
                        "description": p.get("description", ""),
                    })

        if s.get("provider") == "PDB":
            experimental.append(info)
        else:
            models.append(info)

    return SwissModelResponse(
        accession=accession,
        sequence=sequence,
        sequence_length=len(sequence),
        models=models,
        experimental=experimental,
    )


@router.get("/coordinates/{accession}")
async def get_coordinates(accession: str):
    accession = accession.strip().upper()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{SMR_BASE}/uniprot/{accession}.pdb")
            resp.raise_for_status()
            return {"accession": accession, "pdb": resp.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch coordinates: {e}")

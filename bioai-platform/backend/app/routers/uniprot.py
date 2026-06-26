from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.tools.uniprot import UniprotTool
from app.services.ncbi_service import NCBIService
import httpx
from app.config import settings

router = APIRouter()
uniprot_tool = UniprotTool()
ncbi_service = NCBIService()


class UniprotSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Free-text search (gene name, protein name, keyword)")
    max_results: int = Field(20, ge=1, le=50)


class UniprotAccessionRequest(BaseModel):
    accession: str = Field(..., min_length=1, description="UniProt accession (e.g. P04637)")

class UniprotCDSRequest(BaseModel):
    accession: str = Field(..., min_length=1, description="UniProt accession")
    embl_accession: str = Field(..., min_length=1, description="EMBL/GenBank nucleotide accession")


@router.post("/search")
async def search_uniprot(req: UniprotSearchRequest):
    url = f"{settings.UNIPROT_BASE_URL}/search"
    params = {"query": req.query, "format": "json", "size": req.max_results}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="UniProt search failed")
        data = resp.json()
    results = data.get("results", [])
    out = []
    for r in results:
        out.append({
            "accession": r.get("primaryAccession", ""),
            "name": ((r.get("proteinDescription", {}) or {}).get("recommendedName", {}) or {}).get("fullName", {}).get("value", ""),
            "gene_names": [g.get("geneName", {}).get("value", "") for g in (r.get("genes") or []) if g.get("geneName")],
            "organism": (r.get("organism", {}) or {}).get("scientificName", ""),
            "length": ((r.get("sequence", {}) or {}).get("length", 0)),
        })
    return {"results": out, "count": len(out)}


@router.post("/detail")
async def uniprot_detail(req: UniprotAccessionRequest):
    result = await uniprot_tool.run({"accession": req.accession})
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/cds")
async def fetch_uniprot_cds(req: UniprotCDSRequest):
    """Fetch the CDS nucleotide sequence for a UniProt entry given an EMBL/GenBank accession."""
    result = await ncbi_service.fetch_by_accession(req.embl_accession)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {
        "uniprot_accession": req.accession,
        "embl_accession": req.embl_accession,
        "sequence": result.get("sequence", ""),
        "length": result.get("length", 0),
        "description": result.get("description", ""),
        "organism": result.get("organism", ""),
    }

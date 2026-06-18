import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

REACTOME_BASE = "https://reactome.org/ContentService"


class PathwaySearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Gene name or protein identifier")
    species: str = Field("Homo sapiens", description="Species name")


@router.post("/search")
async def search_pathways(req: PathwaySearchRequest):
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{REACTOME_BASE}/search/fireworks",
            params={"query": req.query, "species": req.species},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Reactome search failed")
        data = resp.json()
    results = []
    for item in data if isinstance(data, list) else []:
        results.append({
            "pathway_id": item.get("stId", ""),
            "name": item.get("name", ""),
            "species": (item.get("species", {}) or {}).get("name", ""),
            "url": f"https://reactome.org/content/detail/{item.get('stId', '')}" if item.get("stId") else "",
        })
    return {"results": results, "count": len(results)}


@router.post("/detail")
async def pathway_detail(pathway_id: str):
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{REACTOME_BASE}/data/fireworks/{pathway_id}")
        if resp.status_code != 200:
            raise HTTPException(status_code=404, detail="Pathway not found")
        data = resp.json()
    return {
        "pathway_id": data.get("stId", ""),
        "name": data.get("name", ""),
        "species": (data.get("species", {}) or {}).get("name", ""),
        "description": data.get("definition", ""),
        "url": f"https://reactome.org/content/detail/{data.get('stId', '')}",
    }

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

REACTOME_BASE = "https://reactome.org/ContentService"


class PathwaySearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Gene name or protein identifier")
    species: str = Field("Homo sapiens", description="Species name")


class PathwayDetailRequest(BaseModel):
    pathway_id: str = Field(..., min_length=1, description="Reactome pathway ID (e.g. R-HSA-1640170)")


@router.post("/search")
async def search_pathways(req: PathwaySearchRequest):
    # Try Reactome text search first (handles gene names, proteins, pathways)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{REACTOME_BASE}/search/query",
            params={"q": req.query, "species": req.species, "types": "Pathway"},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Reactome search failed")
        data = resp.json()

    results = []
    seen = set()
    for item in data if isinstance(data, list) else []:
        st_id = item.get("stId", "")
        if not st_id or st_id in seen:
            continue
        seen.add(st_id)
        results.append({
            "pathway_id": st_id,
            "name": item.get("displayName", ""),
            "species": (item.get("species", {}) or {}).get("name", ""),
            "url": f"https://reactome.org/content/detail/{st_id}",
        })

    # If text search gave nothing, try fireworks search (pathway hierarchy)
    if not results:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{REACTOME_BASE}/search/fireworks",
                params={"query": req.query, "species": req.species},
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data if isinstance(data, list) else []:
                    st_id = item.get("stId", "")
                    if not st_id or st_id in seen:
                        continue
                    seen.add(st_id)
                    results.append({
                        "pathway_id": st_id,
                        "name": item.get("name", ""),
                        "species": (item.get("species", {}) or {}).get("name", ""),
                        "url": f"https://reactome.org/content/detail/{st_id}",
                    })

    return {"results": results, "count": len(results)}


@router.post("/detail")
async def pathway_detail(req: PathwayDetailRequest):
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{REACTOME_BASE}/data/fireworks/{req.pathway_id}")
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

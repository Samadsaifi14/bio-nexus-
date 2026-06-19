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


class KEGGSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Gene name or keyword")


class EnrichmentRequest(BaseModel):
    identifiers: list[str] = Field(..., min_length=1, description="List of gene or protein identifiers")


def _extract_entries(data: dict) -> list[dict]:
    entries = []
    for group in data.get("results", []):
        entries.extend(group.get("entries", []))
    return entries


@router.post("/search")
async def search_pathways(req: PathwaySearchRequest):
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{REACTOME_BASE}/search/query",
            params={"query": req.query, "species": req.species, "types": "Pathway"},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Reactome search failed")
        data = resp.json()

    results = []
    seen = set()
    for item in _extract_entries(data):
        st_id = item.get("stId", "")
        if not st_id or st_id in seen:
            continue
        seen.add(st_id)
        results.append({
            "pathway_id": st_id,
            "name": item.get("displayName", item.get("name", "")),
            "species": item.get("species", ["Unknown"])[0] if isinstance(item.get("species"), list) else (item.get("species", {}) or {}).get("name", ""),
            "url": f"https://reactome.org/content/detail/{st_id}",
        })

    if not results:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{REACTOME_BASE}/search/fireworks",
                params={"query": req.query, "species": req.species},
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("entries", []):
                    st_id = item.get("stId", "")
                    if not st_id or st_id in seen:
                        continue
                    seen.add(st_id)
                    results.append({
                        "pathway_id": st_id,
                        "name": item.get("name", ""),
                        "species": item.get("species", ["Unknown"])[0] if isinstance(item.get("species"), list) else "",
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


@router.post("/kegg/search")
async def kegg_search(req: KEGGSearchRequest):
    query = req.query.strip().upper()
    results = []
    seen = set()

    async with httpx.AsyncClient(timeout=15) as client:
        gene_resp = await client.get(f"https://rest.kegg.jp/find/genes/{query}+human")
        if gene_resp.status_code == 200:
            gene_lines = gene_resp.text.strip().split("\n")
            for line in gene_lines:
                if not line.startswith("hsa:"):
                    continue
                kegg_gene_id = line.split("\t")[0]
                link_resp = await client.get(f"https://rest.kegg.jp/link/pathway/{kegg_gene_id}")
                if link_resp.status_code == 200:
                    for link_line in link_resp.text.strip().split("\n"):
                        if link_line.startswith("path:"):
                            pid = link_line.split("\t")[0].replace("path:", "")
                            if pid not in seen:
                                seen.add(pid)
                                name_resp = await client.get(f"https://rest.kegg.jp/list/pathway/hsa")
                                name_map = {}
                                if name_resp.status_code == 200:
                                    for nl in name_resp.text.strip().split("\n"):
                                        parts = nl.split("\t", 1)
                                        if len(parts) == 2:
                                            name_map[parts[0]] = parts[1]
                                name = name_map.get(pid, "").split(" - ")[0] if pid in name_map else ""
                                results.append({
                                    "pathway_id": pid,
                                    "name": name,
                                    "organism": "Homo sapiens",
                                    "url": f"https://www.kegg.jp/entry/{pid}",
                                    "image_url": f"https://rest.kegg.jp/get/{pid}/image",
                                })
                                break  # First gene match only, but may hit multiple pathways

        if not results:
            text_resp = await client.get(f"https://rest.kegg.jp/find/pathway/{query}")
            if text_resp.status_code == 200:
                for line in text_resp.text.strip().split("\n"):
                    parts = line.split("\t", 1)
                    if len(parts) == 2:
                        pid = parts[0].replace("path:", "")
                        name = parts[1].split(" - ")[0]
                        organism = parts[1].split(" - ")[-1] if " - " in parts[1] else ""
                        if pid not in seen:
                            seen.add(pid)
                            results.append({
                                "pathway_id": pid,
                                "name": name,
                                "organism": organism,
                                "url": f"https://www.kegg.jp/entry/{pid}",
                                "image_url": f"https://rest.kegg.jp/get/{pid}/image",
                            })

    return {"results": results, "count": len(results)}


@router.post("/enrichment")
async def pathway_enrichment(req: EnrichmentRequest):
    from app.services.pathway_enrichment import run_enrichment as _run_enrichment
    result = await _run_enrichment(req.identifiers)
    if result is None:
        raise HTTPException(status_code=502, detail="Enrichment analysis failed")
    return result

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
    query = req.query.strip()
    results = []
    seen = set()
    q_upper = query.upper()

    async with httpx.AsyncClient(timeout=15) as client:
        find_resp = await client.get(f"https://rest.kegg.jp/find/hsa/{query}")
        kegg_gene_id = None
        if find_resp.status_code == 200:
            for line in find_resp.text.strip().split("\n"):
                parts = line.split("\t", 1)
                if len(parts) != 2:
                    continue
                gene_id = parts[0]
                after_tab = parts[1]
                symbols_part = after_tab.split(";")[0]
                symbols = [s.strip().upper() for s in symbols_part.split(",")]
                if q_upper in symbols:
                    kegg_gene_id = gene_id
                    break

        if kegg_gene_id:
            gene_resp = await client.get(f"https://rest.kegg.jp/get/{kegg_gene_id}")
            if gene_resp.status_code == 200:
                in_pathway = False
                for line in gene_resp.text.split("\n"):
                    if line.startswith("PATHWAY"):
                        in_pathway = True
                    elif in_pathway:
                        s = line.strip()
                        if s == "":
                            continue
                        if not line.startswith(" "):
                            in_pathway = False
                            continue
                    if not in_pathway:
                        continue
                    rest = line[9:] if line.startswith("PATHWAY") else line.strip()
                    rest = rest.strip()
                    parts = rest.split(None, 1)
                    if len(parts) == 2:
                        pid, pname = parts
                        if pid not in seen:
                            seen.add(pid)
                            results.append({
                                "pathway_id": pid,
                                "name": pname,
                                "organism": "Homo sapiens",
                                "url": f"https://www.kegg.jp/entry/{pid}",
                                "image_url": f"https://rest.kegg.jp/get/{pid}/image",
                            })

        if not results:
            text_resp = await client.get(f"https://rest.kegg.jp/find/pathway/{query}")
            if text_resp.status_code == 200:
                for line in text_resp.text.strip().split("\n"):
                    parts = line.split("\t", 1)
                    if len(parts) == 2:
                        pid = parts[0]
                        name = parts[1].split(" - ")[0]
                        organism = parts[1].split(" - ")[-1] if " - " in parts[1] else ""
                        if pid not in seen:
                            seen.add(pid)
                            results.append({
                                "pathway_id": pid,
                                "name": name,
                                "organism": organism if organism != name else "Homo sapiens",
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

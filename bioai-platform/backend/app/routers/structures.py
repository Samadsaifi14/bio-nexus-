import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter()

PDB_BASE = "https://data.rcsb.org/rest/v1/core"


class StructureSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="PDB ID or UniProt accession")


@router.post("/fetch")
async def fetch_structure(req: StructureSearchRequest):
    q = req.query.strip().upper()

    async with httpx.AsyncClient(timeout=15) as client:
        pdb_resp = await client.get(f"{PDB_BASE}/{q}")
        if pdb_resp.status_code == 200:
            data = pdb_resp.json()
            return {
                "source": "pdb",
                "pdb_id": q,
                "title": data.get("struct", {}).get("title", ""),
                "method": (data.get("exptl", [{}])[0] or {}).get("method", ""),
                "resolution": (data.get("rcsb_entry_info", {}) or {}).get("resolution_combined", [{}])[0],
                "deposited": (data.get("rcsb_accession_info", {}) or {}).get("deposit_date", ""),
                "pdb_url": f"https://files.rcsb.org/view/{q}.pdb",
            }

    af_url = f"{settings.ALPHAFOLD_DB_URL}/{q}"
    async with httpx.AsyncClient(timeout=15) as client:
        af_resp = await client.get(af_url)
        if af_resp.status_code == 200:
            data = af_resp.json()
            if isinstance(data, list) and len(data) > 0:
                entry = data[0]
                return {
                    "source": "alphafold",
                    "uniprot_accession": q,
                    "pdb_url": entry.get("pdbUrl"),
                    "cif_url": entry.get("cifUrl"),
                    "confidence": entry.get("confidenceScore"),
                    "model_created_date": entry.get("modelCreatedDate"),
                }

    raise HTTPException(status_code=404, detail="Structure not found in PDB or AlphaFold")


@router.post("/search")
async def search_pdb(req: StructureSearchRequest):
    url = "https://search.rcsb.org/rcsbsearch/v2/query"
    payload = {
        "query": {
            "type": "terminal",
            "service": "text",
            "parameters": {"value": req.query},
        },
        "return_type": "entry",
        "rows": 20,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="RCSB search failed")
        data = resp.json()
    results = []
    for hit in data.get("result_set", []):
        results.append({
            "pdb_id": hit.get("identifier", ""),
            "score": hit.get("score", 0),
        })
    return {"results": results, "count": len(results)}

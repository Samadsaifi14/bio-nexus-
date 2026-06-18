import httpx
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter()

PDB_BASE = "https://data.rcsb.org/rest/v1/core"
RCSB_SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"


class StructureSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="PDB ID, UniProt accession, or keyword")


def _is_pdb_id(q: str) -> bool:
    return bool(re.fullmatch(r'[A-Za-z0-9]{4}', q))


async def _fetch_pdb(client: httpx.AsyncClient, pdb_id: str) -> dict | None:
    resp = await client.get(f"{PDB_BASE}/entry/{pdb_id}")
    if resp.status_code != 200:
        return None
    data = resp.json()
    return {
        "source": "pdb",
        "pdb_id": pdb_id.upper(),
        "title": data.get("struct", {}).get("title", ""),
        "method": (data.get("exptl", [{}])[0] or {}).get("method", ""),
        "resolution": (data.get("rcsb_entry_info", {}) or {}).get("resolution_combined", [{}])[0],
        "deposited": (data.get("rcsb_accession_info", {}) or {}).get("deposit_date", ""),
        "pdb_url": f"https://files.rcsb.org/view/{pdb_id.upper()}.pdb",
    }


async def _fetch_alphafold(client: httpx.AsyncClient, accession: str) -> dict | None:
    af_url = f"{settings.ALPHAFOLD_DB_URL}/{accession}"
    resp = await client.get(af_url)
    if resp.status_code != 200:
        return None
    data = resp.json()
    if isinstance(data, list) and len(data) > 0:
        entry = data[0]
        return {
            "source": "alphafold",
            "uniprot_accession": accession.upper(),
            "pdb_url": entry.get("pdbUrl"),
            "cif_url": entry.get("cifUrl"),
            "confidence": entry.get("confidenceScore"),
            "model_created_date": entry.get("modelCreatedDate"),
        }
    return None


async def _resolve_pdb_via_rcsb_uniprot(client: httpx.AsyncClient, accession: str) -> list[str]:
    """Find PDB entries associated with a UniProt accession via RCSB."""
    payload = {
        "query": {
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession",
                "operator": "exact_match",
                "value": accession,
            },
        },
        "return_type": "entry",
        "request_options": {
            "paginate": {
                "start": 0,
                "rows": 50,
            },
        },
    }
    resp = await client.post(RCSB_SEARCH, json=payload, timeout=15)
    if resp.status_code != 200:
        return []
    data = resp.json()
    return [hit.get("identifier", "") for hit in data.get("result_set", []) if hit.get("identifier")]


async def _resolve_pdb_via_uniprot(client: httpx.AsyncClient, accession: str) -> list[str]:
    """Find PDB cross-references from UniProt entry."""
    resp = await client.get(f"{UNIPROT_BASE}/{accession}", params={"format": "json"}, timeout=15)
    if resp.status_code != 200:
        return []
    data = resp.json()
    refs = data.get("uniProtKBCrossReferences") or []
    return [r.get("id", "") for r in refs if r.get("database") == "PDB"]


@router.post("/fetch")
async def fetch_structure(req: StructureSearchRequest):
    q = req.query.strip().upper()

    async with httpx.AsyncClient(timeout=15) as client:
        # Strategy 1: If it looks like a PDB ID, try PDB directly
        if _is_pdb_id(q):
            result = await _fetch_pdb(client, q)
            if result:
                return result

        # Strategy 2: Treat as a UniProt accession — look up PDB cross-refs
        pdb_ids = []
        pdb_ids = await _resolve_pdb_via_rcsb_uniprot(client, q)
        if not pdb_ids:
            pdb_ids = await _resolve_pdb_via_uniprot(client, q)

        if pdb_ids:
            result = await _fetch_pdb(client, pdb_ids[0])
            if result:
                return result

        # Strategy 3: Try AlphaFold as fallback
        af_result = await _fetch_alphafold(client, q)
        if af_result:
            return af_result

    raise HTTPException(status_code=404, detail="Structure not found in PDB or AlphaFold")


@router.post("/search")
async def search_pdb(req: StructureSearchRequest):
    payload = {
        "query": {
            "type": "terminal",
            "service": "text",
            "parameters": {"value": req.query},
        },
        "return_type": "entry",
        "request_options": {
            "paginate": {
                "start": 0,
                "rows": 20,
            },
        },
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(RCSB_SEARCH, json=payload)
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

import httpx
import re
from collections import defaultdict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter()

PDB_BASE = "https://data.rcsb.org/rest/v1/core"
RCSB_SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"


class StructureSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="PDB ID, UniProt accession, or keyword")


class StructureInventoryRequest(BaseModel):
    pdb_id: str = Field(..., pattern=r"^[A-Za-z0-9]{4}$", description="Four-character PDB identifier")


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


@router.post("/inventory")
async def structure_inventory(req: StructureInventoryRequest):
    """Return lightweight chain and non-polymer inventory for workbench controls."""
    pdb_id = req.pdb_id.upper()
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"https://files.rcsb.org/download/{pdb_id}.pdb")
    if response.status_code != 200:
        raise HTTPException(status_code=404, detail=f"PDB file not found: {pdb_id}")

    chains: dict[str, set[tuple[str, str]]] = defaultdict(set)
    ligands: dict[tuple[str, str], dict] = {}
    for line in response.text.splitlines():
        if len(line) < 27:
            continue
        record = line[:6].strip()
        if record not in {"ATOM", "HETATM"}:
            continue
        residue = line[17:20].strip() or "UNK"
        chain = line[21].strip() or "_"
        residue_id = f"{line[22:26].strip()}{line[26].strip()}"
        if record == "ATOM":
            chains[chain].add((residue, residue_id))
        elif residue not in {"HOH", "WAT", "DOD"}:
            key = (residue, chain)
            ligands.setdefault(key, {"id": residue, "chain": chain, "residue_count": 0})
            ligands[key]["residue_count"] += 1

    return {
        "pdb_id": pdb_id,
        "chains": [
            {"id": chain, "residue_count": len(residues)}
            for chain, residues in sorted(chains.items())
        ],
        "ligands": sorted(ligands.values(), key=lambda ligand: (ligand["id"], ligand["chain"])),
    }

"""PubChem PUG REST + autocomplete helpers for compound lookup."""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

PUG_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
AUTOCOMPLETE_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound"
_REQUEST_TIMEOUT = 12.0


class PubChemError(Exception):
    pass


async def _get_json(url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise PubChemError("Compound not found in PubChem")
        raise PubChemError(f"PubChem HTTP {e.response.status_code}")
    except (httpx.RequestError, ValueError) as e:
        raise PubChemError(f"PubChem request failed: {e}")


async def name_to_cid(name: str) -> int | None:
    """Resolve a chemical name to a PubChem CID (first hit)."""
    url = f"{PUG_BASE}/name/{quote(name)}/cids/JSON"
    try:
        data = await _get_json(url)
    except PubChemError:
        return None
    ids = data.get("IdentifierList", {}).get("CID", [])
    return int(ids[0]) if ids else None


async def cid_to_record(cid: int) -> dict:
    """Fetch canonical SMILES + name metadata for a CID."""
    url = (
        f"{PUG_BASE}/cid/{int(cid)}/property/"
        f"IsomericSMILES,CanonicalSMILES,IUPACName,MolecularFormula,InChIKey/JSON"
    )
    data = await _get_json(url)
    props = data.get("PropertyTable", {}).get("Properties", [{}])[0]
    return {
        "cid": int(props.get("CID", cid)),
        "smiles": props.get("SMILES") or props.get("IsomericSMILES") or props.get("CanonicalSMILES"),
        "name": props.get("IUPACName"),
        "formula": props.get("MolecularFormula"),
        "inchikey": props.get("InChIKey"),
    }


async def search_suggestions(query: str, limit: int = 10) -> list[dict]:
    """Return PubChem autocomplete suggestions for a compound search box.

    The autocomplete endpoint returns names only, so CIDs are resolved in
    parallel. Each entry: {cid, name}.
    """
    if not query or not query.strip():
        return []
    url = f"{AUTOCOMPLETE_BASE}/{quote(query.strip())}/JSON?limit={int(limit)}"
    try:
        data = await _get_json(url)
    except PubChemError:
        return []
    names = data.get("dictionary_terms", {}).get("compound", [])[:limit]
    if not names:
        return []

    sem = asyncio.Semaphore(6)

    async def _resolve(name: str) -> dict | None:
        async with sem:
            cid = await name_to_cid(name)
        if not cid:
            return None
        return {"cid": int(cid), "name": name}

    resolved = await asyncio.gather(*(_resolve(n) for n in names))
    return [r for r in resolved if r]

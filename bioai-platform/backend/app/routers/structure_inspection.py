"""Fast PDB lookup and chain-integrity inspection."""
import asyncio
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException
from app.services.auth import get_user_id
from app.services.ssrf import validate_url
from app.tools.structure_prep import detect_chain_health, validate_pdb_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/structure-inspection", tags=["structure-inspection"])
RCSB_DOWNLOAD = "https://files.rcsb.org/download"
RCSB_ENTRY = "https://data.rcsb.org/rest/v1/core/entry"
PDBE_SIFTS = "https://www.ebi.ac.uk/pdbe/api/mappings/uniprot"

def _extract_chain_uniprot(payload: dict) -> list[dict]:
    by_chain: dict[str, set[str]] = {}
    for entry in (payload or {}).values():
        if not isinstance(entry, dict):
            continue
        for accession, detail in entry.items():
            if not isinstance(detail, dict):
                continue
            for mapping in detail.get("mappings", []) or []:
                chain = str(mapping.get("chain_id") or "").strip()
                if chain:
                    by_chain.setdefault(chain, set()).add(str(accession).upper())
    return [{"chain": chain, "accessions": sorted(accessions)}
            for chain, accessions in sorted(by_chain.items())]

@router.get("/{pdb_id}")
async def inspect_pdb_chain_integrity(pdb_id: str, user_id: str | None = Depends(get_user_id)):
    try:
        pdb_id = validate_pdb_id(pdb_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pdb_url = f"{RCSB_DOWNLOAD}/{pdb_id}.pdb"
    entry_url = f"{RCSB_ENTRY}/{pdb_id}"
    sifts_url = f"{PDBE_SIFTS}/{pdb_id.lower()}"
    for url in (pdb_url, entry_url, sifts_url):
        validate_url(url)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        pdb_response = await client.get(pdb_url)
        if pdb_response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"PDB entry {pdb_id} was not found")
        pdb_response.raise_for_status()
        pdb_text = pdb_response.text
        if "ATOM" not in pdb_text and "HETATM" not in pdb_text:
            raise HTTPException(status_code=422, detail="The PDB entry contains no coordinate records")

        metadata = {}
        try:
            response = await client.get(entry_url)
            if response.status_code == 200:
                metadata = response.json()
        except (httpx.HTTPError, ValueError):
            logger.info("RCSB metadata unavailable for %s", pdb_id)

        chain_uniprot = []
        mapping_status = "unavailable"
        try:
            response = await client.get(sifts_url)
            if response.status_code == 200:
                payload = response.json()
                chain_uniprot = _extract_chain_uniprot(payload.get(pdb_id.lower(), {}))
                if chain_uniprot:
                    mapping_status = "available"
        except (httpx.HTTPError, ValueError, TypeError):
            logger.info("PDBe SIFTS mapping unavailable for %s", pdb_id)

        # Resolve other experimental PDB entries for each mapped UniProt accession.
        # Keep this bounded: a multimer can map several chains to many accessions.
        alternative_structures: dict[str, list[dict]] = {}
        accessions = sorted({
            accession
            for mapping in chain_uniprot
            for accession in mapping.get("accessions", [])
        })[:8]
        for accession in accessions:
            uniprot_url = f"https://rest.uniprot.org/uniprotkb/{accession}.json"
            validate_url(uniprot_url)
            try:
                uniprot_response = await client.get(uniprot_url, timeout=15)
                if uniprot_response.status_code != 200:
                    alternative_structures[accession] = []
                    continue
                uniprot_record = uniprot_response.json()
                pdb_refs = []
                seen_pdbs: set[str] = set()
                for cross_ref in uniprot_record.get("uniProtKBCrossReferences", []) or []:
                    if cross_ref.get("database") != "PDB":
                        continue
                    alternative_id = str(cross_ref.get("id") or "").upper()
                    if len(alternative_id) == 4 and alternative_id not in seen_pdbs:
                        seen_pdbs.add(alternative_id)
                        pdb_refs.append({
                            "pdb_id": alternative_id,
                            "url": f"https://www.rcsb.org/structure/{alternative_id}",
                        })
                alternative_structures[accession] = pdb_refs[:30]
            except (httpx.HTTPError, ValueError, TypeError):
                logger.info("UniProt cross-reference lookup unavailable for %s", accession)
                alternative_structures[accession] = []

    health = await asyncio.to_thread(detect_chain_health, pdb_text)
    entry_info = metadata.get("rcsb_entry_info", {}) if isinstance(metadata, dict) else {}
    struct = metadata.get("struct", {}) if isinstance(metadata.get("struct"), dict) else {}
    methods = metadata.get("exptl", []) if isinstance(metadata.get("exptl"), list) else []
    method = ", ".join(sorted({str(x.get("method")) for x in methods if x.get("method")})) or None
    resolution = entry_info.get("resolution_combined") or []
    return {
        "pdb_id": pdb_id,
        "title": struct.get("title"),
        "experimental_method": method,
        "resolution_angstrom": resolution[0] if resolution else None,
        "chain_health": {
            "has_missing_residues": health.has_missing_residues,
            "missing_residue_count": health.missing_residue_count,
            "missing_ranges": health.missing_ranges[:100],
            "has_chain_breaks": health.has_chain_breaks,
            "chain_break_count": health.chain_break_count,
            "chain_breaks": health.chain_breaks[:100],
            "is_broken": health.is_broken,
            "chains": health.chains,
            "total_residues": health.total_residues,
        },
        "chain_uniprot": chain_uniprot,
        "alternative_structures": alternative_structures,
        "mapping_status": mapping_status,
        "mapping_source": "PDBe SIFTS",
        "sources": {
            "rcsb": f"https://www.rcsb.org/structure/{pdb_id}",
            "pdbe": f"https://www.ebi.ac.uk/pdbe/entry/pdb/{pdb_id.lower()}",
        },
    }

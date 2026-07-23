import httpx
from typing import Any
from app.tools.base import BaseTool
from app.config import settings
from app.services.cache import ttl_cache


class AlphaFoldTool(BaseTool):
    name = "alphafold"

    @ttl_cache(ttl=86400, prefix="alphafold")
    async def run(self, input: dict) -> dict:
        uniprot_accession = input.get("uniprot_accession", "").strip()
        if not uniprot_accession:
            return {"error": "No UniProt accession provided", "structure_available": False}

        # NCBI RefSeq accessions can't be cached as-is because we need
        # to map them to UniProt first (AlphaFold only indexes by UniProt).
        # Skip cache for NCBI IDs — the mapped UniProt result will be cached.
        import re
        is_ncbi = uniprot_accession[:3] in ("NP_", "XP_", "YP_", "WP_")
        if is_ncbi:
            return await self._lookup(uniprot_accession)

        result = await self._lookup(uniprot_accession)
        return result

    async def _lookup(self, accession: str) -> dict:
        # AlphaFold only indexes by UniProt accessions. If this looks like
        # an NCBI RefSeq ID, try mapping to UniProt first.
        import re
        is_ncbi = accession[:3] in ("NP_", "XP_", "YP_", "WP_")
        if is_ncbi:
            from app.services.sequence_utils import map_refseq_to_uniprot
            mapped = await map_refseq_to_uniprot(accession)
            if mapped:
                accession = mapped

        url = f"{settings.ALPHAFOLD_DB_URL}/{accession}"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            if resp.status_code == 404:
                return {
                    "uniprot_accession": accession,
                    "structure_available": False,
                    "message": "No AlphaFold prediction available for this protein",
                    "pdb_url": None,
                    "cif_url": None,
                    "confidence": None,
                }
            resp.raise_for_status()
            data = resp.json()
            entry = data[0] if isinstance(data, list) else data
            return {
                "uniprot_accession": accession,
                "structure_available": True,
                "pdb_url": entry.get("pdbUrl", ""),
                "cif_url": entry.get("cifUrl", ""),
                "confidence": entry.get("confidenceScore", None),
                "model_created_date": entry.get("modelCreatedDate", ""),
                "latest_version": entry.get("latestVersion", 0),
            }

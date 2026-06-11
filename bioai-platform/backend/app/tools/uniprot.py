import httpx
from typing import Any
from app.tools.base import BaseTool
from app.config import settings
from app.services.cache import ttl_cache


class UniprotTool(BaseTool):
    name = "uniprot"

    @ttl_cache(ttl=86400, prefix="uniprot")
    async def run(self, input: dict) -> dict:
        accession = input.get("accession", "").strip()
        if not accession:
            return {"error": "No accession provided"}

        data = await self._fetch(accession)
        if "error" in data:
            return data

        return {
            "accession": data.get("primaryAccession", ""),
            "full_name": self._extract_name(data),
            "ec_number": (data.get("proteinDescription", {}) or {}).get("ecNumbers", [{}])[0].get("ecNumber", "") if data.get("proteinDescription") else "",
            "gene_names": [g.get("geneName", {}).get("value", "") for g in (data.get("genes") or []) if g.get("geneName")],
            "organism": ((data.get("organism", {}) or {}).get("scientificName", "")),
            "functions": self._extract_functions(data),
            "keywords": [kw.get("name", "") for kw in (data.get("keywords") or [])],
            "sequence_length": ((data.get("sequence", {}) or {}).get("length", 0)),
            "subcellular_locations": self._extract_locations(data),
            "pdb_ids": self._extract_pdb(data),
            "features": self._extract_features(data),
            "go_terms": self._extract_go_terms(data),
        }

    async def _fetch(self, accession: str) -> dict:
        url = f"{settings.UNIPROT_BASE_URL}/{accession}"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params={"format": "json"})
            if resp.status_code == 404:
                return {"error": f"Accession {accession} not found"}
            resp.raise_for_status()
            return resp.json()

    def _extract_name(self, data: dict) -> str:
        desc = data.get("proteinDescription", {}) or {}
        rec_name = desc.get("recommendedName", {}) or {}
        return (rec_name.get("fullName", {}) or {}).get("value", "")

    def _extract_functions(self, data: dict) -> list[str]:
        comments = data.get("comments") or []
        funcs = []
        for c in comments:
            if c.get("commentType") == "FUNCTION":
                texts = c.get("texts") or []
                for t in texts:
                    val = (t.get("value") or "").strip()
                    if val:
                        funcs.append(val)
        return funcs

    def _extract_locations(self, data: dict) -> list[str]:
        comments = data.get("comments") or []
        locs = []
        for c in comments:
            if c.get("commentType") == "SUBCELLULAR_LOCATION":
                subcels = c.get("subcellularLocations") or []
                for s in subcels:
                    loc = (s.get("location", {}) or {}).get("value", "")
                    if loc:
                        locs.append(loc)
        return locs

    def _extract_pdb(self, data: dict) -> list[str]:
        refs = data.get("uniProtKBCrossReferences") or []
        pdbs = []
        for r in refs:
            if r.get("database") == "PDB":
                pdbs.append(r.get("id", ""))
        return pdbs

    def _extract_features(self, data: dict) -> list[dict]:
        features = data.get("features") or []
        result = []
        for f in features:
            result.append({
                "type": f.get("type", ""),
                "description": f.get("description", ""),
                "begin": (f.get("location", {}) or {}).get("start", {}).get("value"),
                "end": (f.get("location", {}) or {}).get("end", {}).get("value"),
            })
        return result

    def _extract_go_terms(self, data: dict) -> list[str]:
        refs = data.get("uniProtKBCrossReferences") or []
        go = []
        for r in refs:
            if r.get("database") == "GO":
                term = r.get("properties", [{}])[0].get("value", "") if r.get("properties") else ""
                if term:
                    go.append(term)
        return go

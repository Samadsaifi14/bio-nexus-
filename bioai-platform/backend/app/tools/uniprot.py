import re
from typing import Any

import httpx

from app.config import settings
from app.services.cache import ttl_cache
from app.tools.base import BaseTool


_ACCESSION_TOKEN = re.compile(r"^[A-Z0-9]+(?:-\d+)?$")


class UniprotTool(BaseTool):
    name = "uniprot"

    @ttl_cache(ttl=86400, prefix="uniprot")
    async def run(self, input: dict) -> dict:
        accession = str(input.get("accession", "") or "").strip().upper()
        if not accession:
            return {"error": "No accession provided"}
        if len(accession) > 24 or not _ACCESSION_TOKEN.fullmatch(accession):
            return {"error": "Invalid UniProt accession format"}

        data = await self._fetch(accession)
        if "error" in data:
            return data

        ec_numbers = self._extract_ec_numbers(data)
        return {
            "accession": data.get("primaryAccession", ""),
            "reviewed": self._is_reviewed(data),
            "full_name": self._extract_name(data),
            # Keep the legacy singular field for existing exports/UI while also
            # preserving every EC number reported by the UniProt entry.
            "ec_number": ec_numbers[0] if ec_numbers else "",
            "ec_numbers": ec_numbers,
            "gene_names": [
                g.get("geneName", {}).get("value", "")
                for g in (data.get("genes") or [])
                if g.get("geneName") and g.get("geneName", {}).get("value")
            ],
            "organism": (data.get("organism", {}) or {}).get("scientificName", ""),
            "functions": self._extract_functions(data),
            "keywords": [
                kw.get("name", "")
                for kw in (data.get("keywords") or [])
                if kw.get("name")
            ],
            "sequence": (data.get("sequence", {}) or {}).get("value", ""),
            "sequence_length": (data.get("sequence", {}) or {}).get("length", 0),
            "subcellular_locations": self._extract_locations(data),
            "pdb_ids": self._extract_pdb(data),
            "features": self._extract_features(data),
            "go_terms": self._extract_go_terms(data),
            "go_terms_detailed": self._extract_go_terms_detailed(data),
            "cds_accessions": self._extract_cds_accessions(data),
            "source": "UniProtKB",
            "entry_version": (data.get("entryAudit", {}) or {}).get("entryVersion"),
            "sequence_version": (data.get("entryAudit", {}) or {}).get("sequenceVersion"),
            "last_annotation_update": (data.get("entryAudit", {}) or {}).get("lastAnnotationUpdateDate"),
        }

    async def _fetch(self, accession: str) -> dict:
        accession = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", accession).strip().upper()
        if len(accession) > 24 or not _ACCESSION_TOKEN.fullmatch(accession):
            return {"error": "Invalid UniProt accession format"}
        url = f"{settings.UNIPROT_BASE_URL}/{accession}"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params={"format": "json"})
        except httpx.HTTPError as exc:
            return {"error": f"UniProt request failed for {accession}: {exc.__class__.__name__}"}
        if resp.status_code == 404:
            return {"error": f"Accession {accession} not found"}
        if resp.status_code >= 400:
            return {"error": f"UniProt returned {resp.status_code} for {accession}"}
        try:
            payload = resp.json()
        except ValueError:
            return {"error": f"UniProt returned malformed JSON for {accession}"}
        if not isinstance(payload, dict):
            return {"error": f"UniProt returned an unexpected payload for {accession}"}
        return payload

    def _is_reviewed(self, data: dict) -> bool:
        entry_type = str(data.get("entryType", "") or "").lower()
        return "reviewed" in entry_type and "unreviewed" not in entry_type

    def _extract_name(self, data: dict) -> str:
        desc = data.get("proteinDescription", {}) or {}
        recommended = desc.get("recommendedName", {}) or {}
        full = (recommended.get("fullName", {}) or {}).get("value", "")
        if full:
            return full
        # TrEMBL entries often carry submitted rather than recommended names.
        for key in ("submissionNames", "alternativeNames"):
            for item in desc.get(key) or []:
                value = ((item or {}).get("fullName", {}) or {}).get("value", "")
                if value:
                    return value
        return ""

    def _extract_ec_numbers(self, data: dict) -> list[str]:
        desc = data.get("proteinDescription", {}) or {}
        values: list[str] = []
        seen: set[str] = set()

        name_blocks: list[dict] = []
        recommended = desc.get("recommendedName")
        if isinstance(recommended, dict):
            name_blocks.append(recommended)
        for key in ("submissionNames", "alternativeNames"):
            name_blocks.extend(item for item in (desc.get(key) or []) if isinstance(item, dict))

        for block in name_blocks:
            for ec in block.get("ecNumbers") or []:
                value = str((ec or {}).get("value") or (ec or {}).get("ecNumber") or "").strip()
                if value and value not in seen:
                    seen.add(value)
                    values.append(value)

        # Catalytic-activity comments can carry the EC number even when the
        # protein-name block does not. Preserve those as a second source.
        for comment in data.get("comments") or []:
            if comment.get("commentType") != "CATALYTIC ACTIVITY":
                continue
            value = str(((comment.get("reaction") or {}).get("ecNumber") or "")).strip()
            if value and value not in seen:
                seen.add(value)
                values.append(value)
        return values

    def _extract_functions(self, data: dict) -> list[str]:
        funcs: list[str] = []
        for comment in data.get("comments") or []:
            if comment.get("commentType") == "FUNCTION":
                for text in comment.get("texts") or []:
                    value = (text.get("value") or "").strip()
                    if value:
                        funcs.append(value)
        return funcs

    def _extract_locations(self, data: dict) -> list[str]:
        locs: list[str] = []
        for comment in data.get("comments") or []:
            if comment.get("commentType") == "SUBCELLULAR_LOCATION":
                for item in comment.get("subcellularLocations") or []:
                    location = (item.get("location", {}) or {}).get("value", "")
                    if location:
                        locs.append(location)
        return list(dict.fromkeys(locs))

    def _extract_cds_accessions(self, data: dict) -> list[dict]:
        refs = data.get("uniProtKBCrossReferences") or []
        cds = []
        seen_ids: set[str] = set()
        for ref in refs:
            database = ref.get("database", "")
            if database not in ("EMBL", "GenBank", "DDBJ"):
                continue
            props = {
                p.get("key", ""): p.get("value", "")
                for p in (ref.get("properties") or [])
            }
            accession = ref.get("id", "")
            if accession and accession not in seen_ids:
                seen_ids.add(accession)
                cds.append(
                    {
                        "database": database,
                        "accession": accession,
                        "protein_sequence_id": props.get("protein sequence ID", "") or props.get("ProteinId", ""),
                        "nucleotide_sequence_id": props.get("nucleotide sequence ID", ""),
                    }
                )
        return cds

    def _extract_pdb(self, data: dict) -> list[str]:
        pdbs = [
            ref.get("id", "")
            for ref in (data.get("uniProtKBCrossReferences") or [])
            if ref.get("database") == "PDB" and ref.get("id")
        ]
        return list(dict.fromkeys(pdbs))

    def _extract_features(self, data: dict) -> list[dict]:
        result = []
        for feature in data.get("features") or []:
            location = feature.get("location", {}) or {}
            result.append(
                {
                    "type": feature.get("type", ""),
                    "description": feature.get("description", ""),
                    "begin": (location.get("start", {}) or {}).get("value"),
                    "end": (location.get("end", {}) or {}).get("value"),
                }
            )
        return result

    def _extract_go_terms_detailed(self, data: dict) -> list[dict[str, Any]]:
        terms: list[dict[str, Any]] = []
        for ref in data.get("uniProtKBCrossReferences") or []:
            if ref.get("database") != "GO":
                continue
            props = {
                prop.get("key", ""): prop.get("value", "")
                for prop in (ref.get("properties") or [])
            }
            term = props.get("GoTerm") or props.get("Term") or ""
            terms.append(
                {
                    "id": ref.get("id", ""),
                    "term": term,
                    "evidence": props.get("GoEvidenceType", "") or props.get("Evidence", ""),
                    "source": "UniProtKB cross-reference",
                }
            )
        return terms

    def _extract_go_terms(self, data: dict) -> list[str]:
        return [
            item["term"]
            for item in self._extract_go_terms_detailed(data)
            if item.get("term")
        ]

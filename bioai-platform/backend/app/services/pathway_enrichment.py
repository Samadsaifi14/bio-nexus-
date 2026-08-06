import httpx
import json
import hashlib
import logging

from app.services.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

ANALYSIS_BASE = "https://reactome.org/AnalysisService"


async def run_enrichment(identifiers: list[str]) -> dict | None:
    raw = json.dumps(sorted(identifiers), sort_keys=True)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]
    cache_key = f"enrichment:{key_hash}"

    cached = cache_get(cache_key)
    if cached is not None:
        try:
            result = json.loads(cached)
            if isinstance(result, dict):
                result["from_cache"] = True
            return result
        except (json.JSONDecodeError, TypeError):
            pass
    try:
        body = "\n".join(identifiers)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{ANALYSIS_BASE}/identifiers/projection",
                content=body,
                headers={"Content-Type": "text/plain"},
                params={"pageSize": "20", "page": "1"},
            )
            if resp.status_code != 200:
                logger.warning(f"Reactome Analysis Service returned {resp.status_code}")
                return None

            data = resp.json()
            token = data.get("summary", {}).get("token", "")
            if not token:
                logger.warning("No analysis token returned from Reactome")
                return None

            # The projection response already carries the enriched pathways;
            # the separate /token/{token}/pathways call is unnecessary (and
            # currently 404s for tokens returned with a trailing %3D).
            pathways_data = data
            pathways = []
            for item in pathways_data.get("pathways", []):
                species = item.get("species", {})
                species_name = (
                    species.get("name", "")
                    if isinstance(species, dict)
                    else (species or "")
                )
                entities = item.get("entities", {})
                found = entities.get("found", 0)
                total = entities.get("total", 0)
                pathways.append({
                    "stId": item.get("stId", ""),
                    "name": item.get("name", ""),
                    "species": species_name,
                    "entitiesFound": found,
                    "entitiesTotal": total,
                    "geneRatio": round(found / total, 4) if total else 0.0,
                    "entitiesFDR": entities.get("fdr", 1.0),
                    "entitiesPValue": entities.get("pValue", 1.0),
                })

            pathways.sort(key=lambda p: p["entitiesFDR"])

            result = {
                "token": token,
                "pathways": pathways,
            }
            try:
                cache_set(cache_key, json.dumps(result), ttl=86400)
            except (TypeError, ValueError):
                pass
            result["from_cache"] = False
            return result
    except Exception as e:
        logger.warning(f"Pathway enrichment failed: {e}")
        return None

import httpx
import logging

logger = logging.getLogger(__name__)

ANALYSIS_BASE = "https://reactome.org/AnalysisService"


async def run_enrichment(identifiers: list[str]) -> dict | None:
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

            pathways_resp = await client.get(
                f"{ANALYSIS_BASE}/token/{token}/pathways",
                params={"pageSize": "20", "page": "1"},
            )
            if pathways_resp.status_code != 200:
                logger.warning(f"Failed to fetch pathways for token {token}")
                return None

            pathways_data = pathways_resp.json()
            pathways = []
            for item in pathways_data.get("items", []):
                pathways.append({
                    "stId": item.get("stId", ""),
                    "name": item.get("name", ""),
                    "species": item.get("species", ""),
                    "entitiesFound": item.get("entities", {}).get("found", 0),
                    "entitiesTotal": item.get("entities", {}).get("total", 0),
                    "entitiesFDR": item.get("entities", {}).get("fdr", 1.0),
                })

            pathways.sort(key=lambda p: p["entitiesFDR"])

            return {
                "token": token,
                "pathways": pathways,
            }
    except Exception as e:
        logger.warning(f"Pathway enrichment failed: {e}")
        return None

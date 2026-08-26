import httpx
import json
import hashlib
import logging

from app.services.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

ANALYSIS_BASE = "https://reactome.org/AnalysisService"
GPROFILER_BASE = "https://biit.cs.ut.ee/gprofiler/api/gost/profile/"


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


# ---------------------------------------------------------------------------
# g:Profiler cross-validation enrichment
# ---------------------------------------------------------------------------

async def run_gprofiler_enrichment(
    identifiers: list[str],
    organism: str = "hsapiens",
    sources: list[str] | None = None,
) -> dict | None:
    """Run enrichment analysis via g:Profiler as cross-validation.

    g:Profiler queries multiple annotation databases (GO:BP, GO:MF, GO:CC,
    KEGG, Reactome, WikiPathways) and applies proper multiple-testing
    correction. Use this to validate Reactome-only enrichment results.

    Args:
        identifiers: gene/protein identifiers (symbol, UniProt, Ensembl, etc.)
        organism: g:Profiler organism code (default: hsapiens)
        sources: annotation sources to query. None = all available.

    Returns:
        {"results": [...], "source": "g:Profiler"} or None on failure.
    """
    cache_key = f"gprofiler:{hashlib.sha256(json.dumps(sorted(identifiers)).encode()).hexdigest()[:16]}"
    cached = cache_get(cache_key)
    if cached is not None:
        try:
            return json.loads(cached)
        except (json.JSONDecodeError, TypeError):
            pass

    payload = {
        "organism": organism,
        "query": identifiers,
        "significance_threshold_method": "g_SCS",
        "user_threshold": 0.05,
        "no_evidences": False,
    }
    if sources:
        payload["sources"] = sources

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                GPROFILER_BASE,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                logger.warning("g:Profiler returned %d", resp.status_code)
                return None

            data = resp.json()
            results = []
            for item in data.get("result", []):
                if item.get("significant"):
                    results.append({
                        "source": item.get("source", ""),
                        "term_id": item.get("native", ""),
                        "term_name": item.get("name", ""),
                        "p_value": item.get("p_value", 1.0),
                        "fdr": item.get("p_value_intersections", 1.0),
                        "intersection_size": item.get("intersection_size", 0),
                        "term_size": item.get("term_size", 0),
                        "query_size": item.get("query_size", 0),
                        "effective_domain_size": item.get("effective_domain_size", 0),
                        "source_order": item.get("source_order", 0),
                    })

            results.sort(key=lambda r: r["p_value"])

            result = {
                "results": results,
                "count": len(results),
                "organism": organism,
                "source": "g:Profiler",
            }
            try:
                cache_set(cache_key, json.dumps(result), ttl=86400)
            except (TypeError, ValueError):
                pass
            return result
    except Exception as e:
        logger.warning("g:Profiler enrichment failed: %s", e)
        return None


async def run_cross_validated_enrichment(
    identifiers: list[str],
    organism: str = "hsapiens",
) -> dict:
    """Run both Reactome and g:Profiler enrichment, merging results.

    Returns:
        {
            "reactome": {...} | null,
            "gprofiler": {...} | null,
            "concordant_terms": [...],  # pathways found by both methods
        }
    """
    reactome_result = await run_enrichment(identifiers)
    gprofiler_result = await run_gprofiler_enrichment(identifiers, organism)

    # Find concordant pathways (present in both Reactome and g:Profiler)
    concordant = []
    if reactome_result and gprofiler_result:
        reactome_names = {
            p["name"].lower() for p in reactome_result.get("pathways", [])
        }
        gprofiler_names = {
            r["term_name"].lower() for r in gprofiler_result.get("results", [])
        }
        shared = reactome_names & gprofiler_names
        if shared:
            # Collect details from both sources
            for name_lower in shared:
                r_pathway = next(
                    (p for p in reactome_result.get("pathways", [])
                     if p["name"].lower() == name_lower), None
                )
                g_term = next(
                    (r for r in gprofiler_result.get("results", [])
                     if r["term_name"].lower() == name_lower), None
                )
                concordant.append({
                    "name": r_pathway["name"] if r_pathway else name_lower,
                    "reactome_fdr": r_pathway.get("entitiesFDR") if r_pathway else None,
                    "gprofiler_pvalue": g_term.get("p_value") if g_term else None,
                    "source": "both",
                })

    return {
        "reactome": reactome_result,
        "gprofiler": gprofiler_result,
        "concordant_terms": concordant,
    }

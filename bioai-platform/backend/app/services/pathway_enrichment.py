import hashlib
import json
import logging

import httpx

from app.services.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

ANALYSIS_BASE = "https://reactome.org/AnalysisService"
GPROFILER_BASE = "https://biit.cs.ut.ee/gprofiler/api/gost/profile/"


def _cache_key(prefix: str, identifiers: list[str], extra: str = "") -> str:
    payload = json.dumps({"ids": sorted(identifiers), "extra": extra}, sort_keys=True)
    return f"{prefix}:{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


async def run_enrichment(identifiers: list[str]) -> dict | None:
    """Run Reactome over-representation analysis.

    Reactome-provided p-value and FDR fields are preserved under source-specific
    names. BioNexus does not recalculate or relabel them.
    """
    cache_key = _cache_key("enrichment", identifiers)
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
                logger.warning("Reactome Analysis Service returned %d", resp.status_code)
                return None

            data = resp.json()
            token = data.get("summary", {}).get("token", "")
            if not token:
                logger.warning("No analysis token returned from Reactome")
                return None

            pathways = []
            for item in data.get("pathways", []):
                species = item.get("species", {})
                species_name = species.get("name", "") if isinstance(species, dict) else (species or "")
                entities = item.get("entities", {}) or {}
                found = entities.get("found", 0) or 0
                total = entities.get("total", 0) or 0
                pathways.append({
                    "stId": item.get("stId", ""),
                    "name": item.get("name", ""),
                    "species": species_name,
                    "entitiesFound": found,
                    "entitiesTotal": total,
                    "geneRatio": round(found / total, 4) if total else 0.0,
                    "reactomeFDR": entities.get("fdr"),
                    "reactomePValue": entities.get("pValue"),
                    "significance_source": "Reactome Analysis Service",
                    "correction_method": "Reactome-provided FDR",
                })

            pathways.sort(
                key=lambda p: (
                    p["reactomeFDR"] is None,
                    p["reactomeFDR"] if p["reactomeFDR"] is not None else 1.0,
                )
            )

            result = {
                "token": token,
                "pathways": pathways,
                "method": "Reactome over-representation analysis",
                "significance_note": (
                    "P-value and FDR are reported exactly as supplied by the Reactome Analysis Service. "
                    "BioNexus does not reinterpret these values as model confidence."
                ),
                "from_cache": False,
            }
            try:
                cache_set(cache_key, json.dumps(result), ttl=86400)
            except (TypeError, ValueError):
                pass
            return result
    except Exception as exc:
        logger.warning("Pathway enrichment failed: %s", exc)
        return None


async def run_gprofiler_enrichment(
    identifiers: list[str],
    organism: str = "hsapiens",
    sources: list[str] | None = None,
) -> dict | None:
    """Run g:Profiler enrichment as an independent cross-validation source.

    With ``significance_threshold_method='g_SCS'``, g:Profiler's returned
    ``p_value`` is the multiple-testing-adjusted significance value for that
    method. It is therefore exposed as ``adjusted_p_value`` and never labelled
    FDR. The API's ``p_value_intersections`` field is not used as an FDR proxy.
    """
    cache_key = _cache_key("gprofiler", identifiers, f"{organism}:{','.join(sources or [])}")
    cached = cache_get(cache_key)
    if cached is not None:
        try:
            result = json.loads(cached)
            if isinstance(result, dict):
                result["from_cache"] = True
            return result
        except (json.JSONDecodeError, TypeError):
            pass

    payload: dict = {
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
                if not item.get("significant"):
                    continue
                results.append({
                    "source": item.get("source", ""),
                    "term_id": item.get("native", ""),
                    "term_name": item.get("name", ""),
                    "adjusted_p_value": item.get("p_value"),
                    "correction_method": "g_SCS",
                    "intersection_size": item.get("intersection_size", 0),
                    "term_size": item.get("term_size", 0),
                    "query_size": item.get("query_size", 0),
                    "effective_domain_size": item.get("effective_domain_size", 0),
                    "source_order": item.get("source_order", 0),
                })

            results.sort(
                key=lambda r: (
                    r["adjusted_p_value"] is None,
                    r["adjusted_p_value"] if r["adjusted_p_value"] is not None else 1.0,
                )
            )
            result = {
                "results": results,
                "count": len(results),
                "organism": organism,
                "source": "g:Profiler",
                "correction_method": "g_SCS",
                "significance_note": (
                    "adjusted_p_value is g:Profiler's p_value returned under g_SCS correction; "
                    "it is not labelled as FDR."
                ),
                "from_cache": False,
            }
            try:
                cache_set(cache_key, json.dumps(result), ttl=86400)
            except (TypeError, ValueError):
                pass
            return result
    except Exception as exc:
        logger.warning("g:Profiler enrichment failed: %s", exc)
        return None


async def run_cross_validated_enrichment(
    identifiers: list[str],
    organism: str = "hsapiens",
) -> dict:
    """Run Reactome and g:Profiler and report source-specific concordance.

    Name concordance is descriptive only. It does not combine p-values and does
    not create a new significance statistic.
    """
    reactome_result = await run_enrichment(identifiers)
    gprofiler_result = await run_gprofiler_enrichment(identifiers, organism)

    concordant = []
    if reactome_result and gprofiler_result:
        reactome_by_name = {
            p.get("name", "").strip().lower(): p
            for p in reactome_result.get("pathways", [])
            if p.get("name")
        }
        gprofiler_by_name = {
            r.get("term_name", "").strip().lower(): r
            for r in gprofiler_result.get("results", [])
            if r.get("term_name")
        }
        for key in sorted(reactome_by_name.keys() & gprofiler_by_name.keys()):
            r_pathway = reactome_by_name[key]
            g_term = gprofiler_by_name[key]
            concordant.append({
                "name": r_pathway.get("name", key),
                "reactome_fdr": r_pathway.get("reactomeFDR"),
                "reactome_p_value": r_pathway.get("reactomePValue"),
                "gprofiler_adjusted_p_value": g_term.get("adjusted_p_value"),
                "gprofiler_correction_method": g_term.get("correction_method"),
                "concordance_basis": "case-insensitive pathway/term name match",
                "source": "Reactome + g:Profiler",
            })

    return {
        "reactome": reactome_result,
        "gprofiler": gprofiler_result,
        "concordant_terms": concordant,
        "concordance_note": (
            "Concordance indicates that both services returned a term with the same normalized name. "
            "BioNexus does not pool or combine their significance values."
        ),
    }

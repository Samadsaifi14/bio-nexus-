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


def _reactome_pathway(item: dict) -> dict:
    species = item.get("species", {})
    species_name = species.get("name", "") if isinstance(species, dict) else (species or "")
    entities = item.get("entities", {}) or {}
    found = entities.get("found", 0) or 0
    total = entities.get("total", 0) or 0
    fdr = entities.get("fdr")
    p_value = entities.get("pValue")
    return {
        "stId": item.get("stId", ""),
        "name": item.get("name", ""),
        "species": species_name,
        "entitiesFound": found,
        "entitiesTotal": total,
        "geneRatio": round(found / total, 4) if total else 0.0,
        "reactomeFDR": fdr,
        "reactomePValue": p_value,
        # Backward-compatible aliases consumed by older UI builds.
        "entitiesFDR": fdr,
        "entitiesPValue": p_value,
        "adjustedPValue": fdr,
        "significance_source": "Reactome Analysis Service",
        "correction_method": "Reactome-provided FDR",
        "provider": "reactome",
        "diagram_provider": "reactome",
    }


def _gprofiler_pathway(item: dict, organism: str) -> dict:
    found = item.get("intersection_size", 0) or 0
    total = item.get("term_size", 0) or 0
    adjusted = item.get("adjusted_p_value")
    return {
        "stId": item.get("term_id", ""),
        "name": item.get("term_name", ""),
        "species": organism,
        "entitiesFound": found,
        "entitiesTotal": total,
        "geneRatio": round(found / total, 4) if total else 0.0,
        "reactomeFDR": None,
        "reactomePValue": None,
        "entitiesFDR": None,
        "entitiesPValue": None,
        "adjustedPValue": adjusted,
        "significance_source": "g:Profiler",
        "correction_method": item.get("correction_method", "g_SCS"),
        "provider": "gprofiler",
        "diagram_provider": None,
    }


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

            pathways = [_reactome_pathway(item) for item in data.get("pathways", [])]
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
                "provider": "reactome",
                "provider_label": "Reactome Analysis Service",
                "degraded": False,
                "provider_attempts": [
                    {"provider": "reactome", "status": "success"},
                ],
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


async def run_resilient_enrichment(
    identifiers: list[str],
    organism: str = "hsapiens",
) -> dict | None:
    """Run enrichment through an evidence-preserving provider chain.

    Reactome is primary because BioNexus exposes its native pathway IDs,
    p-values and FDR.  If the service is unavailable or returns no analysis
    token, g:Profiler is a legitimate independent enrichment fallback.  Its
    g_SCS-adjusted p-values remain labelled as such and are never relabelled as
    Reactome FDR.  If both providers fail, return None so the API can expose an
    honest terminal failure rather than synthetic pathway data.
    """
    reactome = await run_enrichment(identifiers)
    if reactome is not None:
        return reactome

    attempts = [{"provider": "reactome", "status": "unavailable"}]
    gprofiler = await run_gprofiler_enrichment(identifiers, organism)
    if gprofiler is None:
        attempts.append({"provider": "gprofiler", "status": "unavailable"})
        logger.warning("All pathway enrichment providers unavailable")
        return None

    attempts.append({"provider": "gprofiler", "status": "success"})
    pathways = [_gprofiler_pathway(item, organism) for item in gprofiler.get("results", [])]
    return {
        "token": "",
        "pathways": pathways,
        "method": "g:Profiler over-representation analysis (fallback)",
        "provider": "gprofiler",
        "provider_label": "g:Profiler",
        "degraded": True,
        "provider_attempts": attempts,
        "significance_note": (
            "Reactome was unavailable. Results are from g:Profiler. adjustedPValue is the "
            "g:Profiler p-value returned under g_SCS correction; it is not Reactome FDR."
        ),
        "from_cache": bool(gprofiler.get("from_cache", False)),
    }


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

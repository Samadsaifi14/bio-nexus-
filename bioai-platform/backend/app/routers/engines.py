"""Scientific engines API (BioNexus 2.0 Components 4 & 5).

Exposes the engine registry: introspection (describe), validation (PASS/FAIL
checks) and export (JSON/CSV/SVG figure) for a canonical engine result.
"""

import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.engines import ENGINES, get_engine
from app.services.plugin_system import plugin_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/engines", tags=["engines"])


class ResultBody(BaseModel):
    # Accepts the canonical BLAST result dict (see _build_blast_result) wrapped
    # under "result"; request bodies are plain JSON without a schema.
    result: dict


def _worker_configured() -> bool:
    run_worker_env = os.getenv("RUN_WORKER")
    if run_worker_env is not None:
        return str(run_worker_env).strip().lower() in ("1", "true", "yes")
    return os.name != "nt"


@router.get("")
async def list_engines():
    """Every registered engine: name, tool, databases, benchmark coverage."""
    return {"engines": [e.describe() for e in ENGINES.values()]}


@router.get("/deployment/components")
async def deployment_components():
    """Report configuration of operationally distinct deployment components.

    This endpoint intentionally does not collapse the control plane, worker and
    artifact store into one boolean. "configured" is not the same as a live
    end-to-end workflow probe.
    """
    artifact_store_configured = bool(
        str(getattr(settings, "SUPABASE_URL", "") or "").strip()
        and str(getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "") or "").strip()
    )
    worker_configured = _worker_configured()
    return {
        "components": {
            "web_control_plane": {
                "status": "LIVE",
                "observed_by": "this HTTP request",
            },
            "production_compute_worker": {
                "status": "CONFIGURED_NOT_PROBED" if worker_configured else "NOT_CONFIGURED_IN_PROCESS",
                "in_process_worker_enabled": worker_configured,
                "availability_inferred_from_web": False,
            },
            "scientific_artifact_store": {
                "status": "CONFIGURED_NOT_PROBED" if artifact_store_configured else "NOT_CONFIGURED",
                "availability_inferred_from_web": False,
            },
        },
        "end_to_end_available": None,
        "availability_semantics": (
            "Web control-plane liveness does not establish production worker or scientific artifact-store availability. "
            "End-to-end workflow availability requires component-specific runtime probes."
        ),
    }


@router.get("/{name}")
async def get_engine_info(name: str):
    engine = get_engine(name)
    if not engine:
        raise HTTPException(status_code=404, detail=f"unknown engine: {name}")
    return engine.describe()


@router.post("/{name}/validate")
async def validate_result(name: str, body: ResultBody):
    """Validate a canonical engine output; returns PASS/FAIL checks,
    augmented by any active plugin validation hooks."""
    engine = get_engine(name)
    if not engine:
        raise HTTPException(status_code=404, detail=f"unknown engine: {name}")
    try:
        result = engine.parse(body.result)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"cannot parse result: {e}")
    report = engine.validate(result).to_dict()
    report["checks"] += plugin_manager.before_validate(name, report, result)
    report["valid"] = all(c.get("passed", False) for c in report["checks"])
    return report


@router.post("/{name}/export")
async def export_result(name: str, body: ResultBody, fmt: str = "json"):
    """Export an engine result to JSON or CSV."""
    engine = get_engine(name)
    if not engine:
        raise HTTPException(status_code=404, detail=f"unknown engine: {name}")
    try:
        result = engine.parse(body.result)
        return {"format": fmt, "content": engine.export(result, fmt)}
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/{name}/figure")
async def figure_result(name: str, body: ResultBody):
    """Render a publication-style SVG figure for the result."""
    engine = get_engine(name)
    if not engine:
        raise HTTPException(status_code=404, detail=f"unknown engine: {name}")
    try:
        result = engine.parse(body.result)
        return {"engine": name, "format": "svg", "svg": engine.figure(result)}
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

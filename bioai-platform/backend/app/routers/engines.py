"""Scientific engines API (BioNexus 2.0 Components 4 & 5).

Exposes the engine registry: introspection (describe), validation (PASS/FAIL
checks) and export (JSON/CSV/SVG figure) for a canonical engine result.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.engines import ENGINES, get_engine
from app.services.plugin_system import plugin_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/engines", tags=["engines"])


class ResultBody(BaseModel):
    # Accepts the canonical BLAST result dict (see _build_blast_result) wrapped
    # under "result"; request bodies are plain JSON without a schema.
    result: dict


@router.get("")
async def list_engines():
    """Every registered engine: name, tool, databases, benchmark coverage."""
    return {"engines": [e.describe() for e in ENGINES.values()]}


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
    report["checks"] += plugin_manager.before_validate(name, report)
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
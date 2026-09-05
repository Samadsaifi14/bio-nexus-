"""Figure Engine routes (Component 8).

- GET /api/figure/formats                 — supported publication formats.
- GET /api/figures/{job_id}               — canonical SVG figure.
- GET /api/figures/{job_id}/export        — SVG/PNG/PDF/TIFF publication export.
- GET /api/figures/{job_id}/export/meta   — deterministic export metadata.
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.services.auth import get_user_id
from app.services.benchmarks import _fetch_job_context
from app.services.experiment_figures import build_experiment_figure
from app.services.figure_export import export_figure

logger = logging.getLogger(__name__)
router = APIRouter(tags=["figure"])


@router.get("/api/figure/formats")
async def figure_formats():
    return {
        "svg": {"content_type": "image/svg+xml", "vector": True, "dpi": None},
        "png": {"content_type": "image/png", "vector": False, "dpi": "300-600"},
        "pdf": {"content_type": "application/pdf", "vector": True, "dpi": None},
        "tiff": {"content_type": "image/tiff", "vector": False, "dpi": "300-600", "compression": "LZW"},
        "policy": "SVG is the canonical source; raster/PDF exports are derived from the same SVG so panels and labels remain identical.",
    }


def _figure_svg(job_id: str) -> str:
    context = _fetch_job_context(job_id)
    if not context:
        raise HTTPException(status_code=404, detail="Job context not found or empty")
    return build_experiment_figure(context, job_id)


@router.get("/api/figures/{job_id}")
async def experiment_figure(job_id: str, user_id: str | None = Depends(get_user_id)):
    """Canonical multi-panel publication figure as SVG."""
    return Response(content=_figure_svg(job_id), media_type="image/svg+xml")


@router.get("/api/figures/{job_id}/export")
async def experiment_figure_export(
    job_id: str,
    format: Literal["svg", "png", "pdf", "tiff"] = Query("svg"),
    dpi: int = Query(300, ge=300, le=600),
    user_id: str | None = Depends(get_user_id),
):
    """Return a publication artifact derived from the canonical SVG.

    Raster exports are restricted to 300-600 DPI. The SHA-256 checksum is
    returned as a response header for archive/provenance capture.
    """
    try:
        artifact = export_figure(_figure_svg(job_id), format, dpi)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Figure conversion unavailable")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    headers = {
        "X-BioNexus-SHA256": artifact.sha256,
        "Content-Disposition": f'attachment; filename="{job_id}.{format}"',
    }
    if artifact.dpi:
        headers["X-BioNexus-DPI"] = str(artifact.dpi)
    return Response(content=artifact.payload, media_type=artifact.content_type, headers=headers)


@router.get("/api/figures/{job_id}/export/meta")
async def experiment_figure_export_metadata(
    job_id: str,
    format: Literal["svg", "png", "pdf", "tiff"] = Query("svg"),
    dpi: int = Query(300, ge=300, le=600),
    user_id: str | None = Depends(get_user_id),
):
    """Metadata/checksum for the exact bytes returned by the export endpoint."""
    try:
        artifact = export_figure(_figure_svg(job_id), format, dpi)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "job_id": job_id,
        "canonical_source": "svg",
        "panel_labels": "embedded in canonical figure",
        "export": artifact.metadata(),
    }

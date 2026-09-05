"""Figure Engine routes (Component 8).

- GET /api/figure/formats          — supported publication formats & layout rules.
- GET /api/figures/{job_id}        — multi-panel publication figure (SVG) for a
                                     recorded experiment, composed from its stored
                                     result context.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Response

from app.services.auth import get_user_id
from app.services.benchmarks import _fetch_job_context
from app.services.experiment_figures import build_experiment_figure

logger = logging.getLogger(__name__)
router = APIRouter(tags=["figure"])


@router.get("/api/figure/formats")
async def figure_formats():
    """Publication formats the Figure Engine can emit (SVG only by design:
    vector output with zero binary raster dependencies in the deployment)."""
    return {
        "svg": {"content_type": "image/svg+xml", "note": "vector, publication-ready"},
        "png": {"content_type": "image/png", "note": "not bundled — rasterization is left to the client/render farm"},
        "pdf": {"content_type": "application/pdf", "note": "not bundled — vector PDF via viewer conversion"},
        "tiff": {"content_type": "image/tiff", "note": "not bundled — 600 DPI TIFF via server-side renderer"},
    }


@router.get("/api/figures/{job_id}")
async def experiment_figure(job_id: str, user_id: str | None = Depends(get_user_id)):
    """One publication figure for a recorded experiment (paneled, captioned)."""
    context = _fetch_job_context(job_id)
    if not context:
        raise HTTPException(status_code=404, detail="Job context not found or empty")
    svg = build_experiment_figure(context, job_id)
    return Response(content=svg, media_type="image/svg+xml")
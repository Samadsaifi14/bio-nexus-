"""Publication Engine routes (Component 10):

- GET /api/experiments/{job_id}/paper?fmt=json|md  — generated manuscript draft.
- GET /api/paper/journal-formats                    — supported journal templates.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Response

from app.services.auth import get_user_id
from app.services.benchmarks import _fetch_job_context
from app.services.publication import JOURNAL_TEMPLATES, render_markdown, render_paper

logger = logging.getLogger(__name__)
router = APIRouter(tags=["publication"])


@router.get("/api/paper/journal-formats")
async def journal_formats():
    """Journal templates the Publication Engine can emit."""
    return {"journals": JOURNAL_TEMPLATES}


@router.get("/api/experiments/{job_id}/paper")
async def experiment_paper(job_id: str, fmt: str = "json", journal: str = "bmc",
                           user_id: str | None = Depends(get_user_id)):
    """Manuscript draft generated from the recorded experiment. Zero external calls."""
    context = _fetch_job_context(job_id)
    if not context:
        raise HTTPException(status_code=404, detail="Job context not found or empty")
    paper = render_paper(context, job_id)
    if fmt == "md":
        return Response(content=render_markdown(paper, journal=journal),
                        media_type="text/markdown")
    return paper
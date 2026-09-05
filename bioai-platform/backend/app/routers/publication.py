"""Publication Engine routes with journal-specific rendering."""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Response

from app.services.auth import get_user_id
from app.services.benchmarks import _fetch_job_context
from app.services.publication import JOURNAL_TEMPLATES, render_paper
from app.services.publication_formats import JOURNAL_FORMATS, completeness, normalize_journal, render_latex, render_markdown

logger=logging.getLogger(__name__); router=APIRouter(tags=["publication"])

@router.get("/api/paper/journal-formats")
async def journal_formats():
    return {"journals":JOURNAL_FORMATS,"legacy_templates":JOURNAL_TEMPLATES,"formats":["json","md","tex"]}

@router.get("/api/experiments/{job_id}/paper")
async def experiment_paper(job_id:str,fmt:str="json",journal:str="bmc_bioinformatics",user_id:str|None=Depends(get_user_id)):
    context=_fetch_job_context(job_id)
    if not context:raise HTTPException(status_code=404,detail="Job context not found or empty")
    try:normalized=normalize_journal(journal)
    except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc))
    paper=render_paper(context,job_id); paper["target_journal"]=JOURNAL_FORMATS[normalized]["label"]; paper["publication_completeness"]=completeness(paper)
    if fmt=="md":return Response(content=render_markdown(paper,normalized),media_type="text/markdown")
    if fmt=="tex":return Response(content=render_latex(paper,normalized),media_type="application/x-tex")
    if fmt!="json":raise HTTPException(status_code=422,detail="fmt must be json, md, or tex")
    return paper

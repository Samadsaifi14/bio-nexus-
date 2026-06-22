import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from app.services.auth import require_user_id
from app.services.supabase import get_supabase
from app.services.export import export_blast_pdf, export_uniprot_pdf

router = APIRouter()


@router.get("/job/{job_id}")
async def export_job(
    job_id: str,
    format: str = Query("pdf", regex="^(pdf|json)$"),
    user_id: str = require_user_id,
):
    supabase = get_supabase()
    job = supabase.table("jobs").select("*").eq("id", job_id).execute()
    if not job.data:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.data[0].get("user_id") and job.data[0]["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not your job")

    context = job.data[0].get("context_json") or {}
    steps = context.get("steps") or {}
    if not steps:
        steps = {}
    blast_data = steps.get("blast", {}).get("data") or context.get("blast") or {}
    uniprot_data = steps.get("uniprot", {}).get("data") or context.get("uniprot") or {}
    sequence = (context.get("query") or {}).get("sequence") or context.get("sequence") or ""

    if format == "json":
        return JSONResponse(
            content=job.data[0],
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="bio-nexus-{job_id[:8]}.json"'},
        )

    pdf_parts = []
    if blast_data.get("hits"):
        pdf_parts.append(export_blast_pdf(blast_data, sequence))
    if uniprot_data.get("accession"):
        pdf_parts.append(export_uniprot_pdf(uniprot_data))

    if not pdf_parts:
        raise HTTPException(status_code=400, detail="No exportable data found for this job")

    merged = pdf_parts[0] if len(pdf_parts) == 1 else pdf_parts[0] + pdf_parts[1]

    return StreamingResponse(
        iter([merged]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="bio-nexus-{job_id[:8]}.pdf"'},
    )

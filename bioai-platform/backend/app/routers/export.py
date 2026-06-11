from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from app.services.export import export_blast_pdf, export_uniprot_pdf

router = APIRouter()


class BlastExportRequest(BaseModel):
    result: dict
    sequence: str = ""


class UniprotExportRequest(BaseModel):
    data: dict


@router.post("/blast")
async def export_blast(req: BlastExportRequest):
    try:
        pdf = export_blast_pdf(req.result, req.sequence)
        return Response(content=pdf, media_type="application/pdf", headers={
            "Content-Disposition": "attachment; filename=blast_results.pdf"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/uniprot")
async def export_uniprot(req: UniprotExportRequest):
    try:
        pdf = export_uniprot_pdf(req.data)
        return Response(content=pdf, media_type="application/pdf", headers={
            "Content-Disposition": f"attachment; filename=uniprot_{req.data.get('accession', 'protein')}.pdf"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pipeline/{job_id}")
async def export_pipeline(job_id: str):
    raise HTTPException(status_code=501, detail="Pipeline PDF export coming in Phase 1.5")

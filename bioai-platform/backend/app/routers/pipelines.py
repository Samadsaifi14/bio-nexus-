from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.services.validators import validate_fasta, ValidationResult
from app.pipeline.engine import PipelineEngine
from app.pipeline.definitions.protein_analysis import get_pipeline_definition
from app.services.supabase import get_supabase
from app.services.rate_limit import check_daily_limit
from app.workers.celery_app import celery_app
from app.workers.pipeline_worker import run_pipeline_sync
from datetime import datetime, timezone
import uuid

router = APIRouter()


class PipelineRunRequest(BaseModel):
    sequence: str
    pipeline_type: str = "protein_analysis"
    database: str = "uniprotkb_swissprot"
    max_hits: int = 10


@router.post("/run", dependencies=[Depends(check_daily_limit)])
async def run_pipeline(req: PipelineRunRequest):
    validation = validate_fasta(req.sequence, "blast")
    if not validation.valid:
        raise HTTPException(status_code=400, detail=validation.error)

    seq = str(validation.sequences[0].seq).upper().replace(" ", "")

    job_id = str(uuid.uuid4())
    supabase = get_supabase()

    supabase.table("jobs").insert({
        "id": job_id,
        "tool": "pipeline",
        "query_preview": seq[:100],
        "status": "pending",
        "pipeline_type": req.pipeline_type,
        "steps_completed": [],
        "context_json": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    if celery_app is not None:
        from app.workers.pipeline_worker import run_pipeline_job
        run_pipeline_job.delay(job_id, seq, req.database, req.max_hits)
    else:
        import threading
        t = threading.Thread(target=run_pipeline_sync, args=(job_id, seq, req.database, req.max_hits), daemon=True)
        t.start()

    return {"job_id": job_id, "status": "pending"}


@router.get("/definitions")
async def list_pipeline_definitions():
    return {"pipelines": [get_pipeline_definition()]}


@router.get("/{pipeline_type}/definition")
async def get_pipeline_definition_endpoint(pipeline_type: str):
    if pipeline_type == "protein_analysis":
        return get_pipeline_definition()
    raise HTTPException(status_code=404, detail=f"Unknown pipeline: {pipeline_type}")

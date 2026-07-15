from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.services.validators import validate_fasta
from app.pipeline.definitions.protein_analysis import get_pipeline_definition
from app.services.supabase import get_supabase
from app.services.rate_limit import check_daily_limit
from app.services.auth import get_user_id
from app.models.responses import PipelineRunResponse, PipelineDefinitionResponse
from datetime import datetime, timezone
import uuid

router = APIRouter()


class PipelineRunRequest(BaseModel):
    sequence: str
    pipeline_type: str = "protein_analysis"
    database: str = "nr"
    max_hits: int = 10
    query_accession: str = ""


@router.post("/run", response_model=PipelineRunResponse, dependencies=[Depends(check_daily_limit)])
async def run_pipeline(req: PipelineRunRequest, user_id: str | None = Depends(get_user_id)):
    validation = validate_fasta(req.sequence, "blast")
    if not validation.valid:
        raise HTTPException(status_code=400, detail=validation.error)

    seq = str(validation.sequences[0].seq).upper()
    clean = "".join(c for c in seq if c.isalpha())

    job_id = str(uuid.uuid4())
    supabase = get_supabase()

    supabase.table("jobs").insert({
        "id": job_id,
        "user_id": user_id,
        "tool": "pipeline",
        "query_preview": clean[:100],
        "status": "queued",
        "pipeline_type": req.pipeline_type,
        "steps_completed": [],
        "context_json": None,
        "progress_pct": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "error": None,
        "share_token": None,
    }).execute()

    return {"job_id": job_id, "status": "queued"}


@router.get("/definitions", response_model=PipelineDefinitionResponse)
async def list_pipeline_definitions():
    return {"pipelines": [get_pipeline_definition()]}


@router.get("/{pipeline_type}/definition")
async def get_pipeline_definition_endpoint(pipeline_type: str):
    if pipeline_type == "protein_analysis":
        return get_pipeline_definition()
    raise HTTPException(status_code=404, detail=f"Unknown pipeline: {pipeline_type}")

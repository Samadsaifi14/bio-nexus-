from datetime import datetime, timezone
import uuid
import hashlib
import json

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

from app.services.validators import validate_fasta
from app.services.workflow_templates import WorkflowRecipe, recipe_plan
from app.pipeline.definitions.protein_analysis import get_pipeline_definition
from app.services.supabase import get_supabase
from app.services.auth import require_user_id
from app.models.responses import PipelineRunResponse, PipelineDefinitionResponse

router = APIRouter()


class PipelineRunRequest(BaseModel):
    sequence: str
    pipeline_type: str = "protein_analysis"
    database: str = ""
    program: str = ""
    max_hits: int = Field(default=100, ge=1, le=100)
    query_accession: str = ""
    fast_mode: bool = False
    workflow_recipe: WorkflowRecipe | None = None


def _effective_pipeline_type(requested: str, program: str) -> str:
    """Restore comprehensive downstream analysis for protein-protein BLAST.

    A standalone BLASTP query produces protein hits that can legitimately feed
    UniProt annotation, protein MSA/phylogeny, domains, pathways and structure.
    Other BLAST program families are intentionally kept search-only because
    their query/subject molecule semantics are not equivalent to a protein
    sequence ready for those downstream stages.
    """
    requested_norm = (requested or "protein_analysis").strip().lower()
    program_norm = (program or "").strip().lower()
    if requested_norm == "blast" and program_norm == "blastp":
        return "protein_analysis"
    return requested_norm


@router.post("/run", response_model=PipelineRunResponse)
async def run_pipeline(
    request: Request,
    req: PipelineRunRequest,
    user_id: str = Depends(require_user_id),
):
    """Create a private, owner-scoped scientific pipeline job.

    The full sequence is retained only in the authenticated job context required by
    the worker. ``query_preview`` deliberately contains metadata rather than sequence
    characters so list/history surfaces cannot accidentally reveal biological input.
    Explicit sharing remains available through the share-token endpoint.
    """
    return _create_pipeline_job(req, user_id)


def _create_pipeline_job(req: PipelineRunRequest, user_id: str, parent_job_id: str | None = None, *, job_id: str | None = None, collection_metadata: dict | None = None):
    if req.pipeline_type not in {"protein_analysis", "blast"}:
        raise HTTPException(status_code=400, detail="Unsupported pipeline type")
    if req.workflow_recipe and req.pipeline_type != "protein_analysis":
        raise HTTPException(status_code=400, detail="Workflow recipes require protein_analysis")
    if req.workflow_recipe:
        recipe = req.workflow_recipe
        req.database, req.program, req.max_hits = recipe.database, recipe.program, recipe.max_hits
        req.fast_mode, req.query_accession = recipe.fast_mode, recipe.query_accession
    validation = validate_fasta(req.sequence, "blast")
    if not validation.valid:
        raise HTTPException(status_code=400, detail=validation.error)

    seq = str(validation.sequences[0].seq).upper()
    if req.workflow_recipe:
        from app.services.sequence_utils import detect_sequence_type
        if detect_sequence_type(seq) != "protein":
            raise HTTPException(status_code=400, detail="Protein workflow recipes require an unambiguous protein sequence")
    clean = "".join(c for c in seq if c.isalpha())

    job_id = job_id or str(uuid.uuid4())
    supabase = get_supabase()
    effective_pipeline_type = _effective_pipeline_type(req.pipeline_type, req.program)

    supabase.table("jobs").insert({
        "id": job_id,
        "parent_job_id": parent_job_id,
        "user_id": user_id,
        "tool": "pipeline",
        "query_preview": f"sequence_length:{len(clean)}",
        "status": "queued",
        "pipeline_type": effective_pipeline_type,
        "steps_completed": [],
        "context_json": {
            **(collection_metadata or {}),
            "sequence": clean,
            "length": len(clean),
            "fast_mode": req.fast_mode,
            "database": req.database,
            "program": req.program,
            "requested_pipeline_type": req.pipeline_type,
            "effective_pipeline_type": effective_pipeline_type,
            "max_hits": req.max_hits,
            "query_accession": req.query_accession,
            "workflow_steps": req.workflow_recipe.steps if req.workflow_recipe else None,
            "alignment_mode": req.workflow_recipe.alignment_mode if req.workflow_recipe else "global",
        },
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


@router.post("/recipes/validate")
async def validate_workflow_recipe(recipe: WorkflowRecipe, user_id: str = Depends(require_user_id)):
    """Validate a portable recipe without creating a job or launching providers."""
    return recipe_plan(recipe)


class WorkflowCollectionRequest(BaseModel):
    fasta: str = Field(max_length=110000)
    recipe: WorkflowRecipe
    submission_id: uuid.UUID


@router.post('/collections/run')
async def run_workflow_collection(request: Request, req: WorkflowCollectionRequest,
                                  user_id: str = Depends(require_user_id)):
    """Queue private per-record jobs after whole-collection and capacity validation."""
    from app.services.workflow_collections import validate_protein_collection
    from app.config import settings
    try:
        records = validate_protein_collection(req.fasta)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    collection_id = str(req.submission_id)
    collection_digest = hashlib.sha256(json.dumps({'records': records, 'recipe': req.recipe.model_dump()}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    client = get_supabase()
    try:
        existing = client.table('jobs').select('id,status,context_json').eq('user_id', user_id).eq('context_json->>collection_id', collection_id).execute().data or []
    except Exception as exc:
        raise HTTPException(status_code=503, detail='Unable to verify collection retry state; no new jobs queued') from exc
    if any(row.get('context_json', {}).get('collection_sha256') != collection_digest for row in existing):
        raise HTTPException(status_code=409, detail='Submission ID already belongs to different collection content or recipe')
    by_id = {row['id']: row for row in existing}
    for record in records:
        record['job_id'] = str(uuid.uuid5(uuid.NAMESPACE_URL, f'bionexus:collection:{user_id}:{collection_id}:{record["identifier"]}'))
    new_count = sum(record['job_id'] not in by_id for record in records)
    # Capacity counts use the verified owner. Retry-only requests consume no new capacity.
    if new_count:
        today = datetime.now(timezone.utc).date().isoformat()
        try:
            used = 0
            pipeline_used = 0
            for table in ('jobs', 'docking_jobs', 'sequencing_jobs', 'ngs_jobs'):
                response = client.table(table).select('id', count='exact').eq('user_id', user_id).gte('created_at', today + 'T00:00:00').execute()
                if response.count is None:
                    raise ValueError('Missing quota count')
                used += response.count
                if table == 'jobs':
                    pipeline_used = response.count
        except Exception as exc:
            raise HTTPException(status_code=503, detail='Unable to verify account capacity; no new collection jobs queued') from exc
        if pipeline_used + new_count > 10 or used + new_count > settings.DAILY_LIMIT:
            raise HTTPException(status_code=429, detail='Collection exceeds remaining daily account or pipeline capacity')
    items = []
    for record in records:
        job_id = record['job_id']
        if job_id in by_id:
            items.append({'identifier': record['identifier'], 'job_id': job_id, 'status': by_id[job_id]['status'], 'reused': True})
            continue
        metadata = {'collection_id': collection_id, 'collection_identifier': record['identifier'],
                    'collection_sha256': collection_digest, 'input_sha256': hashlib.sha256(record['sequence'].encode()).hexdigest()}
        try:
            result = _create_pipeline_job(PipelineRunRequest(sequence=record['sequence'], workflow_recipe=req.recipe), user_id, job_id=job_id, collection_metadata=metadata)
            items.append({'identifier': record['identifier'], **result, 'reused': False})
        except Exception:
            # A concurrent identical request may have won the primary-key insert.
            try:
                rows = client.table('jobs').select('id,status,context_json').eq('id', job_id).eq('user_id', user_id).execute().data or []
                if rows and all(rows[0].get('context_json', {}).get(key) == value for key, value in metadata.items()):
                    items.append({'identifier': record['identifier'], 'job_id': job_id, 'status': rows[0]['status'], 'reused': True})
                    continue
            except Exception:
                pass
            items.append({'identifier': record['identifier'], 'job_id': None, 'status': 'submission_failed', 'error': 'Queue submission unconfirmed; retry this same submission ID to reconcile'})
    failures = sum(item['status'] == 'submission_failed' for item in items)
    status = 'failed' if failures == len(items) else 'partial' if failures else 'submitted'
    return {'items': items, 'total': len(items), 'collection_id': collection_id, 'collection_sha256': collection_digest,
            'format': 'bionexus-protein-collection', 'status': status}

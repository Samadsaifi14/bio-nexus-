"""Protein function prediction endpoints."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

from app.services.supabase import get_client
from app.services.auth import require_user_id
from app.services import job_registry

router = APIRouter(prefix="/api/function", tags=["Function Prediction"])
_TABLE = "docking_jobs"  # reuse table with tool_type="function_predict"
logger = logging.getLogger(__name__)


class FunctionPredictRequest(BaseModel):
    pdb_id: str = Field(..., pattern=r"^[A-Za-z0-9]{4}$", description="4-char PDB ID")


class FunctionPredictResponse(BaseModel):
    job_id: str
    status: str
    result: dict | None = None
    error: str | None = None


def _row_exists(supabase, job_id: str, user_id: str) -> bool:
    """Confirm a submitted row really failed to insert (not just that its
    response was lost). Live evidence: a worker ran a function job whose
    ``POST /api/function/predict`` had returned 502 because httpx lost the
    Supabase response after the row was committed.
    """
    try:
        res = (
            supabase.table(_TABLE)
            .select("id")
            .eq("id", job_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.warning("Could not confirm function job %s after insert error: %s", job_id, exc)
        return False
    return bool(res.data)


@router.post("/predict", response_model=FunctionPredictResponse)
async def predict_function_endpoint(request: Request, body: FunctionPredictRequest, user_id: str = Depends(require_user_id)):
    """Submit a function prediction job (queued through the durable worker)."""
    supabase = get_client()
    job_id = str(uuid.uuid4())

    insert_row = {
        "id": job_id,
        "status": "queued",
        "user_id": user_id,
        "ligand_smiles": f"func:{body.pdb_id}",
        "payload": {
            "pdb_id": body.pdb_id,
            "tool_type": "function_predict",
        },
    }
    try:
        try:
            supabase.table(_TABLE).insert(insert_row).execute()
        except Exception as e:
            if "ligand_smiles" not in str(e):
                raise
            supabase.table(_TABLE).insert({
                "id": job_id, "status": "queued", "user_id": user_id,
                "payload": insert_row["payload"],
            }).execute()
    except Exception:
        # A dropped response is not a failed insert. If the row exists, the job
        # is already queued/running; returning 502 would hide a live job id.
        if not _row_exists(supabase, job_id, user_id):
            raise
        logger.warning("Function insert response lost for %s; row exists, continuing", job_id)

    job_registry.start(
        "function_predict", user_id, job_id=job_id,
        query_preview=f"Function prediction · {body.pdb_id}",
        context={"pdb_id": body.pdb_id},
    )
    return FunctionPredictResponse(job_id=job_id, status="queued")


@router.get("/status/{job_id}", response_model=FunctionPredictResponse)
async def get_function_status(job_id: str, user_id: str = Depends(require_user_id)):
    supabase = get_client()
    row = supabase.table(_TABLE).select("*").eq("id", job_id).eq("user_id", user_id).single().execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="Job not found")

    data = row.data

    if data.get("status") in ("queued", "running") and data.get("claimed_at"):
        try:
            claimed = datetime.fromisoformat(data["claimed_at"].replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - claimed > timedelta(minutes=10):
                supabase.table(_TABLE).update({
                    "status": "failed",
                    "error": "Job timed out (exceeded 10 minute limit)",
                    "done_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", job_id).execute()
                data["status"] = "failed"
                data["error"] = "Job timed out (exceeded 10 minute limit)"
                job_registry.finish(job_id, status="failed", error=data["error"])
        except Exception:
            pass

    result = None
    retrieval_error: str | None = None
    if data.get("storage_url"):
        from app.services.artifact_storage import download_json
        try:
            result = download_json(data["storage_url"])
        except Exception as exc:
            logger.warning(
                "Function result download failed for %s: %s", job_id, exc
            )
            retrieval_error = (
                "The job completed, but its stored result could not be retrieved "
                f"from artifact storage ({type(exc).__name__})."
            )
    elif data.get("result_sdf"):
        try:
            result = json.loads(data["result_sdf"])
        except Exception:
            retrieval_error = "The stored result payload is not valid JSON."

    error = data.get("error")
    if result is None and data.get("status") == "complete":
        # Never report a silent success: a completed row without a payload is a
        # retrieval failure the client must be able to show and act on.
        error = error or retrieval_error or (
            "The job completed but no result payload was stored. Re-run the analysis."
        )

    return FunctionPredictResponse(
        job_id=data["id"],
        status=data["status"],
        result=result,
        error=error,
    )

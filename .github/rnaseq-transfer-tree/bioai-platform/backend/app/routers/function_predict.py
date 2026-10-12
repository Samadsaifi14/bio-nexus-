"""Protein function prediction endpoints."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

from app.services.supabase import get_client
from app.services.auth import require_user_id

router = APIRouter(prefix="/api/function", tags=["Function Prediction"])
_TABLE = "docking_jobs"  # reuse table with tool_type="function_predict"


class FunctionPredictRequest(BaseModel):
    pdb_id: str = Field(..., pattern=r"^[A-Za-z0-9]{4}$", description="4-char PDB ID")


class FunctionPredictResponse(BaseModel):
    job_id: str
    status: str
    result: dict | None = None
    error: str | None = None


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
        supabase.table(_TABLE).insert(insert_row).execute()
    except Exception as e:
        if "ligand_smiles" in str(e):
            supabase.table(_TABLE).insert({
                "id": job_id, "status": "queued", "user_id": user_id,
                "payload": insert_row["payload"],
            }).execute()
        else:
            raise

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
        except Exception:
            pass

    result = None
    if data.get("storage_url"):
        from app.services.artifact_storage import download_json
        result = download_json(data["storage_url"])
    elif data.get("result_sdf"):
        try:
            result = json.loads(data["result_sdf"])
        except Exception:
            pass

    return FunctionPredictResponse(
        job_id=data["id"],
        status=data["status"],
        result=result,
        error=data.get("error"),
    )

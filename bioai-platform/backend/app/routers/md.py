"""Molecular dynamics simulation endpoints (implicit solvent only)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

from app.deps import limiter
from app.services.supabase import get_client
from app.services.auth import require_user_id
from app.services.rate_limit import check_daily_limit
from app.services.artifact_storage import upload_json

router = APIRouter(prefix="/api/md", tags=["MD Simulation"])
_TABLE = "docking_jobs"  # reuse docking_jobs table with md_jobs for now


class MDRunRequest(BaseModel):
    pdb_id: str = Field(..., pattern=r"^[A-Za-z0-9]{4}$", description="4-char PDB ID")
    mode: str = Field(default="minimize", pattern=r"^(minimize|equilibrate|production)$")


class MDJobResponse(BaseModel):
    job_id: str
    status: str
    result: dict | None = None
    error: str | None = None


@router.post("/run", response_model=MDJobResponse, dependencies=[Depends(check_daily_limit)])
@limiter.limit("3/minute")
async def run_md(request: Request, body: MDRunRequest, user_id: str = Depends(require_user_id)):
    """Submit an MD simulation job (queued through the durable worker)."""
    from app.services.ssrf import validate_url

    supabase = get_client()
    job_id = str(uuid.uuid4())

    supabase.table(_TABLE).insert({
        "id": job_id,
        "status": "queued",
        "user_id": user_id,
        "ligand_smiles": f"md:{body.mode}:{body.pdb_id}",
        "payload": {
            "pdb_id": body.pdb_id,
            "mode": body.mode,
            "tool_type": "md",
        },
    }).execute()

    return MDJobResponse(job_id=job_id, status="queued")


@router.get("/status/{job_id}", response_model=MDJobResponse)
async def get_md_status(job_id: str, user_id: str = Depends(require_user_id)):
    supabase = get_client()
    row = supabase.table(_TABLE).select("*").eq("id", job_id).eq("user_id", user_id).single().execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="Job not found")

    data = row.data
    result = None
    if data.get("storage_url"):
        from app.services.artifact_storage import download_json
        result = download_json(data["storage_url"])
    elif data.get("result_sdf"):
        try:
            import json
            result = json.loads(data["result_sdf"])
        except Exception:
            pass

    return MDJobResponse(
        job_id=data["id"],
        status=data["status"],
        result=result,
        error=data.get("error"),
    )

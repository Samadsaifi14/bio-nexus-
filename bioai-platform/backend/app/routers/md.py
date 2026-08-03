"""Molecular dynamics simulation endpoints (implicit solvent only)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

from app.services.supabase import get_client
from app.services.auth import require_user_id

router = APIRouter(prefix="/api/md", tags=["MD Simulation"])
_TABLE = "docking_jobs"  # reuse docking_jobs table with md_jobs for now


class MDRunRequest(BaseModel):
    pdb_id: str = Field(..., pattern=r"^[A-Za-z0-9]{4}$", description="4-char PDB ID")
    mode: str = Field(default="minimize", pattern=r"^(minimize|equilibrate|production)$")
    platform: str | None = Field(default=None, description="Optional OpenMM platform (CPU/Reference)")
    forcefield: str | None = Field(default=None, pattern=r"^[a-z0-9_-]+$", description="Force field from the verified menu (GET /api/md/forcefields)")
    solvent: str | None = Field(default=None, pattern=r"^(obc1|obc2|gbn2)$", description="Implicit solvent model (explicit water not supported)")
    run_length_ps: float | None = Field(default=None, ge=50, le=5000, description="Desired production length in ps (production mode only; engine may clamp to wall-clock budget)")


class MDJobResponse(BaseModel):
    job_id: str
    status: str
    result: dict | None = None
    error: str | None = None


@router.get("/forcefields")
async def get_md_forcefields():
    """Return the force field / solvent menu (verified combos only)."""
    from app.tools.md_config import get_forcefields_menu

    return get_forcefields_menu()


@router.post("/run", response_model=MDJobResponse)
async def run_md(request: Request, body: MDRunRequest, user_id: str = Depends(require_user_id)):
    """Submit an MD simulation job (queued through the durable worker)."""
    from app.services.ssrf import validate_url
    from app.tools.md_config import resolve_combo

    # Reject invalid force field / solvent combinations immediately with an
    # explicit error (no silent AMBER14/OBC2 fallback).
    try:
        resolve_combo(body.forcefield, body.solvent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    supabase = get_client()
    job_id = str(uuid.uuid4())

    insert_row = {
        "id": job_id,
        "status": "queued",
        "user_id": user_id,
        "ligand_smiles": f"md:{body.mode}:{body.pdb_id}",
        "payload": {
            "pdb_id": body.pdb_id,
            "mode": body.mode,
            "platform": body.platform,
            "forcefield": body.forcefield,
            "solvent": body.solvent,
            "run_length_ps": body.run_length_ps,
            "tool_type": "md",
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

    return MDJobResponse(job_id=job_id, status="queued")


@router.get("/status/{job_id}", response_model=MDJobResponse)
async def get_md_status(job_id: str, user_id: str = Depends(require_user_id)):
    supabase = get_client()
    row = supabase.table(_TABLE).select("*").eq("id", job_id).eq("user_id", user_id).single().execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="Job not found")

    data = row.data

    if data.get("status") in ("queued", "running") and data.get("claimed_at"):
        try:
            claimed = datetime.fromisoformat(data["claimed_at"].replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - claimed > timedelta(minutes=60):
                supabase.table(_TABLE).update({
                    "status": "failed",
                    "error": "Job timed out (exceeded 60 minute limit)",
                    "done_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", job_id).execute()
                data["status"] = "failed"
                data["error"] = "Job timed out (exceeded 60 minute limit)"
        except Exception:
            pass

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

from __future__ import annotations

import asyncio
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.config import settings
from app.services.supabase import get_client

router = APIRouter(prefix="/api/docking", tags=["Docking"])
_TABLE = "docking_jobs"


class DockingJobCreate(BaseModel):
    protein_name: str
    protein_sequence: str
    ligand_smiles: str
    grid_center: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    grid_size: list[float] = Field(default_factory=lambda: [20.0, 20.0, 20.0])
    exhaustiveness: int = 8
    num_modes: int = 9


class DockingJobResponse(BaseModel):
    id: str
    status: str
    protein_name: str
    ligand_smiles: str
    affinity: Optional[float] = None
    rmsd_lb: Optional[float] = None
    rmsd_ub: Optional[float] = None
    result_sdf: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


def _prune_old(supabase, max_rows: int = 200):
    """Keep only the most recent rows; drop older ones."""
    try:
        rows = (
            supabase.table(_TABLE)
            .select("id")
            .order("created_at", desc=True)
            .range(max_rows, max_rows + 1000)
            .execute()
            .data
        )
        if rows:
            supabase.table(_TABLE).delete().in_(
                "id", [r["id"] for r in rows]
            ).execute()
    except Exception:
        pass


def _run_docking_sync(job_id: str, payload: dict):
    """Run the full docking pipeline synchronously (called in a thread)."""
    supabase = get_client()
    try:
        supabase.table(_TABLE).update({"status": "running"}).eq("id", job_id).execute()

        from app.tools.docking import (
            smiles_to_pdbqt,
            make_pdb_from_sequence,
            pdb_to_pdbqt_receptor,
            run_vina,
        )

        # Build protein PDB from sequence, then convert to PDBQT.
        # FIX: previously the raw PDB was passed straight to Vina, which
        # requires PDBQT (AutoDock atom types + charges) for the receptor —
        # this was causing every job to fail with a PDBQT parsing error.
        protein_pdb = make_pdb_from_sequence(payload["protein_sequence"])
        protein_pdbqt = pdb_to_pdbqt_receptor(protein_pdb)

        # Prepare ligand PDBQT
        lig_pdbqt = smiles_to_pdbqt(payload["ligand_smiles"])

        # Run AutoDock Vina
        result = run_vina(
            protein_pdbqt=protein_pdbqt,
            ligand_pdbqt=lig_pdbqt,
            grid_center=payload.get("grid_center", [0, 0, 0]),
            grid_size=payload.get("grid_size", [20, 20, 20]),
            exhaustiveness=payload.get("exhaustiveness", 8),
            num_modes=payload.get("num_modes", 9),
        )

        update = {
            "status": "completed",
            "affinity": result.get("affinity"),
            "rmsd_lb": result.get("rmsd_lb"),
            "rmsd_ub": result.get("rmsd_ub"),
            "result_sdf": result.get("result_sdf"),
        }
        supabase.table(_TABLE).update(update).eq("id", job_id).execute()
    except Exception as exc:
        supabase.table(_TABLE).update({"status": "failed", "error": str(exc)[:2000]}).eq("id", job_id).execute()
    finally:
        _prune_old(supabase)


@router.post("/run", response_model=DockingJobResponse)
async def create_docking_job(body: DockingJobCreate):
    supabase = get_client()
    _prune_old(supabase)

    import uuid, datetime
    job_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    row = {
        "id": job_id,
        "status": "queued",
        "protein_name": body.protein_name,
        "protein_sequence": body.protein_sequence,
        "ligand_smiles": body.ligand_smiles,
        "grid_center": body.grid_center,
        "grid_size": body.grid_size,
        "exhaustiveness": body.exhaustiveness,
        "num_modes": body.num_modes,
        "created_at": now,
        "updated_at": now,
    }
    supabase.table(_TABLE).insert(row).execute()

    loop = asyncio.get_event_loop()
    asyncio.ensure_future(loop.run_in_executor(None, _run_docking_sync, job_id, row))

    return DockingJobResponse(**{k: v for k, v in row.items() if k in DockingJobResponse.model_fields})


@router.get("/status/{job_id}", response_model=DockingJobResponse)
async def get_docking_job(job_id: str):
    supabase = get_client()
    result = supabase.table(_TABLE).select("*").eq("id", job_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Docking job not found")
    return DockingJobResponse(**result.data)


@router.get("")
async def list_docking_jobs(limit: int = 50):
    supabase = get_client()
    rows = (
        supabase.table(_TABLE)
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )
    return {"jobs": [DockingJobResponse(**r) for r in rows]}

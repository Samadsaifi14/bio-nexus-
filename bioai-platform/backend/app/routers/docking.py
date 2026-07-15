from __future__ import annotations

import asyncio
import json
import math
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional

from app.services.supabase import get_client

router = APIRouter(prefix="/api/docking", tags=["Docking"])
_TABLE = "docking_jobs"


# ---------------------------------------------------------------------------
# Request / response schemas (match frontend DockingResult type)
# ---------------------------------------------------------------------------

class DockingJobCreate(BaseModel):
    pdb_id: str = ""
    smiles: str
    pdb_url: str = ""
    grid_center: Optional[list[float]] = None
    grid_size: list[float] = Field(default_factory=lambda: [20.0, 20.0, 20.0])
    exhaustiveness: int = 8
    num_modes: int = 9


class DockingJobResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prune_old(supabase, max_rows: int = 200):
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


def _row_to_response(row: dict) -> dict:
    """Convert a Supabase row to the frontend DockingResult shape."""
    result = None
    if row.get("result_sdf"):
        try:
            result = json.loads(row["result_sdf"])
        except Exception:
            pass
    return {
        "job_id": row["id"],
        "status": row["status"],
        "result": result,
        "error": row.get("error"),
    }


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

def _run_docking_sync(job_id: str, payload: dict):
    """Run the full docking pipeline synchronously (in a thread)."""
    supabase = get_client()
    try:
        supabase.table(_TABLE).update({"status": "running"}).eq("id", job_id).execute()

        from app.tools.docking import (
            fetch_pdb_from_rcsb,
            compute_grid_center,
            smiles_to_pdbqt,
            pdb_to_pdbqt_receptor,
            run_vina,
        )
        import urllib.request

        pdb_id = payload.get("pdb_id", "").strip().upper()
        pdb_url = payload.get("pdb_url", "").strip()
        smiles = payload["smiles"]

        # 1. Obtain PDB text
        pdb_text: str | None = None
        if pdb_url:
            try:
                pdb_text = urllib.request.urlopen(pdb_url, timeout=30).read().decode("utf-8", errors="replace")
            except Exception:
                pass
        if not pdb_text and pdb_id:
            pdb_text = fetch_pdb_from_rcsb(pdb_id)

        if not pdb_text:
            raise RuntimeError(
                "Could not obtain a PDB structure. "
                "Provide a valid pdb_id or pdb_url."
            )

        # 2. Strip heteroatoms (keep protein backbone for receptor)
        protein_lines = [
            l for l in pdb_text.splitlines()
            if l.startswith("ATOM") or l.startswith("TER") or l.startswith("END")
        ]
        protein_pdb = "\n".join(protein_lines) if protein_lines else pdb_text

        # 3. Compute grid center if not provided
        grid_center = payload.get("grid_center")
        if not grid_center or all(v == 0 for v in grid_center):
            grid_center = compute_grid_center(protein_pdb)
            # Add a small offset so the center isn't dead on a backbone atom
            grid_center = [round(c + 2.0, 3) for c in grid_center]

        grid_size = payload.get("grid_size", [20.0, 20.0, 20.0])

        # 4. Prepare receptor
        protein_pdbqt = pdb_to_pdbqt_receptor(protein_pdb)

        # 5. Prepare ligand
        lig_pdbqt = smiles_to_pdbqt(smiles)

        # 6. Run AutoDock Vina
        vina_result = run_vina(
            protein_pdbqt=protein_pdbqt,
            ligand_pdbqt=lig_pdbqt,
            grid_center=grid_center,
            grid_size=grid_size,
            exhaustiveness=payload.get("exhaustiveness", 8),
            num_modes=payload.get("num_modes", 9),
        )

        # 7. Compute interaction summary for best pose
        interactions = _compute_interactions(
            protein_pdb, vina_result["ligand_pdb"]
        )
        pose_interactions = _summarize_pose_interactions(
            protein_pdb, vina_result.get("result_sdf", "")
        )

        result_obj = {
            "pdb_id": pdb_id,
            "smiles": smiles,
            "poses": vina_result["poses"],
            "num_poses": vina_result["num_poses"],
            "box_center": {
                "x": grid_center[0],
                "y": grid_center[1],
                "z": grid_center[2],
            },
            "box_size": {
                "x": grid_size[0],
                "y": grid_size[1],
                "z": grid_size[2],
            },
            "vina_log": vina_result.get("vina_log", ""),
            "interactions": interactions,
            "pose_interactions": pose_interactions,
            "ligand_pdb": vina_result.get("ligand_pdb", ""),
        }

        supabase.table(_TABLE).update({
            "status": "completed",
            "result_sdf": json.dumps(result_obj),
        }).eq("id", job_id).execute()

    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        supabase.table(_TABLE).update({
            "status": "failed",
            "error": f"{exc}\n\n{tb}"[:4000],
        }).eq("id", job_id).execute()
    finally:
        _prune_old(supabase)


# ---------------------------------------------------------------------------
# Simple geometric interaction detector (H-bonds, hydrophobic, pi-stacking)
# ---------------------------------------------------------------------------

_RESIDUEPOLAR = {"SER", "THR", "ASN", "GLN", "ASP", "GLU", "ARG", "LYS", "HIS", "CYS", "TYR"}
_RESIDUEHYDRO = {"ALA", "VAL", "LEU", "ILE", "MET", "PHE", "TRP", "PRO", "GLY"}

_PDB_COORD_RE = re.compile(
    r"^(ATOM|HETATM)\s+\d+\s+(\S+)\s+(\S{3})\s+(\S)\s+(\d+)\s+"
    r"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)"
)


def _parse_atom_coords(pdb_text: str) -> list[tuple[str, str, str, str, int, float, float, float]]:
    """Parse PDB into (record, atom_name, res_name, chain, res_seq, x, y, z)."""
    atoms = []
    for line in pdb_text.splitlines():
        m = _PDB_COORD_RE.match(line)
        if m:
            atoms.append((
                m.group(1), m.group(2), m.group(3), m.group(4),
                int(m.group(5)),
                float(m.group(6)), float(m.group(7)), float(m.group(8)),
            ))
    return atoms


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _compute_interactions(protein_pdb: str, ligand_pdb: str) -> dict:
    """Compute simple distance-based interactions between protein and ligand."""
    if not ligand_pdb:
        return {"hbonds": [], "hydrophobic": [], "pi_stacking": []}

    prot_atoms = _parse_atom_coords(protein_pdb)
    lig_atoms = _parse_atom_coords(ligand_pdb)

    hbonds: list[dict] = []
    hydrophobic: list[dict] = []

    HBDONORS = {"N", "O", "S"}
    HBACCEPTORS = {"N", "O", "S"}

    for la in lig_atoms:
        lcoord = (la[5], la[6], la[7])
        for pa in prot_atoms:
            pcoord = (pa[5], pa[6], pa[7])
            d = _distance(lcoord, pcoord)
            aname = la[1]

            if d < 3.5 and (aname in HBDONORS or aname in HBACCEPTORS):
                hbonds.append({
                    "type": "hbond",
                    "ligand_atom": aname,
                    "protein_residue": pa[2],
                    "protein_atom": pa[1],
                    "protein_atom_name": pa[1],
                    "distance": round(d, 2),
                    "confidence": "medium",
                })
                break

        for pa in prot_atoms:
            pcoord = (pa[5], pa[6], pa[7])
            d = _distance(lcoord, pcoord)
            pres = pa[2]
            if d < 4.5 and pres in _RESIDUEHYDRO:
                hydrophobic.append({
                    "type": "hydrophobic",
                    "ligand_atom": la[1],
                    "protein_residue": pres,
                    "protein_atom": pa[1],
                    "protein_atom_name": pa[1],
                    "distance": round(d, 2),
                })
                break

    return {"hbonds": hbonds[:20], "hydrophobic": hydrophobic[:20], "pi_stacking": []}


def _summarize_pose_interactions(protein_pdb: str, output_pdbqt: str) -> list[dict]:
    """Per-pose interaction summary."""
    if not output_pdbqt:
        return []
    models: dict[int, list[str]] = {}
    current: int | None = None
    for line in output_pdbqt.splitlines():
        if line.startswith("MODEL"):
            parts = line.split()
            if len(parts) >= 2:
                current = int(parts[1])
                models[current] = []
        elif line.startswith("ENDMDL"):
            current = None
        elif current is not None:
            models.setdefault(current, []).append(line)

    summaries = []
    for mid in sorted(models.keys()):
        lig_pdb = "\n".join(l for l in models[mid] if l.startswith("HETATM")) + "\nEND"
        inter = _compute_interactions(protein_pdb, lig_pdb)
        summaries.append({
            "model": mid,
            "hbonds": len(inter.get("hbonds", [])),
            "hydrophobic": len(inter.get("hydrophobic", [])),
            "pi_stacking": len(inter.get("pi_stacking", [])),
        })
    return summaries


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@router.post("/run", response_model=DockingJobResponse)
async def create_docking_job(body: DockingJobCreate):
    supabase = get_client()
    _prune_old(supabase)

    import uuid, datetime
    job_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()

    # Fields that may or may not exist in Supabase — only INSERT guaranteed columns
    insert_row = {
        "id": job_id,
        "status": "queued",
        "protein_name": body.pdb_id or "custom",
        "protein_sequence": "",
        "ligand_smiles": body.smiles,
        "created_at": now,
        "updated_at": now,
    }
    supabase.table(_TABLE).insert(insert_row).execute()

    # Pass full params to the background worker (not stored in DB)
    worker_payload = {
        **insert_row,
        "pdb_id": body.pdb_id,
        "pdb_url": body.pdb_url,
        "grid_center": body.grid_center or [0, 0, 0],
        "grid_size": body.grid_size,
        "exhaustiveness": body.exhaustiveness,
        "num_modes": body.num_modes,
    }
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(loop.run_in_executor(None, _run_docking_sync, job_id, worker_payload))

    return DockingJobResponse(job_id=job_id, status="queued", result=None)


@router.get("/status/{job_id}", response_model=DockingJobResponse)
async def get_docking_job(job_id: str):
    supabase = get_client()
    result = supabase.table(_TABLE).select("*").eq("id", job_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Docking job not found")
    return DockingJobResponse(**_row_to_response(result.data))


@router.get("/result/{job_id}/pdb")
async def get_docking_pdb(job_id: str):
    supabase = get_client()
    result = supabase.table(_TABLE).select("result_sdf").eq("id", job_id).single().execute()
    if not result.data or not result.data.get("result_sdf"):
        raise HTTPException(status_code=404, detail="Docking result not found")
    try:
        data = json.loads(result.data["result_sdf"])
    except Exception:
        raise HTTPException(status_code=500, detail="Invalid result data")
    ligand_pdb = data.get("ligand_pdb", "")
    if not ligand_pdb:
        raise HTTPException(status_code=404, detail="No ligand PDB available")
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(ligand_pdb, media_type="text/plain")


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
    return {"jobs": [_row_to_response(r) for r in rows]}

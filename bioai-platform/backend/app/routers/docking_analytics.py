"""Advanced docking analytics independent of the durable docking worker."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.docking_pose_analytics import cluster_poses, water_mediated_interactions

router = APIRouter(prefix="/api/docking/analytics", tags=["docking-analytics"])


class PoseAnalyticsRequest(BaseModel):
    result_pdbqt: str = Field(..., min_length=1, description="Multi-model Vina output PDBQT")
    cluster_cutoff_angstrom: float = Field(2.0, ge=0.1, le=10.0)
    pdb_id: str | None = Field(None, min_length=4, max_length=16, description="Optional original PDB accession for crystallographic-water bridge screening")
    original_pdb_text: str | None = Field(None, description="Optional original unprepared PDB text; preferred for private structures")


async def _original_pdb(body: PoseAnalyticsRequest) -> str | None:
    if body.original_pdb_text:
        return body.original_pdb_text
    if not body.pdb_id:
        return None
    ident = body.pdb_id.strip().upper()
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.get(f"https://files.rcsb.org/download/{ident}.pdb")
    if response.status_code != 200 or "ATOM" not in response.text:
        raise HTTPException(404, f"Could not fetch original PDB for water analysis: {ident}")
    return response.text


@router.post("/poses")
async def docking_pose_analytics(body: PoseAnalyticsRequest):
    """Return pairwise pose RMSD, single-linkage clusters and optional water bridges."""
    clusters = cluster_poses(body.result_pdbqt, body.cluster_cutoff_angstrom)
    pdb_text = await _original_pdb(body)
    if pdb_text is None:
        water = {
            "status": "UNAVAILABLE",
            "reason": "Provide pdb_id or original_pdb_text to screen crystallographic water-mediated contacts.",
            "bridges": [],
        }
    else:
        water = water_mediated_interactions(pdb_text, body.result_pdbqt)
    return {
        "pose_clustering": clusters,
        "water_mediated_interactions": water,
        "scientific_boundary": {
            "pose_rmsd": "Atom-order coordinate-frame RMSD; not symmetry-corrected.",
            "water_bridges": "Distance-based geometric evidence; not an energetic or occupancy calculation.",
        },
    }

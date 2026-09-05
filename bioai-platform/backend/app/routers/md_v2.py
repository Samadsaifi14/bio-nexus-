"""Staged Molecular Dynamics pipeline router (MD v2).

Runs the auditable MD DAG and exposes topology-aware post-trajectory analytics.
The advanced analysis endpoint is deterministic and refuses to fabricate SASA,
hydrogen bonds or secondary structure when their required topology metadata is
not supplied.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.md.advanced_analysis import analyze_trajectory
from app.md.engines import engine_status
from app.md.orchestrator import STAGE_INTRO, build_md_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/md/v2", tags=["md-v2"])
SYNC_PRODUCTION_MAX_PS = 20.0


class AnalyzeRequest(BaseModel):
    pdb_id: str = Field(..., min_length=1, max_length=32, description="PDB ID or structure label")
    forcefield: Optional[str] = Field(default=None, pattern=r"^[a-z0-9_-]+$", description="Force field key from GET /api/md/forcefields")
    solvent: Optional[str] = Field(default=None, pattern=r"^(obc1|obc2|gbn2)$", description="Implicit solvent model")
    production_ps: Optional[float] = Field(default=None, ge=1, le=5000, description="Desired production length in ps")
    nvt_ps: Optional[float] = Field(default=None, ge=5, le=5000)
    pdb_text: Optional[str] = Field(default=None, description="Explicit PDB text for tests/offline use")


class TrajectoryAnalysisRequest(BaseModel):
    coordinates: list[list[list[float]]] = Field(..., description="Cartesian trajectory [frames][atoms][xyz], in angstrom")
    masses: list[float] | None = None
    atom_radii: list[float] | None = Field(default=None, description="van der Waals radii in angstrom; required for SASA")
    hydrogen_bond_triples: list[list[int]] | None = Field(default=None, description="[donor, hydrogen, acceptor] atom indices")
    secondary_structure_timeline: list[Any] | None = Field(default=None, description="Topology-aware DSSP/secondary-structure assignments if already computed")
    contact_cutoff: float = Field(default=8.0, gt=0, le=30)
    temperature_k: float = Field(default=300.0, gt=0, le=1000)
    pca_components: int = Field(default=3, ge=1, le=20)
    free_energy_bins: int = Field(default=30, ge=5, le=100)


@router.get("/stages")
def list_stages():
    pipe = build_md_pipeline()
    return {
        "pipeline": pipe.name,
        "version": pipe.version,
        "stages": [
            {"step": c.step, "tool": c.tool, "inputs": c.inputs, "outputs": c.outputs,
             "fail_blocks": c.fail_blocks, "expectation": STAGE_INTRO.get(c.step, "")}
            for c in pipe.stages
        ],
    }


@router.get("/engine")
def get_engine_status():
    return engine_status()


@router.post("/trajectory/analyze")
def advanced_trajectory_analysis(payload: TrajectoryAnalysisRequest):
    """Generate RMSD/RMSF/Rg/SASA/H-bonds/contact-map/DCCM/PCA/FEL outputs.

    SASA, hydrogen bonds and secondary-structure output are marked unavailable
    unless their required radii/topology assignments are supplied. Coordinates
    are Kabsch-aligned before fluctuation/correlation analyses.
    """
    try:
        return analyze_trajectory(
            payload.coordinates,
            masses=payload.masses,
            atom_radii=payload.atom_radii,
            hydrogen_bond_triples=payload.hydrogen_bond_triples,
            secondary_structure_timeline=payload.secondary_structure_timeline,
            contact_cutoff=payload.contact_cutoff,
            temperature_k=payload.temperature_k,
            pca_components=payload.pca_components,
            free_energy_bins=payload.free_energy_bins,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Advanced MD trajectory analysis failed")
        raise HTTPException(status_code=500, detail=f"trajectory analysis failed: {type(exc).__name__}: {exc}") from exc


@router.post("/analyze")
async def analyze(payload: AnalyzeRequest):
    if payload.pdb_text:
        pdb_text = payload.pdb_text
        pdb_id = payload.pdb_id
    else:
        try:
            from app.tools.structure_prep import fetch_pdb_text
            pdb_text = await fetch_pdb_text(payload.pdb_id)
            pdb_id = payload.pdb_id.upper()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"failed to fetch PDB {payload.pdb_id}: {exc}")

    if not pdb_text or "ATOM" not in pdb_text:
        raise HTTPException(status_code=400, detail="structure contains no ATOM records")

    requested_production_ps = payload.production_ps
    effective_production_ps = min(float(requested_production_ps), SYNC_PRODUCTION_MAX_PS) if requested_production_ps is not None else None
    production_was_capped = requested_production_ps is not None and effective_production_ps is not None and float(requested_production_ps) > effective_production_ps

    sample: dict = {"pdb_id": pdb_id, "pdb_text": pdb_text, "forcefield": payload.forcefield, "solvent": payload.solvent}
    if effective_production_ps is not None:
        sample["production_steps"] = int(effective_production_ps * 1000 / 2.0)
    if payload.nvt_ps:
        sample["nvt_steps"] = int(payload.nvt_ps * 1000 / 2.0)

    pipe = build_md_pipeline()
    try:
        report = await asyncio.to_thread(pipe.run, sample)
    except Exception as exc:
        logger.exception("MD v2 pipeline failed for %s", pdb_id)
        raise HTTPException(status_code=503, detail=f"MD engine failed before producing a scientific result: {type(exc).__name__}: {exc}") from exc

    warnings = report.setdefault("warnings", [])
    if production_was_capped:
        warnings.append(
            f"Requested production length {requested_production_ps:g} ps was capped to {effective_production_ps:g} ps for synchronous hosted execution. Use the durable MD workflow for longer trajectories."
        )

    return {
        "requested": {"pdb_id": pdb_id, "forcefield": payload.forcefield or "default (amber14)", "solvent": payload.solvent or "default (obc2)", "production_ps": requested_production_ps, "effective_production_ps": effective_production_ps, "production_capped": production_was_capped, "synchronous_limit_ps": SYNC_PRODUCTION_MAX_PS, "source": "provided-pdb-text" if payload.pdb_text else "rcsb"},
        "pipeline": report,
    }

"""Staged Molecular Dynamics pipeline router (MD v2) — self-contained.

Runs the 10-stage MD DAG in-process over a fetched PDB structure and returns the
full machine-auditable report (per-stage QC contract status + decision + metrics +
final readiness gate), on the same platform object model as the NGS v2 assay
pipeline. OpenMM is the primary engine; GROMACS availability is gated honestly.

This router intentionally does NOT touch the existing ``/api/md/run`` durable-job
endpoint or its ``docking_jobs`` table — it is a self-contained v2 upgrade.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.md.engines import engine_status
from app.md.orchestrator import STAGE_INTRO, build_md_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/md/v2", tags=["md-v2"])

# MD v2 currently runs inside one HTTP request. Keep explicit production requests
# inside the hosting/proxy budget instead of allowing a long OpenMM run to be
# terminated upstream as an opaque 502. Longer trajectories belong on the durable
# background-job MD endpoint/workflow.
SYNC_PRODUCTION_MAX_PS = 20.0


class AnalyzeRequest(BaseModel):
    pdb_id: str = Field(..., min_length=1, max_length=32, description="PDB ID or structure label")
    forcefield: Optional[str] = Field(
        default=None, pattern=r"^[a-z0-9_-]+$",
        description="Force field key from the verified menu (GET /api/md/forcefields)")
    solvent: Optional[str] = Field(
        default=None, pattern=r"^(obc1|obc2|gbn2)$",
        description="Implicit solvent model")
    production_ps: Optional[float] = Field(
        default=None, ge=1, le=5000,
        description="Desired production length in ps; synchronous v2 execution is capped to its hosting budget")
    nvt_ps: Optional[float] = Field(default=None, ge=5, le=5000)
    pdb_text: Optional[str] = Field(
        default=None,
        description="Explicit PDB text (used instead of an RCSB fetch; for tests/offline use)")


@router.get("/stages")
def list_stages():
    """Return the ordered stage contracts (names + human explanations) for the MD v2 DAG."""
    pipe = build_md_pipeline()
    return {
        "pipeline": pipe.name,
        "version": pipe.version,
        "stages": [
            {"step": c.step, "tool": c.tool, "inputs": c.inputs, "outputs": c.outputs,
             "fail_blocks": c.fail_blocks,
             "expectation": STAGE_INTRO.get(c.step, "")}
            for c in pipe.stages
        ],
    }


@router.get("/engine")
def get_engine_status():
    """Report MD engine availability + versions (OpenMM primary, GROMACS gated)."""
    return engine_status()


@router.post("/analyze")
async def analyze(payload: AnalyzeRequest):
    """Run the full in-process staged MD DAG over a structure and return the audit report."""
    from app.tools.structure_prep import fetch_pdb_text

    if payload.pdb_text:
        pdb_text = payload.pdb_text
        pdb_id = payload.pdb_id
    else:
        try:
            pdb_text = await fetch_pdb_text(payload.pdb_id)
            pdb_id = payload.pdb_id.upper()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"failed to fetch PDB {payload.pdb_id}: {exc}")

    if not pdb_text or "ATOM" not in pdb_text:
        raise HTTPException(status_code=400, detail="structure contains no ATOM records")

    requested_production_ps = payload.production_ps
    effective_production_ps = (
        min(float(requested_production_ps), SYNC_PRODUCTION_MAX_PS)
        if requested_production_ps is not None
        else None
    )
    production_was_capped = (
        requested_production_ps is not None
        and effective_production_ps is not None
        and float(requested_production_ps) > effective_production_ps
    )

    sample: dict = {
        "pdb_id": pdb_id,
        "pdb_text": pdb_text,
        "forcefield": payload.forcefield,
        "solvent": payload.solvent,
    }
    if effective_production_ps is not None:
        sample["production_steps"] = int(effective_production_ps * 1000 / 2.0)  # 2 fs timestep
    if payload.nvt_ps:
        sample["nvt_steps"] = int(payload.nvt_ps * 1000 / 2.0)

    pipe = build_md_pipeline()
    try:
        report = await asyncio.to_thread(pipe.run, sample)
    except Exception as exc:
        logger.exception("MD v2 pipeline failed for %s", pdb_id)
        raise HTTPException(
            status_code=503,
            detail=f"MD engine failed before producing a scientific result: {type(exc).__name__}: {exc}",
        ) from exc

    warnings = report.setdefault("warnings", [])
    if production_was_capped:
        warnings.append(
            f"Requested production length {requested_production_ps:g} ps was capped to "
            f"{effective_production_ps:g} ps for synchronous hosted execution. "
            "Use the durable MD workflow for longer trajectories."
        )

    return {
        "requested": {
            "pdb_id": pdb_id,
            "forcefield": payload.forcefield or "default (amber14)",
            "solvent": payload.solvent or "default (obc2)",
            "production_ps": requested_production_ps,
            "effective_production_ps": effective_production_ps,
            "production_capped": production_was_capped,
            "synchronous_limit_ps": SYNC_PRODUCTION_MAX_PS,
            "source": "provided-pdb-text" if payload.pdb_text else "rcsb",
        },
        "pipeline": report,
    }

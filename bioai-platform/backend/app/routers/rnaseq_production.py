"""Production RNA-seq planning and durable submission routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.models.responses import NgsProductionPlanResponse, NgsProductionSubmitResponse, NgsRnaSeqProductionPlanRequest
from app.ngs.execution import submit_run
from app.ngs.rnaseq_production import build_rnaseq_production_plan
from app.services.auth import require_user_id

router = APIRouter(prefix="/api/ngs/v2/rnaseq/production", tags=["ngs-v2-rnaseq-production"])


@router.post("/plan", response_model=NgsProductionPlanResponse)
def rnaseq_production_plan(payload: NgsRnaSeqProductionPlanRequest):
    """Build a pinned, non-shell nf-core/rnaseq execution contract."""
    return build_rnaseq_production_plan(payload)


@router.post("/submit", response_model=NgsProductionSubmitResponse)
def rnaseq_production_submit(payload: NgsRnaSeqProductionPlanRequest, user_id: str = Depends(require_user_id)):
    """Submit only plans that pass the fail-closed launch contract."""
    plan = build_rnaseq_production_plan(payload)
    if not plan["ready_to_launch"]:
        raise HTTPException(status_code=422, detail={"message": "RNA-seq production launch contract is blocked", "blockers": plan["blockers"]})
    executor = "awsbatch" if payload.execution_profile == "awsbatch" else "slurm" if payload.execution_profile == "slurm" else "local"
    try:
        run = submit_run(executor, plan["command_argv"], payload.outdir, user_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "run_id": run["run_id"],
        "state": "SUBMITTED",
        "executor": executor,
        "executor_job_id": run.get("executor_job_id"),
        "message": "Pinned nf-core/rnaseq run submitted. Scientific claims remain pending until execution artifacts, QC and provenance are imported and validated.",
    }

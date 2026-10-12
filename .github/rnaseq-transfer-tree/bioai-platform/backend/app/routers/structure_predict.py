"""Structure prediction endpoints â€” ESMFold via the public fold service."""

import asyncio
import logging
import threading
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.tools.structure_prep import esmfold_predict
from app.services import job_state
from app.services.de_novo import _mean_plddt_from_pdb  # single CA-only mean pLDDT source (per-residue)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/structure-predict", tags=["structure-predict"])

_JOB_KIND = "structure_predict"

# Live job state, mirrored to Supabase so a restart cannot erase a prediction the
# client is still polling. See app/services/job_state.py.
_jobs: dict[str, dict] = {}
_lock = threading.Lock()

VALID_AA = set("ACDEFGHIKLMNPQRSTVWYX")


def _patch(job_id: str, **kw) -> None:
    with _lock:
        job = _jobs.setdefault(job_id, {"status": "running"})
        job.update(kw)
        snapshot = dict(job)
    job_state.mirror(job_id, _JOB_KIND, snapshot)


def _reconcile() -> int:
    """Restore finished jobs and mark restart-interrupted ones. Called at startup."""
    def hydrate(job_id: str, state: dict) -> None:
        with _lock:
            if job_id not in _jobs:
                _jobs[job_id] = state

    return job_state.reconcile_on_startup(_JOB_KIND, hydrate)


class PredictRequest(BaseModel):
    sequence: str = Field(..., min_length=1, max_length=400, description="Protein sequence (max 400 residues)")
    job_title: str = Field(default="", max_length=200)


class PredictResponse(BaseModel):
    job_id: str
    status: str = "running"


class PredictStatusResponse(BaseModel):
    job_id: str
    status: str
    pdb: str | None = None
    mean_plddt: float | None = None
    ptm: float | None = None
    error: str | None = None


def _validate_sequence(seq: str) -> str:
    clean = seq.upper().replace("\n", "").replace("\r", "").replace(" ", "").replace("-", "")
    invalid = set(clean) - VALID_AA
    if invalid:
        raise ValueError(f"Invalid amino acid characters: {', '.join(sorted(invalid))}")
    if len(clean) < 10:
        raise ValueError("Sequence too short â€” minimum 10 residues")
    if len(clean) > 400:
        raise ValueError("Sequence too long â€” maximum 400 residues for ESMFold")
    return clean


@router.post("/predict", response_model=PredictResponse)
async def submit_prediction(body: PredictRequest):
    try:
        clean_seq = _validate_sequence(body.sequence)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    job_id = str(uuid.uuid4())
    _patch(job_id, status="running", pdb=None, mean_plddt=None, ptm=None, error=None)

    asyncio.create_task(_run_esmfold(job_id, clean_seq))
    return PredictResponse(job_id=job_id)


async def _run_esmfold(job_id: str, sequence: str):
    try:
        pdb_text = await esmfold_predict(sequence)
        if not pdb_text:
            _patch(
                job_id,
                status="failed",
                error="ESMFold service could not fold this sequence — try again shortly",
            )
            return

        # pLDDT lives in the B-factor column of ESMFold PDB output.
        # _mean_plddt_from_pdb (app.services.de_novo) reads CA atoms only, so the
        # mean is per-residue and identical across endpoints for the same model.
        _patch(
            job_id,
            status="complete",
            pdb=pdb_text,
            mean_plddt=_mean_plddt_from_pdb(pdb_text),
            ptm=None,
        )

        # AI interpretation (best-effort, never blocks)
        try:
            from app.ai.tool_interpreter import interpret_tool_result
            result_data = {"pdb_text": pdb_text, "sequence": sequence}
            ai_interp = await interpret_tool_result("structure_predict", result_data)
            if ai_interp:
                _patch(job_id, ai_interpretation=ai_interp)
        except Exception:
            pass

    except Exception as e:
        logger.exception("ESMFold prediction failed for job %s", job_id)
        _patch(job_id, status="failed", error=str(e))


@router.get("/status/{job_id}", response_model=PredictStatusResponse)
async def get_prediction_status(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
        job = dict(job) if job else None
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return PredictStatusResponse(job_id=job_id, **job)

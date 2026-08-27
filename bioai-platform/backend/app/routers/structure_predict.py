"""Structure prediction endpoints â€” ESMFold via the public fold service."""

import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.tools.structure_prep import esmfold_predict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/structure-predict", tags=["structure-predict"])

_jobs: dict[str, dict] = {}

VALID_AA = set("ACDEFGHIKLMNPQRSTVWYX")


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
    _jobs[job_id] = {"status": "running", "pdb": None, "mean_plddt": None, "ptm": None, "error": None}

    asyncio.create_task(_run_esmfold(job_id, clean_seq))
    return PredictResponse(job_id=job_id)


async def _run_esmfold(job_id: str, sequence: str):
    try:
        pdb_text = await esmfold_predict(sequence)
        if not pdb_text:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = "ESMFold service could not fold this sequence — try again shortly"
            return

        # pLDDT lives in the B-factor column of ESMFold PDB output.
        _jobs[job_id]["status"] = "complete"
        _jobs[job_id]["pdb"] = pdb_text
        _jobs[job_id]["mean_plddt"] = _mean_plddt_from_pdb(pdb_text)
        _jobs[job_id]["ptm"] = None

        # AI interpretation (best-effort, never blocks)
        try:
            from app.ai.tool_interpreter import interpret_tool_result
            result_data = {"pdb_text": pdb_text, "sequence": sequence}
            ai_interp = await interpret_tool_result("structure_predict", result_data)
            if ai_interp:
                _jobs[job_id]["ai_interpretation"] = ai_interp
        except Exception:
            pass

    except Exception as e:
        logger.exception("ESMFold prediction failed for job %s", job_id)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)


def _mean_plddt_from_pdb(pdb_text: str) -> float | None:
    """Mean pLDDT across ATOM records (B-factor column, cols 61-66)."""
    values: list[float] = []
    for line in pdb_text.splitlines():
        if line.startswith("ATOM"):
            try:
                values.append(float(line[60:66]))
            except ValueError:
                continue
    if not values:
        return None
    return round(sum(values) / len(values), 2)


@router.get("/status/{job_id}", response_model=PredictStatusResponse)
async def get_prediction_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return PredictStatusResponse(job_id=job_id, **job)

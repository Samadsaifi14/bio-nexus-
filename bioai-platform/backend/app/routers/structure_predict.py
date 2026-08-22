"""Structure prediction endpoints — ESMFold via Hugging Face Inference API."""

import asyncio
import logging
import re
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/structure-predict", tags=["structure-predict"])

_jobs: dict[str, dict] = {}

ESMFOLD_MODEL = "facebook/esmfold_v1"
HF_API_URL = f"https://api-inference.huggingface.co/models/{ESMFOLD_MODEL}"

VALID_AA = set("ACDEFGHIKLMNPQRSTVWYX")


class PredictRequest(BaseModel):
    sequence: str = Field(..., min_length=1, max_length=768, description="Protein sequence (max 768 residues)")
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
        raise ValueError("Sequence too short — minimum 10 residues")
    if len(clean) > 768:
        raise ValueError("Sequence too long — maximum 768 residues for ESMFold")
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
        async with httpx.AsyncClient(timeout=300) as client:
            hf_token = _get_hf_token()
            headers = {}
            if hf_token:
                headers["Authorization"] = f"Bearer {hf_token}"

            resp = await client.post(
                HF_API_URL,
                json={"inputs": sequence},
                headers=headers,
            )

            if resp.status_code == 503:
                data = resp.json()
                wait_time = data.get("estimated_time", 30)
                await asyncio.sleep(min(wait_time, 120))
                resp = await client.post(
                    HF_API_URL,
                    json={"inputs": sequence},
                    headers=headers,
                )

            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, dict) and "error" in data:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = data["error"]
                return

            pdb_text = data.get("pdb", "") if isinstance(data, dict) else str(data)
            mean_plddt = data.get("mean_plddt") if isinstance(data, dict) else None
            ptm = data.get("ptm") if isinstance(data, dict) else None

            if not pdb_text or len(pdb_text) < 50:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = "ESMFold returned empty or invalid PDB"
                return

            _jobs[job_id]["status"] = "complete"
            _jobs[job_id]["pdb"] = pdb_text
            _jobs[job_id]["mean_plddt"] = mean_plddt
            _jobs[job_id]["ptm"] = ptm

    except Exception as e:
        logger.exception("ESMFold prediction failed for job %s", job_id)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)


def _get_hf_token() -> str | None:
    import os
    return os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")


@router.get("/status/{job_id}", response_model=PredictStatusResponse)
async def get_prediction_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return PredictStatusResponse(job_id=job_id, **job)

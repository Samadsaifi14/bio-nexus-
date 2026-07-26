"""ADMET descriptor computation endpoints."""

from __future__ import annotations

import json
import os
import sys
import subprocess

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.services.auth import get_user_id

router = APIRouter(prefix="/api/admet", tags=["ADMET"])


class ADMETRequest(BaseModel):
    smiles: str = Field(..., min_length=1, max_length=500, description="SMILES string")


class ADMETResponse(BaseModel):
    job_id: str | None = None
    status: str = "complete"
    result: dict | None = None
    error: str | None = None


def _compute_in_subprocess(smiles: str) -> dict:
    """Run RDKit computation in an isolated subprocess to prevent segfaults."""
    import tempfile
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(
            'import json, sys, os\n'
            f'sys.path.insert(0, {backend_dir!r})\n'
            'from app.tools.admet import compute_descriptors\n'
            f'result = compute_descriptors({smiles!r})\n'
            'print(json.dumps(result))\n'
        )
        script_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            err = result.stderr.strip()[-500:] if result.stderr else "unknown error"
            if "Invalid SMILES" in err or "ValueError" in err:
                raise ValueError(f"Invalid SMILES: {smiles}")
            raise RuntimeError(f"RDKit subprocess failed: {err}")
        return json.loads(result.stdout)
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


@router.post("/descriptors", response_model=ADMETResponse)
async def compute_descriptors(body: ADMETRequest, user_id: str | None = Depends(get_user_id)):
    """Compute molecular descriptors from SMILES using RDKit.

    Returns Lipinski/Veber compliance, QED score, and key properties.
    """
    try:
        from app.tools.admet import compute_descriptors as _compute
        if os.name == "nt":
            result = _compute_in_subprocess(body.smiles)
        else:
            result = _compute(body.smiles)
        return ADMETResponse(result=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Descriptor computation failed: {e}")

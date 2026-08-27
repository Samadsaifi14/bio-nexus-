"""ADMET descriptor computation endpoints."""

from __future__ import annotations

import json
import os
import sys
import subprocess

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from app.services.auth import get_user_id

router = APIRouter(prefix="/api/admet", tags=["ADMET"])


class ADMETRequest(BaseModel):
    smiles: str | None = Field(None, min_length=1, max_length=500, description="SMILES string")
    name: str | None = Field(None, min_length=1, max_length=200, description="Chemical name (resolved via PubChem)")
    cid: int | None = Field(None, ge=1, description="PubChem compound CID")

    @model_validator(mode="after")
    def _require_one(self) -> "ADMETRequest":
        if not any([self.smiles, self.name, self.cid]):
            raise ValueError("Provide one of: smiles, name, or cid")
        return self


class ADMETResponse(BaseModel):
    job_id: str | None = None
    status: str = "complete"
    result: dict | None = None
    error: str | None = None


class ProToxRequest(BaseModel):
    smiles: str | None = Field(None, min_length=1, max_length=500, description="SMILES string")
    name: str | None = Field(None, min_length=1, max_length=200, description="Chemical name (resolved via PubChem)")
    models: str | None = Field(None, min_length=1, max_length=400, description="Space-separated ProTox model shorthands")

    @model_validator(mode="after")
    def _require_one(self) -> "ProToxRequest":
        if not any([self.smiles, self.name]):
            raise ValueError("Provide one of: smiles or name")
        return self


class SearchHit(BaseModel):
    cid: int
    name: str
    formula: str | None = None
    smiles: str | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHit]


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


async def _resolve_input(body: ADMETRequest) -> tuple[str, str | None, int | None]:
    """Resolve the request to (smiles, chemical_name, cid)."""
    from app.tools.pubchem import cid_to_record, name_to_cid, PubChemError

    if body.smiles:
        return body.smiles.strip(), None, None

    if body.cid:
        try:
            rec = await cid_to_record(body.cid)
        except PubChemError as e:
            raise HTTPException(status_code=404, detail=str(e))
        if not rec.get("smiles"):
            raise HTTPException(status_code=404, detail="PubChem has no SMILES for this CID")
        return rec["smiles"], rec.get("name"), rec["cid"]

    # name given: resolve name -> CID -> SMILES
    try:
        cid = await name_to_cid(body.name or "")
    except PubChemError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not cid:
        raise HTTPException(status_code=404, detail=f"'{body.name}' not found in PubChem")
    try:
        rec = await cid_to_record(cid)
    except PubChemError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not rec.get("smiles"):
        raise HTTPException(status_code=404, detail="PubChem has no SMILES for this compound")
    return rec["smiles"], rec.get("name") or body.name, rec["cid"]


@router.post("/descriptors", response_model=ADMETResponse)
async def compute_descriptors(body: ADMETRequest, user_id: str | None = Depends(get_user_id)):
    """Compute molecular descriptors from SMILES / chemical name / PubChem CID.

    Returns Lipinski/Veber compliance, QED score, and key properties.
    """
    try:
        from app.tools.admet import compute_descriptors as _compute
        smiles, chemical_name, cid = await _resolve_input(body)
        if os.name == "nt":
            result = _compute_in_subprocess(smiles)
        else:
            result = _compute(smiles)
        if chemical_name:
            result["chemical_name"] = chemical_name
        if cid is not None:
            result["pubchem_cid"] = cid

        # AI interpretation (best-effort, never blocks)
        try:
            from app.ai.tool_interpreter import interpret_tool_result
            ai_interp = await interpret_tool_result("admet", result)
            if ai_interp:
                result["ai_interpretation"] = ai_interp
        except Exception:
            pass

        return ADMETResponse(result=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Descriptor computation failed: {e}")


@router.get("/search", response_model=SearchResponse)
async def search_compounds(
    q: str = Query(..., min_length=2, max_length=200, description="Name fragment"),
    limit: int = Query(10, ge=1, le=25),
    user_id: str | None = Depends(get_user_id),
):
    """PubChem autocomplete for chemical name search."""
    from app.tools.pubchem import search_suggestions
    hits = await search_suggestions(q, limit)
    return SearchResponse(query=q, results=hits)


@router.post("/protox", response_model=ADMETResponse)
async def predict_toxicity(body: ProToxRequest, user_id: str | None = Depends(get_user_id)):
    """ProTox 3.0 ML-based toxicity prediction (Charité).

    Queries the ProTox server for acute toxicity, toxicity targets and
    optional additional models (organ toxicity, Tox21 pathways, CYPs…).
    The upstream server queues requests, so a run can take up to ~5 minutes.
    """
    try:
        from app.tools.protox import predict_toxicity as _protox, ProToxError

        smiles, chemical_name, cid = await _resolve_input(
            ADMETRequest(smiles=body.smiles, name=body.name, cid=None)
        )
        result = await _protox(
            smiles=smiles,
            name=chemical_name or None,
            models=body.models,
        )
        result["chemical_name"] = chemical_name or body.name
        if cid is not None:
            result["pubchem_cid"] = cid
        return ADMETResponse(result=result)
    except ProToxError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ProTox prediction failed: {e}")

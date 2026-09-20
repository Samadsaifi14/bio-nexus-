"""Pocket and cavity analysis with explicit method provenance.

The historical route name is retained for compatibility, but results distinguish
CASTp, fpocket and the BioNexus exploratory SASA heuristic. A failure of one
method never silently substitutes another method's values.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.science.result import build_scientific_result, failed_scientific_result
from app.services.identifier_resolution import is_uniprot_accession, resolve_to_uniprot
from app.tools.castp import PocketAnalysisError, analyze_pockets_pdb_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/castp", tags=["Pocket & Cavity Analysis"])

_PDB_ID_RE = re.compile(r"^[A-Za-z0-9]{4}$")
_AA_ALPHABET = set("ACDEFGHIKLMNPQRSTVWY")


class CastpRequest(BaseModel):
    pdb_id: str = Field(default="", description="PDB ID, UniProt accession, gene name, or raw protein sequence")
    sequence: str = Field(default="", description="Raw amino-acid sequence")
    pdb_text: str = Field(default="", description="Raw PDB text")
    probe_radius: float = Field(default=1.4, ge=0.1, le=5.0)
    method: str = Field(default="fpocket", description="CASTp|fpocket|sasa_heuristic")


def _looks_like_sequence(value: str) -> bool:
    seq = "".join((value or "").split()).replace("-", "").replace(".", "")
    return len(seq) >= 15 and all(char in _AA_ALPHABET for char in seq.upper())


async def _fetch_pdb_rcsb(pdb_id: str) -> str:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.get(f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb")
        if response.status_code != 200:
            raise RuntimeError(f"PDB {pdb_id.upper()} not found on RCSB")
        return response.text


async def _fetch_uniprot(accession: str) -> dict[str, Any]:
    from app.tools.uniprot import UniprotTool

    payload = await UniprotTool().run({"accession": accession})
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    return payload


async def _esmfold(seq: str) -> str:
    from app.tools.structure_prep import esmfold_predict

    if len(seq) < 10:
        raise HTTPException(status_code=400, detail="Sequence too short (minimum 10 residues)")
    if len(seq) > 400:
        raise HTTPException(status_code=400, detail="Sequence too long for the hosted ESMFold route (maximum 400 residues)")
    predicted = await esmfold_predict(seq)
    if not predicted:
        raise HTTPException(status_code=502, detail="ESMFold did not return a valid structure")
    return predicted


async def _resolve_structure(body: CastpRequest) -> dict[str, Any]:
    provenance: list[dict[str, str]] = []
    uniprot: dict[str, Any] | None = None

    if body.pdb_text.strip():
        return {
            "pdb_text": body.pdb_text.strip(),
            "pdb_id": "custom",
            "structure_source": "uploaded_pdb_text",
            "sequence_source": "uploaded_pdb_text",
            "embed_pdb": True,
            "uniprot": None,
            "pipeline": [{"step": "input", "status": "ok", "detail": "Using uploaded PDB text"}],
        }

    raw_sequence = body.sequence.strip() or (body.pdb_id.strip() if _looks_like_sequence(body.pdb_id) else "")
    if raw_sequence:
        seq = "".join(raw_sequence.split()).replace("-", "").replace(".", "").upper()
        if any(char not in _AA_ALPHABET for char in seq):
            raise HTTPException(status_code=400, detail="Protein sequence contains unsupported characters")
        provenance.append({"step": "sequence", "status": "ok", "detail": f"Received {len(seq)} amino-acid residues"})
        pdb_text = await _esmfold(seq)
        provenance.append({"step": "structure", "status": "ok", "detail": "Generated a computational ESMFold structure for pocket analysis"})
        return {
            "pdb_text": pdb_text,
            "pdb_id": "predicted",
            "structure_source": "ESMFold computational prediction",
            "sequence_source": "user sequence",
            "embed_pdb": True,
            "uniprot": None,
            "pipeline": provenance,
        }

    identifier = body.pdb_id.strip()
    if not identifier:
        raise HTTPException(status_code=400, detail="Provide pdb_id, sequence, or pdb_text")

    if _PDB_ID_RE.match(identifier):
        try:
            pdb_text = await _fetch_pdb_rcsb(identifier)
            provenance.append({"step": "structure", "status": "ok", "detail": f"Retrieved experimental PDB entry {identifier.upper()} from RCSB"})
            return {
                "pdb_text": pdb_text,
                "pdb_id": identifier.upper(),
                "structure_source": "RCSB PDB experimental structure",
                "sequence_source": "RCSB PDB",
                "embed_pdb": False,
                "uniprot": None,
                "pipeline": provenance,
            }
        except Exception as exc:
            provenance.append({"step": "structure", "status": "skip", "detail": f"RCSB lookup failed: {type(exc).__name__}"})

    resolved = await resolve_to_uniprot(accession=identifier)
    if resolved.get("status") != "resolved" or not resolved.get("accession"):
        raise HTTPException(status_code=404, detail=f"Could not resolve {identifier!r} to an experimental structure or UniProt accession")

    accession = str(resolved["accession"])
    provenance.append({"step": "uniprot", "status": "ok", "detail": f"Resolved {identifier} to UniProt {accession}"})
    try:
        data = await _fetch_uniprot(accession)
        uniprot = {
            "accession": data.get("accession", accession),
            "name": data.get("full_name", ""),
            "organism": data.get("organism", ""),
            "gene_names": data.get("gene_names", []) or [],
            "sequence_length": data.get("sequence_length", 0),
        }
        pdb_ids = data.get("pdb_ids") or []
        if pdb_ids:
            pdb_id = str(pdb_ids[0]).upper()
            pdb_text = await _fetch_pdb_rcsb(pdb_id)
            provenance.append({"step": "structure", "status": "ok", "detail": f"Retrieved UniProt-linked experimental structure {pdb_id}"})
            return {
                "pdb_text": pdb_text,
                "pdb_id": pdb_id,
                "structure_source": "UniProt-linked RCSB PDB experimental structure",
                "sequence_source": f"UniProt {accession}",
                "embed_pdb": False,
                "uniprot": uniprot,
                "pipeline": provenance,
            }
        seq = str(data.get("sequence") or "").strip().upper()
        if not seq:
            raise RuntimeError("UniProt record did not contain a sequence")
        pdb_text = await _esmfold(seq)
        provenance.append({"step": "structure", "status": "ok", "detail": "No linked experimental structure; generated a computational ESMFold structure"})
        return {
            "pdb_text": pdb_text,
            "pdb_id": "predicted",
            "structure_source": "ESMFold computational prediction",
            "sequence_source": f"UniProt {accession}",
            "embed_pdb": True,
            "uniprot": uniprot,
            "pipeline": provenance,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not resolve a structure for {identifier}: {type(exc).__name__}: {exc}")


def _method_label(method: str) -> str:
    key = method.strip().lower().replace("-", "_")
    if key in {"castp", "castp3"}:
        return "CASTp"
    if key in {"fpocket", "f_pocket"}:
        return "fpocket"
    if key in {"heuristic", "sasa", "sasa_heuristic", "bionexus_heuristic"}:
        return "BioNexus exploratory SASA heuristic"
    raise HTTPException(status_code=400, detail="method must be one of CASTp, fpocket, or sasa_heuristic")


@router.post("/analyze")
async def analyze_pockets(body: CastpRequest):
    requested_method = _method_label(body.method)
    resolved = await _resolve_structure(body)
    pdb_text = resolved["pdb_text"]
    input_payload = {
        "pdb_id": resolved["pdb_id"],
        "structure_source": resolved["structure_source"],
        "requested_method": requested_method,
        "probe_radius": body.probe_radius,
        "pdb_text": pdb_text,
    }

    try:
        method_result = await analyze_pockets_pdb_text(
            pdb_text,
            resolved["pdb_id"],
            body.probe_radius,
            method=body.method,
        )
    except PocketAnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    method_status = str(method_result.get("status") or "FAILED")
    engine_version = str(method_result.get("engine_version") or "unknown")
    validation = dict(method_result.get("validation") or {})
    validation.update({
        "requested_method": requested_method,
        "executed_method": method_result.get("method", requested_method),
        "cross_method_substitution": False,
        "structure_evidence": "experimental" if "experimental" in resolved["structure_source"].lower() else "computational" if "esmfold" in resolved["structure_source"].lower() else "uploaded",
    })

    results = {
        "pdb_id": method_result.get("pdb_id", resolved["pdb_id"]),
        "probe_radius": method_result.get("probe_radius", body.probe_radius),
        "total_residues": method_result.get("total_residues", 0),
        "pockets": method_result.get("pockets", []),
        "sequence_source": resolved["sequence_source"],
        "structure_source": resolved["structure_source"],
        "structure_pdb": pdb_text if resolved["embed_pdb"] else "",
        "pipeline": [*resolved["pipeline"], {
            "step": "pocket_analysis",
            "status": "ok" if method_status == "VALID" else "error",
            "detail": f"Requested {requested_method}; executed {method_result.get('method', requested_method)}; status {method_status}",
        }],
        "uniprot": resolved["uniprot"],
        "chains": method_result.get("chains", []),
        "active_sites": [],
    }

    if method_status == "FAILED":
        failed = failed_scientific_result(
            method=requested_method,
            engine=requested_method if requested_method != "BioNexus exploratory SASA heuristic" else "Biopython ShrakeRupley + BioNexus heuristic",
            engine_version=engine_version,
            input_payload=input_payload,
            reason=str(validation.get("reason") or f"{requested_method} failed"),
            parameters={"probe_radius_angstrom": body.probe_radius, "requested_method": requested_method},
            validation=validation,
        )
        failed["results"] = results
        return failed

    scientific = build_scientific_result(
        status=method_status,
        method=str(method_result.get("method") or requested_method),
        engine=str(method_result.get("method") or requested_method),
        engine_version=engine_version,
        input_payload=input_payload,
        parameters={"probe_radius_angstrom": body.probe_radius, "requested_method": requested_method},
        fallback_used=bool(method_result.get("fallback_used", False)),
        fallback_method=method_result.get("fallback_method"),
        results=results,
        evidence_class=str(method_result.get("evidence_class") or "Deterministic computation"),
        validation=validation,
        citations=[
            {"label": "fpocket", "url": "https://github.com/Discngine/fpocket"}
            if str(method_result.get("method")) == "fpocket"
            else {"label": "Biopython", "url": "https://biopython.org/"}
        ],
    )
    return scientific

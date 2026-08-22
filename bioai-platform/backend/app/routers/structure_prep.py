"""Structure preparation pipeline endpoints.

Pipeline: fetch → broken chain detection → SWISS-MODEL repair → PyMOL cleanup → fpocket → CASTp
"""

import asyncio
import logging
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/structure-prep", tags=["structure-prep"])

# In-memory job store (like docking pattern)
_jobs: dict[str, dict] = {}


class PipelineRequest(BaseModel):
    pdb_id: str = Field(default="", description="4-char PDB ID (mutually exclusive with sequence)")
    uniprot_accession: str = Field(default="", description="UniProt accession — will fetch best structure")
    sequence: str = Field(default="", description="Amino acid sequence for SWISS-MODEL repair")
    probe_radius: float = Field(default=1.4, ge=0.5, le=5.0)
    skip_repair: bool = Field(default=False, description="Skip SWISS-MODEL repair even if broken")
    skip_castp: bool = Field(default=False, description="Skip remote CASTp (run fpocket only)")


class ChainHealthResult(BaseModel):
    has_missing_residues: bool
    missing_residue_count: int
    missing_ranges: list[str]
    has_chain_breaks: bool
    chain_break_count: int
    chain_breaks: list[dict]
    is_broken: bool
    chains: list[str]
    total_residues: int


class FpocketPocket(BaseModel):
    id: int
    druggability_score: float
    volume: float
    area: float
    score: float
    num_residues: int


class PipelineStatusResponse(BaseModel):
    job_id: str
    status: str
    step: str = ""
    chain_health: ChainHealthResult | None = None
    fpocket_pockets: list[FpocketPocket] = []
    castp_pockets: list[dict[str, Any]] = []
    cleaned_pdb: str = ""
    error: str | None = None


@router.post("/run")
async def run_pipeline(body: PipelineRequest):
    import uuid
    job_id = str(uuid.uuid4())

    pdb_id = body.pdb_id.strip().upper()
    if not pdb_id and not body.uniprot_accession and not body.sequence:
        raise HTTPException(status_code=400, detail="Provide pdb_id, uniprot_accession, or sequence")

    _jobs[job_id] = {
        "status": "running",
        "step": "fetching",
        "chain_health": None,
        "fpocket_pockets": [],
        "castp_pockets": [],
        "cleaned_pdb": "",
        "error": None,
    }

    asyncio.create_task(_run_pipeline(job_id, body))
    return {"job_id": job_id, "status": "running"}


@router.get("/status/{job_id}", response_model=PipelineStatusResponse)
async def get_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return PipelineStatusResponse(job_id=job_id, **job)


async def _run_pipeline(job_id: str, body: PipelineRequest):
    from app.tools.structure_prep import (
        detect_chain_health, pymol_cleanup, run_fpocket,
        castp_submit, castp_poll, fetch_pdb_text,
        swissmodel_fetch_structures, swissmodel_fetch_pdb,
    )

    try:
        # ── Step 1: Fetch structure ────────────────────────────────────
        _jobs[job_id]["step"] = "fetching"
        pdb_text = None

        if body.pdb_id:
            pdb_text = await fetch_pdb_text(body.pdb_id)
        elif body.uniprot_accession:
            smr = await swissmodel_fetch_structures(body.uniprot_accession)
            # Try experimental first, then homology models
            for s in smr.get("experimental", []) + smr.get("models", []):
                if s.get("coordinates_url"):
                    pdb_text = await swissmodel_fetch_pdb(s["template"])
                    if pdb_text:
                        break
            if not pdb_text:
                # Fall back to RCSB using first experimental template
                if smr.get("experimental"):
                    template = smr["experimental"][0].get("template", "")
                    if template:
                        pdb_text = await fetch_pdb_text(template)
        elif body.sequence:
            # For raw sequences, generate a minimal PDB placeholder
            # The real use case is: user provides sequence → SWISS-MODEL builds model
            pdb_text = _make_sequence_pdb(body.sequence)

        if not pdb_text:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = "Could not fetch/build structure"
            return

        # ── Step 2: Detect broken chains ───────────────────────────────
        _jobs[job_id]["step"] = "analyzing"
        health = detect_chain_health(pdb_text)
        _jobs[job_id]["chain_health"] = {
            "has_missing_residues": health.has_missing_residues,
            "missing_residue_count": health.missing_residue_count,
            "missing_ranges": health.missing_ranges[:50],
            "has_chain_breaks": health.has_chain_breaks,
            "chain_break_count": health.chain_break_count,
            "chain_breaks": health.chain_breaks[:20],
            "is_broken": health.is_broken,
            "chains": health.chains,
            "total_residues": health.total_residues,
        }

        # ── Step 3: SWISS-MODEL repair if broken ──────────────────────
        if health.is_broken and not body.skip_repair and body.uniprot_accession:
            _jobs[job_id]["step"] = "repairing"
            try:
                smr = await swissmodel_fetch_structures(body.uniprot_accession)
                for s in smr.get("experimental", []) + smr.get("models", []):
                    if s.get("coordinates_url") and s.get("coverage", 0) > 0.8:
                        repaired = await swissmodel_fetch_pdb(s["template"])
                        if repaired and len(repaired) > len(pdb_text) * 0.5:
                            pdb_text = repaired
                            # Re-check after repair
                            health = detect_chain_health(pdb_text)
                            _jobs[job_id]["chain_health"] = {
                                "has_missing_residues": health.has_missing_residues,
                                "missing_residue_count": health.missing_residue_count,
                                "missing_ranges": health.missing_ranges[:50],
                                "has_chain_breaks": health.has_chain_breaks,
                                "chain_break_count": health.chain_break_count,
                                "chain_breaks": health.chain_breaks[:20],
                                "is_broken": health.is_broken,
                                "chains": health.chains,
                                "total_residues": health.total_residues,
                            }
                            break
            except Exception as e:
                logger.warning("SWISS-MODEL repair failed: %s", e)

        # ── Step 4: PyMOL cleanup ─────────────────────────────────────
        _jobs[job_id]["step"] = "cleaning"
        cleaned = pymol_cleanup(pdb_text)

        # ── Step 5: fpocket (local, instant) ──────────────────────────
        _jobs[job_id]["step"] = "running_fpocket"
        fpocket_result = run_fpocket(cleaned, body.probe_radius)
        _jobs[job_id]["fpocket_pockets"] = fpocket_result.pockets

        # ── Step 6: CASTp (remote, async) ─────────────────────────────
        if not body.skip_castp:
            _jobs[job_id]["step"] = "running_castp"
            try:
                castp_sub = await castp_submit(cleaned, body.probe_radius)
                if castp_sub.get("job_id"):
                    # Poll for results
                    for _ in range(30):
                        await asyncio.sleep(3)
                        castp_res = await castp_poll(castp_sub["job_id"])
                        if castp_res.get("status") == "complete":
                            _jobs[job_id]["castp_pockets"] = castp_res.get("pockets", [])
                            break
            except Exception as e:
                logger.warning("CASTp job failed: %s", e)

        _jobs[job_id]["step"] = "complete"
        _jobs[job_id]["status"] = "complete"
        _jobs[job_id]["cleaned_pdb"] = cleaned[:50000]

    except Exception as e:
        logger.exception("Pipeline failed for job %s", job_id)
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)


def _make_sequence_pdb(sequence: str) -> str:
    """Generate a minimal PDB with CA atoms for a raw sequence (for visualization)."""
    lines = ["HEADER    SEQUENCE MODEL"]
    for i, aa in enumerate(sequence, 1):
        lines.append(
            f"ATOM  {i:5d}  CA  {aa.upper():3s} A{i:4d}    "
            f"  {0.0:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00  0.00           C"
        )
    lines.append("END")
    return "\n".join(lines)

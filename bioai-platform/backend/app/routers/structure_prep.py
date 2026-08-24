"""Structure preparation pipeline endpoints.

Pipeline: fetch → broken chain detection → SWISS-MODEL repair → cleanup → fpocket → CASTp

Jobs persist to the `structure_prep_jobs` Supabase table (same pattern as
docking_jobs/sequencing_jobs) so state survives restarts and reads are
scoped to the owning user.
"""

import asyncio
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.services.auth import require_user_id
from app.services.supabase import get_supabase
from app.tools.structure_prep import validate_pdb_id, validate_template, validate_uniprot_accession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/structure-prep", tags=["structure-prep"])

_TABLE = "structure_prep_jobs"

# Strong refs so in-flight pipeline tasks are never garbage-collected mid-run.
_TASKS: set[asyncio.Task] = set()

# A running job with no update for this long is dead (restart killed the task,
# or a step hung) — the status endpoint fails it instead of spinning forever.
_STALE_AFTER = timedelta(minutes=20)

# Protein alphabet incl. ambiguity codes; validated before any network call (A4).
_AA_RE = re.compile(r"^[ACDEFGHIKLMNPQRSTVWYBXZUJ]+$")


class PipelineRequest(BaseModel):
    pdb_id: str = Field(default="", description="4-char PDB ID (mutually exclusive with sequence)")
    uniprot_accession: str = Field(default="", description="UniProt accession — will fetch best structure")
    sequence: str = Field(default="", description="Amino acid sequence for de novo prediction")
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
    # Explicit integrity/outcome tags — never silently degraded:
    chain_integrity: str = "unknown"   # intact | repaired | broken_unrepaired | unknown
    castp_status: str = "pending"      # pending | skipped | running | complete | timed_out | error
    fpocket_status: str = "pending"    # pending | running | complete | unavailable | error
    cleaned_pdb: str = ""
    error: str | None = None


def _validate_request(body: PipelineRequest) -> PipelineRequest:
    """Reject malformed identifiers before any job creation or network call (A4)."""
    inputs = [body.pdb_id.strip(), body.uniprot_accession.strip(), body.sequence.strip()]
    n_inputs = sum(1 for v in inputs if v)
    if n_inputs == 0:
        raise HTTPException(status_code=400, detail="Provide pdb_id, uniprot_accession, or sequence")
    if n_inputs > 1:
        raise HTTPException(status_code=400, detail="Provide only one of pdb_id, uniprot_accession, or sequence")

    try:
        if body.pdb_id.strip():
            body.pdb_id = validate_pdb_id(body.pdb_id)
        if body.uniprot_accession.strip():
            body.uniprot_accession = validate_uniprot_accession(body.uniprot_accession)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if body.sequence.strip():
        seq = body.sequence.strip().upper().replace("\n", "").replace(" ", "").replace("-", "")
        if len(seq) < 10 or len(seq) > 400:
            raise HTTPException(status_code=400, detail=f"Sequence must be 10–400 residues (got {len(seq)})")
        if not _AA_RE.match(seq):
            raise HTTPException(status_code=400, detail="Sequence contains non-amino-acid characters")
        body.sequence = seq

    return body


@router.post("/run")
async def run_pipeline(body: PipelineRequest, user_id: str = Depends(require_user_id)):
    body = _validate_request(body)

    supabase = get_supabase()
    job_id = str(uuid.uuid4())
    supabase.table(_TABLE).insert({
        "id": job_id,
        "user_id": user_id,
        "status": "running",
        "step": "fetching",
        "payload": {
            "pdb_id": body.pdb_id,
            "uniprot_accession": body.uniprot_accession,
            "probe_radius": body.probe_radius,
            "skip_repair": body.skip_repair,
            "skip_castp": body.skip_castp,
        },
    }).execute()

    task = asyncio.create_task(_run_pipeline(job_id, body))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return {"job_id": job_id, "status": "running"}


@router.get("/status/{job_id}", response_model=PipelineStatusResponse)
async def get_status(job_id: str, user_id: str = Depends(require_user_id)):
    res = (
        get_supabase()
        .table(_TABLE)
        .select("*")
        .eq("id", job_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Job not found")
    row = res.data

    # Watchdog: a "running" row that hasn't been touched in a while means its
    # task died (restart/hang). Fail it so clients stop polling an eternal
    # spinner. updated_at is written on every step change by _update_job.
    if row.get("status") == "running":
        ts = _parse_ts(row.get("updated_at")) or _parse_ts(row.get("created_at"))
        if ts and datetime.now(timezone.utc) - ts > _STALE_AFTER:
            message = "Job stalled or was interrupted by a server restart — please re-run"
            try:
                _update_job(get_supabase(), job_id, status="failed", error=message)
            except Exception:
                logger.exception("Could not persist stale-fail for job %s", job_id)
            row = {**row, "status": "failed", "error": message}

    return _row_to_response(job_id, row)


def _parse_ts(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _row_to_response(job_id: str, row: dict) -> PipelineStatusResponse:
    result = row.get("result") or {}
    return PipelineStatusResponse(
        job_id=job_id,
        status=row.get("status", "running"),
        step=row.get("step", ""),
        chain_health=result.get("chain_health"),
        fpocket_pockets=result.get("fpocket_pockets", []),
        castp_pockets=result.get("castp_pockets", []),
        chain_integrity=row.get("chain_integrity", "unknown"),
        castp_status=row.get("castp_status", "pending"),
        fpocket_status=row.get("fpocket_status", "pending"),
        cleaned_pdb=result.get("cleaned_pdb", ""),
        error=row.get("error"),
    )


def _chain_health_dict(health) -> dict:
    return {
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


def _update_job(supabase, job_id: str, **fields) -> None:
    # MUST stay a plain sync function: every call site relies on the update
    # executing immediately. (It was once `async def` called without `await`,
    # so no write ever ran and jobs sat in "running" forever.)
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    supabase.table(_TABLE).update(fields).eq("id", job_id).execute()


def _fail(supabase, job_id: str, message: str) -> None:
    logger.error("Structure prep job %s failed: %s", job_id, message)
    try:
        _update_job(supabase, job_id, status="failed", error=message)
    except Exception:
        logger.exception("Could not persist failure state for job %s", job_id)


async def _run_pipeline(job_id: str, body: PipelineRequest) -> None:
    from app.tools.structure_prep import (
        detect_chain_health, pymol_cleanup, run_fpocket,
        castp_submit, castp_poll, fetch_pdb_text,
        swissmodel_fetch_structures, swissmodel_fetch_pdb,
        esmfold_predict, _biopython_cleanup, FpocketResult,
    )

    supabase = get_supabase()

    # Everything that lands in the result jsonb, written progressively.
    result_fields: dict[str, Any] = {}

    try:
        # ── Step 1: Fetch/predict structure ───────────────────────────
        _update_job(supabase, job_id, step="fetching")
        pdb_text = None

        if body.pdb_id:
            pdb_text = await fetch_pdb_text(body.pdb_id)
        elif body.uniprot_accession:
            smr = await swissmodel_fetch_structures(body.uniprot_accession)
            for s in smr.get("experimental", []) + smr.get("models", []):
                if s.get("coordinates_url"):
                    pdb_text = await swissmodel_fetch_pdb(s["template"])
                    if pdb_text:
                        break
            if not pdb_text and smr.get("experimental"):
                template = smr["experimental"][0].get("template", "")
                if template:
                    pdb_text = await fetch_pdb_text(template)
        elif body.sequence:
            _update_job(supabase, job_id, step="predicting_structure")
            pdb_text = await esmfold_predict(body.sequence)
            if not pdb_text:
                _fail(supabase, job_id, "ESMFold could not predict a structure for this sequence")
                return

        if not pdb_text:
            _fail(supabase, job_id, "Could not fetch/build structure")
            return

        # ── Step 2: Detect broken chains ──────────────────────────────
        _update_job(supabase, job_id, step="analyzing")
        health = await asyncio.to_thread(detect_chain_health, pdb_text)
        result_fields["chain_health"] = _chain_health_dict(health)
        _update_job(supabase, job_id, result=result_fields)

        # ── Step 3: SWISS-MODEL repair if broken ─────────────────────
        # Repair requires an accession AND a >80%-coverage template. When it
        # can't run or doesn't help, the run proceeds but is tagged
        # broken_unrepaired so downstream consumers discount it (A3).
        chain_integrity = "intact"
        if health.is_broken:
            chain_integrity = "broken_unrepaired"
            _update_job(supabase, job_id, chain_integrity=chain_integrity)
            if not body.skip_repair and body.uniprot_accession:
                _update_job(supabase, job_id, step="repairing")
                try:
                    smr = await swissmodel_fetch_structures(body.uniprot_accession)
                    for s in smr.get("experimental", []) + smr.get("models", []):
                        if s.get("coordinates_url") and s.get("coverage", 0) > 0.8:
                            repaired = await swissmodel_fetch_pdb(s["template"])
                            if repaired and len(repaired) > len(pdb_text) * 0.5:
                                pdb_text = repaired
                                # Re-check after repair
                                health = await asyncio.to_thread(detect_chain_health, pdb_text)
                                result_fields["chain_health"] = _chain_health_dict(health)
                                _update_job(supabase, job_id, result=result_fields)
                                if not health.is_broken:
                                    chain_integrity = "repaired"
                                    _update_job(supabase, job_id, chain_integrity=chain_integrity)
                                break
                except Exception as e:
                    logger.warning("SWISS-MODEL repair failed: %s", e)

        # ── Step 4: Cleanup ───────────────────────────────────────────
        # pymol2 has no internal timeout; bound it and fall back to
        # Biopython stripping rather than hanging the whole job.
        _update_job(supabase, job_id, step="cleaning")
        try:
            cleaned = await asyncio.wait_for(
                asyncio.to_thread(pymol_cleanup, pdb_text), timeout=120
            )
        except asyncio.TimeoutError:
            logger.warning("pymol cleanup timed out for job %s; using Biopython fallback", job_id)
            cleaned = await asyncio.to_thread(_biopython_cleanup, pdb_text)

        # ── Step 5: fpocket (local binary) ────────────────────────────
        # Offloaded to a thread: subprocess.run would otherwise block the
        # event loop for up to 60s and freeze every concurrent request.
        _update_job(supabase, job_id, step="running_fpocket", fpocket_status="running")
        try:
            fpocket_result = await asyncio.wait_for(
                asyncio.to_thread(run_fpocket, cleaned, body.probe_radius), timeout=90
            )
        except asyncio.TimeoutError:
            fpocket_result = FpocketResult(raw_output="fpocket timed out", status="error")
        result_fields["fpocket_pockets"] = fpocket_result.pockets
        _update_job(
            supabase, job_id,
            fpocket_status=fpocket_result.status,
            result=result_fields,
        )

        # ── Step 6: CASTp (remote, async) ─────────────────────────────
        castp_pockets: list[dict] = []
        if body.skip_castp:
            _update_job(supabase, job_id, castp_status="skipped")
        else:
            _update_job(supabase, job_id, step="running_castp", castp_status="running")
            castp_status = "timed_out"
            try:
                castp_sub = await castp_submit(cleaned, body.probe_radius)
                if castp_sub.get("status") == "complete":
                    castp_status = "complete"
                elif castp_sub.get("job_id"):
                    for _ in range(30):
                        await asyncio.sleep(3)
                        castp_res = await castp_poll(castp_sub["job_id"])
                        if castp_res.get("status") == "complete":
                            castp_pockets = castp_res.get("pockets", [])
                            castp_status = "complete"
                            break
            except Exception as e:
                logger.warning("CASTp job failed: %s", e)
                castp_status = "error"
            result_fields["castp_pockets"] = castp_pockets
            _update_job(
                supabase, job_id,
                castp_status=castp_status,
                result=result_fields,
            )

        result_fields["cleaned_pdb"] = cleaned[:50000]
        _update_job(
            supabase, job_id,
            step="complete",
            status="complete",
            chain_integrity=chain_integrity,
            result=result_fields,
        )

    except Exception as e:
        _fail(supabase, job_id, str(e))

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.deps import limiter
from app.services.supabase import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/docking", tags=["docking"])

_TABLE = "docking_jobs"
_MAX_JOBS = 200
_JOB_TTL = 7200


def _prune_jobs() -> None:
    sb = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=_JOB_TTL)).strftime('%Y-%m-%dT%H:%M:%S')
    sb.table(_TABLE).delete().lt("done_at", cutoff).execute()
    count = sb.table(_TABLE).select("id", count="exact").execute().count or 0
    if count > _MAX_JOBS:
        to_delete = (
            sb.table(_TABLE)
            .select("id")
            .in_("status", ("complete", "failed"))
            .order("created_at", desc=True)
            .range(_MAX_JOBS, _MAX_JOBS + 500)
            .execute()
            .data
        )
        ids = [r["id"] for r in to_delete]
        if ids:
            sb.table(_TABLE).delete().in_("id", ids).execute()


class DockingRequest(BaseModel):
    pdb_id: str = ""
    smiles: str
    pdb_url: str = ""


class DockingJob(BaseModel):
    job_id: str
    pdb_id: str = ""
    pdb_url: str = ""
    smiles: str
    status: str = "queued"
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str = ""
    done_at: Optional[str] = None


def _init(job_id: str, req: DockingRequest) -> None:
    try:
        _prune_jobs()
    except Exception:
        pass
    get_supabase().table(_TABLE).insert({
        "id":      job_id,
        "pdb_id":  req.pdb_id,
        "pdb_url": req.pdb_url,
        "smiles":  req.smiles,
        "status":  "queued",
        "result":  None,
        "error":   None,
        "done_at": None,
    }).execute()


def _patch(job_id: str, **kw) -> None:
    get_supabase().table(_TABLE).update(kw).eq("id", job_id).execute()


def _read(job_id: str) -> dict | None:
    rows = get_supabase().table(_TABLE).select("*").eq("id", job_id).execute().data
    return dict(rows[0]) if rows else None


async def _worker(job_id: str) -> None:
    """Run docking job — calls the new docking module directly."""
    job = _read(job_id)
    if not job:
        return

    try:
        from app.tools.docking import (
            _ensure_vina,
            smiles_to_pdbqt,
            make_pdb_from_sequence,
            run_vina,
        )
    except Exception as exc:
        logger.exception("Failed to import docking tools for job %s", job_id)
        _patch(job_id, status="failed", error=str(exc),
               done_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'))
        return

    _patch(job_id, status="importing_tool")
    try:
        vina_bin = _ensure_vina()
    except Exception as exc:
        logger.exception("Vina download/locate failed for job %s", job_id)
        _patch(job_id, status="failed", error=str(exc),
               done_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'))
        return

    _patch(job_id, status="building_params")
    try:
        import httpx as _httpx
        pdb_url = job.get("pdb_url", "")
        pdb_id = job.get("pdb_id", "")
        smiles = job.get("smiles", "")

        if not pdb_url and pdb_id:
            pdb_url = f"https://files.rcsb.org/download/{pdb_id}.pdb"

        if not pdb_url:
            _patch(job_id, status="failed", error="pdb_id or pdb_url is required",
                   done_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'))
            return

        async with _httpx.AsyncClient(timeout=30) as client:
            r = await client.get(pdb_url)
            if r.status_code != 200:
                _patch(job_id, status="failed", error=f"PDB not found at {pdb_url}",
                       done_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'))
                return
            pdb_content = r.text

        _patch(job_id, status="converting_ligand")
        ligand_pdbqt = smiles_to_pdbqt(smiles)

        _patch(job_id, status="running_vina")
        result = await run_vina(
            protein_pdbqt=pdb_content,
            ligand_pdbqt=ligand_pdbqt,
            exhaustiveness=2,
            num_modes=3,
        )

        if "error" in result and not result.get("poses"):
            _patch(job_id, status="failed", error=result["error"],
                   done_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'))
        else:
            _patch(job_id, status="complete", result=result,
                   done_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'))

    except Exception as exc:
        logger.exception("Worker crashed for job %s", job_id)
        _patch(job_id, status="failed", error=str(exc),
               done_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'))


@router.get("/vimontest")
async def vina_montest():
    import os, subprocess, time
    from app.tools.docking import _ensure_vina
    steps = {}
    try:
        vina_bin = _ensure_vina()
        steps["cmd"] = vina_bin
        steps["exists"] = os.path.isfile(vina_bin)
        steps["exec"] = os.access(vina_bin, os.X_OK)
    except Exception as e:
        steps["error"] = repr(e)
        return steps
    try:
        r = subprocess.run([vina_bin, "--version"], capture_output=True, timeout=10)
        steps["vina_version"] = r.stdout.decode(errors="replace").strip()
        steps["rc"] = r.returncode
    except Exception as e:
        steps["error"] = repr(e)

    # Test OS timeout: run `sleep 30` with 5s timeout
    import tempfile
    tdir = tempfile.mkdtemp(prefix="vt_")
    out = os.path.join(tdir, "out.log")
    err = os.path.join(tdir, "err.log")
    try:
        proc = None
        of = open(out, "wb")
        ef = open(err, "wb")
        try:
            proc = await asyncio.create_subprocess_exec("sleep", "30", stdout=of, stderr=ef)
            start = time.time()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
                steps["timeout_sleep"] = f"COMPLETED_{round(time.time() - start, 2)}s"
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                steps["timeout_sleep"] = f"TIMEOUT_{round(time.time() - start, 2)}s"
        finally:
            of.close()
            ef.close()
    except Exception as exc:
        steps["timeout_sleep"] = f"ERR: {exc}"
    import shutil; shutil.rmtree(tdir, ignore_errors=True)

    return steps

@router.get("/debug")
async def debug_deps():
    import asyncio, os, sys, shutil, subprocess
    steps = {}
    steps["python"] = sys.version
    steps["vina_in_path"] = shutil.which("vina") or "NOT FOUND"
    try:
        from app.tools.docking import _ensure_vina
        vina_bin = _ensure_vina()
        steps["VINA_CMD"] = vina_bin or "None"
        steps["vina_exists"] = os.path.isfile(vina_bin) if vina_bin else False
        steps["vina_executable"] = os.access(vina_bin, os.X_OK) if vina_bin else False
    except Exception as e:
        steps["import_error"] = str(e)
    # try running vina --version
    cmd = steps.get("VINA_CMD", "")
    if cmd and os.access(cmd, os.X_OK):
        try:
            r = subprocess.run([cmd, "--version"], capture_output=True, timeout=10)
            steps["vina_version_rc"] = r.returncode
            steps["vina_version_out"] = r.stdout.decode(errors="replace").strip()
            steps["vina_version_err"] = r.stderr.decode(errors="replace").strip()[:200]
        except FileNotFoundError:
            steps["vina_version_err"] = "FileNotFoundError"
        except subprocess.TimeoutExpired:
            steps["vina_version_err"] = "TIMEOUT after 10s"
        except Exception as e:
            steps["vina_version_err"] = str(e)[:200]
    else:
        steps["vina_version_err"] = "binary not accessible"
    steps["which_timeout"] = shutil.which("timeout") or "NOT FOUND"
    steps["tempdir"] = __import__("tempfile").gettempdir()
    steps["cwd"] = os.getcwd()
    return steps


@router.post("/run")
async def run_docking(req: DockingRequest, background_tasks: BackgroundTasks):
    if not req.pdb_id.strip() and not req.pdb_url.strip():
        raise HTTPException(400, detail="pdb_id or pdb_url is required")
    if not req.smiles.strip():
        raise HTTPException(400, detail="smiles is required")

    job_id = str(uuid.uuid4())
    _init(job_id, req)
    background_tasks.add_task(_worker, job_id)
    return {"job_id": job_id, "status": "queued"}


@router.get("/status/{job_id}")
@limiter.exempt
async def get_status(job_id: str):
    job = _read(job_id)
    if not job:
        raise HTTPException(404, detail=f"Job {job_id} not found")
    return job


@router.get("/result/{job_id}/pdb", response_class=PlainTextResponse)
@limiter.exempt
async def get_pdb_result(job_id: str):
    job = _read(job_id)
    if not job:
        raise HTTPException(404, detail=f"Job {job_id} not found")
    if job.get("status") != "complete":
        raise HTTPException(400, detail="Job not yet complete")
    result = job.get("result", {})
    ligand_pdb = result.get("ligand_pdb", "")
    if not ligand_pdb:
        raise HTTPException(404, detail="No ligand PDB available")
    return ligand_pdb

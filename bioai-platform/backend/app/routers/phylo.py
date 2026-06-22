"""
Phylogenetic tree router — three methods:
  nj    : Neighbor-Joining via Clustal Omega guide tree (~60s)
  upgma : UPGMA computed locally from Clustal alignment (adds ~0s after MSA)
  ml    : Maximum Likelihood via local PhyML binary (~3-5 min, includes bootstrap)

PhyML binary must be installed at build time (see Dockerfile).
Download source from: https://github.com/stephaneguindon/phyml
Compile: ./configure --enable-phyml && make && make install

Job lifecycle (in-memory, thread-safe):
  queued -> msa_running -> msa_done -> tree_running -> complete | error
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from typing import Literal, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/phylo", tags=["phylo"])

# ── EBI base URLs ──────────────────────────────────────────────────────────────
_EBI_CLUSTALO = "https://www.ebi.ac.uk/Tools/services/rest/clustalo"
_EMAIL        = "bionexus@demo.com"

# ── PhyML protein models (most-used first) ────────────────────────────────────
PROTEIN_MODELS = ["LG", "WAG", "JTT", "Blosum62", "MtREV", "Dayhoff"]
DNA_MODELS     = ["GTR", "HKY85", "K80", "F81", "TN93", "SYM"]

# ─── Models ───────────────────────────────────────────────────────────────────

Method      = Literal["nj", "ml", "upgma"]
SeqType     = Literal["protein", "dna"]
JobPhase    = Literal["queued", "msa_running", "msa_done", "tree_running", "complete", "error"]


class PhyloRequest(BaseModel):
    sequences: list[dict]
    method: Method     = "nj"
    seq_type: SeqType  = "protein"
    # ML-only options
    model: str         = "LG"
    bootstrap: int     = Field(100, ge=0, le=1000)


class PhyloJob(BaseModel):
    job_id: str
    method: Method
    seq_type: SeqType
    model: Optional[str]
    bootstrap: Optional[int]
    phase: JobPhase
    aln_fasta:   Optional[str] = None
    newick:      Optional[str] = None
    stats:       Optional[str] = None
    error:       Optional[str] = None
    created_at:  float = 0.0
    msa_done_at: Optional[float] = None
    done_at:     Optional[float] = None


class RunResponse(BaseModel):
    job_id: str
    status: str


# ─── In-memory store ──────────────────────────────────────────────────────────

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def _init(job_id: str, req: PhyloRequest) -> None:
    with _lock:
        _jobs[job_id] = {
            "job_id":    job_id,
            "method":    req.method,
            "seq_type":  req.seq_type,
            "model":     req.model,
            "bootstrap": req.bootstrap,
            "phase":     "queued",
            "aln_fasta": None,
            "newick":    None,
            "stats":     None,
            "error":     None,
            "created_at": time.time(),
            "msa_done_at": None,
            "done_at":   None,
            "_req":      req.model_dump(),
        }


def _patch(job_id: str, **kw) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(kw)


def _read(job_id: str) -> dict | None:
    with _lock:
        return dict(_jobs[job_id]) if job_id in _jobs else None


# ─── EBI helpers (same pattern as alignment.py) ───────────────────────────────

async def _ebi_submit(url: str, data: dict) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url + "/run", data=data)
        r.raise_for_status()
        return r.text.strip()


async def _ebi_poll(url: str, ebi_job: str, interval: float = 2.0, max_polls: int = 150) -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        for _ in range(max_polls):
            await asyncio.sleep(interval)
            r = await client.get(f"{url}/status/{ebi_job}")
            status = r.text.strip()
            if status in ("FINISHED", "FAILED", "ERROR", "NOT_FOUND"):
                return status
    return "TIMEOUT"


async def _ebi_result(url: str, ebi_job: str, result_type: str, retries: int = 3) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(retries):
            try:
                r = await client.get(f"{url}/result/{ebi_job}/{result_type}")
                if r.status_code == 200:
                    return r.text
                await asyncio.sleep(2 ** attempt)
            except httpx.RequestError:
                await asyncio.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to fetch EBI result {result_type} after {retries} attempts")


# ─── MSA via Clustal Omega ────────────────────────────────────────────────────

def _to_fasta(sequences: list[dict]) -> str:
    return "\n".join(f">{s['id']}\n{s['sequence']}" for s in sequences)


async def _run_clustalo(job_id: str, sequences: list[dict], stype: str) -> tuple[str, str] | None:
    _patch(job_id, phase="msa_running")
    fasta = _to_fasta(sequences)

    try:
        ebi_job = await _ebi_submit(_EBI_CLUSTALO, {
            "email":    _EMAIL,
            "sequence": fasta,
            "outfmt":   "fa",
            "stype":    "protein" if stype == "protein" else "dna",
        })
        logger.info(f"[{job_id}] Clustal Omega job: {ebi_job}")
    except Exception as e:
        _patch(job_id, phase="error", error=f"Clustal Omega submission failed: {e}")
        return None

    status = await _ebi_poll(_EBI_CLUSTALO, ebi_job)
    if status != "FINISHED":
        _patch(job_id, phase="error", error=f"Clustal Omega ended with status: {status}")
        return None

    try:
        aln_fasta = await _ebi_result(_EBI_CLUSTALO, ebi_job, "fa")
        nj_newick = await _ebi_result(_EBI_CLUSTALO, ebi_job, "phylotree")
    except Exception as e:
        _patch(job_id, phase="error", error=f"Clustal Omega result fetch failed: {e}")
        return None

    _patch(job_id, phase="msa_done", aln_fasta=aln_fasta, msa_done_at=time.time())
    return aln_fasta, nj_newick


# ─── UPGMA (pure Python) ──────────────────────────────────────────────────────

def _parse_aligned_fasta(fasta: str) -> dict[str, str]:
    seqs: dict[str, str] = {}
    cur = None
    for line in fasta.strip().splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            cur = stripped[1:].split()[0]
            seqs[cur] = ""
        elif cur:
            seqs[cur] += stripped
    return seqs


def _p_distance(s1: str, s2: str) -> float:
    pairs = [(a, b) for a, b in zip(s1, s2) if a != "-" and b != "-"]
    if not pairs:
        return 1.0
    return sum(1 for a, b in pairs if a != b) / len(pairs)


def _upgma_newick(aln_fasta: str) -> str:
    seqs = _parse_aligned_fasta(aln_fasta)
    names = list(seqs.keys())
    n = len(names)

    if n < 2:
        return f"({names[0]}:0.0);" if names else "();"

    dist: dict[tuple[str, str], float] = {}
    for i in range(n):
        for j in range(i + 1, n):
            d = _p_distance(seqs[names[i]], seqs[names[j]])
            dist[(names[i], names[j])] = d
            dist[(names[j], names[i])] = d

    clusters: dict[str, dict] = {
        nm: {"newick": nm, "height": 0.0, "size": 1} for nm in names
    }

    counter = 0
    while len(clusters) > 1:
        ckeys = list(clusters.keys())
        min_d = float("inf")
        best = ("", "")
        for i in range(len(ckeys)):
            for j in range(i + 1, len(ckeys)):
                a, b = ckeys[i], ckeys[j]
                d = dist.get((a, b), float("inf"))
                if d < min_d:
                    min_d = d
                    best = (a, b)

        a, b = best
        new_h = min_d / 2.0
        bl_a  = max(0.0, new_h - clusters[a]["height"])
        bl_b  = max(0.0, new_h - clusters[b]["height"])
        new_nw = f"({clusters[a]['newick']}:{bl_a:.6f},{clusters[b]['newick']}:{bl_b:.6f})"
        new_sz = clusters[a]["size"] + clusters[b]["size"]

        counter += 1
        new_id = f"__c{counter}"

        for c in ckeys:
            if c in (a, b):
                continue
            da = dist.get((a, c), dist.get((c, a), 0.0))
            db = dist.get((b, c), dist.get((c, b), 0.0))
            nd = (da * clusters[a]["size"] + db * clusters[b]["size"]) / new_sz
            dist[(new_id, c)] = nd
            dist[(c, new_id)] = nd

        del clusters[a]
        del clusters[b]
        clusters[new_id] = {"newick": new_nw, "height": new_h, "size": new_sz}

    root = next(iter(clusters.values()))
    return root["newick"] + ";"


# ─── PhyML local (subprocess) ────────────────────────────────────────────────

def fasta_to_phylip(fasta: str) -> str:
    """Convert aligned FASTA to relaxed PHYLIP (names up to 100 chars)."""
    seqs: dict[str, str] = {}
    cur: str | None = None
    for line in fasta.strip().splitlines():
        t = line.strip()
        if t.startswith(">"):
            cur = t[1:].split()[0][:100]
            seqs[cur] = ""
        elif cur:
            seqs[cur] += t.upper()
    if not seqs:
        return ""
    n = len(seqs)
    L = len(next(iter(seqs.values())))
    lines = [f"{n} {L}"]
    for name, s in seqs.items():
        lines.append(f"{name:<100}{s}")
    return "\n".join(lines)


async def _run_phyml_local(job_id: str, aln_fasta: str, req: PhyloRequest) -> None:
    """Run PhyML as a subprocess on a temp PHYLIP file."""
    _patch(job_id, phase="tree_running")

    import os
    import tempfile

    fd, phy_path = tempfile.mkstemp(suffix=".phy")
    os.close(fd)
    try:
        with open(phy_path, "w") as f:
            f.write(fasta_to_phylip(aln_fasta))

        datatype = "aa" if req.seq_type == "protein" else "nt"
        model = req.model if req.model else ("LG" if req.seq_type == "protein" else "GTR")

        proc = await asyncio.create_subprocess_exec(
            "phyml",
            "-i", phy_path,
            "-d", datatype,
            "-m", model,
            "-b", str(req.bootstrap if req.bootstrap else 0),
            "-o", "tlr",
            "--no_memory_check",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=900)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            _patch(job_id, phase="error", error="PhyML timed out after 15 minutes")
            return

        if proc.returncode != 0:
            err_text = stderr.decode("utf-8", errors="replace")[:500] if stderr else ""
            _patch(job_id, phase="error",
                   error=f"PhyML failed (exit {proc.returncode}): {err_text}")
            return

        tree_path = phy_path + "_phyml_tree.txt"
        stats_path = phy_path + "_phyml_stats.txt"

        newick = None
        stats = None
        if os.path.exists(tree_path):
            with open(tree_path) as f:
                newick = f.read().strip()
        if os.path.exists(stats_path):
            with open(stats_path) as f:
                stats = f.read().strip()

        if not newick:
            _patch(job_id, phase="error", error="PhyML produced no output tree")
            return

        _patch(job_id, phase="complete", newick=newick, stats=stats, done_at=time.time())
    except Exception as e:
        _patch(job_id, phase="error", error=f"PhyML error: {e}")
    finally:
        for suffix in ["", "_phyml_tree.txt", "_phyml_stats.txt", "_phyml_boot_trees.txt"]:
            p = phy_path + suffix
            if os.path.exists(p):
                os.remove(p)


# ─── Main pipeline worker ─────────────────────────────────────────────────────

async def _worker(job_id: str) -> None:
    job = _read(job_id)
    if not job:
        return

    req = PhyloRequest(**job["_req"])

    result = await _run_clustalo(job_id, req.sequences, req.seq_type)
    if result is None:
        return

    aln_fasta, nj_newick = result

    if req.method == "nj":
        _patch(job_id, phase="complete",
               newick=nj_newick.strip(), done_at=time.time())

    elif req.method == "upgma":
        _patch(job_id, phase="tree_running")
        try:
            newick = _upgma_newick(aln_fasta)
            _patch(job_id, phase="complete",
                   newick=newick, done_at=time.time())
        except Exception as e:
            _patch(job_id, phase="error", error=f"UPGMA computation failed: {e}")

    elif req.method == "ml":
        await _run_phyml_local(job_id, aln_fasta, req)

    else:
        _patch(job_id, phase="error", error=f"Unknown method: {req.method}")


# ─── API endpoints ─────────────────────────────────────────────────────────────

@router.post("/run", response_model=RunResponse)
async def run_phylo(
    req: PhyloRequest,
    background_tasks: BackgroundTasks,
):
    if len(req.sequences) < 2:
        raise HTTPException(400, detail="At least 2 sequences are required")
    if len(req.sequences) > 50:
        raise HTTPException(400, detail="Maximum 50 sequences per run")

    valid_models = PROTEIN_MODELS if req.seq_type == "protein" else DNA_MODELS
    if req.method == "ml" and req.model not in valid_models:
        raise HTTPException(
            400,
            detail=f"Model '{req.model}' not valid for {req.seq_type}. "
                   f"Choose from: {', '.join(valid_models)}"
        )

    job_id = str(uuid.uuid4())
    _init(job_id, req)
    background_tasks.add_task(_worker, job_id)
    return RunResponse(job_id=job_id, status="queued")


@router.get("/status/{job_id}")
async def get_status(job_id: str):
    job = _read(job_id)
    if not job:
        raise HTTPException(404, detail=f"Job {job_id} not found")
    return {k: v for k, v in job.items() if not k.startswith("_")}


@router.get("/models")
async def list_models(seq_type: SeqType = "protein"):
    return {
        "seq_type": seq_type,
        "models": PROTEIN_MODELS if seq_type == "protein" else DNA_MODELS,
        "default": "LG" if seq_type == "protein" else "GTR",
    }

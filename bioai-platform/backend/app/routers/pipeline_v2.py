"""
In-memory pipeline v2 — runs BLAST → UniProt → MSA → Phylo → Domains → Interpretation
in a background thread. Uses a thread-safe dict for job storage.
"""

import asyncio
import logging
import threading
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.deps import limiter
from app.services.rate_limit import check_daily_limit_pipelines
from app.services.auth import get_user_id
from app.services.supabase import get_supabase
from app.integrations.ncbi import blast as ncbi_blast
from app.integrations.ncbi.parser import parse_blast_xml
from app.services.validators import validate_fasta
from app.services.sequence_utils import detect_source_from_accession, map_refseq_to_uniprot, detect_sequence_type
from app.services.blast_config import resolve_blast_params
from app.services.identifier_resolution import resolve_to_uniprot
from app.tools.ebi_msa import EBI_TOOLS, run_ebi_msa, run_ebi_msa_best_effort
from app.tools.blast import BlastTool
from app.tools.uniprot import UniprotTool
from app.tools.pairwise_alignment import pairwise_align, VALID_MODES

logger = logging.getLogger(__name__)
router = APIRouter()

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

STEP_ORDER = ["blast", "uniprot", "msa", "phylo", "domains", "pathway_enrichment", "alphafold", "interpret"]


def _get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        return _jobs.get(job_id)


def _is_real_uuid(job_id: str) -> bool:
    try:
        uuid.UUID(job_id)
        return True
    except (ValueError, AttributeError):
        return False


def _persist_v2_final(job_id: str, status: str, context: dict, error: str | None = None):
    """Update the persisted wizard job row with the final status + full context."""
    if not _is_real_uuid(job_id):
        return
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "status": status,
        "progress_pct": 100,
        "completed_at": now,
        "context_json": context,
        "error_message": error,
    }
    if error:
        payload["error"] = error
    try:
        get_supabase().table("jobs").update(payload).eq("id", job_id).execute()
    except Exception as e:
        logger.warning("Could not update v2 job %s to Supabase: %s", job_id, e)


def _persist_v2_job(job_id: str, payload: dict):
    """Persist a wizard v2 job to Supabase (best-effort) so it shows up in
    the user's job history and can be shared. Uses the service role key."""
    try:
        get_supabase().table("jobs").insert(payload).execute()
    except Exception as e:
        logger.warning("Could not persist v2 job %s to Supabase: %s", job_id, e)


def _set_step_status(job_id: str, step: str, status: str, progress: int = 0, data: dict | None = None, error: str | None = None):
    with _jobs_lock:
        if job_id not in _jobs:
            return
        _jobs[job_id]["steps"][step] = {"status": status, "progress": progress, "data": data, "error": error}
        if status == "running":
            _jobs[job_id]["current_step"] = step


def _set_job_failed(job_id: str, message: str):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = message


class PipelineV2RunRequest(BaseModel):
    sequence: str = Field(..., min_length=6, description="Protein sequence (FASTA or raw)")
    steps: list[str] = Field(default_factory=lambda: list(STEP_ORDER), description="Steps to run")
    fast_mode: bool = Field(default=False, description="Use Swiss-Prot instead of nr for faster results")
    database: str = Field("", description="BLAST database override")
    program: str = Field("", description="BLAST program override")
    max_hits: int = Field(100, description="Max BLAST hits to return")
    query_accession: str = Field("", description="Optional query accession for display")
    alignment_mode: str = Field("global", description="Alignment mode for the MSA step: 'global' (full-length) or 'local' (Smith-Waterman refinement of query vs top hit)")
    parent_job_id: str | None = Field(None, description="Parent job ID for DAG branching")


@router.post("/run")
async def run_pipeline_v2(request: Request, req: PipelineV2RunRequest, user_id: str | None = Depends(get_user_id)):
    validation = validate_fasta(req.sequence, "blast")
    if not validation.valid:
        raise HTTPException(status_code=400, detail=validation.error)

    alignment_mode = req.alignment_mode.lower()
    if alignment_mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"alignment_mode must be one of {list(VALID_MODES)}, got {alignment_mode!r}")

    seq = str(validation.sequences[0].seq).upper()
    clean = "".join(c for c in seq if c.isalpha())

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    requested = [s for s in req.steps if s in STEP_ORDER]
    if not requested:
        requested = list(STEP_ORDER)

    steps_dict = {s: {"status": "pending", "progress": 0, "data": None, "error": None} for s in STEP_ORDER}

    blast_params = {
        "database": req.database,
        "program": req.program,
        "max_hits": req.max_hits,
        "query_accession": req.query_accession,
    }

    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "current_step": None,
            "steps": steps_dict,
            "requested_steps": requested,
            "sequence": clean,
            "blast_params": blast_params,
            "alignment_mode": alignment_mode,
            "error": None,
            "created_at": now,
        }

    # Best-effort persistence so wizard jobs appear in history and can be shared.
    persist_payload = {
        "id": job_id,
        "user_id": user_id,
        "tool": "wizard_v2",
        "pipeline_type": "wizard_v2",
        "query_preview": clean[:60],
        "status": "running",
        "progress_pct": 0,
        "title": "Wizard pipeline",
        "description": "Pipeline v2 wizard run",
        "created_at": now,
    }
    if req.parent_job_id:
        persist_payload["parent_job_id"] = req.parent_job_id
    _persist_v2_job(job_id, persist_payload)

    t = threading.Thread(
        target=_run_pipeline,
        args=(job_id, clean, requested),
        kwargs={"fast_mode": req.fast_mode, "blast_params": blast_params, "alignment_mode": alignment_mode},
        daemon=True,
    )
    t.start()

    return {"job_id": job_id}


@router.get("/status/{job_id}")
async def get_pipeline_v2_status(job_id: str):
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


async def run_pipeline(
    sequence: str,
    organism: str = "Homo sapiens",
    analysis_type: str = "comprehensive",
    status_callback=None,
    fast_mode: bool = False,
    blast_params: dict | None = None,
) -> dict:
    """Public async entry point for the pipeline (used by pipeline_worker).

    Creates a temporary in-memory job, runs the configured steps, and
    returns the context dict with all results.
    """
    job_id = f"worker-{uuid.uuid4().hex[:12]}"
    requested = list(STEP_ORDER)
    steps_dict = {s: {"status": "pending", "progress": 0, "data": None, "error": None} for s in STEP_ORDER}

    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "current_step": None,
            "steps": steps_dict,
            "requested_steps": requested,
            "sequence": sequence,
            "blast_params": blast_params or {},
            "error": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    try:
        await _execute(
            job_id,
            sequence,
            requested,
            status_callback=status_callback,
            fast_mode=fast_mode,
            blast_params=blast_params,
        )
    finally:
        job = _get_job(job_id)
        with _jobs_lock:
            _jobs.pop(job_id, None)

    if job and job.get("status") == "failed":
        raise RuntimeError(job.get("error", "Pipeline failed"))

    query_accession = ((blast_params or {}).get("query_accession") or "").strip()
    context: dict = {
        "sequence": sequence,
        "length": len(sequence),
        "query": {
            "sequence": sequence,
            "length": len(sequence),
            "sequence_type": detect_sequence_type(sequence) or "protein",
        },
    }
    if query_accession:
        context["query"]["accession"] = query_accession
    if job:
        for step_name, step_info in job.get("steps", {}).items():
            if step_info.get("data"):
                context[step_name] = step_info["data"]
    return context


# ---------------------------------------------------------------------------
# Background pipeline
# ---------------------------------------------------------------------------

def _run_pipeline(job_id: str, sequence: str, steps: list[str], fast_mode: bool = False, blast_params: dict | None = None, alignment_mode: str = "global"):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            _execute(job_id, sequence, steps, fast_mode=fast_mode, blast_params=blast_params, alignment_mode=alignment_mode)
        )
    except Exception as e:
        logger.exception(f"[{job_id}] Unhandled pipeline error")
        _set_job_failed(job_id, f"Pipeline error: {e}")
    finally:
        loop.close()
        asyncio.set_event_loop(None)


async def _execute(job_id: str, sequence: str, steps: list[str], status_callback=None, fast_mode: bool = False, blast_params: dict | None = None, alignment_mode: str = "global"):
    context: dict = {
        "sequence": sequence,
        "length": len(sequence),
        "query": {
            "sequence": sequence,
            "length": len(sequence),
            "sequence_type": detect_sequence_type(sequence) or "protein",
        },
    }

    _STEP_FRONTEND = {
        "blast": "running",
        "uniprot": "fetching_uniprot",
        "msa": "running_msa",
        "phylo": "running_msa",
        "domains": "fetching_uniprot",
        "pathway_enrichment": "pathway_enrichment",
        "alphafold": "fetching_alphafold",
        "interpret": "interpreting",
    }

    _failed_step = None
    _failed_error = None

    async def _notify(step_key: str):
        if status_callback:
            try:
                await status_callback(_STEP_FRONTEND.get(step_key, "running"))
            except Exception:
                pass

    def _mark(step_key: str, status: str, **kw):
        _set_step_status(job_id, step_key, status, **kw)

    def _fail(step_key: str, msg: str):
        nonlocal _failed_step, _failed_error
        _mark(step_key, "failed", error=msg)
        _failed_step = step_key
        _failed_error = msg

    # ---- Step 1: BLAST (must run first) ----
    denovo_mode = False
    if "blast" in steps:
        await _notify("blast")
        _mark("blast", "running", progress=10)
        result = await _run_blast(
            sequence,
            status_callback=status_callback,
            fast_mode=fast_mode,
            blast_params=blast_params,
        )
        zero_hits = result.get("count", 0) == 0
        if zero_hits and (detect_sequence_type(sequence) or "protein") == "protein":
            # Tier 6: no database match at all — characterize from sequence
            # alone instead of failing the run (techspec.md §1).
            denovo_mode = True
            result["_note"] = "No BLAST hits found — switching to de novo characterization"
            _mark("blast", "complete", progress=100, data=result)
        else:
            _mark("blast", "failed" if zero_hits else "complete", progress=100, data=result)
            if zero_hits:
                _failed_step = "blast"
                _failed_error = result.get("error", "No BLAST hits found")
        context["blast"] = result

    if denovo_mode:
        context["query"]["confidence"] = "de_novo"
        await _run_denovo_steps(job_id, sequence, steps, _mark, context)
        await _finalize_context(job_id, context)
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["status"] = "complete"
                _jobs[job_id]["context"] = context
        _persist_v2_final(job_id, "complete", context)
        return

    # ---- Step 2: Fan-out — UniProt, MSA, Pathway run in parallel ----
    #    They all only depend on BLAST results, not on each other.
    blast_data = context.get("blast", {})
    hits = (blast_data.get("hits") if isinstance(blast_data, dict) else []) or []
    top_hit = blast_data.get("top_hit") if isinstance(blast_data, dict) else None

    async def _do_uniprot():
        candidates = ([top_hit] + hits[:5]) if top_hit else hits[:5]
        last_result: dict | None = None
        for idx, candidate in enumerate(candidates):
            # Only the top candidate may trigger the expensive EBI sequence
            # BLAST fallback — otherwise a pathological query could run it up
            # to 6 times (up to ~3 min each).
            last_result = await _run_uniprot(
                candidate,
                query_sequence=sequence,
                try_sequence=idx == 0,
            )
            if "error" not in last_result:
                return last_result
        return last_result if last_result else {"error": "No BLAST hits for UniProt lookup"}

    async def _do_msa():
        if not hits:
            return {"error": "No BLAST hits for MSA"}
        return await _run_msa(sequence, hits, alignment_mode)

    async def _do_pathway():
        return await _run_pathway_enrichment(context)

    fan_out = []
    fan_names = []
    if "uniprot" in steps and not _failed_step:
        fan_out.append(_do_uniprot())
        fan_names.append("uniprot")
    if "msa" in steps and not _failed_step:
        fan_out.append(_do_msa())
        fan_names.append("msa")
    if "pathway_enrichment" in steps and not _failed_step:
        fan_out.append(_do_pathway())
        fan_names.append("pathway_enrichment")

    if fan_out:
        # Notify for the first active step in the fan-out
        await _notify(fan_names[0])
        for name in fan_names:
            _mark(name, "running", progress=10)

        results = await asyncio.gather(*fan_out, return_exceptions=True)

        for name, res in zip(fan_names, results):
            if isinstance(res, Exception):
                _fail(name, str(res)[:500])
                continue

            if name == "uniprot":
                s = "complete" if "error" not in res else "failed"
                _mark("uniprot", s, progress=100, data=res)
                context["uniprot"] = res
                if res.get("confidence"):
                    context["query"]["confidence"] = res["confidence"]
                if "error" in res:
                    _failed_step = "uniprot"
                    _failed_error = res["error"]

            elif name == "msa":
                s = "complete" if res.get("aln_fasta") else "failed"
                _mark("msa", s, progress=100, data=res)
                context["msa"] = res
                if res.get("phylotree"):
                    context.setdefault("phylo_data", {})["phylotree_newick"] = res["phylotree"]

            elif name == "pathway_enrichment":
                s = "complete" if res and res.get("pathways") else "failed"
                _mark("pathway_enrichment", s, progress=100, data=res or {})
                context["pathway_enrichment"] = res

    # ---- Step 3: Phylo (instant — copies from MSA) ----
    if "phylo" in steps and not _failed_step:
        _mark("phylo", "running", progress=10)
        newick = None
        msa_data = context.get("msa", {})
        if isinstance(msa_data, dict):
            newick = msa_data.get("phylotree")
        if not newick:
            newick = context.get("phylo_data", {}).get("phylotree_newick")
        if newick:
            _mark("phylo", "complete", progress=100, data={"phylotree_newick": newick})
            context["phylo"] = {"phylotree_newick": newick}
        else:
            _mark("phylo", "failed", error="No phylotree available from MSA")

    # ---- Step 4: Domains + AlphaFold in parallel ----
    # When UniProt resolution exhausted all tiers, these fall back to their
    # sequence-only equivalents instead of being silently skipped (§1.2).
    uniprot_data = context.get("uniprot", {})
    accession = uniprot_data.get("accession") if isinstance(uniprot_data, dict) else None
    resolved_uniprot = bool(uniprot_data.get("resolved_uniprot")) if isinstance(uniprot_data, dict) else False

    post_uniprot = []
    post_uniprot_names = []
    if "domains" in steps and not _failed_step:
        post_uniprot.append(
            _run_domains_or_denovo(sequence, accession, resolved_uniprot)
        )
        post_uniprot_names.append("domains")
    if "alphafold" in steps and not _failed_step:
        post_uniprot.append(
            _run_alphafold_or_esmfold(context, sequence, accession, resolved_uniprot)
        )
        post_uniprot_names.append("alphafold")

    if post_uniprot:
        await _notify(post_uniprot_names[0])
        for name in post_uniprot_names:
            _mark(name, "running", progress=10)

        results2 = await asyncio.gather(*post_uniprot, return_exceptions=True)

        for name, res in zip(post_uniprot_names, results2):
            if isinstance(res, Exception):
                _fail(name, str(res)[:500])
                continue

            if name == "domains":
                s = "complete" if res.get("domains") is not None else "failed"
                _mark("domains", s, progress=100, data=res)
                context["domains"] = res
            elif name == "alphafold":
                s = "complete" if res else "failed"
                _mark("alphafold", s, progress=100, data=res or {})
                context["alphafold"] = res

    # ---- Step 5: Interpret (needs all context) ----
    if "interpret" in steps and not _failed_step:
        await _notify("interpret")
        _mark("interpret", "running", progress=10)
        result = await _run_interpret(context)
        s = "complete" if result.get("interpretation") else "failed"
        _mark("interpret", s, progress=100, data=result)
        context["interpret"] = result

    # ---- Final status ----
    if _failed_step and _failed_step in ("blast", "uniprot"):
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = f"Pipeline failed at {_failed_step}: {_failed_error}"
        _persist_v2_final(job_id, "failed", context, error=f"Pipeline failed at {_failed_step}: {_failed_error}")
    else:
        await _finalize_context(job_id, context)
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["status"] = "complete"
                _jobs[job_id]["context"] = context
        _persist_v2_final(job_id, "complete", context)


async def _finalize_context(job_id: str, context: dict):
    """Pre-persist hook: capture source pages (§3) + build the final report."""
    user_id = None
    with _jobs_lock:
        entry = _jobs.get(job_id)
        if entry:
            user_id = entry.get("user_id")
    try:
        _capture_run_sources(job_id, context, user_id)
    except Exception as e:  # captures must never break a run
        logger.warning("[%s] page capture wiring failed: %s", job_id, e)
    try:
        from app.services.final_synthesis import synthesize

        context["final_report"] = await synthesize(context)
    except Exception as e:
        logger.warning("[%s] final synthesis failed: %s", job_id, e)


def _capture_run_sources(job_id: str, context: dict, user_id: str | None):
    """Queue one page_captures row per external source this run queried."""
    from app.services.page_capture import capture_bg

    blast = context.get("blast") or {}
    top_hit = blast.get("top_hit")
    if top_hit and top_hit.get("accession"):
        capture_bg(job_id, "ncbi", f"https://www.ncbi.nlm.nih.gov/protein/{top_hit['accession']}", user_id)

    uniprot = context.get("uniprot") or {}
    if uniprot.get("_de_novo"):
        pass  # no external annotation source was queried in de novo mode
    elif uniprot.get("accession"):
        capture_bg(job_id, "uniprot", f"https://www.uniprot.org/uniprotkb/{uniprot['accession']}", user_id)
        pdb_ids = uniprot.get("pdb_ids") or []
        if pdb_ids:
            capture_bg(job_id, "rcsb", f"https://www.rcsb.org/structure/{pdb_ids[0]}", user_id)

    domains = context.get("domains") or {}
    dom_list = domains.get("domains") or []
    if dom_list and dom_list[0].get("accession"):
        acc = dom_list[0]["accession"]
        if str(acc).startswith("IPR"):
            capture_bg(job_id, "interpro", f"https://www.ebi.ac.uk/interpro/entry/InterPro/{acc}", user_id)

    af = context.get("alphafold") or {}
    if af.get("structure_available") and af.get("source") != "esmfold" and uniprot.get("accession"):
        capture_bg(job_id, "alphafold", f"https://alphafold.ebi.ac.uk/uniprot/{uniprot['accession']}", user_id)

    pathway = context.get("pathway_enrichment") or {}
    pw_list = (pathway.get("pathways") if isinstance(pathway, dict) else None) or []
    if pw_list and pw_list[0].get("stId"):
        # run_enrichment queries the Reactome projection API exclusively
        capture_bg(
            job_id, "reactome",
            f"https://reactome.org/PathwayBrowser/#{pw_list[0]['stId']}",
            user_id,
        )


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------

# NCBI database name → EBI ncbiblast database name. EBI has no direct "nr"
# equivalent; uniprotkb is its closest comprehensive protein database.
EBI_BLAST_DATABASE_MAP = {
    "nr": "uniprotkb",
    "swissprot": "uniprotkb_swissprot",
    "pdb": "pdb",
    "pdbaa": "pdb_nr",
    "refseq_protein": "refseq_protein",
    "env_nr": "env_nr",
    "nt": "nt",
    "refseq_rna": "refseq_rna",
    "refseq_genomic": "refseq_genomic",
    "est": "est",
    "gss": "gss",
}


def _build_blast_result(
    hits: list[dict],
    *,
    source: str,
    database: str,
    program: str,
    seq_type: str,
    query_accession: str,
    query_length: int,
    display_limit: int = 20,
) -> dict:
    """Normalize parsed hits (NCBI XML parser or EBI tool) into the pipeline's
    canonical BLAST result shape consumed by the frontend."""
    top_hit = hits[0] if hits else None
    return {
        "count": len(hits),
        "source": source,
        "database": database,
        "program": program,
        "query_sequence_type": seq_type,
        "query_accession": query_accession,
        "query_length": query_length,
        "top_hit": {
            "accession": top_hit["accession"],
            "description": top_hit["description"],
            "evalue": top_hit["evalue"],
            "evalue_raw": str(top_hit["evalue"]),
            "identity_pct": top_hit["identity_pct"],
            "bit_score": top_hit["bit_score"],
            "alignment_length": top_hit.get("alignment_length", 0),
        } if top_hit else None,
        "hits": [
            {
                "accession": h["accession"],
                "description": h["description"],
                "organism": h.get("organism", ""),
                "evalue": h["evalue"],
                "evalue_raw": str(h["evalue"]),
                "identity_pct": h["identity_pct"],
                "bit_score": h["bit_score"],
                "alignment_length": h.get("alignment_length", 0),
                "query_coverage_pct": round(h.get("alignment_length", 0) / query_length * 100, 1) if query_length > 0 else 0,
                "hit_alignment": h.get("hit_alignment", ""),
                "query_alignment": h.get("query_alignment", ""),
                "midline": h.get("midline", ""),
                "score": h.get("score", 0),
                "positive": h.get("positive", 0),
                "gaps": h.get("gaps", 0),
                "query_from": h.get("query_from", 0),
                "query_to": h.get("query_to", 0),
                "hit_from": h.get("hit_from", 0),
                "hit_to": h.get("hit_to", 0),
            }
            for h in hits[:display_limit]
        ],
    }


async def _run_ebi_blast_fallback(
    sequence: str,
    program: str,
    database: str,
    seq_type: str,
    max_hits: int,
) -> dict | None:
    """Run BLAST against EBI (uncached) and return a canonical result, or None
    if the database has no EBI equivalent or EBI itself fails."""
    ebi_database = EBI_BLAST_DATABASE_MAP.get(database)
    if not ebi_database:
        logger.warning("No EBI database equivalent for '%s' — skipping fallback", database)
        return None
    try:
        result = await BlastTool().run_uncached({
            "sequence": sequence,
            "program": program,
            "database": ebi_database,
            "max_hits": max_hits,
        })
    except Exception as e:
        logger.warning("EBI BLAST fallback failed: %s", e)
        return None
    if result.get("error") or not result.get("hits"):
        logger.warning("EBI BLAST fallback returned no hits: %s", result.get("error", "empty"))
        return None
    query_length = len("".join(sequence.replace("\n", "").replace(" ", "").split("-")))
    return _build_blast_result(
        result["hits"],
        source="ebi",
        database=database,
        program=program,
        seq_type=seq_type,
        query_accession="",
        query_length=query_length,
    )


async def _run_blast(
    sequence: str,
    status_callback=None,
    fast_mode: bool = False,
    blast_params: dict | None = None,
) -> dict:
    blast_params = blast_params or {}
    try:
        program, database, seq_type = resolve_blast_params(
            sequence,
            program=blast_params.get("program"),
            database=blast_params.get("database"),
            fast_mode=fast_mode,
        )
    except ValueError as e:
        logger.warning("BLAST param resolution failed: %s", e)
        return {"error": str(e), "count": 0, "hits": []}

    try:
        max_hits = int(blast_params.get("max_hits") or 100)
    except (TypeError, ValueError):
        max_hits = 100
    max_hits = max(5, min(max_hits, 100))
    query_accession = (blast_params.get("query_accession") or "").strip()

    if status_callback:
        try:
            await status_callback("submitted_to_ncbi")
        except Exception:
            pass

    # EBI is fast & reliable (~30s) and returns UniProt accessions the rest of
    # the pipeline consumes directly. NCBI chronically stalls (long WAITING
    # even with an API key), so run EBI FIRST and fall back to NCBI.
    ebi_result = await _run_ebi_blast_fallback(sequence, program, database, seq_type, max_hits)
    if ebi_result is not None:
        if status_callback:
            try:
                await status_callback("parsing")
            except Exception:
                pass
        return ebi_result

    # EBI unavailable for this database or failed — try NCBI before failing.
    ncbi_error: str | None = None
    results = await ncbi_blast.run_blast_with_retry(
        sequence,
        retries=2,
        max_wait_seconds=600 if fast_mode else 900,
        database=database,
        program=program,
        hitlist_size=max_hits,
    )

    if "error" not in results:
        parsed = parse_blast_xml(results["raw"])
        if "error" not in parsed:
            if status_callback:
                try:
                    await status_callback("parsing")
                except Exception:
                    pass
            hits = parsed.get("hits", [])[:max_hits]
            return _build_blast_result(
                hits,
                source="ncbi",
                database=database,
                program=program,
                seq_type=seq_type,
                query_accession=query_accession,
                query_length=parsed.get("query_length", 0),
            )
        ncbi_error = parsed["error"]
    else:
        ncbi_error = results["error"]

    logger.warning("EBI BLAST unavailable and NCBI failed (%s)", ncbi_error)
    return {"error": ncbi_error or "BLAST failed via EBI and NCBI", "count": 0, "hits": []}


async def _run_uniprot(top_hit: dict, query_sequence: str | None = None, try_sequence: bool = True) -> dict:
    accession = (top_hit.get("accession") or "").strip()
    if not accession:
        return {"error": "No accession"}
    desc = (top_hit.get("description") or "").strip()
    organism = (top_hit.get("organism") or "").strip()

    # Resolve ANY BLAST-hit accession (RefSeq, GenBank, PDB, Ensembl, ...) to a
    # UniProt accession via the strategy ladder in identifier_resolution:
    #   direct -> xref search (fast) -> name search -> EBI sequence BLAST -> idmapping
    # Exhausting all tiers returns an explicit unresolved/de_novo result (§1).
    try:
        resolved = await resolve_to_uniprot(
            accession=accession,
            sequence=query_sequence,
            description=desc,
            organism=organism or None,
            try_sequence=try_sequence,
        )
    except Exception as e:
        logger.warning("Identifier resolution failed for %s: %s", accession, e)
        resolved = None

    if not resolved or resolved.get("status") != "resolved":
        logger.info("No UniProt mapping for %s, using BLAST data only", accession)
        return {
            "accession": accession,
            "full_name": top_hit.get("description", ""),
            "organism": top_hit.get("organism", ""),
            "gene_names": [],
            "functions": [],
            "keywords": [],
            "subcellular_locations": [],
            "pdb_ids": [],
            "go_terms": [],
            "sequence": "",
            "sequence_length": 0,
            "features": [],
            "resolution": {
                "uniprot_accession": None,
                "method": "de_novo",
                "original_accession": accession,
            },
            "resolved_uniprot": False,
            # BLAST-derived similarity is homolog-grade certainty at best (§1.1)
            "confidence": "homolog",
            "_note": f"No UniProt mapping found for {accession} — showing BLAST-derived data only",
        }

    uniprot_acc = resolved["accession"]
    method = resolved["method"]

    tool = UniprotTool()
    result = await tool.run({"accession": uniprot_acc})
    if "error" in result:
        return {"error": result["error"]}

    return {
        "accession": result.get("accession", uniprot_acc),
        "full_name": result.get("full_name", ""),
        "organism": result.get("organism", ""),
        "gene_names": result.get("gene_names", []),
        "functions": result.get("functions", []),
        "keywords": result.get("keywords", []),
        "subcellular_locations": result.get("subcellular_locations", []),
        "pdb_ids": result.get("pdb_ids", []),
        "go_terms": result.get("go_terms", []),
        "sequence": result.get("sequence", ""),
        "sequence_length": result.get("sequence_length", 0),
        "features": [
            f for f in (result.get("features", []) or [])
            if f.get("type") in ("ACTIVE_SITE", "BINDING", "MUTAGENESIS", "SITE", "MOD_RES")
        ],
        "resolution": {
            "uniprot_accession": uniprot_acc,
            "method": method,
            "original_accession": accession,
        },
        "resolved_uniprot": True,
        "confidence": resolved.get("confidence", "identified"),
    }


async def _run_msa(query_sequence: str, blast_hits: list, alignment_mode: str = "global") -> dict:
    sequences = [("query", query_sequence)]

    for hit in blast_hits[:5]:
        acc = hit.get("accession", "")
        hit_seq = hit.get("hit_alignment", "")

        if acc:
            source = detect_source_from_accession(acc)
            mapped_acc = acc
            if source == "ncbi":
                mapped = await map_refseq_to_uniprot(acc)
                if mapped:
                    mapped_acc = mapped
            try:
                tool = UniprotTool()
                ud = await tool.run({"accession": mapped_acc})
                if "error" not in ud and ud.get("sequence"):
                    clean_seq = "".join(c for c in ud["sequence"] if c.isalpha()).upper()
                    if len(clean_seq) > 10:
                        sequences.append((acc, clean_seq))
                        continue
            except Exception:
                pass

        if hit_seq:
            clean = "".join(c for c in hit_seq if c.isalpha()).upper()
            if len(clean) > 10:
                sequences.append((f"{acc}_aln", clean))

    if len(sequences) < 2:
        return {"error": "Not enough sequences for MSA", "aln_fasta": None, "phylotree": None}

    fasta_lines = []
    for sid, sseq in sequences:
        fasta_lines.append(f">{sid}")
        for i in range(0, len(sseq), 80):
            fasta_lines.append(sseq[i:i + 80])
    fasta_str = "\n".join(fasta_lines)

    try:
        email = settings.NCBI_EMAIL or "bioflow@example.com"
        seq_type = detect_sequence_type(query_sequence) or "protein"
        stype = "protein" if seq_type == "protein" else "dna"
        try:
            # Try local MAFFT first (fast, no network dependency)
            from app.tools.mafft_local import run_local_mafft
            local_result = await asyncio.get_running_loop().run_in_executor(
                None, run_local_mafft, fasta_str, "auto", 1, 300,
            )
            if local_result and local_result.get("aln_fasta"):
                method = "mafft-local"
                aln_fasta = local_result["aln_fasta"]
                phylotree = ""
            else:
                raise ValueError("local MAFFT unavailable or returned empty")
        except Exception:
            try:
                result = await run_ebi_msa_best_effort(
                    sequence=fasta_str,
                    stype=stype,
                    email=email,
                )
                method = result["method"]
                aln_fasta = result["aln_fasta"]
                phylotree = result["phylotree"]
            except Exception as e:
                logger.warning("EBI MSA unavailable (%s) — using in-process fallback", e)
                from app.tools.msa_fallback import progressive_msa
                fallback = await asyncio.get_running_loop().run_in_executor(
                    None, progressive_msa, sequences, stype
                )
                aln_fasta, phylotree = fallback
                method = "in-process fallback"

        payload = {
            "aln_fasta": aln_fasta,
            "phylotree": phylotree,
            "sequence_count": len(sequences),
            "alignment_mode": alignment_mode,
            "method": method,
            "_fallback": method != "clustalo",
        }

        # Local mode: refine query vs the best non-query sequence with an
        # in-process Smith-Waterman alignment so the wizard can show which
        # region actually matches (EBI MSA itself is always global).
        if alignment_mode == "local" and len(sequences) > 1:
            subject_id, subject_seq = sequences[1]
            try:
                payload["pairwise"] = pairwise_align(query_sequence, subject_seq, mode="local")
                payload["pairwise_subject"] = subject_id
            except Exception as e:
                logger.warning("Local pairwise refinement failed: %s", e)

        return payload

    except Exception as e:
        return {"error": str(e), "aln_fasta": None, "phylotree": None}


async def _run_domains(accession: str) -> dict:
    """Run domain analysis using the shared tool module (eliminates code duplication)."""
    try:
        from app.tools.domain_analysis import fetch_interpro_domains
        return await fetch_interpro_domains(accession)
    except Exception as e:
        return {"error": str(e), "uniprot_accession": accession, "sequence_length": 0, "domains": []}


async def _run_denovo_steps(job_id: str, sequence: str, steps: list[str], _mark, context: dict) -> None:
    """Tier-6 branch (techspec.md §1): characterize from sequence alone.

    Runs when BLAST finds no homolog at all. Composition/function hints land
    in the uniprot slot (the annotation slot); MSA/phylo/pathways are marked
    explicitly unavailable rather than left empty.
    """
    import asyncio as _asyncio
    from app.services.de_novo import (
        composition_stats, esmfold_structure, function_hints, interpro_sequence_search,
    )

    unavailable = "Unavailable for de novo sequences — no identified homolog"

    async def _do_annotation():
        bundle = {"_de_novo": True}
        try:
            bundle["composition"] = composition_stats(sequence)
        except Exception as e:
            bundle["composition"] = {"error": str(e)}
        try:
            bundle["function_hints"] = function_hints(sequence)
        except Exception as e:
            bundle["function_hints"] = {"error": str(e)}
        return bundle

    async def _do_domains():
        try:
            return await interpro_sequence_search(sequence)
        except Exception as e:
            logger.warning("De novo InterProScan failed: %s", e)
            return {"error": str(e), "domains": [], "sequence_length": 0}

    async def _do_structure():
        try:
            return await esmfold_structure(sequence)
        except Exception as e:
            logger.warning("De novo ESMFold failed: %s", e)
            return {"structure_available": False, "source": "esmfold", "message": str(e)}

    fan = []
    names = []
    if "uniprot" in steps:
        fan.append(_do_annotation())
        names.append("uniprot")
    if "domains" in steps:
        fan.append(_do_domains())
        names.append("domains")
    if "alphafold" in steps:
        fan.append(_do_structure())
        names.append("alphafold")

    for name in names:
        _mark(name, "running", progress=10)
    results = await _asyncio.gather(*fan, return_exceptions=True)

    for name, res in zip(names, results):
        if isinstance(res, Exception):
            _mark(name, "failed", error=str(res)[:500])
            continue
        ok = (
            res.get("domains") is not None if name == "domains"
            else res.get("structure_available") is True if name == "alphafold"
            else True
        )
        _mark(name, "complete" if ok else "failed", progress=100,
              data=res, error=None if ok else "Prediction returned nothing usable")
        context[name] = res

    # Annotation-database features have no de novo substitute — say so.
    for name in ("msa", "phylo", "pathway_enrichment"):
        if name in steps:
            _mark(name, "failed", error=unavailable)


async def _run_domains_or_denovo(sequence: str, accession: str | None, resolved_uniprot: bool) -> dict:
    """Accession lookup when resolved; InterProScan sequence-search otherwise."""
    if accession and resolved_uniprot:
        return await _run_domains(accession)
    from app.services.de_novo import interpro_sequence_search
    try:
        result = await interpro_sequence_search(sequence)
        result["confidence"] = "de_novo"
        return result
    except Exception as e:
        return {"error": str(e), "domains": [], "sequence_length": 0}


async def _run_alphafold_or_esmfold(
    context: dict, sequence: str, accession: str | None, resolved_uniprot: bool,
) -> dict:
    """AlphaFold DB lookup when resolved; ESMFold ab initio otherwise."""
    if accession and resolved_uniprot:
        result = await _run_alphafold(context)
        return result or {}
    from app.services.de_novo import esmfold_structure
    try:
        return await esmfold_structure(sequence)
    except Exception as e:
        return {"structure_available": False, "source": "esmfold", "message": str(e)}


async def _run_pathway_enrichment(context: dict) -> dict | None:
    gene_names = []
    uniprot = context.get("uniprot", {})
    if isinstance(uniprot, dict):
        gene_names = uniprot.get("gene_names", [])[:20] if isinstance(uniprot.get("gene_names"), list) else []
    if not gene_names:
        blast_data = context.get("blast", {})
        if isinstance(blast_data, dict):
            for hit in (blast_data.get("hits") or [])[:10]:
                words = (hit.get("description", "") or "").replace("(", " ").replace(")", " ").split()
                for w in words:
                    if w.isupper() and len(w) >= 2 and not w.startswith("OS="):
                        gene_names.append(w)
                        break
    if not gene_names:
        return None
    try:
        from app.services.pathway_enrichment import run_enrichment
        result = await run_enrichment(gene_names)
        return result
    except Exception as e:
        logger.warning(f"Pathway enrichment failed: {e}")
        return None


async def _run_alphafold(context: dict) -> dict | None:
    uniprot_data = context.get("uniprot", {})
    accession = uniprot_data.get("accession") if isinstance(uniprot_data, dict) else None
    if not accession:
        return None
    try:
        from app.tools.alphafold import AlphaFoldTool
        result = await AlphaFoldTool().run({"uniprot_accession": accession})
        return result
    except Exception as e:
        logger.warning(f"AlphaFold fetch failed for {accession}: {e}")
        return {"structure_available": False, "message": str(e)}


async def _run_interpret(context: dict) -> dict:
    from app.ai.interpreter import interpret_text
    prompt_context = {
        "blast": context.get("blast", {}),
        "uniprot": context.get("uniprot", {}),
        "alphafold": context.get("alphafold", {}),
        "pathway_enrichment": context.get("pathway_enrichment", {}),
        "query_confidence": context.get("query", {}).get("confidence", "identified"),
    }
    return await interpret_text("protein_analysis", prompt_context)

"""
In-memory pipeline v2 — runs BLAST → UniProt → MSA → Phylo → Domains → Interpretation
in a background thread. Uses a thread-safe dict for job storage.
"""

import asyncio
import logging
import threading
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from litellm import acompletion

from app.config import settings
from app.deps import limiter
from app.services.rate_limit import check_daily_limit_pipelines
from app.integrations.ncbi import blast as ncbi_blast
from app.integrations.ncbi.parser import parse_blast_xml
from app.services.validators import validate_fasta
from app.services.sequence_utils import detect_source_from_accession, map_refseq_to_uniprot, detect_sequence_type
from app.services.blast_config import resolve_blast_params
from app.tools.ebi_msa import EBI_TOOLS, run_ebi_msa
from app.tools.uniprot import UniprotTool
from app.ai.llm_client import llm_client

logger = logging.getLogger(__name__)
router = APIRouter()

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

STEP_ORDER = ["blast", "uniprot", "msa", "phylo", "domains", "pathway_enrichment", "alphafold", "interpret"]


def _get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        return _jobs.get(job_id)


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


@router.post("/run")
async def run_pipeline_v2(request: Request, req: PipelineV2RunRequest):
    validation = validate_fasta(req.sequence, "blast")
    if not validation.valid:
        raise HTTPException(status_code=400, detail=validation.error)

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
            "error": None,
            "created_at": now,
        }

    t = threading.Thread(
        target=_run_pipeline,
        args=(job_id, clean, requested),
        kwargs={"fast_mode": req.fast_mode, "blast_params": blast_params},
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

def _run_pipeline(job_id: str, sequence: str, steps: list[str], fast_mode: bool = False, blast_params: dict | None = None):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            _execute(job_id, sequence, steps, fast_mode=fast_mode, blast_params=blast_params)
        )
    except Exception as e:
        logger.exception(f"[{job_id}] Unhandled pipeline error")
        _set_job_failed(job_id, f"Pipeline error: {e}")
    finally:
        loop.close()
        asyncio.set_event_loop(None)


async def _execute(job_id: str, sequence: str, steps: list[str], status_callback=None, fast_mode: bool = False, blast_params: dict | None = None):
    context: dict = {"sequence": sequence, "length": len(sequence)}

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
    if "blast" in steps:
        await _notify("blast")
        _mark("blast", "running", progress=10)
        result = await _run_blast(
            sequence,
            status_callback=status_callback,
            fast_mode=fast_mode,
            blast_params=blast_params,
        )
        _mark("blast", "complete" if result.get("count", 0) > 0 else "failed", progress=100, data=result)
        context["blast"] = result
        if result.get("count", 0) == 0:
            _failed_step = "blast"
            _failed_error = result.get("error", "No BLAST hits found")

    # ---- Step 2: Fan-out — UniProt, MSA, Pathway run in parallel ----
    #    They all only depend on BLAST results, not on each other.
    blast_data = context.get("blast", {})
    hits = (blast_data.get("hits") if isinstance(blast_data, dict) else []) or []
    top_hit = blast_data.get("top_hit") if isinstance(blast_data, dict) else None

    async def _do_uniprot():
        candidates = ([top_hit] + hits[:5]) if top_hit else hits[:5]
        for candidate in candidates:
            result = await _run_uniprot(candidate)
            if "error" not in result:
                return result
        return result if result else {"error": "No BLAST hits for UniProt lookup"}

    async def _do_msa():
        if not hits:
            return {"error": "No BLAST hits for MSA"}
        return await _run_msa(sequence, hits)

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

    # ---- Step 4: Domains + AlphaFold in parallel (both need UniProt accession) ----
    uniprot_data = context.get("uniprot", {})
    accession = uniprot_data.get("accession") if isinstance(uniprot_data, dict) else None

    post_uniprot = []
    post_uniprot_names = []
    if "domains" in steps and accession and not _failed_step:
        post_uniprot.append(_run_domains(accession))
        post_uniprot_names.append("domains")
    if "alphafold" in steps and accession and not _failed_step:
        post_uniprot.append(_run_alphafold(context))
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
    else:
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["status"] = "complete"
                _jobs[job_id]["context"] = context


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------

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

    results = await ncbi_blast.run_blast_with_retry(
        sequence,
        retries=2,
        max_wait_seconds=600 if fast_mode else 900,
        database=database,
        program=program,
        hitlist_size=max_hits,
    )

    if "error" in results:
        return {"error": results["error"], "count": 0, "hits": []}

    if status_callback:
        try:
            await status_callback("parsing")
        except Exception:
            pass

    parsed = parse_blast_xml(results["raw"])
    if "error" in parsed:
        raise RuntimeError(f"BLAST XML parse failed: {parsed['error']}")

    hits = parsed.get("hits", [])[:max_hits]
    top_hit = hits[0] if hits else None
    query_length = parsed.get("query_length", 0)

    return {
        "count": len(hits),
        "source": "ncbi",
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
            for h in hits[:20]
        ],
    }


async def _run_uniprot(top_hit: dict) -> dict:
    accession = top_hit.get("accession", "")
    if not accession:
        return {"error": "No accession"}

    try:
        source = detect_source_from_accession(accession)
        if source == "ncbi":
            mapped = await map_refseq_to_uniprot(accession)
            if mapped:
                accession = mapped
            else:
                # Could not map to UniProt — try searching by protein name
                desc = top_hit.get("description", "")
                gene_name = desc.split(",")[0].split("[" )[0].strip() if desc else ""
                if gene_name:
                    logger.info("NCBI mapping failed for %s, searching UniProt by name: %s", accession, gene_name)
                    try:
                        async with httpx.AsyncClient(timeout=10) as client:
                            r = await client.get(
                                "https://rest.uniprot.org/uniprotkb/search",
                                params={"query": f"gene:{gene_name} AND reviewed:true", "format": "json", "size": 1},
                            )
                            if r.status_code == 200:
                                data = r.json()
                                results = data.get("results", [])
                                if results:
                                    hit = results[0]
                                    tool = UniprotTool()
                                    result = await tool.run({"accession": hit["primaryAccession"]})
                                    if "error" not in result:
                                        return {
                                            "accession": result.get("accession", ""),
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
                                        }
                    except Exception as e:
                        logger.warning("UniProt name search failed for %s: %s", gene_name, e)

                # Still no UniProt data — return partial data from BLAST hit
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
                    "_note": f"UniProt mapping unavailable for {accession}",
                }

        tool = UniprotTool()
        result = await tool.run({"accession": accession})
        if "error" in result:
            return {"error": result["error"]}

        return {
            "accession": result.get("accession", ""),
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
        }
    except Exception as e:
        logger.warning("UniProt lookup failed for %s: %s", accession, e)
        return {"error": f"UniProt lookup failed: {e}"}


async def _run_msa(query_sequence: str, blast_hits: list) -> dict:
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
        result = await run_ebi_msa(
            base_url=EBI_TOOLS["clustalo"],
            sequence=fasta_str,
            stype=stype,
            email=email,
        )
        return {
            "aln_fasta": result["aln_fasta"],
            "phylotree": result["phylotree"],
            "sequence_count": len(sequences),
        }

    except Exception as e:
        return {"error": str(e), "aln_fasta": None, "phylotree": None}


async def _run_domains(accession: str) -> dict:
    """Run domain analysis using the shared tool module (eliminates code duplication)."""
    try:
        from app.tools.domain_analysis import fetch_interpro_domains
        return await fetch_interpro_domains(accession)
    except Exception as e:
        return {"error": str(e), "uniprot_accession": accession, "sequence_length": 0, "domains": []}


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
    providers = llm_client.get_providers()
    if not providers:
        return {"interpretation": "AI interpretation unavailable: no LLM API keys configured"}

    prompt_context = {
        "blast": context.get("blast", {}),
        "uniprot": context.get("uniprot", {}),
        "alphafold": context.get("alphafold", {}),
        "pathway_enrichment": context.get("pathway_enrichment", {}),
    }

    prompt = llm_client.build_prompt("protein_analysis", prompt_context)
    last_error = None

    for provider in providers:
        try:
            response = await asyncio.wait_for(
                acompletion(
                    model=provider["model"],
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=2000,
                    timeout=25,
                    api_key=provider["api_key"],
                ),
                timeout=30,
            )
            text = response.choices[0].message.content if response.choices else ""
            return {"interpretation": text}
        except asyncio.TimeoutError:
            logger.warning("LLM provider %s timed out", provider["name"])
            last_error = "LLM request timed out"
            continue
        except Exception as e:
            logger.warning("LLM provider %s failed: %s", provider["name"], e)
            last_error = str(e)
            continue

    if "organization_restricted" in str(last_error) or "Organization has been restricted" in str(last_error):
        return {"interpretation": "AI interpretation unavailable: provider restriction. Please try again later."}
    return {"interpretation": f"AI interpretation unavailable: {last_error}"}

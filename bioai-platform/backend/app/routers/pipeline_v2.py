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
from app.services.sequence_utils import detect_source_from_accession, map_refseq_to_uniprot
from app.tools.uniprot import UniprotTool
from app.ai.llm_client import llm_client

logger = logging.getLogger(__name__)
router = APIRouter()

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

STEP_ORDER = ["blast", "uniprot", "msa", "phylo", "domains", "pathway_enrichment", "alphafold", "interpret"]

EBI_CLUSTALO = "https://www.ebi.ac.uk/Tools/services/rest/clustalo"


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


@router.post("/run", dependencies=[Depends(check_daily_limit_pipelines)])
@limiter.limit("10/minute")
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

    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "current_step": None,
            "steps": steps_dict,
            "requested_steps": requested,
            "sequence": clean,
            "error": None,
            "created_at": now,
        }

    t = threading.Thread(target=_run_pipeline, args=(job_id, clean, requested), daemon=True)
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
            "error": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    try:
        await _execute(job_id, sequence, requested, status_callback=status_callback)
    finally:
        job = _get_job(job_id)
        with _jobs_lock:
            _jobs.pop(job_id, None)

    if job and job.get("status") == "failed":
        raise RuntimeError(job.get("error", "Pipeline failed"))

    context: dict = {
        "sequence": sequence,
        "length": len(sequence),
        "query": {
            "sequence": sequence,
            "length": len(sequence),
            "sequence_type": "protein",
        },
    }
    if job:
        for step_name, step_info in job.get("steps", {}).items():
            if step_info.get("data"):
                context[step_name] = step_info["data"]
    return context


# ---------------------------------------------------------------------------
# Background pipeline
# ---------------------------------------------------------------------------

def _run_pipeline(job_id: str, sequence: str, steps: list[str]):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_execute(job_id, sequence, steps))
    except Exception as e:
        logger.exception(f"[{job_id}] Unhandled pipeline error")
        _set_job_failed(job_id, f"Pipeline error: {e}")
    finally:
        loop.close()
        asyncio.set_event_loop(None)


async def _execute(job_id: str, sequence: str, steps: list[str], status_callback=None):
    context: dict = {"sequence": sequence, "length": len(sequence)}

    # Map pipeline steps to frontend status labels
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

    for step in STEP_ORDER:
        if step not in steps:
            continue

        _set_step_status(job_id, step, "running", progress=10)
        if status_callback:
            try:
                await status_callback(_STEP_FRONTEND.get(step, "running"))
            except Exception:
                pass

        try:
            if step == "blast":
                result = await _run_blast(sequence, status_callback=status_callback)
                _set_step_status(job_id, step, "complete" if result.get("count", 0) > 0 else "failed", progress=100, data=result)
                context["blast"] = result

            elif step == "uniprot":
                blast_data = context.get("blast", {})
                hits = (blast_data.get("hits") if isinstance(blast_data, dict) else []) or []
                top_hit = blast_data.get("top_hit") if isinstance(blast_data, dict) else None
                candidates = ([top_hit] + hits[:5]) if top_hit else hits[:5]
                result = None
                for candidate in candidates:
                    result = await _run_uniprot(candidate)
                    if "error" not in result:
                        break
                if result:
                    s = "complete" if "error" not in result else "failed"
                    _set_step_status(job_id, step, s, progress=100, data=result)
                    context["uniprot"] = result
                else:
                    _set_step_status(job_id, step, "failed", error="No BLAST hits for UniProt lookup")

            elif step == "msa":
                blast_data = context.get("blast", {})
                hits = (blast_data.get("hits") if isinstance(blast_data, dict) else []) or []
                if hits:
                    result = await _run_msa(sequence, hits)
                    s = "complete" if result.get("aln_fasta") else "failed"
                    _set_step_status(job_id, step, s, progress=100, data=result)
                    context["msa"] = result
                    if result.get("phylotree"):
                        context.setdefault("phylo_data", {})["phylotree_newick"] = result["phylotree"]
                else:
                    _set_step_status(job_id, step, "failed", error="No BLAST hits for MSA")

            elif step == "phylo":
                newick = None
                msa_data = context.get("msa", {})
                if isinstance(msa_data, dict):
                    newick = msa_data.get("phylotree")
                if not newick:
                    newick = context.get("phylo_data", {}).get("phylotree_newick")
                if newick:
                    _set_step_status(job_id, step, "complete", progress=100, data={"phylotree_newick": newick})
                    context["phylo"] = {"phylotree_newick": newick}
                else:
                    _set_step_status(job_id, step, "failed", error="No phylotree available from MSA")

            elif step == "domains":
                uniprot_data = context.get("uniprot", {})
                accession = uniprot_data.get("accession") if isinstance(uniprot_data, dict) else None
                if accession:
                    result = await _run_domains(accession)
                    s = "complete" if result.get("domains") is not None else "failed"
                    _set_step_status(job_id, step, s, progress=100, data=result)
                    context["domains"] = result
                else:
                    _set_step_status(job_id, step, "failed", error="No UniProt accession for domain lookup")

            elif step == "pathway_enrichment":
                result = await _run_pathway_enrichment(context)
                s = "complete" if result and result.get("pathways") else "failed"
                _set_step_status(job_id, step, s, progress=100, data=result or {})
                context["pathway_enrichment"] = result

            elif step == "alphafold":
                result = await _run_alphafold(context)
                s = "complete" if result else "failed"
                _set_step_status(job_id, step, s, progress=100, data=result or {})
                context["alphafold"] = result

            elif step == "interpret":
                result = await _run_interpret(context)
                s = "complete" if result.get("interpretation") else "failed"
                _set_step_status(job_id, step, s, progress=100, data=result)
                context["interpret"] = result

        except Exception as step_exc:
            logger.warning("[%s] Step %s failed: %s", job_id, step, step_exc)
            _set_step_status(job_id, step, "failed", error=str(step_exc)[:500])

    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id]["status"] = "complete"
            _jobs[job_id]["context"] = context


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------

async def _run_blast(sequence: str, status_callback=None) -> dict:
    if status_callback:
        try:
            await status_callback("submitted_to_ncbi")
        except Exception:
            pass

    submit_result = await ncbi_blast.submit_blast(sequence)
    if "error" in submit_result:
        return {"error": submit_result["error"], "count": 0, "hits": []}

    rid = submit_result["rid"]
    poll_interval = min(submit_result.get("estimated_seconds", 60) / 2, 15)

    if status_callback:
        try:
            await status_callback("polling_ncbi")
        except Exception:
            pass

    for _ in range(40):
        await asyncio.sleep(poll_interval)
        status_result = await ncbi_blast.check_status(rid)
        s = status_result["status"]
        if s == "READY":
            break
        if s in ("ERROR", "FAILED"):
            return {"error": f"NCBI BLAST failed: {s}", "count": 0, "hits": []}
    else:
        return {"error": "NCBI BLAST timed out", "count": 0, "hits": []}

    if status_callback:
        try:
            await status_callback("parsing")
        except Exception:
            pass

    results = await ncbi_blast.fetch_results(rid)
    if "error" in results:
        return {"error": results["error"], "count": 0, "hits": []}

    parsed = parse_blast_xml(results["raw"])
    if "error" in parsed:
        raise RuntimeError(f"BLAST XML parse failed: {parsed['error']}")

    hits = parsed.get("hits", [])
    top_hit = hits[0] if hits else None
    query_length = parsed.get("query_length", 0)

    return {
        "count": len(hits),
        "source": "ncbi",
        "database": "nr",
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
        async with httpx.AsyncClient(timeout=30) as client:
            submit_resp = await client.post(
                f"{EBI_CLUSTALO}/run",
                data={"email": email, "stype": "protein", "sequence": fasta_str},
                headers={"Accept": "text/plain"},
            )
            if submit_resp.status_code != 200:
                return {"error": f"EBI submission failed: {submit_resp.text[:200]}", "aln_fasta": None, "phylotree": None}

            job_id = submit_resp.text.strip()

            for _ in range(120):
                await asyncio.sleep(2)
                sr = await client.get(f"{EBI_CLUSTALO}/status/{job_id}")
                status = sr.text.strip()
                if status == "FINISHED":
                    break
                if status == "ERROR":
                    return {"error": "EBI alignment failed", "aln_fasta": None, "phylotree": None}
            else:
                return {"error": "EBI alignment timed out", "aln_fasta": None, "phylotree": None}

            await asyncio.sleep(1)

            fa_resp = await client.get(f"{EBI_CLUSTALO}/result/{job_id}/fa", headers={"Accept": "text/plain"})
            aln_fasta = fa_resp.text if fa_resp.status_code == 200 else None

            phylotree = None
            for _ in range(3):
                try:
                    tr = await client.get(f"{EBI_CLUSTALO}/result/{job_id}/phylotree", headers={"Accept": "text/plain"})
                    if tr.status_code == 200:
                        phylotree = tr.text
                        break
                except Exception:
                    await asyncio.sleep(1)

        return {"aln_fasta": aln_fasta, "phylotree": phylotree, "sequence_count": len(sequences)}

    except Exception as e:
        return {"error": str(e), "aln_fasta": None, "phylotree": None}


async def _run_domains(accession: str) -> dict:
    try:
        url = f"https://www.ebi.ac.uk/interpro/api/entry/all/protein/UniProt/{accession.upper()}/?format=json&page_size=50"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url)
            if r.status_code == 404:
                return {"uniprot_accession": accession, "sequence_length": 0, "domains": []}
            if r.status_code != 200:
                return {"error": f"InterPro returned {r.status_code}"}
            data = r.json()

        domains: list[dict] = []
        seq_len = 0

        for result in data.get("results", []):
            entry = result.get("metadata", {})
            db = entry.get("source_database", "").upper()
            acc = entry.get("accession", "")
            name_raw = entry.get("name")
            name_str = name_raw if isinstance(name_raw, str) else (
                name_raw.get("name", acc) if isinstance(name_raw, dict) else acc
            )

            for protein in result.get("proteins", []):
                if protein.get("accession", "").upper() != accession.upper():
                    continue
                seq_len = protein.get("protein_length", seq_len)
                for loc in protein.get("entry_protein_locations", []):
                    for fragment in loc.get("fragments", []):
                        domains.append({
                            "accession": acc,
                            "name": name_str,
                            "source_db": db,
                            "start": fragment.get("start", 0),
                            "end": fragment.get("end", 0),
                            "score": loc.get("score"),
                        })

        domains.sort(key=lambda d: d["start"])
        return {"uniprot_accession": accession.upper(), "sequence_length": seq_len, "domains": domains}

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
    if not llm_client.has_api_key():
        return {"interpretation": "AI interpretation unavailable: GROQ_API_KEY not configured"}

    prompt_context = {
        "blast": context.get("blast", {}),
        "uniprot": context.get("uniprot", {}),
        "alphafold": context.get("alphafold", {}),
        "pathway_enrichment": context.get("pathway_enrichment", {}),
    }

    prompt = llm_client.build_prompt("protein_analysis", prompt_context)

    try:
        response = await asyncio.wait_for(
            acompletion(
                model=llm_client.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,
                timeout=25,
                api_key=llm_client.api_key,
            ),
            timeout=30,
        )
        text = response.choices[0].message.content if response.choices else ""
        return {"interpretation": text}
    except asyncio.TimeoutError:
        logger.warning("GROQ interpret step timed out (restricted API key?)")
        return {"interpretation": "AI interpretation unavailable: LLM request timed out"}
    except Exception as e:
        logger.warning("GROQ interpret step failed: %s", e)
        return {"interpretation": f"AI interpretation unavailable: {e}"}

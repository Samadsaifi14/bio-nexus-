"""
Background job executor for bioinformatics pipelines.

For the prototype, uses asyncio.create_task (not Celery) —
sufficient for single-instance. Raw responses are stored
to R2/local before any parsing occurs.
"""

import asyncio
import logging
from typing import Optional

import httpx

from app.config import settings
from app.integrations.ncbi import blast as ncbi_blast
from app.integrations.ncbi.parser import parse_blast_xml
from app.core.storage import store_raw_response, store_result
from app.data.demo_results import get_demo_result

logger = logging.getLogger(__name__)

DEMO_MODE = settings.DEMO_MODE

STEP_STATUSES = [
    "submitted_to_ncbi",
    "polling_ncbi",
    "parsing",
    "interpreting",
    "fetching_alphafold",
    "complete",
]


def _supa_headers() -> dict:
    return {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


async def _patch_job(job_id: str, payload: dict) -> None:
    url = f"{settings.SUPABASE_URL}/rest/v1/jobs?id=eq.{job_id}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.patch(url, headers=_supa_headers(), json=payload)
        if resp.status_code not in (200, 204):
            logger.error(f"[{job_id}] Supabase PATCH {resp.status_code}: {resp.text[:300]}")
    except Exception as e:
        logger.error(f"[{job_id}] Supabase PATCH exception: {e}")


def _matches_demo(sequence: str) -> Optional[dict]:
    from app.data.demo_results import DEMO_SEQUENCES
    seq_clean = "".join(c for c in sequence if c.isalpha()).upper()
    for key, info in DEMO_SEQUENCES.items():
        demo_clean = "".join(c for c in info["sequence"] if c.isalpha()).upper()
        if seq_clean == demo_clean:
            return info
    return None


async def execute_blast_job(job_id: str, sequence: str, database: str = "nr", max_hits: int = 10) -> None:
    steps_completed: list[str] = []

    async def _set_step(step: str, progress_pct: int) -> None:
        steps_completed.append(step)
        await _patch_job(job_id, {
            "status": step,
            "steps_completed": steps_completed,
            "progress_pct": progress_pct,
        })
        logger.info(f"[{job_id}] Step: {step}")

    try:
        await _set_step("submitted_to_ncbi", 10)

        sequence_clean = "".join(c for c in sequence if c.isalpha()).upper()
        seq_for_blast = sequence_clean if len(sequence_clean) > 20 else sequence_clean

        demo_info = _matches_demo(sequence)
        if DEMO_MODE and demo_info:
            logger.info(f"[{job_id}] Demo mode: using cached result for {demo_info['name']}")
            await _set_step("polling_ncbi", 30)
            await asyncio.sleep(1)
            await _set_step("parsing", 50)
            demo_result = get_demo_result(sequence)
            parsed = demo_result if demo_result else {"error": "Demo result not found", "hits": []}
            await _set_step("interpreting", 70)
        else:
            if DEMO_MODE:
                demo_label = _matches_demo(sequence)
                if not demo_label:
                    logger.info(f"[{job_id}] Demo mode ON but sequence doesn't match known demo sequences — falling through to real NCBI call")
            await _set_step("polling_ncbi", 30)

            submit_result = await ncbi_blast.submit_blast(seq_for_blast, database=database)
            if "error" in submit_result:
                raise RuntimeError(f"NCBI submission failed: {submit_result['error']}")

            rid = submit_result["rid"]
            poll_interval = min(submit_result["estimated_seconds"] / 2, 15)
            max_polls = 40

            await _patch_job(job_id, {
                "context_json": {"ncbi_rid": rid, "poll_interval": poll_interval},
            })

            for attempt in range(max_polls):
                await asyncio.sleep(poll_interval)
                status_result = await ncbi_blast.check_status(rid)
                status = status_result["status"]
                if status == "READY":
                    break
                if status in ("ERROR", "FAILED"):
                    raise RuntimeError(f"NCBI BLAST failed with status: {status}")
            else:
                raise RuntimeError("NCBI BLAST timed out")

            await _set_step("parsing", 50)

            results = await ncbi_blast.fetch_results(rid)
            if "error" in results:
                raise RuntimeError(f"NCBI fetch failed: {results['error']}")

            raw_xml = results["raw"]
            await store_raw_response(job_id, "blast", "ncbi_blast", raw_xml, "xml")

            parsed = parse_blast_xml(raw_xml)
            if "error" in parsed:
                raise RuntimeError(f"BLAST XML parse error: {parsed['error']}")

            await _set_step("interpreting", 70)

        await store_result(job_id, "blast_hits", parsed, "json")

        top_hit = parsed["hits"][0] if parsed.get("hits") else None
        context = {
            "query": {
                "sequence": sequence,
                "length": len(sequence_clean),
            },
            "blast": {
                "count": len(parsed.get("hits", [])),
                "source": "demo" if (DEMO_MODE and demo_info) else "ncbi",
                "database": parsed.get("database", "nr"),
                "top_hit": {
                    "accession": top_hit["accession"],
                    "description": top_hit["description"],
                    "evalue": top_hit["evalue"],
                    "evalue_raw": top_hit.get("evalue_raw", str(top_hit["evalue"])),
                    "identity_pct": top_hit["identity_pct"],
                    "bit_score": top_hit["bit_score"],
                    "alignment_length": top_hit.get("alignment_length", 0),
                } if top_hit else None,
                "hits": [
                    {
                        "accession": h["accession"],
                        "description": h["description"],
                        "evalue": h["evalue"],
                        "evalue_raw": h.get("evalue_raw", str(h["evalue"])),
                        "identity_pct": h["identity_pct"],
                        "bit_score": h["bit_score"],
                    }
                    for h in parsed.get("hits", [])[:max_hits]
                ],
            },
        }

        if top_hit:
            try:
                from app.tools.uniprot import UniprotTool
                from app.services.sequence_utils import map_refseq_to_uniprot, detect_source_from_accession
                uniprot = UniprotTool()
                accession = demo_info.get("uniprot_accession", top_hit["accession"]) if (DEMO_MODE and demo_info) else top_hit["accession"]
                source = detect_source_from_accession(accession)
                if source == "ncbi":
                    mapped = await map_refseq_to_uniprot(accession)
                    if mapped:
                        logger.info(f"[{job_id}] Mapped RefSeq {accession} -> UniProt {mapped}")
                        accession = mapped
                uniprot_result = await uniprot.run({"accession": accession})
                if "error" not in uniprot_result:
                    context["uniprot"] = {
                        "accession": uniprot_result.get("accession", ""),
                        "full_name": uniprot_result.get("full_name", ""),
                        "organism": uniprot_result.get("organism", ""),
                        "gene_names": uniprot_result.get("gene_names", []),
                        "functions": uniprot_result.get("functions", []),
                        "keywords": uniprot_result.get("keywords", []),
                        "subcellular_locations": uniprot_result.get("subcellular_locations", []),
                        "pdb_ids": uniprot_result.get("pdb_ids", []),
                        "features": [
                            f for f in (uniprot_result.get("features", []) or [])
                            if f.get("type") in ("ACTIVE_SITE", "BINDING", "MUTAGENESIS")
                        ],
                        "go_terms": uniprot_result.get("go_terms", []),
                        "sequence_length": uniprot_result.get("sequence_length", 0),
                    }
            except Exception as e:
                logger.warning(f"[{job_id}] UniProt fetch failed (non-fatal): {e}")

        alphafold_data = None
        uniprot_id = context.get("uniprot", {}).get("accession")
        if uniprot_id:
            try:
                await _set_step("fetching_alphafold", 85)
                from app.tools.alphafold import AlphaFoldTool
                af_result = await AlphaFoldTool().run({"uniprot_accession": uniprot_id})
                alphafold_data = af_result
            except Exception as e:
                logger.warning(f"[{job_id}] AlphaFold fetch failed for {uniprot_id}: {e}")
                alphafold_data = {"structure_available": False, "message": str(e)}

        context["alphafold"] = alphafold_data

        await _patch_job(job_id, {
            "status": "complete",
            "context_json": context,
            "steps_completed": steps_completed,
            "progress_pct": 100,
        })

        logger.info(f"[{job_id}] Pipeline complete (demo={DEMO_MODE})")

    except Exception as exc:
        logger.error(f"[{job_id}] Pipeline failed: {exc}", exc_info=True)
        await _patch_job(job_id, {
            "status": "failed",
            "error": str(exc),
        })


async def _set_job_failed(job_id: str, message: str) -> None:
    await _patch_job(job_id, {"status": "failed", "error": message})


def run_pipeline_sync(job_id: str, sequence: str, database: str = "nr", max_hits: int = 10) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(execute_blast_job(job_id, sequence, database=database, max_hits=max_hits))
    except Exception:
        logger.exception(f"[{job_id}] FATAL: unhandled exception in background thread")
        try:
            loop.run_until_complete(_set_job_failed(job_id, "Internal pipeline error"))
        except Exception:
            pass
    finally:
        loop.close()
        asyncio.set_event_loop(None)

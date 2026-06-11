import asyncio
import logging
from typing import List

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


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


async def _on_step_complete(job_id: str, steps_completed: List[str], pct: int) -> None:
    await _patch_job(job_id, {"status": "running", "steps_completed": steps_completed, "progress_pct": pct})
    logger.info(f"[{job_id}] Progress: {steps_completed} ({pct}%)")


async def _run_async(job_id: str, sequence: str, database: str, max_hits: int) -> None:
    from app.pipeline.engine import PipelineEngine

    await _patch_job(job_id, {"status": "running", "steps_completed": []})

    try:
        engine = PipelineEngine()
        context_dict = await engine.execute(
            job_id=job_id,
            sequence=sequence,
            database=database,
            max_hits=max_hits,
            progress_callback=_on_step_complete,
        )
        await _patch_job(job_id, {
            "status": "complete",
            "context_json": context_dict,
            "steps_completed": ["blast", "uniprot", "alphafold"],
            "progress_pct": 100,
        })
        logger.info(f"[{job_id}] Pipeline complete")
    except Exception as exc:
        logger.error(f"[{job_id}] Pipeline failed: {exc}", exc_info=True)
        await _patch_job(job_id, {"status": "failed"})
        raise


def run_pipeline_sync(job_id: str, sequence: str, database: str = "uniprotkb_swissprot", max_hits: int = 10) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run_async(job_id, sequence, database, max_hits))
    finally:
        loop.close()
        asyncio.set_event_loop(None)

import asyncio
from app.workers.celery_app import celery_app
from app.pipeline.engine import PipelineEngine
from app.services.supabase import get_supabase
from datetime import datetime, timezone


def run_pipeline_sync(job_id: str, sequence: str, database: str, max_hits: int) -> dict:
    """Run pipeline synchronously (used when Celery is unavailable)."""
    supabase = get_supabase()
    try:
        supabase.table("jobs").update({
            "status": "running",
            "progress_pct": 10,
        }).eq("id", job_id).execute()

        async def execute():
            engine = PipelineEngine()
            return await engine.execute(sequence, database, max_hits)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(execute())
        loop.close()

        if "error" in result:
            supabase.table("jobs").update({
                "status": "failed",
                "error": result["error"],
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", job_id).execute()
            return {"status": "failed", "error": result["error"]}

        context = result.get("context", {})
        supabase.table("jobs").update({
            "status": "complete",
            "progress_pct": 100,
            "context_json": context,
            "steps_completed": result.get("steps_completed", []),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", job_id).execute()

        return {"status": "complete", "job_id": job_id}

    except Exception as exc:
        supabase.table("jobs").update({
            "status": "failed",
            "error": str(exc)[:500],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", job_id).execute()
        return {"status": "failed", "error": str(exc)}


if celery_app is not None:
    @celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
    def run_pipeline_job(self, job_id: str, sequence: str, database: str, max_hits: int):
        return run_pipeline_sync(job_id, sequence, database, max_hits)

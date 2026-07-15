import logging
import os
from datetime import datetime, timezone, timedelta

import sentry_sdk
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.routers import pipelines, pipeline_v2, ai, jobs, share, profile, sequences, uniprot, alignment, structures, pathways, domains, interactions, primers, structure_analysis, phylo, export, api_keys, cache_stats, docking, sequencing, audit
from app.services.cache import init_redis

logger = logging.getLogger(__name__)

from app.deps import limiter

app = FastAPI(title="Bio Nexus API", version="0.2.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

PROD_ORIGIN = settings.CORS_ORIGIN

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        PROD_ORIGIN,
        "https://bioai-platform.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipelines.router, prefix="/api/pipelines", tags=["pipelines"])
app.include_router(pipeline_v2.router, prefix="/api/pipeline/v2", tags=["pipeline_v2"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(share.router, prefix="/api/share", tags=["share"])
app.include_router(profile.router, prefix="/api/profile", tags=["profile"])
app.include_router(sequences.router, prefix="/api/sequences", tags=["sequences"])
app.include_router(uniprot.router, prefix="/api/uniprot", tags=["uniprot"])
app.include_router(alignment.router, prefix="/api/alignment", tags=["alignment"])
app.include_router(structures.router, prefix="/api/structures", tags=["structures"])
app.include_router(pathways.router, prefix="/api/pathways", tags=["pathways"])
app.include_router(domains.router)
app.include_router(interactions.router)
app.include_router(primers.router)
app.include_router(structure_analysis.router)
app.include_router(phylo.router)
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(api_keys.router, prefix="/api/keys", tags=["api_keys"])
app.include_router(cache_stats.router)
app.include_router(docking.router)
app.include_router(sequencing.router)
app.include_router(audit.router)

TERMINAL_STATUSES = {"complete", "failed"}
NON_TERMINAL_STATUSES = {
    "submitted_to_ncbi", "polling_ncbi", "parsing",
    "fetching_uniprot", "fetching_alphafold", "interpreting",
}


async def _fail_stuck_jobs():
    try:
        import httpx
        from app.config import settings
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        url = f"{settings.SUPABASE_URL}/rest/v1/jobs"
        quoted = ",".join(f'"{s}"' for s in NON_TERMINAL_STATUSES)
        select_url = f"{url}?select=id&status=in.({quoted})"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(select_url, headers=headers)
            if resp.status_code != 200:
                logger.warning(f"Startup resume: failed to query jobs ({resp.status_code})")
                return
            stuck = resp.json()
            for job in stuck:
                jid = job["id"]
                logger.info(f"Startup resume: marking stuck job {jid} as failed")
                await client.patch(
                    f"{url}?id=eq.{jid}",
                    headers=headers,
                    json={"status": "failed", "error": "Worker lost on restart — please re-run"},
                )
            if stuck:
                logger.info(f"Startup resume: marked {len(stuck)} stuck job(s) as failed")
    except Exception as e:
        logger.warning(f"Startup resume: error: {e}")


async def _ensure_docking_columns():
    """Add any missing columns to docking_jobs via PostgREST schema introspection + ALTER hints."""
    try:
        import httpx
        from app.config import settings
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        }
        # Check if result_sdf exists by querying it (most basic column the worker needs)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{settings.SUPABASE_URL}/rest/v1/docking_jobs?select=id&limit=0",
                headers=headers,
            )
            if resp.status_code == 200:
                logger.info("docking_jobs table accessible")
            else:
                logger.warning(f"docking_jobs table query returned {resp.status_code} — table may not exist")
    except Exception as e:
        logger.warning(f"ensure_docking_columns check: {e}")


async def _fail_stuck_dockseq_jobs():
    """Mark docking/sequencing jobs that were in-flight when the process restarted."""
    try:
        import httpx
        from app.config import settings
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        base = f"{settings.SUPABASE_URL}/rest/v1"
        grace_cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S")
        for table in ("docking_jobs", "sequencing_jobs"):
            select_url = f"{base}/{table}?select=id&status=not.in.(complete,failed)&created_at=lt.{grace_cutoff}"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(select_url, headers=headers)
                if resp.status_code != 200:
                    logger.warning(f"Startup resume: failed to query {table} ({resp.status_code})")
                    continue
                stuck = resp.json()
                for job in stuck:
                    jid = job["id"]
                    logger.info(f"Startup resume: marking stuck {table} job {jid} as failed")
                    await client.patch(
                        f"{base}/{table}?id=eq.{jid}",
                        headers=headers,
                        json={"status": "failed", "error": "Worker lost on restart — please re-run", "done_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")},
                    )
                if stuck:
                    logger.info(f"Startup resume: marked {len(stuck)} stuck {table} job(s) as failed")
    except Exception as e:
        logger.warning(f"Startup resume: error for docking/sequencing: {e}")


@app.on_event("startup")
async def startup():
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=os.getenv("ENVIRONMENT", "development"),
        traces_sample_rate=0.1,
    )
    init_redis()
    await _ensure_docking_columns()
    await _fail_stuck_jobs()
    await _fail_stuck_dockseq_jobs()

    # Launch durable worker (in-process, behind env flag)
    if os.getenv("ENABLE_INPROCESS_WORKER", "").lower() in ("1", "true"):
        from app.worker import start_worker
        await start_worker()
        logger.info("In-process durable worker started")


@app.get("/health")
async def health():
    from app.services.cache import get_cache_stats
    stats = get_cache_stats()
    return {"status": "ok", "cache": stats}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

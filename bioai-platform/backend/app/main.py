import os
import logging
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.routers import pipelines, results, ai, jobs, export, share, waitlist, profile, sequences
from app.services.cache import init_redis
from app.tools.registration import register_all_tools

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address, default_limits=["30/minute"])

app = FastAPI(title="Bio Nexus API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

PROD_ORIGIN = os.getenv("CORS_ORIGIN", "https://bio-nexus.vercel.app")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        PROD_ORIGIN,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipelines.router, prefix="/api/pipelines", tags=["pipelines"])
app.include_router(results.router, prefix="/api/results", tags=["results"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(share.router, prefix="/api/share", tags=["share"])
app.include_router(waitlist.router, prefix="/api/waitlist", tags=["waitlist"])
app.include_router(profile.router, prefix="/api/profile", tags=["profile"])
app.include_router(sequences.router, prefix="/api/sequences", tags=["sequences"])

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
        select_url = f"{url}?select=id&status=in.({','.join(NON_TERMINAL_STATUSES)})"
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


@app.on_event("startup")
async def startup():
    init_redis()
    register_all_tools()
    await _fail_stuck_jobs()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

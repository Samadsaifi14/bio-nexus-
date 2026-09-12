import logging
import os
import threading
from contextlib import asynccontextmanager
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
from app.logging_config import setup_logging
from app.middleware import RequestIDMiddleware
from app.routers import pipelines, pipeline_v2, ai, jobs, share, profile, sequences, uniprot, alignment, structures, pathways, domains, interactions, primers, structure_analysis, structure_insights, phylo, phylo_insights, export, api_keys, cache_stats, docking, docking_analytics, sequencing, ngs, ngs_v2, ngs_demo, rnaseq_production, audit, admet, md, md_v2, function_predict, seq_tools, castp, swissmodel, structure_predict, structure_prep, structure_export, history, templates, tool_cards, experiments, benchmarks, engines, figure, evidence, publication, datasets, dashboard, reproducibility, paper_artifacts, plugins
from app.services.cache import init_redis

setup_logging()
logger = logging.getLogger(__name__)

from app.deps import limiter

_CONTINUOUS_PAPERS_STOP = threading.Event()


@asynccontextmanager
async def lifespan(app):
    """Initialize request-critical services and explicitly enabled daemons."""
    await _startup_services()

    from app.services.paper_artifacts import start_continuous_thread
    if os.environ.get("BIONEXUS_CONTINUOUS_PAPERS", "0").strip().lower() in ("1", "true", "yes"):
        app.state.continuous_thread = start_continuous_thread(_CONTINUOUS_PAPERS_STOP)
        logger.info("continuous paper generation daemon started")
    else:
        logger.info("continuous paper generation daemon disabled")
    try:
        yield
    finally:
        _CONTINUOUS_PAPERS_STOP.set()


app = FastAPI(title="Bio Nexus API", version="0.2.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(RequestIDMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.CORS_ORIGINS),
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
app.include_router(structure_insights.router)
app.include_router(phylo.router)
app.include_router(phylo_insights.router)
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(api_keys.router, prefix="/api/keys", tags=["api_keys"])
app.include_router(cache_stats.router)
app.include_router(docking.router)
app.include_router(docking_analytics.router)
app.include_router(sequencing.router)
app.include_router(ngs.router)
app.include_router(ngs_v2.router)
app.include_router(ngs_demo.router)
app.include_router(rnaseq_production.router)
app.include_router(audit.router)
app.include_router(admet.router)
app.include_router(md.router)
app.include_router(md_v2.router)
app.include_router(function_predict.router)
app.include_router(seq_tools.router)
app.include_router(castp.router)
app.include_router(swissmodel.router)
app.include_router(structure_predict.router)
app.include_router(structure_export.router)
app.include_router(structure_prep.router)
app.include_router(history.router, prefix="/api/history", tags=["history"])
app.include_router(templates.router, prefix="/api/templates", tags=["templates"])
app.include_router(tool_cards.router, prefix="/api/tools", tags=["tool_cards"])
app.include_router(experiments.router)
app.include_router(benchmarks.router)
app.include_router(engines.router)
app.include_router(figure.router)
app.include_router(evidence.router)
app.include_router(publication.router)
app.include_router(datasets.router)
app.include_router(dashboard.router)
app.include_router(reproducibility.router)
app.include_router(paper_artifacts.router)
app.include_router(plugins.router)

TERMINAL_STATUSES = {"complete", "failed"}
NON_TERMINAL_STATUSES = {"submitted_to_ncbi", "polling_ncbi", "parsing", "fetching_uniprot", "fetching_alphafold", "interpreting"}


async def _fail_stuck_jobs():
    try:
        import httpx
        headers = {"apikey": settings.SUPABASE_SERVICE_ROLE_KEY, "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}", "Content-Type": "application/json", "Prefer": "return=minimal"}
        url = f"{settings.SUPABASE_URL}/rest/v1/jobs"
        quoted = ",".join(f'"{s}"' for s in NON_TERMINAL_STATUSES)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{url}?select=id&status=in.({quoted})", headers=headers)
            if resp.status_code != 200:
                logger.warning("Startup resume: failed to query jobs (%s)", resp.status_code)
                return
            stuck = resp.json()
            for job in stuck:
                await client.patch(f"{url}?id=eq.{job['id']}", headers=headers, json={"status": "failed", "error": "Worker lost on restart — please re-run"})
            if stuck:
                logger.info("Startup resume: marked %d stuck job(s) as failed", len(stuck))
    except Exception as exc:
        logger.warning("Startup resume: error: %s", type(exc).__name__)


async def _ensure_docking_columns():
    try:
        import httpx
        headers = {"apikey": settings.SUPABASE_SERVICE_ROLE_KEY, "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}"}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{settings.SUPABASE_URL}/rest/v1/docking_jobs?select=id&limit=0", headers=headers)
            if resp.status_code == 200:
                logger.info("docking_jobs table accessible")
            else:
                logger.warning("docking_jobs table query returned %s", resp.status_code)
    except Exception as exc:
        logger.warning("docking schema check failed: %s", type(exc).__name__)


async def _fail_stuck_dockseq_jobs():
    try:
        import httpx
        headers = {"apikey": settings.SUPABASE_SERVICE_ROLE_KEY, "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}", "Content-Type": "application/json", "Prefer": "return=minimal"}
        base = f"{settings.SUPABASE_URL}/rest/v1"
        grace_cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S")
        async with httpx.AsyncClient(timeout=10) as client:
            for table in ("docking_jobs", "sequencing_jobs", "ngs_jobs"):
                resp = await client.get(f"{base}/{table}?select=id&status=not.in.(complete,failed)&created_at=lt.{grace_cutoff}", headers=headers)
                if resp.status_code != 200:
                    logger.warning("Startup resume: failed to query %s (%s)", table, resp.status_code)
                    continue
                stuck = resp.json()
                for job in stuck:
                    await client.patch(f"{base}/{table}?id=eq.{job['id']}", headers=headers, json={"status": "failed", "error": "Worker lost on restart — please re-run", "done_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")})
                if stuck:
                    logger.info("Startup resume: marked %d stuck %s job(s) as failed", len(stuck), table)
    except Exception as exc:
        logger.warning("Startup resume failed for docking/sequencing: %s", type(exc).__name__)


def _sentry_filter(event, hint):
    if event.get("exception"):
        exc = event["exception"].get("values", [{}])[0]
        if exc.get("type") == "HTTPException" and "429" in str(exc.get("value", "")):
            return None
    return event


async def _startup_services():
    """Initialize backend services that must be active before requests run."""
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=os.getenv("ENVIRONMENT", "development"),
        traces_sample_rate=0.1,
        send_default_pii=False,
        enable_tracing=True,
        before_send=_sentry_filter,
    )
    init_redis()
    await _ensure_docking_columns()
    await _fail_stuck_jobs()
    await _fail_stuck_dockseq_jobs()
    try:
        import openmm
        logger.info("OpenMM %s available — full MD simulation enabled", openmm.__version__)
    except ImportError:
        logger.warning("OpenMM not available — MD will use the configured fallback path")
    try:
        from app.tools.md_config import verify_ff_solvent_combos
        combos = verify_ff_solvent_combos()
        logger.info("MD force field verification: %d verified force fields", len(combos))
    except Exception as exc:
        logger.warning("MD force field verification failed during startup: %s", type(exc).__name__)
    run_worker_env = os.getenv("RUN_WORKER")
    run_worker = str(run_worker_env).strip().lower() in ("1", "true", "yes") if run_worker_env is not None else os.name != "nt"
    if run_worker:
        from app.worker import start_worker
        await start_worker()
        logger.info("In-process durable worker started")
    else:
        logger.info("In-process durable worker disabled")


@app.get("/health")
async def health():
    """Minimal public liveness response."""
    return {"status": "ok", "version": "0.2.0"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    from app.logging_config import request_id_var
    rid = request_id_var.get("")
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "request_id": rid})
    logger.exception("Unhandled exception")
    sentry_sdk.capture_exception(exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error", "request_id": rid})

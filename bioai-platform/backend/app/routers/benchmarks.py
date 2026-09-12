from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.benchmarking.bbs2 import evaluate_ai_bundle, registry as bbs2_registry
from app.services.auth import require_user_id
from app.services.job_access import owns_job
from app.services.benchmarks import (
    batch_summary,
    get_benchmark,
    list_benchmarks,
    run_benchmark,
)

router = APIRouter(prefix="/api/benchmarks", tags=["benchmarks"])


class RunRequest(BaseModel):
    job_id: str


class AIBenchmarkRequest(BaseModel):
    generated_text: str = ""
    evidence_text: str = ""
    generated_citations: list[str] = []
    allowed_citations: list[str] = []
    claims: list[dict] = []


@router.get("")
async def get_benchmarks(category: str | None = None, limit: int = 100):
    """Persisted benchmark catalog, optionally filtered by category."""
    records = list_benchmarks(category)
    return {"count": len(records), "benchmarks": records[: max(1, min(limit, 100))]}


@router.get("/bbs2")
async def get_bbs2_registry():
    """Versioned BBS-2 benchmark specification and coverage semantics."""
    return bbs2_registry()


@router.post("/bbs2/ai/evaluate")
async def evaluate_bbs2_ai(req: AIBenchmarkRequest):
    """Run deterministic numeric/citation/unsupported-claim fidelity checks."""
    return evaluate_ai_bundle(req.model_dump())


@router.get("/summary")
async def get_summary(category: str | None = None):
    return batch_summary(category)


@router.get("/{benchmark_id}")
async def get_one(benchmark_id: str):
    bench = get_benchmark(benchmark_id)
    if not bench:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return {"benchmark": bench}


@router.post("/{benchmark_id}/run")
async def run(
    benchmark_id: str,
    req: RunRequest,
    user_id: str = Depends(require_user_id),
):
    """Benchmark only a job owned by the authenticated caller."""
    bench = get_benchmark(benchmark_id)
    if not bench:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    if not owns_job(req.job_id, user_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"run": run_benchmark(benchmark_id, req.job_id)}


@router.post("/seed")
async def seed():
    """Catalog seeding is a deployment/maintenance operation, never a public API action."""
    raise HTTPException(status_code=403, detail="Benchmark catalog seeding is disabled through the public API")

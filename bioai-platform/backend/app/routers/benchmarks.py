from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.benchmarks import (
    batch_summary,
    get_benchmark,
    list_benchmarks,
    run_benchmark,
    seed_benchmarks,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/benchmarks", tags=["benchmarks"])


class RunRequest(BaseModel):
    job_id: str


@router.get("")
async def get_benchmarks(category: str | None = None, limit: int = 100):
    """Benchmark catalog (BBS-1 expansion), optionally filtered by category."""
    records = list_benchmarks(category)
    return {"count": len(records), "benchmarks": records[:limit]}


@router.get("/summary")
async def get_summary(category: str | None = None):
    """Per-category pass/fail statistics across recorded benchmark runs."""
    return batch_summary(category)


@router.get("/{benchmark_id}")
async def get_one(benchmark_id: str):
    bench = get_benchmark(benchmark_id)
    if not bench:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return {"benchmark": bench}


@router.post("/{benchmark_id}/run")
async def run(benchmark_id: str, req: RunRequest):
    """Execute a benchmark against the stored context of an existing job.

    Compares measured vs expected within accepted tolerance and records the
    verdict (passed/failed/error) to benchmark_runs.
    """
    bench = get_benchmark(benchmark_id)
    if not bench:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    summary = run_benchmark(benchmark_id, req.job_id)
    return {"run": summary}


@router.post("/seed")
async def seed():
    """Upsert the JSON benchmark catalog (app/data/benchmarks) into the DB."""
    count = seed_benchmarks()
    return {"seeded": count}
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.benchmarking.ai_grounding import evaluate_grounding
from app.benchmarking.bbs2 import registry as bbs2_registry
from app.benchmarking.docking_redock import canonical_redocking_fixture
from app.benchmarking.giab import (
    GermlineBenchmarkPlanError,
    GermlineBenchmarkRequest,
    build_germline_truth_benchmark_plan,
)
from app.benchmarking.validation_claims import validation_claims
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


class GermlineTruthBenchmarkRequest(BaseModel):
    query_vcf: str
    truth_vcf: str
    confident_regions_bed: str
    reference_fasta: str
    query_reference_build: str
    truth_reference_build: str
    truth_set_id: str
    output_prefix: str
    stratification_tsv: str | None = None
    evaluator: str = "hap.py"


@router.get("")
async def get_benchmarks(category: str | None = None, limit: int = 100):
    """Persisted benchmark catalog, optionally filtered by category."""
    records = list_benchmarks(category)
    return {"count": len(records), "benchmarks": records[: max(1, min(limit, 100))]}


@router.get("/bbs2")
async def get_bbs2_registry():
    """Versioned BBS-2 benchmark specification and coverage semantics."""
    return bbs2_registry()


@router.get("/validation-claims")
async def get_validation_claims():
    """Scientific claim ceilings that apply regardless of UI wording."""
    return {
        "claims": validation_claims(),
        "semantics": "execution != reference concordance != independent scientific validation",
    }


@router.get("/docking/redock-fixture")
async def get_redocking_fixture():
    """Canonical BBS-1 redocking fixture; fixture readiness is not a passed benchmark."""
    return canonical_redocking_fixture()


@router.post("/germline/giab/plan")
async def plan_germline_truth_benchmark(req: GermlineTruthBenchmarkRequest):
    """Plan a non-synthetic hap.py truth-set benchmark for an external authorized worker."""
    try:
        request = GermlineBenchmarkRequest(**req.model_dump())
        return build_germline_truth_benchmark_plan(request)
    except GermlineBenchmarkPlanError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/bbs2/ai/evaluate")
async def evaluate_bbs2_ai(req: AIBenchmarkRequest):
    """Run grounding checks without promoting them to biological validation."""
    return evaluate_grounding(req.model_dump())


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

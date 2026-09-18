"""Authenticated RNA-seq count-matrix differential-expression execution."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.rnaseq.expression import (
    ExpressionParameters,
    MAX_COUNTS_BYTES,
    MAX_METADATA_BYTES,
    RnaSeqExpressionError,
    execute_expression_analysis,
    load_manifest,
)
from app.rnaseq.study_scope import (
    CI_SALS_GENES,
    FULL_SALS_GENES,
    FULL_SALS_SAMPLES,
    classify_rnaseq_study_scope,
)
from app.services.auth import require_user_id

router = APIRouter(prefix="/api/ngs/v2/rnaseq/expression", tags=["ngs-v2-rnaseq-expression"])

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "rnaseq"
DEMO_COUNTS = DATA_DIR / "Cer_SALS_every100_validation_subset.tsv"
DEMO_METADATA = DATA_DIR / "Cer_SALS_metadata.tsv"


def _parse_covariates(raw: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _http_error(exc: RnaSeqExpressionError) -> HTTPException:
    status = 503 if "Rscript is not installed" in str(exc) or "storage is unavailable" in str(exc) else 422
    return HTTPException(status_code=status, detail=str(exc))


def _with_study_scope(result: dict) -> dict:
    result["study_scope"] = classify_rnaseq_study_scope(result)
    return result


async def _save_upload(upload: UploadFile, target: Path, max_bytes: int) -> None:
    written = 0
    with target.open("wb") as handle:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                raise HTTPException(status_code=413, detail=f"{upload.filename or 'upload'} exceeds the allowed size.")
            handle.write(chunk)
    if written == 0:
        raise HTTPException(status_code=422, detail=f"{upload.filename or 'upload'} is empty.")


@router.get("/capabilities")
def expression_capabilities():
    rscript = shutil.which("Rscript")
    return {
        "engine": "DESeq2",
        "rscript_available": bool(rscript),
        "workflow": [
            "raw_integer_counts",
            "metadata_alignment",
            "prefilter",
            "median_of_ratios_normalization",
            "vst_qc",
            "pca",
            "sample_distance",
            "negative_binomial_glm",
            "benjamini_hochberg_fdr",
            "ma_plot",
            "volcano_plot",
            "complexheatmap",
        ],
        "study_scope": {
            "bundled_fixture": {
                "genes": CI_SALS_GENES,
                "samples": FULL_SALS_SAMPLES,
                "classification": "CI_REGRESSION_ONLY",
                "supports_biological_claims": False,
            },
            "full_sals_expected_shape": {"genes": FULL_SALS_GENES, "samples": FULL_SALS_SAMPLES},
            "full_study_note": (
                "A matching full SALS upload is retained as a full-study statistical execution with checksums and derived artifacts, "
                "but independent biological interpretation remains required before manuscript-level ALS claims."
            ),
        },
        "privacy": "Uploaded count matrices are processed in a temporary directory. Derived artifacts are stored in a private per-user bucket; raw uploads are not persisted by this route.",
    }


@router.post("/run")
async def run_expression_analysis(
    counts: UploadFile = File(...),
    metadata: UploadFile = File(...),
    condition_column: str = Form("condition"),
    reference_level: str = Form(...),
    test_level: str = Form(...),
    covariates: str = Form(""),
    alpha: float = Form(0.05),
    lfc_threshold: float = Form(1.0),
    min_count: int = Form(10),
    min_samples: int = Form(0),
    top_heatmap_genes: int = Form(40),
    user_id: str = Depends(require_user_id),
):
    params = ExpressionParameters(
        condition_column=condition_column.strip(),
        reference_level=reference_level.strip(),
        test_level=test_level.strip(),
        covariates=_parse_covariates(covariates),
        alpha=alpha,
        lfc_threshold=lfc_threshold,
        min_count=min_count,
        min_samples=min_samples,
        top_heatmap_genes=top_heatmap_genes,
    )
    try:
        params.validate()
    except RnaSeqExpressionError as exc:
        raise _http_error(exc) from exc

    with tempfile.TemporaryDirectory(prefix="bionexus-rnaseq-upload-") as tmp:
        tmpdir = Path(tmp)
        counts_path = tmpdir / "counts.tsv"
        metadata_path = tmpdir / "metadata.tsv"
        await _save_upload(counts, counts_path, MAX_COUNTS_BYTES)
        await _save_upload(metadata, metadata_path, MAX_METADATA_BYTES)
        try:
            return _with_study_scope(execute_expression_analysis(
                user_id=user_id,
                counts_path=counts_path,
                metadata_path=metadata_path,
                params=params,
                source_label="user-upload",
            ))
        except RnaSeqExpressionError as exc:
            raise _http_error(exc) from exc


@router.post("/demo")
def run_cer_sals_demo(user_id: str = Depends(require_user_id)):
    if not DEMO_COUNTS.exists() or not DEMO_METADATA.exists():
        raise HTTPException(status_code=503, detail="The bundled cerebellum SALS validation subset is not installed.")
    params = ExpressionParameters(
        condition_column="condition",
        reference_level="healthy",
        test_level="SALS",
        alpha=0.05,
        lfc_threshold=1.0,
        min_count=10,
        min_samples=8,
        top_heatmap_genes=40,
    )
    try:
        return _with_study_scope(execute_expression_analysis(
            user_id=user_id,
            counts_path=DEMO_COUNTS,
            metadata_path=DEMO_METADATA,
            params=params,
            source_label="bundled-deterministic-every-100th-gene-subset-of-course-supplied-cerebellum-SALS-matrix",
        ))
    except RnaSeqExpressionError as exc:
        raise _http_error(exc) from exc


@router.get("/runs/{run_id}")
def get_expression_run(run_id: str, user_id: str = Depends(require_user_id)):
    try:
        return _with_study_scope(load_manifest(user_id, run_id))
    except RnaSeqExpressionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

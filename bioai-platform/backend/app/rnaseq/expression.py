"""Authenticated DESeq2 execution and private artifact storage for RNA-seq count matrices."""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.supabase import get_supabase

BUCKET = "rnaseq-artifacts"
MAX_COUNTS_BYTES = 60 * 1024 * 1024
MAX_METADATA_BYTES = 5 * 1024 * 1024
R_SCRIPT = Path(__file__).with_name("deseq2_analysis.R")
SAFE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.]*$")
ARTIFACT_CONTENT_TYPES = {
    ".tsv": "text/tab-separated-values; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".pdf": "application/pdf",
    ".png": "image/png",
}


class RnaSeqExpressionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExpressionParameters:
    condition_column: str = "condition"
    reference_level: str = "healthy"
    test_level: str = "SALS"
    covariates: tuple[str, ...] = ()
    alpha: float = 0.05
    lfc_threshold: float = 1.0
    min_count: int = 10
    min_samples: int = 2
    top_heatmap_genes: int = 40

    def validate(self) -> None:
        if not SAFE_NAME.fullmatch(self.condition_column):
            raise RnaSeqExpressionError("Condition column must use letters, numbers, underscore or dot and start with a letter.")
        for covariate in self.covariates:
            if not SAFE_NAME.fullmatch(covariate):
                raise RnaSeqExpressionError(f"Unsupported covariate name: {covariate}")
        if self.reference_level == self.test_level:
            raise RnaSeqExpressionError("Reference and test levels must differ.")
        if not 0 < self.alpha < 1:
            raise RnaSeqExpressionError("alpha must be between 0 and 1.")
        if self.lfc_threshold < 0:
            raise RnaSeqExpressionError("lfc_threshold must be non-negative.")
        if self.min_count < 0:
            raise RnaSeqExpressionError("min_count must be non-negative.")
        if self.min_samples < 1:
            raise RnaSeqExpressionError("min_samples must be at least 1.")
        if not 2 <= self.top_heatmap_genes <= 500:
            raise RnaSeqExpressionError("top_heatmap_genes must be between 2 and 500.")


def _safe_user_key(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:32]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_bucket() -> None:
    sb = get_supabase()
    try:
        buckets = sb.storage.list_buckets() or []
        names = {getattr(bucket, "name", None) or (bucket.get("name") if isinstance(bucket, dict) else None) for bucket in buckets}
        if BUCKET not in names:
            sb.storage.create_bucket(BUCKET, options={"public": False})
    except Exception as exc:
        raise RnaSeqExpressionError(f"Private RNA-seq artifact storage is unavailable ({type(exc).__name__}).") from exc


def _upload_bytes(path: str, data: bytes, content_type: str) -> None:
    sb = get_supabase()
    sb.storage.from_(BUCKET).upload(path, data, {"content-type": content_type, "upsert": "true"})


def _signed_url(path: str, expires_in: int = 3600) -> str:
    sb = get_supabase()
    response = sb.storage.from_(BUCKET).create_signed_url(path, expires_in)
    if isinstance(response, dict):
        return str(response.get("signedURL") or response.get("signedUrl") or response.get("signed_url") or "")
    return str(getattr(response, "signed_url", "") or getattr(response, "signedURL", ""))


def _artifact_entry(filename: str, data: bytes) -> dict[str, Any]:
    """Return durable artifact metadata only; access URLs are issued on read."""
    return {
        "name": filename,
        "kind": Path(filename).stem,
        "content_type": ARTIFACT_CONTENT_TYPES.get(Path(filename).suffix.lower(), mimetypes.guess_type(filename)[0] or "application/octet-stream"),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _hydrate_manifest(manifest: dict[str, Any], prefix: str) -> dict[str, Any]:
    """Attach short-lived owner access URLs without mutating stored provenance."""
    hydrated = json.loads(json.dumps(manifest))
    for artifact in hydrated.get("artifacts", []):
        artifact["url"] = _signed_url(f"{prefix}/{artifact['name']}")
    hydrated["manifest_url"] = _signed_url(f"{prefix}/manifest.json")
    return hydrated


def _run_r(counts_path: Path, metadata_path: Path, outdir: Path, params: ExpressionParameters, timeout_seconds: int = 600) -> dict[str, Any]:
    rscript = shutil.which(os.environ.get("BIONEXUS_RSCRIPT", "Rscript"))
    if not rscript:
        raise RnaSeqExpressionError("Rscript is not installed in the backend runtime; DESeq2 execution is unavailable.")
    if not R_SCRIPT.exists():
        raise RnaSeqExpressionError("Bundled DESeq2 execution script is missing.")

    argv = [
        rscript,
        str(R_SCRIPT),
        str(counts_path),
        str(metadata_path),
        str(outdir),
        params.condition_column,
        params.reference_level,
        params.test_level,
        ",".join(params.covariates),
        str(params.alpha),
        str(params.lfc_threshold),
        str(params.min_count),
        f"{params.min_samples}:{params.top_heatmap_genes}",
    ]
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RnaSeqExpressionError(f"DESeq2 execution exceeded {timeout_seconds} seconds.") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "DESeq2 failed").strip().splitlines()[-1]
        raise RnaSeqExpressionError(f"DESeq2 execution failed: {detail[:500]}")

    summary_path = outdir / "analysis_summary.json"
    if not summary_path.exists():
        raise RnaSeqExpressionError("DESeq2 completed without emitting analysis_summary.json.")
    try:
        return json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RnaSeqExpressionError("DESeq2 summary artifact is invalid JSON.") from exc


def execute_expression_analysis(
    *,
    user_id: str,
    counts_path: Path,
    metadata_path: Path,
    params: ExpressionParameters,
    source_label: str,
) -> dict[str, Any]:
    params.validate()
    if counts_path.stat().st_size > MAX_COUNTS_BYTES:
        raise RnaSeqExpressionError("Count matrix exceeds the 60 MB analysis limit.")
    if metadata_path.stat().st_size > MAX_METADATA_BYTES:
        raise RnaSeqExpressionError("Metadata file exceeds the 5 MB analysis limit.")

    run_id = str(uuid.uuid4())
    counts_sha256 = sha256_file(counts_path)
    metadata_sha256 = sha256_file(metadata_path)

    with tempfile.TemporaryDirectory(prefix="bionexus-rnaseq-") as tmp:
        outdir = Path(tmp) / "results"
        outdir.mkdir(parents=True, exist_ok=True)
        summary = _run_r(counts_path, metadata_path, outdir, params)

        provenance = {
            "run_id": run_id,
            "source_label": source_label,
            "counts_sha256": counts_sha256,
            "metadata_sha256": metadata_sha256,
            "condition_column": params.condition_column,
            "reference_level": params.reference_level,
            "test_level": params.test_level,
            "covariates": list(params.covariates),
            "alpha": params.alpha,
            "lfc_threshold": params.lfc_threshold,
            "min_count": params.min_count,
            "min_samples": params.min_samples,
            "top_heatmap_genes": params.top_heatmap_genes,
            "execution": "Rscript + DESeq2 + ComplexHeatmap",
            "claim_boundary": "Deterministic statistical output; biological interpretation and external validation remain separate.",
        }
        manifest = {
            "run_id": run_id,
            "state": "SUCCEEDED",
            "summary": summary,
            "provenance": provenance,
            "artifacts": [],
        }
        (outdir / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")

        _ensure_bucket()
        prefix = f"{_safe_user_key(user_id)}/{run_id}"
        artifacts: list[dict[str, Any]] = []
        for file_path in sorted(outdir.iterdir()):
            if not file_path.is_file() or file_path.name == "manifest.json":
                continue
            data = file_path.read_bytes()
            storage_path = f"{prefix}/{file_path.name}"
            _upload_bytes(storage_path, data, ARTIFACT_CONTENT_TYPES.get(file_path.suffix.lower(), "application/octet-stream"))
            artifacts.append(_artifact_entry(file_path.name, data))

        manifest["artifacts"] = artifacts
        manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
        manifest_path = f"{prefix}/manifest.json"
        _upload_bytes(manifest_path, manifest_bytes, "application/json")
        return _hydrate_manifest(manifest, prefix)


def load_manifest(user_id: str, run_id: str) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", run_id):
        raise RnaSeqExpressionError("Invalid RNA-seq run identifier.")
    prefix = f"{_safe_user_key(user_id)}/{run_id}"
    sb = get_supabase()
    try:
        raw = sb.storage.from_(BUCKET).download(f"{prefix}/manifest.json")
    except Exception as exc:
        raise RnaSeqExpressionError("RNA-seq result was not found for this user.") from exc
    if not isinstance(raw, (bytes, bytearray)):
        raise RnaSeqExpressionError("RNA-seq manifest could not be read.")
    manifest = json.loads(bytes(raw).decode("utf-8"))
    return _hydrate_manifest(manifest, prefix)

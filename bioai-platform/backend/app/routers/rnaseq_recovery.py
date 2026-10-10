"""Reviewed archives, durable expression jobs and production quantifier handoff."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.rnaseq import durable
from app.rnaseq.count_recovery import MAX_BYTES, archive_members, assemble_counts, safe_member
from app.rnaseq.geo_counts import GeoCountsError, parse_matrix, count_file_issue
from app.rnaseq.input_contract import CountOrigin
from app.rnaseq.expression import ExpressionParameters, RnaSeqExpressionError
from app.routers.rnaseq_expression import _save_upload
from app.services.auth import require_user_id

router = APIRouter(prefix="/api/ngs/v2/rnaseq/recovery", tags=["rnaseq-recovery"])


async def geo_files(accession: str, filenames: list[str]):
    import httpx
    from app.rnaseq.geo_counts import fetch_series, _get_limited
    if not filenames or len(filenames) > 64 or len(set(filenames)) != len(filenames):
        raise GeoCountsError("Select up to 64 distinct GEO supplements")
    async with httpx.AsyncClient(timeout=45) as client:
        series = await fetch_series(client, accession)
        if series.get("workflow_issue"):
            raise GeoCountsError(series["workflow_issue"])
        listed = {item["name"]: item for item in series["files"]}
        files = {}; checksums = {}; total = 0
        for name in filenames:
            if name not in listed:
                raise GeoCountsError("Select only files listed by this GEO Series")
            body = await _get_limited(client, listed[name]["url"], limit=MAX_BYTES - total)
            total += len(body)
            checksums[name] = hashlib.sha256(body).hexdigest()
            members = archive_members(body, name) if name.lower().endswith((".zip", ".tar", ".tar.gz", ".tgz")) else {name: body}
            for member, content in members.items():
                key = name + "::" + member
                files[key] = content
            if sum(len(value) for value in files.values()) > MAX_BYTES or len(files) > 256:
                raise GeoCountsError("Selected supplements exceed recovery limits")
        return files, {"accession": series["accession"], "source_sha256": checksums,
                       "source_urls": {name: listed[name]["url"] for name in filenames}}


class GeoRecoverySelection(BaseModel):
    accession: str
    filenames: list[str]


@router.post("/geo/inspect")
async def inspect_geo(payload: GeoRecoverySelection, user: str = Depends(require_user_id)):
    try:
        files, source = await geo_files(payload.accession, payload.filenames)
        return {"source": source, "members": [{"name": name, "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(), "count_issue": count_file_issue(name.rsplit("::", 1)[-1]),
            "salmon_candidate": name.endswith("quant.sf")} for name, body in files.items()]}
    except GeoCountsError as exc:
        raise failure(exc) from exc


def failure(exc):
    return HTTPException(503 if "unavailable" in str(exc).lower() else 422, str(exc))


@router.get("/capabilities")
def capabilities():
    return {"counts": durable.readiness(), "salmon": durable.readiness(True),
            "archive_limit_bytes": MAX_BYTES, "inference_gate": "QC_REVIEW"}


@router.post("/inspect")
async def inspect(archive: UploadFile = File(...), user: str = Depends(require_user_id)):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "archive"
        await _save_upload(archive, path, MAX_BYTES)
        try:
            files = archive_members(path.read_bytes(), archive.filename or "")
        except GeoCountsError as exc:
            raise failure(exc) from exc
    return {
        "members": [{"name": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                     "count_issue": count_file_issue(name), "salmon_candidate": name.endswith("quant.sf")}
                    for name, body in files.items()]}


def prepare_salmon(files: dict[str, bytes], mapping: dict[str, str], tx2gene: bytes) -> tuple[bytes, dict[str, bytes]]:
    if len(mapping) < 4 or len(set(mapping.values())) != len(mapping):
        raise GeoCountsError("Map at least four distinct sample quantifications")
    output = io.StringIO(); writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(["sample", "quant_file"])
    extras = {"tx2gene.tsv": tx2gene}
    for index, (member, sample) in enumerate(mapping.items()):
        if member not in files or not member.endswith("quant.sf") or not sample.strip():
            raise GeoCountsError("Select actual quant.sf files and explicit sample names")
        name = f"quant_{index}.sf"
        extras[name] = files[member]; writer.writerow([sample, name])
    return output.getvalue().encode(), extras


def submit_prepared(user, counts: bytes, metadata: bytes, params, source, input_kind="raw_counts", extras=None):
    with tempfile.TemporaryDirectory() as folder:
        counts_path = Path(folder) / "counts.tsv"; counts_path.write_bytes(counts)
        metadata_path = Path(folder) / "metadata.tsv"; metadata_path.write_bytes(metadata)
        return durable.enqueue(user, counts_path, metadata_path, params, source, input_kind=input_kind, extras=extras)


@router.post("/submit")
async def submit(
    data: UploadFile = File(...), metadata: UploadFile = File(...),
    origin: str = Form(...), parameters: str = Form(...),
    mapping: str = Form("{}"), matrix_member: str = Form(""),
    tx2gene: UploadFile | None = File(None), user: str = Depends(require_user_id),
):
    try:
        evidence = CountOrigin.model_validate_json(origin); source = evidence.check()
        params = ExpressionParameters(**json.loads(parameters)); params.validate()
        selected = json.loads(mapping)
        if not isinstance(selected, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in selected.items()):
            raise GeoCountsError("File-to-sample mapping must be a string object")
        with tempfile.TemporaryDirectory() as folder:
            data_path = Path(folder) / "data"; meta_path = Path(folder) / "metadata"
            await _save_upload(data, data_path, MAX_BYTES); await _save_upload(metadata, meta_path, 5 * 1024 * 1024)
            body = data_path.read_bytes(); name = data.filename or ""
            source.update({"source_filename": name, "source_sha256": hashlib.sha256(body).hexdigest()})
            files = archive_members(body, name) if name.lower().endswith((".zip", ".tar", ".tar.gz", ".tgz")) else {name: body}
            extras = None
            if evidence.kind == "salmon":
                if not tx2gene:
                    raise GeoCountsError("Salmon import requires the matching tx2gene TSV")
                mapping_path = Path(folder) / "tx2gene.tsv"
                await _save_upload(tx2gene, mapping_path, MAX_BYTES)
                counts, extras = prepare_salmon(files, selected, mapping_path.read_bytes())
                source["file_to_sample"] = selected
            elif selected:
                counts, audit = assemble_counts(files, selected); source.update(audit)
            else:
                member = matrix_member or name
                if member not in files:
                    raise GeoCountsError("Select a matrix member in the archive")
                matrix = parse_matrix(files[member], member, [])
                text = io.StringIO(); writer = csv.writer(text, delimiter="\t", lineterminator="\n")
                writer.writerow(["gene", *matrix["columns"]]); writer.writerows(matrix["rows"])
                counts = text.getvalue().encode()
                source["matrix_member"] = member
            metadata_bytes = meta_path.read_bytes()
            require_units(metadata_bytes)
            return await run_in_threadpool(submit_prepared, user, counts, metadata_bytes, params, source, evidence.kind, extras)
    except (ValueError, TypeError, GeoCountsError, RnaSeqExpressionError) as exc:
        raise failure(exc) from exc


@router.post("/geo/submit")
async def submit_geo(source_selection: str = Form(...), origin: str = Form(...), parameters: str = Form(...),
    metadata: UploadFile = File(...), source_sha256: str = Form(...), mapping: str = Form("{}"),
    matrix_member: str = Form(""), user: str = Depends(require_user_id)):
    try:
        selection = GeoRecoverySelection.model_validate_json(source_selection)
        evidence = CountOrigin.model_validate_json(origin)
        if evidence.kind != "raw_counts":
            raise GeoCountsError("GEO supplement recovery imports raw counts; use production import for Salmon")
        origin_record = evidence.check()
        files, source = await geo_files(selection.accession, selection.filenames)
        if source["source_sha256"] != json.loads(source_sha256):
            raise GeoCountsError("GEO supplements changed since inspection; inspect again")
        selected = json.loads(mapping)
        # Keep only the member suffix for filename classification, but retain exact source identities.
        if not isinstance(selected, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in selected.items()):
            raise GeoCountsError("File-to-sample mapping must be a string object")
        if selected:
            renamed = {f"sample_{index}_" + name.rsplit("::", 1)[-1].rsplit("/", 1)[-1]: files[name]
                       for index, name in enumerate(selected) if name in files}
            renamed_mapping = {f"sample_{index}_" + name.rsplit("::", 1)[-1].rsplit("/", 1)[-1]: sample
                               for index, (name, sample) in enumerate(selected.items())}
            counts, audit = assemble_counts(renamed, renamed_mapping)
            source.update(audit); source["reviewed_source_mapping"] = selected
        else:
            if matrix_member not in files:
                raise GeoCountsError("Choose a reviewed cohort matrix member")
            matrix = parse_matrix(files[matrix_member], matrix_member.rsplit("::", 1)[-1], [])
            output = io.StringIO(); writer = csv.writer(output, delimiter="\t", lineterminator="\n")
            writer.writerow(["gene", *matrix["columns"]]); writer.writerows(matrix["rows"])
            counts = output.getvalue().encode(); source["matrix_member"] = matrix_member
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "metadata"; await _save_upload(metadata, path, 5 * 1024 * 1024)
            require_units(path.read_bytes())
            return await run_in_threadpool(submit_prepared, user, counts, path.read_bytes(), ExpressionParameters(**json.loads(parameters)),
                                          {**origin_record, **source})
    except (ValueError, TypeError, KeyError, RnaSeqExpressionError) as exc:
        raise failure(exc) from exc


def require_units(metadata: bytes):
    try:
        rows = list(csv.DictReader(io.StringIO(metadata.decode("utf-8-sig")), delimiter="\t"))
        if not rows or any(not row.get("experimental_unit", "").strip() for row in rows):
            raise GeoCountsError("Metadata needs a reviewed experimental_unit for every sample")
    except UnicodeError as exc:
        raise GeoCountsError("Metadata must use UTF-8") from exc


class QcApproval(BaseModel):
    reviewed: bool
    checkpoint_sha256: str


@router.get("/jobs/{job_id}")
def job_status(job_id: str, user: str = Depends(require_user_id)):
    try:
        return durable.status(job_id, user)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Job not found") from exc
    except RnaSeqExpressionError as exc:
        raise failure(exc) from exc


@router.post("/jobs/{job_id}/approve")
def approve(job_id: str, payload: QcApproval, user: str = Depends(require_user_id)):
    try:
        if not payload.reviewed:
            raise RnaSeqExpressionError("Review PCA, sample distance and experimental design before inference")
        return durable.approve(job_id, user, payload.checkpoint_sha256)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Job not found") from exc
    except RnaSeqExpressionError as exc:
        raise failure(exc) from exc


@router.post("/production/{run_id}/import")
async def import_production(run_id: str, metadata: UploadFile = File(...), tx2gene: UploadFile = File(...),
    mapping: str = Form(...), origin: str = Form(...), parameters: str = Form(...),
    read_qc_reviewed: bool = Form(False), user: str = Depends(require_user_id)):
    """Import selected Salmon objects only from the authenticated owner's completed run."""
    from app.ngs.execution import get_run
    from app.ngs.rnaseq_resources import validate_owned_output
    try:
        record = await run_in_threadpool(get_run, run_id, user)
        validate_owned_output(record["outdir"], user)
        if record["state"] != "SUCCEEDED" or record["workflow"] != "nf-core/rnaseq" or not read_qc_reviewed:
            raise GeoCountsError("Require a completed RNA-seq run and reviewed read/alignment QC")
        selected = json.loads(mapping)
        evidence = CountOrigin.model_validate_json(origin)
        if evidence.kind != "salmon":
            raise GeoCountsError("Production bridge currently imports Salmon quant.sf via tximport")
        source = evidence.check(); source.update({"production_run_id": run_id, "workflow_revision": record["revision"],
            "command_sha256": record.get("command_sha256"), "read_qc_reviewed": True})
        files = await run_in_threadpool(production_files, record["outdir"], selected)
        with tempfile.TemporaryDirectory() as folder:
            meta = Path(folder) / "metadata"; tx = Path(folder) / "tx"
            await _save_upload(metadata, meta, 5 * 1024 * 1024); await _save_upload(tx2gene, tx, MAX_BYTES)
            require_units(meta.read_bytes())
            counts, extras = prepare_salmon(files, selected, tx.read_bytes())
            source["selected_quant_sha256"] = {name: hashlib.sha256(body).hexdigest() for name, body in files.items()}
            return await run_in_threadpool(submit_prepared, user, counts, meta.read_bytes(), ExpressionParameters(**json.loads(parameters)), source, "salmon", extras)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Production run or selected artifact not found") from exc
    except (ValueError, TypeError, RuntimeError, RnaSeqExpressionError) as exc:
        raise failure(exc) from exc


def production_files(outdir: str, mapping: dict) -> dict[str, bytes]:
    if not isinstance(mapping, dict) or not mapping or len(mapping) > 256 or any(not isinstance(k, str) or not isinstance(v, str) for k, v in mapping.items()):
        raise GeoCountsError("Invalid production file selection")
    result = {}; total = 0
    for member in mapping:
        safe_member(member)
        if not member.endswith("quant.sf"):
            raise GeoCountsError("Select Salmon quant.sf artifacts")
        if outdir.startswith("s3://"):
            from urllib.parse import urlparse
            import boto3
            from app.config import settings
            parsed = urlparse(outdir)
            client = boto3.client("s3", region_name=settings.NGS_AWS_REGION or None)
            response = client.get_object(Bucket=parsed.netloc, Key=parsed.path.strip("/") + "/" + member)
            with response["Body"] as stream:
                body = stream.read(MAX_BYTES - total + 1)
        else:
            path = (Path(outdir).resolve() / member).resolve()
            if not path.is_relative_to(Path(outdir).resolve()):
                raise GeoCountsError("Artifact escapes production output directory")
            with path.open("rb") as stream:
                body = stream.read(MAX_BYTES - total + 1)
        total += len(body)
        if total > MAX_BYTES:
            raise GeoCountsError("Selected quantifications exceed the 60 MB import limit")
        result[member] = body
    return result

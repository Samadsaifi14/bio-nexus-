"""Reviewed executor resources and owner-specific production namespaces."""
from __future__ import annotations

import csv
import hashlib
import os
import io
from pathlib import Path

from app.config import settings


def namespace(user: str) -> str:
    return hashlib.sha256(user.encode()).hexdigest()[:32]


def _below(value: str, base: str) -> bool:
    if value.startswith("s3://"):
        return base.startswith("s3://") and value.startswith(base.rstrip("/") + "/") and ".." not in value.split("/")
    return Path(value).is_absolute() and Path(value).resolve().is_relative_to(Path(base).resolve())


def validate_owned_output(outdir: str, user: str) -> None:
    if outdir.startswith("s3://"):
        base = os.environ.get("BIONEXUS_RNASEQ_S3_OUTPUT_ROOT", "")
        if not base.startswith("s3://"):
            raise RuntimeError("RNA-seq S3 output storage is unavailable: configure BIONEXUS_RNASEQ_S3_OUTPUT_ROOT")
        base = base.rstrip("/") + "/" + namespace(user)
    else:
        base = str(Path(settings.NGS_RUN_ROOT).resolve() / namespace(user))
        if Path(base).is_relative_to(Path("/tmp")) or Path(base).is_relative_to(Path("/var/tmp")):
            raise RuntimeError("RNA-seq durable output is unavailable: configure NGS_RUN_ROOT on persistent storage")
    if not _below(outdir, base) or outdir.rstrip("/") == base.rstrip("/"):
        raise RuntimeError(f"Use a distinct run output below your private namespace: {base}/")


def validate_submission(request, user: str) -> None:
    record_root = Path(settings.NGS_RUN_ROOT).resolve()
    if record_root.is_relative_to(Path("/tmp")) or record_root.is_relative_to(Path("/var/tmp")):
        raise RuntimeError("Durable production records are unavailable: mount persistent NGS_RUN_ROOT")
    validate_owned_output(request.outdir, user)
    input_root = os.environ.get("BIONEXUS_RNASEQ_S3_INPUT_ROOT", "") if request.samplesheet_path.startswith("s3://") else settings.NGS_INPUT_ROOT
    if not input_root:
        raise RuntimeError("RNA-seq input storage is unavailable")
    private_input = input_root.rstrip("/") + "/" + namespace(user)
    if not _below(request.samplesheet_path, private_input):
        raise RuntimeError(f"Stage the reviewed sample sheet below your private input namespace: {private_input}/")
    if request.custom_config:
        trusted = os.environ.get("BIONEXUS_RNASEQ_CONFIG_ROOT", "")
        if not trusted or not _below(request.custom_config, trusted):
            raise RuntimeError("Select a configuration from administrator-reviewed BIONEXUS_RNASEQ_CONFIG_ROOT")
    for reference in (request.fasta, request.gtf):
        if reference and not _below(reference, input_root):
            raise RuntimeError("Custom references must be staged within the configured input resource root")
    if request.samplesheet_path.startswith("s3://"):
        from urllib.parse import urlparse
        import boto3
        parsed = urlparse(request.samplesheet_path)
        try:
            response = boto3.client("s3", region_name=settings.NGS_AWS_REGION or None).get_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"))
            with response["Body"] as stream:
                body = stream.read(5 * 1024 * 1024 + 1)
        except Exception as exc:
            raise RuntimeError("Reviewed S3 sample sheet is unavailable") from exc
    else:
        path = Path(request.samplesheet_path)
        if not path.is_file() or path.stat().st_size > 5 * 1024 * 1024:
            raise RuntimeError("Reviewed sample sheet is absent or exceeds 5 MB")
        body = path.read_bytes()
    if len(body) > 5 * 1024 * 1024:
        raise RuntimeError("Sample sheet exceeds 5 MB")
    try:
        rows = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))
    except UnicodeError as exc:
        raise RuntimeError("Sample sheet must use UTF-8") from exc
    if not rows or len(rows) > 10000:
        raise RuntimeError("Sample sheet is empty or exceeds 10,000 libraries")
    for row in rows:
        if not row.get("sample", "").strip() or row.get("strandedness") not in {"auto", "unstranded", "forward", "reverse"}:
            raise RuntimeError("Sample sheet requires sample IDs and valid sample-level strandedness")
        if not row.get("fastq_1"):
            raise RuntimeError("Every sample requires fastq_1")
        for read in (row.get("fastq_1"), row.get("fastq_2")):
            if read and not _below(read, private_input):
                raise RuntimeError("FASTQ paths must remain within the owner's staged input namespace")

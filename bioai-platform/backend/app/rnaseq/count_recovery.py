"""Bounded archive inspection and explicit per-sample raw-count assembly.

Archives are read in memory, never extracted. Missing genes are not filled with
zero. The caller must review common counting method and annotation provenance.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import tarfile
import zipfile
from pathlib import PurePosixPath

from app.rnaseq.geo_counts import GeoCountsError, count_file_issue

MAX_BYTES = 60 * 1024 * 1024
MAX_MEMBERS = 256


def safe_member(name: str) -> str:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise GeoCountsError("Archive contains an unsafe member path.")
    return str(path)


def archive_members(payload: bytes, filename: str) -> dict[str, bytes]:
    if len(payload) > MAX_BYTES:
        raise GeoCountsError("Recovery archive exceeds 60 MB.")
    result: dict[str, bytes] = {}
    total = 0
    def add(name, size, handle):
        nonlocal total
        name = safe_member(name)
        if name in result or len(result) >= MAX_MEMBERS or size < 0 or total + size > MAX_BYTES:
            raise GeoCountsError("Archive has duplicate members or exceeds inspection limits.")
        body = handle.read(MAX_BYTES - total + 1)
        total += len(body)
        if len(body) != size or total > MAX_BYTES:
            raise GeoCountsError("Archive exceeds decompression limits.")
        result[name] = body
    try:
        if filename.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                if len(archive.infolist()) > MAX_MEMBERS:
                    raise GeoCountsError("Too many archive entries.")
                for item in archive.infolist():
                    if item.is_dir():
                        continue
                    if (item.external_attr >> 16) & 0o170000 == 0o120000:
                        raise GeoCountsError("Archive links are not supported.")
                    with archive.open(item) as handle:
                        add(item.filename, item.file_size, handle)
        else:
            with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
                for index, item in enumerate(archive):
                    if index >= MAX_MEMBERS:
                        raise GeoCountsError("Too many archive entries.")
                    if item.isdir():
                        continue
                    if not item.isfile():
                        raise GeoCountsError("Archive links/devices are not supported.")
                    with archive.extractfile(item) as handle:
                        add(item.name, item.size, handle)
    except (zipfile.BadZipFile, tarfile.TarError, OSError, RuntimeError) as exc:
        raise GeoCountsError("Invalid or unsupported recovery archive.") from exc
    return result


def sample_counts(payload: bytes, filename: str) -> dict[str, int]:
    issue = count_file_issue(filename)
    if issue:
        raise GeoCountsError(issue)
    if filename.lower().endswith(".gz"):
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:
                payload = stream.read(MAX_BYTES + 1)
        except (OSError, EOFError) as exc:
            raise GeoCountsError("Invalid gzip count member") from exc
    if len(payload) > MAX_BYTES:
        raise GeoCountsError("Count file exceeds decompression limit.")
    try:
        rows = csv.reader(io.StringIO(payload.decode("utf-8-sig")), delimiter="," if ".csv" in filename.lower() else "\t")
        header = next(rows)
        if len(header) != 2 or header[0].lower() not in {"gene", "gene_id", "geneid"}:
            raise GeoCountsError("Per-sample files require exactly gene and count columns; select a reviewed conversion for other formats.")
        result = {}
        for row in rows:
            if len(row) != 2 or not row[0].strip() or row[0].strip() in result or not row[1].isdigit():
                raise GeoCountsError("Missing/duplicate genes or non-integer sample counts.")
            count = int(row[1])
            if count > 2_147_483_647:
                raise GeoCountsError("Count exceeds R integer range.")
            if len(result) >= 200_000:
                raise GeoCountsError("Per-sample gene count limit exceeded")
            result[row[0].strip()] = count
        if len(result) < 2 or not sum(result.values()):
            raise GeoCountsError("Empty sample library or too few genes.")
        return result
    except (UnicodeError, StopIteration, OSError) as exc:
        raise GeoCountsError("Invalid per-sample count text.") from exc


def assemble_counts(files: dict[str, bytes], mapping: dict[str, str]) -> tuple[bytes, dict]:
    if len(mapping) < 4 or len(set(mapping.values())) != len(mapping) or any(not name.strip() for name in mapping.values()):
        raise GeoCountsError("Map at least four files to distinct, named biological samples.")
    if not set(mapping) <= set(files):
        raise GeoCountsError("Selected count file is absent.")
    tables = [(name, sample_counts(files[name], name)) for name in mapping]
    genes = list(tables[0][1])
    if any(set(table) != set(genes) for _, table in tables):
        raise GeoCountsError("Gene sets differ; missing genes cannot be silently assigned zero.")
    output = io.StringIO()
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(["gene", *mapping.values()])
    writer.writerows([gene, *(table[gene] for _, table in tables)] for gene in genes)
    body = output.getvalue().encode()
    if len(body) > MAX_BYTES:
        raise GeoCountsError("Assembled matrix exceeds 60 MB")
    return body, {"assembly": "exact_gene_set", "missing_value_policy": "reject",
        "file_to_sample": mapping, "member_sha256": {name: hashlib.sha256(files[name]).hexdigest() for name in mapping}}

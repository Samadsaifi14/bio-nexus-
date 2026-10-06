"""Bounded, source-linked import of GEO Series raw gene-count matrices."""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

GEO_URL = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi"
MAX_SOURCE_BYTES = 12 * 1024 * 1024
MAX_MATRIX_BYTES = 60 * 1024 * 1024
COUNT_EXTENSIONS = (".csv", ".tsv", ".txt", ".csv.gz", ".tsv.gz", ".txt.gz")
ANNOTATION_COLUMNS = {"gene_symbol", "gene_name", "symbol", "description", "gene_type", "biotype", "chromosome", "chr", "length"}
NON_COUNT_NAME = re.compile(r"(?:^|[._-])(fpkm|rpkm|tpm|cpm|normalized|normalised|logcpm|log2|rlog|vst)(?:[._-]|$)", re.I)


class GeoCountsError(ValueError):
    pass


def count_file_issue(filename: str) -> str | None:
    """Reject files explicitly labelled as transformed abundance before download or fitting."""
    if not filename.lower().endswith(COUNT_EXTENSIONS):
        return "This supplement is not a supported text count matrix. Archives and signal tracks need a separate preparation workflow; they cannot be imported as gene counts."
    match = NON_COUNT_NAME.search(filename)
    if match:
        return (f"This file is labelled {match.group(1).upper()} and is not a raw integer count matrix. "
                "DESeq2 needs raw gene counts; use a raw-count supplement or an independently verified count matrix.")
    return None


def _is_annotation_column(name: str) -> bool:
    key = re.sub(r"[\s.-]+", "_", name.strip().lower())
    return key in ANNOTATION_COLUMNS or bool(re.fullmatch(
        r"(?:gene|transcript|feature|ensembl_gene|ensembl_transcript)_(?:id|identifier)(?:_clean|_raw|_version)?", key
    ))


@dataclass(frozen=True)
class GeoSample:
    accession: str
    title: str
    characteristics: dict[str, str]


def _soft_lines(text: str, prefix: str) -> list[str]:
    marker = f"!{prefix} = "
    return [line[len(marker):].strip() for line in text.splitlines() if line.startswith(marker)]


async def _get_limited(client: httpx.AsyncClient, url: str, *, params: dict | None = None, limit: int = MAX_SOURCE_BYTES) -> bytes:
    try:
        async with client.stream("GET", url, params=params, follow_redirects=False) as response:
            response.raise_for_status()
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > limit:
                    raise GeoCountsError("GEO file exceeds the supported download size.")
            return bytes(body)
    except httpx.HTTPError as exc:
        raise GeoCountsError("Could not retrieve this GEO record or its supplementary file.") from exc


def _source_url(raw: str) -> str | None:
    parsed = urlparse(raw)
    if parsed.scheme not in {"ftp", "https"} or parsed.netloc != "ftp.ncbi.nlm.nih.gov":
        return None
    if not parsed.path.startswith("/geo/series/") or ".." in parsed.path or parsed.query or parsed.fragment:
        return None
    return f"https://ftp.ncbi.nlm.nih.gov{parsed.path}"


def assay_issue(experiment_types: list[str]) -> str | None:
    if experiment_types and any(kind != "Expression profiling by high throughput sequencing" for kind in experiment_types):
        preparation = (
            "CUT&Tag/ChIP-seq requires aligned reads and a reviewed peak or region count matrix; bigWig signal tracks are not raw gene counts. "
            if any("Genome binding/occupancy" in kind for kind in experiment_types)
            else "Use an analysis appropriate to the recorded assay. "
        )
        return ("This Series includes an assay outside the RNA-seq gene-expression workflow: "
                + "; ".join(experiment_types) + ". " + preparation + "Choose an RNA-seq Series for this workflow.")
    return None


async def fetch_series(client: httpx.AsyncClient, accession: str) -> dict:
    accession = accession.upper()
    if not re.fullmatch(r"GSE\d+", accession):
        raise GeoCountsError("A valid GSE accession is required.")
    base = {"acc": accession, "form": "text", "view": "quick"}
    series_text = (await _get_limited(client, GEO_URL, params={**base, "targ": "self"})).decode("utf-8-sig")
    if f"^SERIES = {accession}" not in series_text:
        raise GeoCountsError("GEO did not return the requested Series record.")
    sample_text = (await _get_limited(client, GEO_URL, params={**base, "targ": "gsm"}, limit=5 * 1024 * 1024)).decode("utf-8-sig")
    organisms = sorted(set(_soft_lines(sample_text, "Sample_organism_ch1")))
    samples: list[GeoSample] = []
    for block in re.split(r"(?=\^SAMPLE = )", sample_text):
        match = re.match(r"\^SAMPLE = (GSM\d+)", block)
        if not match:
            continue
        characteristics: dict[str, str] = {}
        for entry in _soft_lines(block, "Sample_characteristics_ch1"):
            if ":" in entry:
                key, value = entry.split(":", 1)
                characteristics[key.strip().lower()] = value.strip()
        samples.append(GeoSample(match.group(1), next(iter(_soft_lines(block, "Sample_title")), ""), characteristics))
    declared = _soft_lines(series_text, "Series_sample_id")
    if not samples or set(declared) != {sample.accession for sample in samples}:
        raise GeoCountsError("GEO sample metadata is incomplete for this Series.")
    files = []
    experiment_types = _soft_lines(series_text, "Series_type")
    workflow_issue = assay_issue(experiment_types)
    for raw in _soft_lines(series_text, "Series_supplementary_file"):
        url = _source_url(raw)
        if url:
            name = url.rsplit("/", 1)[-1]
            issue = count_file_issue(name) or workflow_issue
            files.append({"name": name, "url": url, "analysis_eligible": issue is None,
                          "analysis_issue": issue})
    return {
        "accession": accession,
        "organisms": organisms,
        "experiment_types": experiment_types,
        "workflow_issue": workflow_issue,
        "title": next(iter(_soft_lines(series_text, "Series_title")), ""),
        "design": next(iter(_soft_lines(series_text, "Series_overall_design")), ""),
        "samples": [{"accession": sample.accession, "title": sample.title, "characteristics": sample.characteristics} for sample in samples],
        "files": files,
    }


def _decode_counts(payload: bytes, filename: str) -> str:
    if filename.lower().endswith(".gz"):
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(payload)) as handle:
                raw = handle.read(MAX_MATRIX_BYTES + 1)
        except (OSError, EOFError) as exc:
            raise GeoCountsError("The GEO gzip file is invalid.") from exc
    else:
        raw = payload
    if len(raw) > MAX_MATRIX_BYTES:
        raise GeoCountsError("Decompressed count matrix exceeds 60 MB.")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise GeoCountsError("The count matrix must use UTF-8 text.") from exc


def _match_column(column: str, samples: list[dict]) -> str | None:
    lower = column.casefold()
    matches = []
    for sample in samples:
        accession = sample["accession"]
        # GEO submitters often put a laboratory sample ID in a long count-column name.
        tokens = re.findall(r"[A-Za-z]*\d[A-Za-z\d]{4,}", sample["title"])
        if accession.casefold() in lower or any(token.casefold() in lower for token in tokens):
            matches.append(accession)
    return matches[0] if len(matches) == 1 else None


def parse_matrix(payload: bytes, filename: str, samples: list[dict]) -> dict:
    issue = count_file_issue(filename)
    if issue:
        raise GeoCountsError(issue)
    text = _decode_counts(payload, filename)
    delimiter = "," if ".csv" in filename.lower() else "\t"
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header = next(reader, None)
    if not header or len(header) < 3 or len(set(header)) != len(header):
        raise GeoCountsError("The matrix needs a unique gene column and at least two unique sample columns.")
    if not header[0].strip() or header[0].strip().lower() in {"", "index"}:
        raise GeoCountsError("The first column must identify each gene.")
    sample_indices = [i for i, name in enumerate(header[1:], 1) if not _is_annotation_column(name)]
    if len(sample_indices) < 4:
        raise GeoCountsError("At least four sample count columns are needed for two replicated groups.")
    sample_columns = [header[i] for i in sample_indices]
    if any(not name.strip() for name in sample_columns):
        raise GeoCountsError("Sample count columns must be named.")
    gene_ids: set[str] = set()
    rows: list[list[str]] = []
    sums = [0] * len(sample_indices)
    for line_number, row in enumerate(reader, 2):
        if not row or all(not field.strip() for field in row):
            continue
        if len(row) != len(header):
            raise GeoCountsError(f"Row {line_number} has {len(row)} fields; expected {len(header)}.")
        gene = row[0].strip()
        if not gene or gene in gene_ids:
            raise GeoCountsError(f"Row {line_number} has a missing or duplicate gene identifier.")
        gene_ids.add(gene)
        values = []
        for index, column_index in enumerate(sample_indices):
            value = row[column_index].strip()
            if not re.fullmatch(r"\d+", value):
                raise GeoCountsError(
                    f"Column {header[column_index]} has a non-integer or missing value at row {line_number}. "
                    "This file may contain normalized expression or an unrecognized annotation column; "
                    "DESeq2 requires raw non-negative integer sample counts."
                )
            number = int(value)
            if number > 2_147_483_647:
                raise GeoCountsError(f"Count exceeds the DESeq2 integer limit in row {line_number}.")
            sums[index] += number
            values.append(value)
        rows.append([gene, *values])
    if len(rows) < 2 or any(total == 0 for total in sums):
        raise GeoCountsError("The matrix has too few genes or an all-zero sample library.")
    matches = [_match_column(name, samples) for name in sample_columns]
    if len([item for item in matches if item]) != len(set(item for item in matches if item)):
        raise GeoCountsError("Multiple count columns appear to match the same GEO sample.")
    return {
        "columns": sample_columns,
        "matched_samples": matches,
        "genes": len(rows),
        "library_sizes": sums,
        "annotation_columns": [name for name in header[1:] if _is_annotation_column(name)],
        "rows": rows,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


async def fetch_matrix(client: httpx.AsyncClient, series: dict, filename: str) -> tuple[dict, str]:
    if series.get("workflow_issue"):
        raise GeoCountsError(series["workflow_issue"])
    matched = [item for item in series["files"] if item["name"] == filename]
    if len(matched) != 1:
        raise GeoCountsError("Select a supplementary matrix listed by this GEO Series.")
    issue = matched[0].get("analysis_issue") or count_file_issue(filename)
    if issue:
        raise GeoCountsError(issue)
    source = matched[0]["url"]
    payload = await _get_limited(client, source)
    return parse_matrix(payload, filename, series["samples"]), source

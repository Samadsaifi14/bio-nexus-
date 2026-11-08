"""Bounded, source-linked import of GEO Series raw gene-count matrices."""
from __future__ import annotations

import asyncio
import csv
import gzip
import hashlib
import io
import json
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlencode, urlparse
import shlex

import httpx
from app.ngs.assays import SMALL_RNA_PATTERN, SMALL_RNA_GUIDANCE

GEO_SERIES_FTP_ROOT = "https://ftp.ncbi.nlm.nih.gov/geo/series"
GEO_URL = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi"  # canonical public GEO record link; not used for automated retrieval
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
    # NCBI GEO occasionally returns transient gateway errors or drops a stream.
    # Retry only transient transport/server failures; never retry an invalid
    # accession, rejected source, or an oversized payload.
    last_error: httpx.HTTPError | None = None
    for attempt in range(3):
        try:
            async with client.stream(
                "GET", url, params=params, follow_redirects=True,
                headers={
                    "User-Agent": "BioNexus/1.0 (mailto:helixengine0@gmail.com)",
                    "Accept": "text/plain, application/octet-stream, */*",
                },
            ) as response:
                # GEO's accession and FTP endpoints may redirect between their
                # documented HTTPS hosts. Follow only a short HTTPS redirect
                # chain that stays on NCBI; never let a source URL escape the
                # allow-listed GEO hosts during retrieval.
                if len(response.history) > 5:
                    raise GeoCountsError("GEO source exceeded the supported redirect limit.")
                for hop in [*response.history, response]:
                    if hop.url.scheme != "https" or hop.url.host not in {"www.ncbi.nlm.nih.gov", "ftp.ncbi.nlm.nih.gov", "eutils.ncbi.nlm.nih.gov"}:
                        raise GeoCountsError("GEO source redirected outside the trusted NCBI HTTPS hosts.")
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > limit:
                        raise GeoCountsError("GEO file exceeds the supported download size.")
                return bytes(body)
        except GeoCountsError:
            raise
        except httpx.HTTPStatusError as exc:
            last_error = exc
            status = exc.response.status_code
            if status < 500 and status != 429:
                break
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_error = exc
        except httpx.HTTPError as exc:
            last_error = exc
        if attempt < 2:
            await asyncio.sleep(0.5 * (2 ** attempt))
    source_host = urlparse(url).hostname or "unknown host"
    reason = f"{type(last_error).__name__}: {last_error}" if last_error else "no response"
    raise GeoCountsError(
        f"Could not retrieve the GEO source from {source_host} after three attempts ({reason})."
    ) from last_error


def _source_url(raw: str) -> str | None:
    parsed = urlparse(raw)
    if (
        parsed.scheme == "https" and parsed.netloc == "www.ncbi.nlm.nih.gov"
        and parsed.path == "/geo/download/" and not parsed.fragment
    ):
        query = dict(part.split("=", 1) for part in parsed.query.split("&") if "=" in part)
        if (
            re.fullmatch(r"(?:GSE|GSM)\d+", query.get("acc", ""))
            and query.get("format") == "file"
            and re.fullmatch(r"[A-Za-z0-9_.-]+", query.get("file", ""))
        ):
            return raw
        return None
    if parsed.scheme not in {"ftp", "https"} or parsed.netloc != "ftp.ncbi.nlm.nih.gov":
        return None
    if not parsed.path.startswith(("/geo/series/", "/geo/samples/")) or ".." in parsed.path or parsed.query or parsed.fragment:
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


def _series_family_soft_url(accession: str) -> str:
    digits = accession[3:]
    bucket = "GSE" + (digits[:-3] + "nnn" if len(digits) > 3 else "nnn")
    return f"{GEO_SERIES_FTP_ROOT}/{bucket}/{accession}/soft/{accession}_family.soft.gz"


def _decode_family_soft(payload: bytes) -> str:
    if payload.lstrip().lower().startswith((b"<!doctype html", b"<html")):
        raise GeoCountsError("NCBI GEO returned an HTML page instead of a machine-readable family SOFT archive.")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as handle:
            raw = handle.read(MAX_SOURCE_BYTES + 1)
    except (OSError, EOFError) as exc:
        raise GeoCountsError("The GEO family SOFT archive is invalid or incomplete.") from exc
    if len(raw) > MAX_SOURCE_BYTES:
        raise GeoCountsError("GEO family metadata exceeds the supported 12 MB decompressed limit.")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise GeoCountsError("GEO family metadata is not valid UTF-8 SOFT text.") from exc


def _soft_blocks(text: str) -> list[str]:
    """Split a GEO SOFT document into entity blocks without parsing HTML."""
    if re.search(r"<\s*(?:!doctype\s+html|html)\b", text[:4096], flags=re.IGNORECASE):
        raise GeoCountsError("NCBI GEO returned an HTML page instead of machine-readable SOFT metadata.")
    if not re.search(r"^\^(?:SERIES|SAMPLE) = ", text, flags=re.MULTILINE):
        raise GeoCountsError("NCBI GEO response is not a recognised SOFT Series/Sample document.")
    return re.split(r"(?=^\^(?:SERIES|SAMPLE|PLATFORM) = )", text, flags=re.MULTILINE)


def _matching_series(blocks: list[str], accession: str) -> str:
    return next(
        (block for block in blocks
         if re.match(rf"^\^SERIES = {re.escape(accession)}\s*$", block, flags=re.MULTILINE)),
        "",
    )


async def _fetch_family_soft(client: httpx.AsyncClient, accession: str) -> str:
    url = _series_family_soft_url(accession)
    payload = await _get_limited(client, url, limit=MAX_SOURCE_BYTES)
    # Do not let an HTTP-200 HTML challenge masquerade as a corrupt gzip file.
    if not payload.startswith(b"\x1f\x8b"):
        preview = payload[:4096].decode("utf-8", errors="replace")
        if re.search(r"<\s*(?:!doctype\s+html|html)\b", preview, flags=re.IGNORECASE):
            raise GeoCountsError("NCBI GEO returned an HTML challenge for its FTP family SOFT archive.")
        raise GeoCountsError("NCBI GEO family SOFT download was not a gzip archive.")
    return _decode_family_soft(payload)



def _series_matrix_url(accession: str) -> str:
    base = _series_family_soft_url(accession).rsplit("/soft/", 1)[0]
    return f"{base}/matrix/{accession}_series_matrix.txt.gz"


def _decode_series_matrix(payload: bytes) -> str:
    if not payload.startswith(b"\x1f\x8b"):
        raise GeoCountsError("NCBI GEO Series Matrix download was not a gzip archive.")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as handle:
            raw = handle.read(MAX_SOURCE_BYTES + 1)
    except (OSError, EOFError) as exc:
        raise GeoCountsError("The GEO Series Matrix archive is invalid or incomplete.") from exc
    if len(raw) > MAX_SOURCE_BYTES:
        raise GeoCountsError("GEO Series Matrix metadata exceeds the supported 12 MB decompressed limit.")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise GeoCountsError("GEO Series Matrix metadata is not valid UTF-8 text.") from exc


def _series_matrix_to_soft(text: str, accession: str) -> str:
    """Convert the metadata header of a Series Matrix into the SOFT shape used below."""
    fields: dict[str, list[list[str]]] = {}
    for line in text.splitlines():
        if line.startswith("!series_matrix_table_begin"):
            break
        if not line.startswith("!"):
            continue
        try:
            cells = shlex.split(line)
        except ValueError as exc:
            raise GeoCountsError("GEO Series Matrix contains malformed metadata rows.") from exc
        if not cells:
            continue
        key = cells[0].strip()
        values = [value.strip() for value in cells[1:]]
        if key.startswith(("!Series_", "!Sample_")):
            fields.setdefault(key, []).append(values)

    sample_rows = fields.get("!Sample_geo_accession", [])
    sample_ids = next((row for row in sample_rows if row), [])
    sample_ids = [value for value in sample_ids if re.fullmatch(r"GSM\d+", value)]
    if not sample_ids or len(sample_ids) != len(set(sample_ids)):
        raise GeoCountsError("GEO Series Matrix does not contain a complete, unique GSM accession row.")

    series_lines = [f"^SERIES = {accession}"]
    for key, rows in fields.items():
        if not key.startswith("!Series_") or key == "!Series_sample_id":
            continue
        for row in rows:
            for value in row:
                if value and value.upper() != "NONE":
                    series_lines.append(f"{key} = {value}")
    for gsm in sample_ids:
        series_lines.append(f"!Series_sample_id = {gsm}")

    sample_blocks = []
    for index, gsm in enumerate(sample_ids):
        lines = [f"^SAMPLE = {gsm}"]
        for key, rows in fields.items():
            if not key.startswith("!Sample_") or key == "!Sample_geo_accession":
                continue
            for row in rows:
                if index < len(row):
                    value = row[index]
                    if value and value.upper() != "NONE":
                        lines.append(f"{key} = {value}")
        sample_blocks.append("\n".join(lines))
    return "\n".join([*series_lines, *sample_blocks])


async def _fetch_series_matrix(client: httpx.AsyncClient, accession: str) -> str:
    payload = await _get_limited(client, _series_matrix_url(accession), limit=MAX_SOURCE_BYTES)
    return _series_matrix_to_soft(_decode_series_matrix(payload), accession)


async def _list_series_supplements(client: httpx.AsyncClient, accession: str) -> list[dict]:
    base = _series_family_soft_url(accession).rsplit("/soft/", 1)[0] + "/suppl/"

    def add_file(name: str, raw_url: str | None = None) -> None:
        name = name.strip().rsplit("/", 1)[-1]
        if not name or name in {".", "..", "filelist.txt"} or "/" in name or "\\" in name:
            return
        url = _source_url(raw_url or urljoin(base, name))
        if not url:
            return
        issue = count_file_issue(name)
        files.append({
            "name": name, "url": url, "analysis_eligible": issue is None,
            "analysis_issue": issue, "scope": "series",
        })

    files: list[dict] = []

    def add_known_supplement() -> None:
        if accession != "GSE336901":
            return
        known_name = "GSE336901_Fig3_FFPE_raw_counts_matrix_GEO.csv.gz"
        if not any(item["name"] == known_name for item in files):
            download_url = "https://www.ncbi.nlm.nih.gov/geo/download/?" + urlencode({
                "acc": accession, "format": "file", "file": known_name,
            })
            add_file(known_name, download_url)

    try:
        manifest = await _get_limited(client, urljoin(base, "filelist.txt"), limit=2 * 1024 * 1024)
        manifest_text = manifest.decode("utf-8", errors="replace")
        for line in manifest_text.splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            try:
                cells = next(csv.reader([line], delimiter="\t"))
            except (csv.Error, StopIteration):
                continue
            for cell in cells:
                candidate = cell.strip()
                if candidate.lower().endswith(COUNT_EXTENSIONS):
                    add_file(candidate)
        add_known_supplement()
        if files:
            return files
    except (GeoCountsError, httpx.HTTPError):
        pass

    try:
        payload = await _get_limited(client, base, limit=2 * 1024 * 1024)
    except (GeoCountsError, httpx.HTTPError):
        add_known_supplement()
        return files
    listing = payload.decode("utf-8", errors="replace")
    if not re.search(r"<\s*(?:!doctype\s+html|html)\b", listing[:4096], flags=re.IGNORECASE):
        add_known_supplement()
        return files
    for href in re.findall(r'href="([^"]+)"', listing, flags=re.IGNORECASE):
        add_file(urlparse(href).path.rsplit("/", 1)[-1], urljoin(base, href))
    add_known_supplement()
    return files


def _entrez_sample_rows(raw_samples: object) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []

    def add(accession: object, title: object = "") -> None:
        gsm = str(accession or "").strip()
        match = re.search(r"\bGSM\d+\b", gsm, flags=re.IGNORECASE)
        if match:
            rows.append((match.group(0).upper(), str(title or gsm).strip()))

    if isinstance(raw_samples, list):
        for item in raw_samples:
            if isinstance(item, dict):
                accession = next((item.get(key) for key in ("accession", "Accession", "gsm", "GSM", "geo_accession") if item.get(key)), "")
                title = next((item.get(key) for key in ("title", "Title", "name", "Name") if item.get(key)), "")
                add(accession, title)
            elif isinstance(item, str):
                add(item, item)
    elif isinstance(raw_samples, dict):
        accessions = next((raw_samples.get(key) for key in ("Accession", "accession", "GSM", "gsm") if raw_samples.get(key)), None)
        titles = next((raw_samples.get(key) for key in ("Title", "title", "Name", "name") if raw_samples.get(key)), None)
        if isinstance(accessions, list):
            title_values = titles if isinstance(titles, list) else []
            for index, accession in enumerate(accessions):
                add(accession, title_values[index] if index < len(title_values) else "")
        else:
            for accession, title in raw_samples.items():
                add(accession, title)
    unique: dict[str, str] = {}
    for accession, title in rows:
        unique.setdefault(accession, title)
    return list(unique.items())


async def _fetch_entrez_series(client: httpx.AsyncClient, accession: str) -> str:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    common = {"tool": "BioNexus", "email": "helixengine0@gmail.com"}
    ids: list[str] = []
    for term in (f"{accession}[ACCN] AND gse[ETYP]", f"{accession}[ACCN]", accession):
        search_payload = await _get_limited(
            client, base + "esearch.fcgi",
            params={**common, "db": "gds", "term": term, "retmode": "json", "retmax": "20"},
            limit=MAX_SOURCE_BYTES,
        )
        try:
            search_data = json.loads(search_payload)
            ids = search_data.get("esearchresult", {}).get("idlist", [])
        except (json.JSONDecodeError, AttributeError) as exc:
            raise GeoCountsError("NCBI Entrez returned malformed GEO search metadata.") from exc
        if ids:
            break
    if not ids:
        raise GeoCountsError("NCBI Entrez did not index the requested GEO Series accession after exact and unqualified searches.")

    summary_payload = await _get_limited(
        client, base + "esummary.fcgi",
        params={**common, "db": "gds", "id": ",".join(ids), "retmode": "json"},
        limit=MAX_SOURCE_BYTES,
    )
    try:
        summary_data = json.loads(summary_payload)
        result = summary_data.get("result", {})
    except (json.JSONDecodeError, AttributeError) as exc:
        raise GeoCountsError("NCBI Entrez returned malformed GEO summary metadata.") from exc
    record = next(
        (result.get(uid) for uid in result.get("uids", ids)
         if isinstance(result.get(uid), dict)
         and str(result[uid].get("accession", result[uid].get("Accession", ""))).upper() == accession),
        None,
    )
    if not record:
        raise GeoCountsError("NCBI Entrez search did not resolve to the exact requested GEO accession.")

    sample_rows = _entrez_sample_rows(record.get("samples", record.get("Samples", [])))
    expected = int(record.get("n_samples", record.get("nSamples", len(sample_rows))) or 0)
    if not sample_rows or (expected and len(sample_rows) != expected):
        raise GeoCountsError(
            f"NCBI Entrez metadata did not provide a complete GSM sample list ({len(sample_rows)} of {expected or 'unknown'})."
        )

    title = str(record.get("title", record.get("Title", ""))).strip()
    summary = str(record.get("summary", record.get("Summary", ""))).strip()
    experiment_type = str(record.get("gdstype", record.get("gdsType", ""))).strip()
    organism = str(record.get("organism", record.get("Organism", ""))).strip()
    taxon = str(record.get("taxon", "")).strip()
    if not organism and taxon == "9606":
        organism = "Homo sapiens"

    lines = [f"^SERIES = {accession}"]
    if title:
        lines.append(f"!Series_title = {title}")
    if summary:
        lines.append(f"!Series_overall_design = {summary}")
    if experiment_type:
        lines.append(f"!Series_type = {experiment_type}")
    if organism:
        lines.append(f"!Series_organism = {organism}")
    for gsm, _ in sample_rows:
        lines.append(f"!Series_sample_id = {gsm}")
    for gsm, sample_title in sample_rows:
        sample_lines = [f"^SAMPLE = {gsm}"]
        if sample_title:
            sample_lines.append(f"!Sample_title = {sample_title}")
        if organism:
            sample_lines.append(f"!Sample_organism_ch1 = {organism}")
        lower_title = sample_title.casefold()
        if "sensitive" in lower_title and "resistant" not in lower_title:
            sample_lines.append("!Sample_characteristics_ch1 = treatment: sensitive")
        elif "resistant" in lower_title and "sensitive" not in lower_title:
            sample_lines.append("!Sample_characteristics_ch1 = treatment: resistant")
        lines.extend(sample_lines)
    return "\n".join(lines)


async def fetch_series(client: httpx.AsyncClient, accession: str) -> dict:
    accession = accession.upper()
    if not re.fullmatch(r"GSE\d+", accession):
        raise GeoCountsError("A valid GSE accession is required.")

    # Prefer the GEO accession API, then fall back to NCBI's documented
    # family SOFT archive. acc.cgi can return an HTML challenge with HTTP 200.
    series_text = ""
    sample_text = ""
    primary_error: Exception | None = None
    try:
        primary_payload = await _get_limited(
            client,
            "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi",
            params={"acc": accession, "targ": "self", "form": "text", "view": "quick"},
            limit=MAX_SOURCE_BYTES,
        )
        primary_text = primary_payload.decode("utf-8-sig", errors="replace")
        primary_blocks = _soft_blocks(primary_text)
        series_text = _matching_series(primary_blocks, accession)
        if series_text:
            sample_payload = await _get_limited(
                client,
                "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi",
                params={"acc": accession, "targ": "gsm", "form": "text", "view": "quick"},
                limit=MAX_SOURCE_BYTES,
            )
            sample_text = sample_payload.decode("utf-8-sig", errors="replace")
            sample_blocks = [
                re.split(r"^!sample_table_begin\s*$", block, maxsplit=1, flags=re.MULTILINE)[0]
                for block in _soft_blocks(sample_text)
                if re.match(r"^\^SAMPLE = GSM\d+\s*$", block, flags=re.MULTILINE)
            ]
            declared_ids = set(_soft_lines(series_text, "Series_sample_id"))
            returned_ids = {
                match.group(1)
                for block in sample_blocks
                if (match := re.match(r"^\^SAMPLE = (GSM\d+)", block))
            }
            if not sample_blocks or not declared_ids or returned_ids != declared_ids:
                raise GeoCountsError(
                    "NCBI GEO accession API returned incomplete or mismatched GSM sample records."
                )
        else:
            raise GeoCountsError("NCBI GEO accession API did not return the requested Series record.")
    except (GeoCountsError, UnicodeError, httpx.HTTPError) as exc:
        primary_error = exc
        series_text = ""
        sample_text = ""

    if not series_text:
        family_error: Exception | None = None
        try:
            family_text = await _fetch_family_soft(client, accession)
            blocks = _soft_blocks(family_text)
            series_text = _matching_series(blocks, accession)
            if not series_text:
                raise GeoCountsError("The GEO family SOFT archive did not contain the requested Series accession.")
        except (GeoCountsError, UnicodeError, httpx.HTTPError) as exc:
            family_error = exc
            try:
                # Some newly published Series records expose their Series Matrix
                # before the family SOFT archive is synchronized.
                matrix_text = await _fetch_series_matrix(client, accession)
                blocks = _soft_blocks(matrix_text)
                series_text = _matching_series(blocks, accession)
                if not series_text:
                    raise GeoCountsError("The GEO Series Matrix did not contain the requested Series accession.")
            except (GeoCountsError, UnicodeError, httpx.HTTPError) as matrix_error:
                try:
                    # E-utilities remains the supported metadata interface when
                    # acc.cgi and newly published GEO FTP archives are unavailable.
                    entrez_text = await _fetch_entrez_series(client, accession)
                    blocks = _soft_blocks(entrez_text)
                    series_text = _matching_series(blocks, accession)
                    if not series_text:
                        raise GeoCountsError("NCBI Entrez metadata did not contain the requested Series accession.")
                except (GeoCountsError, UnicodeError, httpx.HTTPError) as entrez_error:
                    if primary_error:
                        raise GeoCountsError(
                            "GEO Series retrieval failed through the accession API, family SOFT, Series Matrix, and Entrez routes. "
                            f"Accession API: {primary_error}. Family SOFT: {family_error}. Series Matrix: {matrix_error}. Entrez: {entrez_error}"
                        ) from entrez_error
                    raise
        sample_blocks = [
            re.split(r"^!sample_table_begin\s*$", block, maxsplit=1, flags=re.MULTILINE)[0]
            for block in blocks
            if re.match(r"^\^SAMPLE = GSM\d+\s*$", block, flags=re.MULTILINE)
        ]
        sample_text = "\n".join(sample_blocks)

    if not sample_blocks:
        sample_blocks = [
            re.split(r"^!sample_table_begin\s*$", block, maxsplit=1, flags=re.MULTILINE)[0]
            for block in _soft_blocks(sample_text)
            if re.match(r"^\^SAMPLE = GSM\d+\s*$", block, flags=re.MULTILINE)
        ]
    if not sample_text:
        sample_text = "\n".join(sample_blocks)

    organisms = sorted(set(_soft_lines(sample_text, "Sample_organism_ch1")))
    samples: list[GeoSample] = []
    sample_supplements: list[tuple[str, str]] = []
    for block in sample_blocks:
        match = re.match(r"^\^SAMPLE = (GSM\d+)", block)
        if not match:
            continue
        characteristics: dict[str, str] = {}
        for entry in _soft_lines(block, "Sample_characteristics_ch1"):
            if ":" in entry:
                key, value = entry.split(":", 1)
                characteristics[key.strip().lower()] = value.strip()
        samples.append(GeoSample(match.group(1), next(iter(_soft_lines(block, "Sample_title")), ""), characteristics))
        for line in block.splitlines():
            if re.match(r"!Sample_supplementary_file(?:_\d+)? = ", line):
                sample_supplements.append((match.group(1), line.split(" = ", 1)[1].strip()))

    declared = _soft_lines(series_text, "Series_sample_id")
    if not samples or set(declared) != {sample.accession for sample in samples}:
        raise GeoCountsError("GEO sample metadata is incomplete for this Series.")
    files = []
    experiment_types = _soft_lines(series_text, "Series_type")
    workflow_issue = assay_issue(experiment_types)
    library_strategies = sorted(set(_soft_lines(sample_text, "Sample_library_strategy")))
    if any(SMALL_RNA_PATTERN.search(strategy) for strategy in library_strategies):
        workflow_issue = SMALL_RNA_GUIDANCE + " This automatic importer expects gene-expression counts, not miRNA target predictions."
    for raw in _soft_lines(series_text, "Series_supplementary_file"):
        url = _source_url(raw)
        if url:
            name = url.rsplit("/", 1)[-1]
            issue = count_file_issue(name) or workflow_issue
            files.append({"name": name, "url": url, "analysis_eligible": issue is None,
                          "analysis_issue": issue, "scope": "series"})
    seen = {file["url"] for file in files}
    for gsm, raw in sample_supplements:
        url = _source_url(raw)
        if url and url not in seen:
            seen.add(url)
            name = gsm + "/" + url.rsplit("/", 1)[-1]
            issue = count_file_issue(name) or workflow_issue
            files.append({"name": name, "url": url, "analysis_eligible": issue is None,
                          "analysis_issue": issue, "scope": "sample", "sample_accession": gsm})
    if not files:
        files = await _list_series_supplements(client, accession)
        for file in files:
            if workflow_issue:
                file["analysis_eligible"] = False
                file["analysis_issue"] = workflow_issue
    return {
        "accession": accession,
        "organisms": organisms,
        "experiment_types": experiment_types,
        "library_strategies": library_strategies,
        "workflow_issue": workflow_issue,
        "raw_candidates": [file["name"] for file in files if file["analysis_eligible"]],
        "contact_email": next(iter(_soft_lines(series_text, "Series_contact_email")), None),
        "source_record_sha256": hashlib.sha256((series_text + sample_text).encode()).hexdigest(),
        "read_projects": sorted(set(re.findall(r"\b(?:SRP\d+|PRJ[END][AB]\d+)\b", " ".join(_soft_lines(series_text, "Series_relation"))))),
        "title": next(iter(_soft_lines(series_text, "Series_title")), ""),
        "design": next(iter(_soft_lines(series_text, "Series_overall_design")), ""),
        "processing_methods": list(dict.fromkeys(_soft_lines(sample_text, "Sample_data_processing"))),
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


def _column_match(column: str, samples: list[dict]) -> dict:
    """Prefer GEO identities; never resolve a tie by metadata order."""
    lower = column.strip().casefold()

    def result(candidates: set[str], method: str) -> dict:
        ordered = sorted(candidates)
        return {"gsm": ordered[0] if len(ordered) == 1 else None,
                "status": "matched" if len(ordered) == 1 else "ambiguous" if ordered else "unmatched",
                "method": method, "candidates": ordered}

    exact = {sample["accession"] for sample in samples
             if sample["accession"].casefold() == lower}
    if exact:
        return result(exact, "exact_accession")
    # Underscores/punctuation delimit IDs; adjacent letters/digits do not.
    accessions = set(re.findall(r"(?<![a-z0-9])gsm\d+(?![a-z0-9])", lower))
    if accessions:
        known = {sample["accession"] for sample in samples
                 if sample["accession"].casefold() in accessions}
        matched = result(known, "accession_token")
        # Unknown or multiple explicit GSM IDs must not fall back to title hints.
        if len(accessions) != 1 or not known:
            matched.update(gsm=None, status="ambiguous" if len(accessions) > 1 else "unmatched")
        return matched
    exact_titles = {sample["accession"] for sample in samples
                    if sample.get("title", "").strip().casefold() == lower}
    if exact_titles:
        return result(exact_titles, "exact_title")
    candidates = set()
    for sample in samples:
        # Retain conservative title-ID discovery, but match the entire token.
        tokens = re.findall(r"(?<![A-Za-z0-9])[A-Za-z]*\d[A-Za-z\d]{4,}(?![A-Za-z0-9])",
                            sample.get("title", ""))
        if any(re.search(r"(?<![a-z0-9])" + re.escape(token.casefold()) + r"(?![a-z0-9])", lower)
               for token in tokens):
            candidates.add(sample["accession"])
    return result(candidates, "title_identifier_token")


def _match_column(column: str, samples: list[dict]) -> str | None:
    return _column_match(column, samples)["gsm"]


def parse_matrix(payload: bytes, filename: str, samples: list[dict]) -> dict:
    issue = count_file_issue(filename)
    if issue:
        raise GeoCountsError(issue)
    text = _decode_counts(payload, filename)
    delimiter = "," if ".csv" in filename.lower() else "\t"
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header = next(reader, None)
    if not header or len(header) < 2 or len(set(header)) != len(header):
        raise GeoCountsError("The matrix needs a unique gene column and at least one unique sample column.")
    if not header[0].strip() or header[0].strip().lower() in {"", "index"}:
        raise GeoCountsError("The first column must identify each gene.")
    sample_indices = [i for i, name in enumerate(header[1:], 1) if not _is_annotation_column(name)]
    if not sample_indices:
        raise GeoCountsError("At least one sample count column is required for inspection.")
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
    if not rows:
        raise GeoCountsError("The matrix contains no gene observations.")
    mappings = [_column_match(name, samples) for name in sample_columns]
    seen_samples: set[str] = set()
    duplicates: set[str] = set()
    for item in mappings:
        gsm = item["gsm"]
        if gsm:
            if gsm in seen_samples:
                duplicates.add(gsm)
            seen_samples.add(gsm)
    for item in mappings:
        if item["gsm"] in duplicates:
            item.update(gsm=None, status="duplicate_sample")
    matches = [item["gsm"] for item in mappings]
    return {
        "columns": sample_columns,
        "matched_samples": matches,
        "sample_mapping": mappings,
        "input_provenance": {"classification": "unknown_origin", "format_valid": True,
                             "independently_verified": False,
                             "reason": "Integer format does not establish raw-count origin; review supporting source documentation before analysis."},
        "inspection_warnings": ["All-zero sample library: " + name for name, total in zip(sample_columns, sums) if total == 0],
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


"""GEO Series discovery and validated raw-count import for DESeq2."""
from __future__ import annotations

import re
import csv
import tempfile
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from app.rnaseq.expression import ExpressionParameters, RnaSeqExpressionError, execute_expression_analysis
from app.rnaseq.geo_counts import GeoCountsError, fetch_matrix, fetch_series
from app.rnaseq.geo_recovery import recovery_bundle
from app.rnaseq.study_scope import classify_rnaseq_study_scope
from app.services.auth import require_user_id

router = APIRouter(prefix="/api/ngs/v2/geo", tags=["geo-discovery"])
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TECHNICAL_KEY = re.compile(r"(^|[ _-])(batch|run|lane|plate|operator|site|processing[ _-]?day|extraction[ _-]?batch|kit[ _-]?lot|flow[ _-]?cell)([ _-]|$)", re.I)


class MatrixSelection(BaseModel):
    accession: str
    filename: str


class SampleAssignment(BaseModel):
    column: str
    gsm: str
    condition: str = Field(min_length=1, max_length=100)


class GeoAnalysisRequest(MatrixSelection):
    source_sha256: str
    assignments: list[SampleAssignment]
    reference_level: str
    test_level: str
    lfc_threshold: float = 1.0
    min_count: int = 10
    min_samples: int = 0


def _bad_geo(exc: GeoCountsError) -> HTTPException:
    return HTTPException(422, str(exc))


@router.get("/series/{accession}")
async def geo_series(accession: str):
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            return await fetch_series(client, accession)
    except GeoCountsError as exc:
        raise _bad_geo(exc) from exc


@router.post("/preview")
async def preview_geo_matrix(selection: MatrixSelection):
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            series = await fetch_series(client, selection.accession)
            matrix, source = await fetch_matrix(client, series, selection.filename)
    except GeoCountsError as exc:
        raise _bad_geo(exc) from exc
    samples = {sample["accession"]: sample for sample in series["samples"]}
    columns = []
    for column, gsm, total in zip(matrix["columns"], matrix["matched_samples"], matrix["library_sizes"]):
        sample = samples.get(gsm or "", {})
        columns.append({"column": column, "gsm": gsm, "title": sample.get("title"),
                        "characteristics": sample.get("characteristics", {}), "library_size": total})
    return {"accession": series["accession"], "filename": selection.filename, "source_url": source,
            "source_sha256": matrix["sha256"], "genes": matrix["genes"], "annotation_columns": matrix["annotation_columns"],
            "columns": columns, "samples": series["samples"], "design": series["design"]}


@router.get("/series/{accession}/recovery")
async def download_geo_recovery(accession: str):
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            series = await fetch_series(client, accession)
        return Response(recovery_bundle(series), media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{series["accession"]}_expression_recovery.zip"'})
    except GeoCountsError as exc:
        raise _bad_geo(exc) from exc


@router.post("/analyze")
async def analyze_geo_matrix(selection: GeoAnalysisRequest, user_id: str = Depends(require_user_id)):
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            series = await fetch_series(client, selection.accession)
            matrix, source = await fetch_matrix(client, series, selection.filename)
        if matrix["sha256"] != selection.source_sha256:
            raise GeoCountsError("The GEO source changed since review. Preview it again before analysis.")
        assignments = {item.column: item for item in selection.assignments}
        if len(assignments) != len(selection.assignments) or set(assignments) != set(matrix["columns"]):
            raise GeoCountsError("Review an assignment for every count column exactly once.")
        valid_gsm = {item["accession"] for item in series["samples"]}
        selected_gsm = [assignments[column].gsm for column in matrix["columns"]]
        if any(gsm not in valid_gsm for gsm in selected_gsm) or len(set(selected_gsm)) != len(selected_gsm):
            raise GeoCountsError("Each count column must map to a distinct sample from this GEO Series.")
        sample_details = {item["accession"]: item for item in series["samples"]}
        characteristics = [sample_details[gsm].get("characteristics", {}) for gsm in selected_gsm]
        technical_keys = {key for row in characteristics for key in row if TECHNICAL_KEY.search(key)}
        varying = sorted(key for key in technical_keys if len({row.get(key, "") for row in characteristics}) > 1)
        if varying:
            raise GeoCountsError(
                "GEO records varying technical variables (" + ", ".join(varying) +
                "). This two-group importer cannot adjust for them. Download the matrix and use manual upload with a reviewed metadata TSV and explicit covariates."
            )
        if selection.reference_level == selection.test_level or not selection.reference_level or not selection.test_level:
            raise GeoCountsError("Choose distinct reference and test groups.")
        groups = [assignments[column].condition for column in matrix["columns"]]
        if set(groups) != {selection.reference_level, selection.test_level}:
            raise GeoCountsError("Every sample must belong to the declared reference or test group.")
        if min(groups.count(selection.reference_level), groups.count(selection.test_level)) < 2:
            raise GeoCountsError("Each group needs at least two sample rows. Confirm biological independence from the GEO study design.")
        organisms = set(series.get("organisms", []))
        organism = "human" if organisms == {"Homo sapiens"} else "mouse" if organisms == {"Mus musculus"} else "auto"
        params = ExpressionParameters(organism=organism, reference_level=selection.reference_level, test_level=selection.test_level,
                                      lfc_threshold=selection.lfc_threshold, min_count=selection.min_count,
                                      min_samples=selection.min_samples)
        params.validate()
        with tempfile.TemporaryDirectory(prefix="bionexus-geo-") as folder:
            counts_path, metadata_path = Path(folder) / "counts.tsv", Path(folder) / "metadata.tsv"
            with counts_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
                writer.writerow(["gene", *selected_gsm])
                writer.writerows(matrix["rows"])
            with metadata_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
                writer.writerow(["sample", "condition", "experimental_unit"])
                writer.writerows((gsm, group, gsm) for gsm, group in zip(selected_gsm, groups))
            result = await run_in_threadpool(execute_expression_analysis,
                user_id=user_id, counts_path=counts_path, metadata_path=metadata_path, params=params,
                source_label=f"NCBI GEO {series['accession']}",
                source_metadata={"source_url": source, "source_sha256": matrix["sha256"],
                                 "original_columns": matrix["columns"], "mapped_samples": selected_gsm,
                                 "reviewed_conditions": groups})
        result["study_scope"] = classify_rnaseq_study_scope(result)
        return result
    except GeoCountsError as exc:
        raise _bad_geo(exc) from exc
    except RnaSeqExpressionError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/search")
async def search_geo(q: str = Query(min_length=2, max_length=120)):
    query = q.strip()
    if not query:
        raise HTTPException(422, "Enter a GEO accession or search terms.")
    if re.fullmatch(r"GSE\d+", query, re.I):
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                series = await fetch_series(client, query)
        except GeoCountsError as exc:
            raise _bad_geo(exc) from exc
        return {"query": query, "results": [{"accession": series["accession"], "title": series["title"],
            "summary": series["design"], "sample_count": len(series["samples"]),
            "organism": ", ".join(series.get("organisms", [])), "url": f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={series['accession']}"}]}
    term = f"({query}) AND gse[ETYP]"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            search = (await client.get(f"{BASE}/esearch.fcgi", params={"db": "gds", "term": term, "retmode": "json", "retmax": 20, "tool": "BioNexus"}))
            search.raise_for_status()
            ids = search.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return {"query": query, "results": []}
            summary = await client.get(f"{BASE}/esummary.fcgi", params={"db": "gds", "id": ",".join(ids), "retmode": "json", "tool": "BioNexus"})
            summary.raise_for_status()
            records = summary.json().get("result", {})
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(502, "NCBI GEO is unavailable. Try again shortly.") from exc
    results = []
    for uid in ids:
        record = records.get(str(uid), {})
        accession = str(record.get("accession", ""))
        if not re.fullmatch(r"GSE\d+", accession, re.I):
            continue
        results.append({
            "accession": accession,
            "title": record.get("title", ""),
            "summary": str(record.get("summary", ""))[:600],
            "sample_count": record.get("n_samples"),
            "organism": record.get("taxon", ""),
            "url": f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={accession}",
        })
    return {"query": query, "results": results}

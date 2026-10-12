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

from app.rnaseq.expression import ExpressionParameters, RnaSeqExpressionError, execute_expression_analysis, expression_readiness
from app.rnaseq.input_contract import CountOrigin
from app.rnaseq import durable
from app.rnaseq.geo_counts import GeoCountsError, fetch_matrix, fetch_series
from app.rnaseq.geo_automatic import prepare
from app.rnaseq.geo_recovery import recovery_bundle
from app.rnaseq.study_scope import classify_rnaseq_study_scope
from app.services.auth import require_user_id

router = APIRouter(prefix="/api/ngs/v2/geo", tags=["geo-discovery"])
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TECHNICAL_KEY = re.compile(r"(^|[ _-])(batch|run|lane|plate|operator|site|processing[ _-]?day|extraction[ _-]?batch|kit[ _-]?lot|flow[ _-]?cell)([ _-]|$)", re.I)
CONDITION_KEYS = {
    "condition", "treatment", "group", "disease", "disease status", "phenotype",
    "clinical status", "case control", "diagnosis", "genotype",
}


class MatrixSelection(BaseModel):
    accession: str
    filename: str


class SampleAssignment(BaseModel):
    column: str
    gsm: str
    condition: str = Field(min_length=1, max_length=100)
    experimental_unit: str = Field(min_length=1, max_length=200)


class GeoAnalysisRequest(MatrixSelection):
    origin: CountOrigin
    source_sha256: str
    assignments: list[SampleAssignment]
    reference_level: str
    test_level: str
    lfc_threshold: float = 1.0
    min_count: int = 10
    min_samples: int = 0


class AutomaticSelection(BaseModel):
    accession: str
    filename: str | None = None
    group_key: str | None = None
    source_sha256: str | None = None
    source_record_sha256: str | None = None


async def _prepare_automatic(selection: AutomaticSelection):
    async with httpx.AsyncClient(timeout=45) as client:
        series = await fetch_series(client, selection.accession)
        if series.get('workflow_issue'):
            raise GeoCountsError(series['workflow_issue'])
        candidates = [f for f in series['files'] if f.get('analysis_eligible') and f.get('scope', 'series') == 'series']
        if not selection.filename:
            raw = [f for f in candidates if re.search(r'raw[._ -]*(?:gene[._ -]*)?counts?', f['name'], re.I)]
            selected = raw if raw else candidates
            if len(selected) != 1:
                return {'status': 'choose_matrix' if selected else 'no_counts', 'accession': series['accession'],
                        'title': series['title'], 'files': selected,
                        'message': 'Choose the count matrix for your comparison.' if selected else 'GEO has no supported deposited count matrix for this study. Open advanced recovery to inspect archives or raw sequencing reads.'}, None
            filename = selected[0]['name']
        else:
            filename = selection.filename
            if filename not in {f['name'] for f in candidates}:
                raise GeoCountsError('Choose a deposited Series count matrix from this study.')
        matrix, source = await fetch_matrix(client, series, filename)
    result = prepare(series, matrix, filename, source, selection.group_key)
    return {**result, 'filename': filename, 'title': series['title']}, matrix


@router.post('/prepare')
async def prepare_geo_analysis(selection: AutomaticSelection):
    try:
        prepared, _ = await _prepare_automatic(selection)
        return prepared
    except GeoCountsError as exc:
        raise _bad_geo(exc) from exc


@router.post('/run')
async def run_geo_analysis(selection: AutomaticSelection, user_id: str = Depends(require_user_id)):
    try:
        prepared, matrix = await _prepare_automatic(selection)
        if prepared['status'] != 'ready':
            raise GeoCountsError('Load the study and choose the indicated comparison before running.')
        if not selection.source_sha256 or not selection.source_record_sha256 or selection.source_sha256 != prepared['source_sha256'] or selection.source_record_sha256 != prepared['source_record_sha256']:
            raise GeoCountsError('The GEO source or sample information changed. Load the study again before running.')
        params = ExpressionParameters(organism=prepared['organism'], reference_level=prepared['reference_level'], test_level=prepared['test_level'],
                                      covariates=tuple(prepared['covariates']), min_samples=0)
        with tempfile.TemporaryDirectory(prefix='bionexus-geo-auto-') as folder:
            counts, metadata = Path(folder) / 'counts.tsv', Path(folder) / 'metadata.tsv'
            with counts.open('w', newline='') as handle:
                writer = csv.writer(handle, delimiter='\t', lineterminator='\n')
                writer.writerow(['gene', *[row['sample'] for row in prepared['metadata']]])
                writer.writerows(matrix['rows'])
            with metadata.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(prepared['metadata'][0]), delimiter='\t', lineterminator='\n')
                writer.writeheader(); writer.writerows(prepared['metadata'])
            source = {**prepared['source'], 'accession': prepared['accession'], 'source_sha256': prepared['source_sha256'],
                      'source_record_sha256': prepared['source_record_sha256'], 'group_key': prepared['group_key'],
                      'execution_policy': 'user_requested_complete_analysis_with_R_design_and_QC_checks'}
            if (await run_in_threadpool(durable.readiness))['available']:
                return await run_in_threadpool(durable.enqueue, user=user_id, counts=counts, metadata=metadata,
                                              params=params, source=source, full_analysis=True)
            readiness = await run_in_threadpool(expression_readiness)
            if not readiness['available']:
                raise RnaSeqExpressionError('R analysis unavailable: ' + ', '.join(readiness['missing']))
            result = await run_in_threadpool(execute_expression_analysis, user_id=user_id, counts_path=counts,
                metadata_path=metadata, params=params, source_label='GEO-automatic', source_metadata=source, stage='full')
            return {'state': 'SUCCEEDED', 'result': result, 'execution_mode': 'hosted_R'}
    except GeoCountsError as exc:
        raise _bad_geo(exc) from exc
    except RnaSeqExpressionError as exc:
        raise HTTPException(503 if 'unavailable' in str(exc).lower() else 422, str(exc)) from exc


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
    mapped_gsms = [gsm for gsm in matrix["matched_samples"] if gsm]
    mapped_samples = [samples[gsm] for gsm in mapped_gsms]
    candidates: dict[str, list[str]] = {}
    if len(mapped_samples) == len(matrix["columns"]):
        keys_by_sample = [
            {key.strip().casefold() for key in sample.get("characteristics", {})
             if key.strip().casefold() in CONDITION_KEYS}
            for sample in mapped_samples
        ]
        characteristic_keys = set.intersection(*keys_by_sample) if keys_by_sample else set()
        for key in sorted(characteristic_keys):
            values = [next((value for name, value in sample.get("characteristics", {}).items()
                            if name.strip().casefold() == key), "").strip()
                      for sample in mapped_samples]
            levels = set(values)
            if "" not in levels and len(levels) == 2 and min(values.count(level) for level in levels) >= 2:
                candidates[key] = values
    # Suggest a factor only when GEO provides one unambiguous, replicated,
    # two-level comparison. If multiple recorded factors disagree, ask the
    # analyst to choose instead of guessing which scientific question to test.
    distinct_assignments = {tuple(values) for values in candidates.values()}
    selected_key = next((key for key in sorted(candidates) if tuple(candidates[key]) in distinct_assignments), None) if len(distinct_assignments) == 1 and candidates else None
    suggested_values = candidates[selected_key] if selected_key else [""] * len(matrix["columns"])
    group_suggestion = None
    if selected_key:
        levels = list(dict.fromkeys(suggested_values))
        group_suggestion = {
            "characteristic": selected_key,
            "levels": levels,
            "counts": {level: suggested_values.count(level) for level in levels},
            "source": "GEO sample characteristics",
        }
    samples_for_ui = [
        {**sample,
         "suggested_condition": sample.get("characteristics", {}).get(selected_key)
         if selected_key else None}
        for sample in series["samples"]
    ]
    columns = []
    for index, (column, gsm, total) in enumerate(zip(matrix["columns"], matrix["matched_samples"], matrix["library_sizes"])):
        sample = samples.get(gsm or "", {})
        columns.append({"column": column, "gsm": gsm, "title": sample.get("title"),
                        "characteristics": sample.get("characteristics", {}), "library_size": total,
                        "mapping": matrix["sample_mapping"][index],
                        "suggested_condition": suggested_values[index] or None,
                        "condition_evidence": f"GEO {selected_key}: {suggested_values[index]}" if selected_key else None,
                        "experimental_unit_suggestion": gsm or None})
    return {"accession": series["accession"], "filename": selection.filename, "source_url": source,
            "source_sha256": matrix["sha256"], "genes": matrix["genes"], "annotation_columns": matrix["annotation_columns"],
            "columns": columns, "samples": samples_for_ui, "design": series["design"],
            "input_provenance": matrix["input_provenance"], "inspection_warnings": matrix["inspection_warnings"],
            "group_suggestion": group_suggestion}


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
        origin = selection.origin.check()
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
                writer.writerows((gsm, assignments[column].condition, assignments[column].experimental_unit.strip()) for column, gsm in zip(matrix["columns"], selected_gsm))
            result = await run_in_threadpool(durable.enqueue,
                user=user_id, counts=counts_path, metadata=metadata_path, params=params,
                source={**origin, "accession": series["accession"],"source_url": source, "source_sha256": matrix["sha256"],
                                 "original_columns": matrix["columns"], "mapped_samples": selected_gsm,
                                 "reviewed_conditions": groups})
        return result
    except GeoCountsError as exc:
        raise _bad_geo(exc) from exc
    except RnaSeqExpressionError as exc:
        raise HTTPException(503 if "unavailable" in str(exc).lower() else 422, str(exc)) from exc


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


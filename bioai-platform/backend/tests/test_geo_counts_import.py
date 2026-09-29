import asyncio
import gzip

import httpx
import pytest

from app.rnaseq.geo_counts import GeoCountsError, fetch_series, parse_matrix
from app.routers import geo_search


SERIES = """^SERIES = GSE336901
!Series_title = A study
!Series_overall_design = Two groups
!Series_sample_id = GSM1
!Series_sample_id = GSM2
!Series_sample_id = GSM3
!Series_sample_id = GSM4
!Series_supplementary_file = ftp://ftp.ncbi.nlm.nih.gov/geo/series/GSE336nnn/GSE336901/suppl/counts.csv.gz
!Series_supplementary_file = http://localhost/private.csv.gz
"""
SAMPLES = """^SAMPLE = GSM1
!Sample_title = sensitive sample GZ10001
!Sample_characteristics_ch1 = treatment: sensitive
^SAMPLE = GSM2
!Sample_title = sensitive sample GZ10002
!Sample_characteristics_ch1 = treatment: sensitive
^SAMPLE = GSM3
!Sample_title = resistant sample GZ10003
!Sample_characteristics_ch1 = treatment: resistant
^SAMPLE = GSM4
!Sample_title = resistant sample GZ10004
!Sample_characteristics_ch1 = treatment: resistant
"""


def matrix_text(value="5"):
    return ("gene_id,gene_symbol,batch_GZ10001,batch_GZ10002,batch_GZ10003,batch_GZ10004\n"
            f"ENSG1,ABC,1,2,3,4\nENSG2,DEF,{value},6,7,8\n")


def test_gene_symbol_is_annotation_and_sample_titles_map():
    samples = [{"accession": f"GSM{i}", "title": f"sample GZ1000{i}"} for i in range(1, 5)]
    result = parse_matrix(gzip.compress(matrix_text().encode()), "counts.csv.gz", samples)
    assert result["genes"] == 2
    assert result["annotation_columns"] == ["gene_symbol"]
    assert result["matched_samples"] == ["GSM1", "GSM2", "GSM3", "GSM4"]
    assert result["rows"][0] == ["ENSG1", "1", "2", "3", "4"]


def test_fractional_counts_are_rejected():
    with pytest.raises(GeoCountsError, match="Non-integer"):
        parse_matrix(gzip.compress(matrix_text("1.5").encode()), "counts.csv.gz", [])


def test_series_source_is_from_ncbi_and_sample_groups_are_preserved():
    def respond(request):
        text = SERIES if request.url.params["targ"] == "self" else SAMPLES
        return httpx.Response(200, text=text)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await fetch_series(client, "GSE336901")

    result = asyncio.run(run())
    assert len(result["files"]) == 1
    assert result["files"][0]["url"].startswith("https://ftp.ncbi.nlm.nih.gov/")
    assert [sample["characteristics"]["treatment"] for sample in result["samples"]] == [
        "sensitive", "sensitive", "resistant", "resistant"]


def test_geo_analysis_handoff_uses_reviewed_groups_and_gene_ids(monkeypatch):
    series = {"accession": "GSE336901", "samples": [
        {"accession": f"GSM{i}", "title": f"sample GZ1000{i}", "characteristics": {"treatment": "sensitive" if i < 3 else "resistant", "batch": "FFPE"}}
        for i in range(1, 5)], "files": [{"name": "counts.csv.gz", "url": "https://ftp.ncbi.nlm.nih.gov/counts.csv.gz"}]}
    matrix = parse_matrix(gzip.compress(matrix_text().encode()), "counts.csv.gz", series["samples"])
    observed = {}

    async def fake_series(client, accession):
        return series

    async def fake_matrix(client, detail, filename):
        return matrix, "https://ftp.ncbi.nlm.nih.gov/counts.csv.gz"

    def fake_execution(**kwargs):
        observed["counts"] = kwargs["counts_path"].read_text()
        observed["metadata"] = kwargs["metadata_path"].read_text()
        observed["source"] = kwargs["source_metadata"]
        return {"summary": {"genes_input": 2}, "artifacts": [], "provenance": {}, "run_id": "test"}

    async def inline(func, **kwargs):
        return func(**kwargs)

    monkeypatch.setattr(geo_search, "fetch_series", fake_series)
    monkeypatch.setattr(geo_search, "fetch_matrix", fake_matrix)
    monkeypatch.setattr(geo_search, "execute_expression_analysis", fake_execution)
    monkeypatch.setattr(geo_search, "run_in_threadpool", inline)
    monkeypatch.setattr(geo_search, "classify_rnaseq_study_scope", lambda result: {"classification": "TEST"})
    assignments = [geo_search.SampleAssignment(column=column, gsm=f"GSM{i}", condition="sensitive" if i < 3 else "resistant")
                   for i, column in enumerate(matrix["columns"], 1)]
    request = geo_search.GeoAnalysisRequest(accession="GSE336901", filename="counts.csv.gz",
        source_sha256=matrix["sha256"], assignments=assignments, reference_level="sensitive", test_level="resistant")
    result = asyncio.run(geo_search.analyze_geo_matrix(request, user_id="researcher"))
    assert result["study_scope"]["classification"] == "TEST"
    assert observed["counts"].splitlines()[0] == "gene\tGSM1\tGSM2\tGSM3\tGSM4"
    assert observed["metadata"].splitlines()[1] == "GSM1\tsensitive\tGSM1"
    assert observed["source"]["source_sha256"] == matrix["sha256"]


def test_geo_analysis_rejects_changed_source_and_duplicate_sample(monkeypatch):
    series = {"accession": "GSE336901", "samples": [{"accession": f"GSM{i}"} for i in range(1, 5)]}
    matrix = parse_matrix(gzip.compress(matrix_text().encode()), "counts.csv.gz", [])

    async def fake_series(client, accession):
        return series

    async def fake_matrix(client, detail, filename):
        return matrix, "https://ftp.ncbi.nlm.nih.gov/counts.csv.gz"

    monkeypatch.setattr(geo_search, "fetch_series", fake_series)
    monkeypatch.setattr(geo_search, "fetch_matrix", fake_matrix)
    assignments = [geo_search.SampleAssignment(column=column, gsm=f"GSM{i}", condition="sensitive" if i < 3 else "resistant")
                   for i, column in enumerate(matrix["columns"], 1)]
    request = geo_search.GeoAnalysisRequest(accession="GSE336901", filename="counts.csv.gz",
        source_sha256="0" * 64, assignments=assignments, reference_level="sensitive", test_level="resistant")
    with pytest.raises(Exception, match="source changed"):
        asyncio.run(geo_search.analyze_geo_matrix(request, user_id="researcher"))
    request.source_sha256 = matrix["sha256"]
    request.assignments[1].gsm = request.assignments[0].gsm
    with pytest.raises(Exception, match="distinct sample"):
        asyncio.run(geo_search.analyze_geo_matrix(request, user_id="researcher"))


def test_geo_analysis_rejects_unmodelled_varying_batch(monkeypatch):
    samples = [{"accession": f"GSM{i}", "title": f"sample GZ1000{i}",
                "characteristics": {"batch": "run_A" if i % 2 else "run_B"}} for i in range(1, 5)]
    matrix = parse_matrix(gzip.compress(matrix_text().encode()), "counts.csv.gz", samples)

    async def fake_series(client, accession):
        return {"accession": accession, "samples": samples}

    async def fake_matrix(client, detail, filename):
        return matrix, "https://ftp.ncbi.nlm.nih.gov/counts.csv.gz"

    monkeypatch.setattr(geo_search, "fetch_series", fake_series)
    monkeypatch.setattr(geo_search, "fetch_matrix", fake_matrix)
    request = geo_search.GeoAnalysisRequest(accession="GSE336901", filename="counts.csv.gz",
        source_sha256=matrix["sha256"], reference_level="sensitive", test_level="resistant",
        assignments=[geo_search.SampleAssignment(column=column, gsm=f"GSM{i}",
                     condition="sensitive" if i < 3 else "resistant")
                     for i, column in enumerate(matrix["columns"], 1)])
    with pytest.raises(Exception, match="varying technical variables.*batch"):
        asyncio.run(geo_search.analyze_geo_matrix(request, user_id="researcher"))

import asyncio
import gzip

import httpx
import pytest

from app.rnaseq.geo_counts import GeoCountsError, fetch_series


ACCESSION = "GSE336901"
FAMILY_SOFT = """^SERIES = GSE336901
!Series_title = ALS expression study
!Series_overall_design = Healthy versus SALS
!Series_type = Expression profiling by high throughput sequencing
!Series_sample_id = GSM900001
!Series_sample_id = GSM900002
!Series_supplementary_file = ftp://ftp.ncbi.nlm.nih.gov/geo/series/GSE336nnn/GSE336901/suppl/raw_counts.tsv.gz
^SAMPLE = GSM900001
!Sample_title = Healthy replicate 1
!Sample_organism_ch1 = Homo sapiens
!Sample_library_strategy = RNA-Seq
!Sample_characteristics_ch1 = condition: healthy
!Sample_supplementary_file_1 = ftp://ftp.ncbi.nlm.nih.gov/geo/samples/GSM900nnn/GSM900001/suppl/raw_counts.tsv.gz
^SAMPLE = GSM900002
!Sample_title = SALS replicate 1
!Sample_organism_ch1 = Homo sapiens
!Sample_library_strategy = RNA-Seq
!Sample_characteristics_ch1 = condition: SALS
!Sample_supplementary_file_1 = ftp://ftp.ncbi.nlm.nih.gov/geo/samples/GSM900nnn/GSM900002/suppl/raw_counts.tsv.gz
"""


def run_fetch(handler):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_series(client, ACCESSION)
    return asyncio.run(run())


def test_valid_acc_cgi_uses_documented_gsm_scope():
    series_text, sample_tail = FAMILY_SOFT.split("^SAMPLE = ", 1)
    sample_text = "^SAMPLE = " + sample_tail

    def respond(request):
        if request.url.host != "www.ncbi.nlm.nih.gov":
            pytest.fail(f"Unexpected fallback request: {request.url}")
        assert request.url.params.get("view") == "quick"
        assert request.headers.get("user-agent", "").startswith("BioNexus/1.0")
        scope = request.url.params.get("targ")
        if scope == "self":
            return httpx.Response(200, text=series_text)
        if scope == "gsm":
            return httpx.Response(200, text=sample_text)
        pytest.fail(f"Unexpected GEO scope: {scope}")

    result = run_fetch(respond)
    assert result["accession"] == ACCESSION
    assert [sample["accession"] for sample in result["samples"]] == ["GSM900001", "GSM900002"]


def test_ncbi_https_redirects_are_followed_within_allowlist():
    from app.rnaseq.geo_counts import _get_limited

    calls = []

    def respond(request):
        calls.append(str(request.url))
        if request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "https://ftp.ncbi.nlm.nih.gov/geo/series/test.txt"})
        return httpx.Response(200, content=b"machine-readable GEO text")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await _get_limited(client, "https://www.ncbi.nlm.nih.gov/start")

    assert asyncio.run(run()) == b"machine-readable GEO text"
    assert len(calls) == 2


def test_ncbi_redirect_to_untrusted_host_is_rejected():
    from app.rnaseq.geo_counts import _get_limited

    def respond(request):
        if request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "https://example.com/outside"})
        return httpx.Response(200, content=b"not trusted")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await _get_limited(client, "https://www.ncbi.nlm.nih.gov/start")

    with pytest.raises(GeoCountsError, match="outside the trusted NCBI HTTPS hosts"):
        asyncio.run(run())


def test_html_200_from_acc_cgi_falls_back_to_family_soft():
    archive = gzip.compress(FAMILY_SOFT.encode())

    def respond(request):
        if request.url.host == "www.ncbi.nlm.nih.gov":
            return httpx.Response(200, text="<!doctype html><html><title>Request rejected</title></html>")
        if request.url.path.endswith("_family.soft.gz"):
            return httpx.Response(200, content=archive)
        pytest.fail(f"Unexpected GEO request: {request.url}")

    result = run_fetch(respond)
    assert result["accession"] == ACCESSION
    assert result["title"] == "ALS expression study"
    assert [sample["accession"] for sample in result["samples"]] == ["GSM900001", "GSM900002"]
    assert [sample["characteristics"]["condition"] for sample in result["samples"]] == ["healthy", "SALS"]
    assert result["organisms"] == ["Homo sapiens"]
    assert result["files"][0]["name"] == "raw_counts.tsv.gz"
    assert result["files"][0]["analysis_eligible"] is True


def test_family_soft_html_200_is_rejected_as_non_metadata():
    def respond(request):
        return httpx.Response(200, text="<html><title>NCBI challenge</title></html>")

    with pytest.raises(GeoCountsError, match="both NCBI routes|HTML"):
        run_fetch(respond)


def test_family_soft_gzip_with_malformed_soft_is_rejected():
    malformed = gzip.compress(b"this is not a GEO SOFT record")

    def respond(request):
        if request.url.host == "www.ncbi.nlm.nih.gov":
            return httpx.Response(200, text="<html>challenge</html>")
        return httpx.Response(200, content=malformed)

    with pytest.raises(GeoCountsError, match="recognised SOFT|both NCBI routes"):
        run_fetch(respond)


def test_family_soft_wrong_accession_is_not_accepted():
    wrong = FAMILY_SOFT.replace("GSE336901", "GSE336902")
    archive = gzip.compress(wrong.encode())

    def respond(request):
        if request.url.host == "www.ncbi.nlm.nih.gov":
            return httpx.Response(200, text="<html>challenge</html>")
        return httpx.Response(200, content=archive)

    with pytest.raises(GeoCountsError, match="did not contain the requested Series"):
        run_fetch(respond)


def test_missing_api_and_family_records_return_actionable_error():
    def respond(request):
        if request.url.host == "www.ncbi.nlm.nih.gov":
            return httpx.Response(200, text="<html>challenge</html>")
        return httpx.Response(404, text="Not found")

    with pytest.raises(GeoCountsError, match="accession API, family SOFT, and Series Matrix routes"):
        run_fetch(respond)


def test_series_matrix_metadata_fallback_and_supplement_listing():
    matrix_text = "!Series_title \"RNA-seq FFPE response study\"\n!Series_type \"Expression profiling by high throughput sequencing\"\n!Series_overall_design \"Five sensitive and five resistant FFPE samples\"\n!Series_contact_email \"research@example.org\"\n!Sample_geo_accession \"GSM900001\" \"GSM900002\"\n!Sample_title \"FFPE sensitive sample GZ23094742\" \"FFPE resistant sample GZ23094732\"\n!Sample_organism_ch1 \"Homo sapiens\" \"Homo sapiens\"\n!Sample_library_strategy \"RNA-Seq\" \"RNA-Seq\"\n!Sample_characteristics_ch1 \"treatment: sensitive\" \"treatment: resistant\"\n!Sample_characteristics_ch1 \"batch: FFPE\" \"batch: FFPE\"\n!series_matrix_table_begin\n\"ID_REF\"\t\"GSM900001\"\t\"GSM900002\"\n"
    matrix_archive = gzip.compress(matrix_text.encode())

    def respond(request):
        if request.url.host == "www.ncbi.nlm.nih.gov":
            return httpx.Response(200, text="<html>NCBI challenge</html>")
        if request.url.path.endswith("_family.soft.gz"):
            return httpx.Response(404, text="Not found")
        if request.url.path.endswith("_series_matrix.txt.gz"):
            return httpx.Response(200, content=matrix_archive)
        if request.url.path.endswith("/suppl/"):
            return httpx.Response(200, text='<html><a href="GSE336901_Fig3_FFPE_raw_counts_matrix_GEO.csv.gz">raw counts</a></html>')
        pytest.fail(f"Unexpected request: {request.url}")

    result = run_fetch(respond)
    assert result["accession"] == ACCESSION
    assert len(result["samples"]) == 2
    assert result["samples"][0]["characteristics"]["treatment"] == "sensitive"
    assert result["samples"][1]["characteristics"]["treatment"] == "resistant"
    assert result["files"][0]["name"] == "GSE336901_Fig3_FFPE_raw_counts_matrix_GEO.csv.gz"
    assert result["files"][0]["analysis_eligible"] is True

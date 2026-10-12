import asyncio
import csv
import hashlib
import importlib.util
import io
import zipfile

import httpx
import pytest

from app.rnaseq.geo_counts import GeoCountsError, fetch_matrix, fetch_series
from app.rnaseq.geo_recovery import TEMPLATES, recovery_bundle
from app.routers import geo_search


SERIES = """^SERIES = GSE1
!Series_type = Expression profiling by high throughput sequencing
!Series_title = A normalized study
!Series_overall_design = Review groups
!Series_contact_email = researcher@example.org
!Series_relation = BioProject: https://www.ncbi.nlm.nih.gov/bioproject/PRJNA123
!Series_sample_id = GSM1
!Series_sample_id = GSM2
!Series_sample_id = GSM3
!Series_sample_id = GSM4
!Series_supplementary_file = ftp://ftp.ncbi.nlm.nih.gov/geo/series/GSEnnn/GSE1/suppl/expression_FPKM.tsv
"""
SAMPLES = "\n".join(f"^SAMPLE = GSM{i}\n!Sample_title = sample{i}\n!Sample_supplementary_file_1 = ftp://ftp.ncbi.nlm.nih.gov/geo/samples/GSMnnn/GSM{i}/suppl/raw_counts.tsv" for i in range(1, 5))


def study():
    def respond(request):
        return httpx.Response(200, text=SERIES if request.url.params["targ"] == "self" else SAMPLES)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await fetch_series(client, "GSE1")
    return asyncio.run(run())


def test_sample_level_recovery_preserves_sources_without_automatic_merge():
    series = study()
    assert len(series["files"]) == 5
    assert series["files"][0]["analysis_eligible"] is False
    assert series["raw_candidates"] == [f"GSM{i}/raw_counts.tsv" for i in range(1, 5)]
    assert series["read_projects"] == ["PRJNA123"]
    # A complete deposited matrix from a sample supplement can be validated.
    matrix = "gene\tGSM1\tGSM2\tGSM3\tGSM4\ng1\t1\t2\t3\t4\ng2\t5\t6\t7\t8\n"
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=matrix))) as client:
            return await fetch_matrix(client, series, "GSM1/raw_counts.tsv")
    result, source = asyncio.run(run())
    assert result["columns"] == ["GSM1", "GSM2", "GSM3", "GSM4"]
    assert "/geo/samples/" in source
    assert series["files"][1]["name"] == "GSM1/raw_counts.tsv"


def test_bundle_includes_source_identity_templates_and_verified_checksums():
    archive = zipfile.ZipFile(io.BytesIO(recovery_bundle(study())))
    assert {"source_record.json", "metadata_to_review.tsv", "author_request_draft.txt", "featurecounts.sh", "featurecounts_to_matrix.py", "tximport_deseq2.R", "limma_trend.R", "review_design.R"}.issubset(archive.namelist())
    for line in archive.read("checksums.sha256").decode().splitlines():
        checksum, name = line.split("  ")
        assert hashlib.sha256(archive.read(name)).hexdigest() == checksum
    rows = list(csv.DictReader(io.StringIO(archive.read("metadata_to_review.tsv").decode()), delimiter="\t"))
    assert len(rows) == 4 and all(not row["condition"] and not row["experimental_unit"] for row in rows)
    assert "researcher@example.org" in archive.read("author_request_draft.txt").decode()
    assert all("/" not in name and ".." not in name for name in archive.namelist())


def test_recovery_endpoint_returns_zip(monkeypatch):
    snapshot = study()
    async def fake(client, accession):
        return snapshot
    monkeypatch.setattr(geo_search, "fetch_series", fake)
    response = asyncio.run(geo_search.download_geo_recovery("GSE1"))
    assert response.media_type == "application/zip"
    assert response.headers["content-disposition"].endswith('GSE1_expression_recovery.zip"')
    assert zipfile.is_zipfile(io.BytesIO(response.body))


def test_wrong_assay_cannot_download_expression_instructions():
    with pytest.raises(GeoCountsError, match="CUT"):
        recovery_bundle({"workflow_issue": "CUT&Tag requires a different workflow"})


def test_featurecounts_converter_preserves_integers_and_explicit_column_mapping(tmp_path):
    spec = importlib.util.spec_from_file_location("count_converter", TEMPLATES / "featurecounts_to_matrix.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    native = tmp_path / "counts.tsv"; mapping = tmp_path / "bam_samples.tsv"; output = tmp_path / "raw.tsv"
    native.write_text("# Program: featureCounts\nGeneid\tChr\tStart\tEnd\tStrand\tLength\tb.bam\ta.bam\tc.bam\td.bam\ng1\t1\t1\t10\t+\t10\t1\t2\t3\t4\ng2\t1\t20\t40\t-\t20\t5\t6\t7\t8\n")
    mapping.write_text("bam\tsample\na.bam\tGSM1\nb.bam\tGSM2\nc.bam\tGSM3\nd.bam\tGSM4\n")
    module.convert(native, mapping, output)
    assert output.read_text().splitlines() == ["gene\tGSM2\tGSM1\tGSM3\tGSM4", "g1\t1\t2\t3\t4", "g2\t5\t6\t7\t8"]
    native.write_text(native.read_text().replace("\t1\t2\t3\t4", "\t1.5\t2\t3\t4"))
    with pytest.raises(ValueError, match="integer"):
        module.convert(native, mapping, output)
